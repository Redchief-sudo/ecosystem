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
    
    async def _do_initialize(self) -> bool:
        """Initialize task manager."""
        self.logger.info("Initializing TaskManager")
        # Initialize tasks storage
        self.register_item("tasks", {})
        return True
    
    async def _do_start(self) -> bool:
        """Start task manager."""
        self.logger.info("Starting TaskManager")
        self._shutdown = False
        return True
    
    async def _do_stop(self) -> bool:
        """Stop task manager."""
        self.logger.info("Stopping TaskManager")
        self._shutdown = True
        
        # Cancel all running tasks
        tasks = self.get_item("tasks") or {}
        for task_id, task_info in tasks.items():
            if task_info.task and not task_info.task.done():
                task_info.task.cancel()
                try:
                    await task_info.task
                except asyncio.CancelledError:
                    self.logger.debug(f"Task {task_id} cancelled")
        
        return True
    
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
            task_info = tasks.get(task_id)
            if task_info and task_info.task and not task_info.task.done():
                self.logger.debug(f"Task {task_id} already exists and is running")
                return task_info.task
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
        # Always update the tasks dict when creating a task
        self.register_item("tasks", tasks)
        self._metrics.tasks_created += 1
        
        self.logger.debug(f"Created task: {task_id} ({task_type})")
        return task
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        async with self._lock:
            tasks = self.get_item("tasks") or {}
            task_info = tasks.get(task_id)
            if not task_info:
                return False
            
            if task_info.task and not task_info.task.done():
                task_info.task.cancel()
                task_info.status = TaskStatus.CANCELLED
                self._metrics.tasks_cancelled += 1
                # Update task state in registry
                self.register_item("tasks", tasks)
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
    
    async def stop(self) -> None:
        """Stop the task manager and clean up all tasks.
        
        This method:
        1. Sets the shutdown flag to prevent new tasks from starting
        2. Cancels all running tasks
        3. Waits for tasks to complete cancellation
        4. Cleans up resources
        """
        if self._shutdown:
            self.logger.warning("TaskManager already shutting down")
            return
            
        self.logger.info("Initiating TaskManager shutdown...")
        self._shutdown = True
        
        # Get all tasks and cancel them
        tasks = self.get_item("tasks") or {}
        if not tasks:
            self.logger.info("No active tasks to cancel")
            return
            
        self.logger.info(f"Cancelling {len(tasks)} running tasks...")
        
        # Create a list of tasks to cancel
        tasks_to_cancel = []
        for task_id, task_info in tasks.items():
            if task_info.task and not task_info.task.done():
                tasks_to_cancel.append(task_info.task)
                task_info.status = TaskStatus.CANCELLED
                self._metrics.tasks_cancelled += 1
        
        # Cancel all tasks
        for task in tasks_to_cancel:
            task.cancel()
        
        # Wait for tasks to complete cancellation
        if tasks_to_cancel:
            self.logger.info(f"Waiting for {len(tasks_to_cancel)} tasks to complete cancellation...")
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        
        # Clear the tasks dictionary
        self.register_item("tasks", {})
        self.logger.info("TaskManager shutdown complete")
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
            # Create a task but don't await it; instead return a coroutine for the caller to await
            # Since we're in sync context but need sync behavior, use run_coroutine_threadsafe
            asyncio.create_task(self._cancel_all_tasks())
            # Give it a moment to execute
            import time
            time.sleep(0.1)
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
                try:
                    await task_info.task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                self.logger.error(f"Error cancelling task {task_info.task_id}: {e}")
        
        # Clear all tasks from registry after cancellation
        async with self._lock:
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
                try:
                    await task_info.task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                self.logger.error(f"Error cancelling task {task_info.task_id}: {e}")
        
        # Update final task states but keep the history
        async with self._lock:
            tasks = self.get_item("tasks") or {}
            for task_id, task_info in tasks.items():
                if task_info.task and task_info.task.done():
                    if task_info.task.cancelled():
                        task_info.status = TaskStatus.CANCELLED
                    elif task_info.task.exception():
                        task_info.status = TaskStatus.FAILED
                    else:
                        task_info.status = TaskStatus.COMPLETED
            self.register_item("tasks", tasks)

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
