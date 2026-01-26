import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.base_component import BaseManager

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskConfig:
    """Configuration for a task."""
    task_id: str
    task_type: str
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: Optional[float] = None
    restart_on_failure: bool = True

@dataclass
class TaskInfo:
    """Information about a running task."""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retries: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    task: Optional[asyncio.Task] = None

class TaskMetrics:
    """Track task performance metrics."""
    def __init__(self):
        self.tasks_created = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.tasks_cancelled = 0
        self.tasks_restarted = 0
        self.restart_failures = 0
        self.failure_reasons: Dict[str, int] = {}
        self.execution_times: List[float] = []
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        avg_time = sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0
        return {
            "tasks_created": self.tasks_created,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_cancelled": self.tasks_cancelled,
            "tasks_restarted": self.tasks_restarted,
            "restart_failures": self.restart_failures,
            "failure_reasons": self.failure_reasons.copy(),
            "average_execution_time": avg_time,
            "success_rate": self.tasks_completed / max(self.tasks_created, 1)
        }

class TaskManager(BaseManager):
    """Centralized task management for the trading system."""
    
    def __init__(self):
        super().__init__("task_manager")
        self._metrics = TaskMetrics()
        self._lock = asyncio.Lock()
        self._shutdown = False
    
    def create_engine_task(
        self,
        coro,
        task_id: str,
        task_type: str = "general",
        config: Optional[TaskConfig] = None
    ):
        """Create and track an engine task."""
        if self._shutdown:
            return None
            
        tasks = self.get_item("tasks") or {}
        if task_id in tasks:
            existing_task = tasks[task_id].task
            if existing_task and not existing_task.done():
                self.logger.debug(f"Task {task_id} already exists and is running")
                return existing_task
            # Task exists but is done, allow recreation
            self.logger.debug(f"Task {task_id} exists but is done, recreating")
            
        config = config or TaskConfig(task_id=task_id, task_type=task_type)
        task = asyncio.create_task(coro, name=task_id)
        
        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            task=task,
            created_at=time.time()
        )
        
        tasks[task_id] = task_info
        # Ensure tasks dict is registered
        if not self.get_item("tasks"):
            self.register_item("tasks", tasks)
        self._metrics.tasks_created += 1
        
        self.logger.debug(f"Created task: {task_id} ({task_type})")
        return task
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        async with self._lock:
            task_info = self.get_item("tasks") or {}.get(task_id)
            if not task_info:
                return False
            
            if task_info.task and not task_info.task.done():
                task_info.task.cancel()
                task_info.status = TaskStatus.CANCELLED
                self._metrics.tasks_cancelled += 1
                return True
        
        return False
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a task."""
        tasks = self.get_item("tasks") or {}
        task_info = tasks.get(task_id)
        if not task_info:
            return None
        
        return {
            "task_id": task_info.task_id,
            "task_type": task_info.task_type,
            "status": task_info.status.value,
            "created_at": task_info.created_at,
            "started_at": task_info.started_at,
            "completed_at": task_info.completed_at,
            "retries": task_info.retries,
            "max_retries": task_info.max_retries,
            "error_message": task_info.error_message
        }
    
    @property
    def tasks(self) -> Dict[str, TaskInfo]:
        """Get all tasks."""
        return self.get_item("tasks") or {}
    
    def task_status(self, task_id: str) -> Optional[str]:
        """Get task status as string."""
        tasks = self.get_item("tasks") or {}
        task_info = tasks.get(task_id)
        if not task_info:
            return None
        
        if task_info.task and task_info.task.done():
            if task_info.task.exception():
                return "failed"
            return "done"
        return task_info.status.value
    
    def create_task(
        self,
        coro,
        task_id: str,
        task_type: str = "general",
        restart: bool = False
    ):
        """Create a task (alias for create_engine_task for compatibility)."""
        tasks = self.get_item("tasks") or {}
        if task_id in tasks and not restart:
            self.logger.warning(f"Task {task_id} already exists")
            return tasks[task_id].task

        # Cancel existing task if restarting
        if task_id in tasks and restart:
            self.cancel_task(task_id)

        return self.create_engine_task(coro, task_id, task_type)
    
    def create_scanner_task(
        self,
        coro,
        task_id: str,
        task_type: str = "scanner"
    ):
        """Create a scanner task."""
        return self.create_engine_task(coro, task_id, task_type)
    
    def schedule_engine_task(self, coro, task_id: str):
        """Schedule an engine task (synchronous wrapper for async create_engine_task)."""
        # This is called from sync context, so we need to schedule it
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.create_engine_task(coro, task_id, "engine"))
        else:
            asyncio.run(self.create_engine_task(coro, task_id, "engine"))
    
    def cancel_all(self):
        """Cancel all tasks (synchronous wrapper)."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self._cancel_all_tasks())
        else:
            asyncio.run(self._cancel_all_tasks())
    
    async def _cancel_all_tasks(self):
        """Cancel all running tasks."""
        tasks_to_cancel = []
        async with self._lock:
            tasks = self.get_item("tasks") or {}
            for task_info in tasks.values():
                if task_info.task and not task_info.task.done():
                    tasks_to_cancel.append(task_info)
        
        # Cancel tasks outside of lock
        for task_info in tasks_to_cancel:
            try:
                task_info.task.cancel()
                task_info.status = TaskStatus.CANCELLED
                self._metrics.tasks_cancelled += 1
            except Exception as e:
                self.logger.error(f"Error cancelling task {task_info.task_id}: {e}")
        
        # Clear all tasks
        self.register_item("tasks", {})
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get task metrics."""
        return self._metrics.get_summary()
    
    async def shutdown(self):
        """Shutdown all tasks."""
        self._shutdown = True
        
        # Cancel all running tasks
        tasks_to_cancel = []
        async with self._lock:
            for task_info in (self.get_item("tasks") or {}).values():
                if task_info.task and not task_info.task.done():
                    tasks_to_cancel.append(task_info)
        
        # Cancel tasks outside of lock
        for task_info in tasks_to_cancel:
            try:
                task_info.task.cancel()
                await task_info.task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"Error cancelling task {task_info.task_id}: {e}")

    async def _do_initialize(self) -> bool:
        """Initialize task manager."""
        self.register_item("tasks", {})
        self.logger.info("Task manager initialized")
        return True
    
    async def _do_start(self) -> bool:
        """Start task manager."""
        self.logger.info("Task manager started")
        return True
    
    async def _do_shutdown(self) -> None:
        """Shutdown task manager."""
        self._shutdown = True
        await self._cancel_all_tasks()
        self.logger.info("Task manager shutdown")

# Global task manager instance
task_manager = TaskManager()
