import asyncio
import logging
import time
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

import yaml
from .scanner_settings import ScannerSettings

# Set up logger
logger = logging.getLogger("scanner.director")


class SimplePathManager:
    """Simple path manager for scanner operations."""
    def __init__(self, base_path: str = "/tmp/ecosystem"):
        self.base_path = Path(base_path)
        
    def get_path(self, name: str) -> Path:
        return self.base_path / name


class ScanDirector:
    """
    Master scanner orchestrator (clean version, no legacy/boost_mode).
    """

    def __init__(
        self,
        network_manager,
        memory=None,
        config: Optional[Dict] = None,
        critical_scanners: Optional[list] = None,
        ai_controller=None,
        path_manager: Optional[SimplePathManager] = None,
    ):
        # Use injected path manager or fallback for backwards compatibility
        self.path_manager = path_manager
        if self.path_manager is None:
            self.path_manager = SimplePathManager()
        self.network_manager = network_manager
        self.memory = memory
        self.config = config or {}
        self.critical_scanners = critical_scanners or []
        self.ai_controller = ai_controller

        # Initialize attributes that don't depend on network clients
        self.scanner_health = {}
        self.max_failures = 3
        # Scan scheduling / timeouts (defaults chosen to avoid "looks hung" behavior)
        scanner_cfg = self.config.get("scanner", {}) if isinstance(self.config, dict) else {}
        self.max_concurrent_chains = int(scanner_cfg.get("max_workers", 8))
        # Upper bound per chain scan (across all scanners) to keep trade loop responsive
        self.per_chain_timeout_s = float(scanner_cfg.get("scan_chain_timeout_s", 60.0))  # Increased from 20s
        # Upper bound per scanner call (per chain)
        self.per_scanner_timeout_s = float(scanner_cfg.get("scan_scanner_timeout_s", 30.0))  # Increased from 10s

        self.last_scan_time = None
        self.scan_duration = 0.0
        self.total_scans = 0
        self.successful_scans = 0

        # These will be initialized in initialize() after network clients are available
        self.enabled_networks = []
        self.scanners = []

        logger.info("ScanDirector created - awaiting network initialization")

    # ============================================================
    # INITIALIZATION
    # ============================================================

    async def initialize(self):
        logger.info("🚀 Initializing ScanDirector...")

        # For NetworkConfig, we don't need to validate network manager clients
        if hasattr(self.network_manager, 'NETWORKS'):
            logger.info(f"NetworkConfig available with {len(self.network_manager.NETWORKS)} networks")
        elif not self.network_manager or not getattr(self.network_manager, "clients", None):
            raise RuntimeError("Network manager with clients is required")
        else:
            logger.info(f"Network manager validated: {len(self.network_manager.clients)} clients available")

        # Initialize networks and scanners
        self.enabled_networks = self._get_enabled_networks()
        self.scanners = self._initialize_scanners()

        logger.info(
            f"Initialized ScanDirector with {len(self.scanners)} scanners "
            f"and {len(self.enabled_networks)} networks"
        )

        # Initialize individual scanners
        for scanner in self.scanners:
            try:
                if hasattr(scanner, "initialize") and callable(scanner.initialize):
                    await scanner.initialize()
                logger.info(f"✅ Scanner ready: {scanner.__class__.__name__}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {scanner.__class__.__name__}: {e}", exc_info=True)
        logger.info("🚀 All scanners initialized")

    def get_expected_scan_timeout_seconds(self) -> float:
        """
        Compute an upper bound for a full scan_all() call, based on concurrency and per-chain timeout.
        Used by the trading loop to avoid arbitrary hardcoded timeouts that break at scale.
        """
        chains = max(1, len(self.enabled_networks))
        workers = max(1, int(self.max_concurrent_chains))
        batches = math.ceil(chains / workers)
        # Add small buffer for scheduling overhead
        return float(batches * self.per_chain_timeout_s + 2.0)

    def _initialize_scanners(self) -> List:
        scanners = []
        # Look for scanners under scanner.scanners (new unified config structure)
        scanner_config = self.config.get("scanner", {})
        scanner_configs = scanner_config.get("scanners", {})
        
        # Fallback to old structure for backward compatibility
        if not scanner_configs:
            scanner_configs = self.config.get("scanners", {})
            
        logger.info(f"🔍 Found scanner configs: {list(scanner_configs.keys())}")

        built_in_scanners = {
            "dex_screener": "scanners.discovery.dex_screener_scanner.DexScreenerScanner",
            "onchain_scanner_ultra": "scanners.discovery.onchain_scanner.OnChainScannerUltra",
            "mempool_scanner": "scanners.discovery.mempool_scanner.MempoolScannerUltra",
            "token_analyzer": "scanners.discovery.token_analyzer.TokenAnalyzer",
            "ai_discovery_scanner": "scanners.discovery.ai_discovery_scanner.AIDiscoveryScanner",
            "new_scanner": "scanners.new_scanner.NewScanner"
        }

        for name, cfg in scanner_configs.items():
            logger.info(f"🔍 Processing scanner: {name} with config: {cfg}")
            
            # Initialize ScannerSettings if this is the settings scanner
            if name == "settings":
                try:
                    scanner_settings = ScannerSettings.from_dict(self.config)
                    logger.info(f"✅ ScannerSettings initialized: {scanner_settings}")
                    continue
                except Exception as e:
                    logger.warning(f"⚠️ Scanner settings class initialization failed: {e}")
                    continue
            
            if not isinstance(cfg, dict) or not cfg.get("enabled", True):
                logger.info(f"⚠️ Scanner {name} disabled or misconfigured")
                continue

            class_path = cfg.get("class") or built_in_scanners.get(name)
            if not class_path:
                logger.warning(f"⚠️ Scanner {name} class not found")
                continue
                
            logger.info(f"🔍 Loading scanner {name} with class: {class_path}")

            if not self._check_scanner_capability_gating(name):
                logger.warning(f"⚠️ Scanner {name} disabled due to capability requirements not met")
                continue

            try:
                module_path, class_name = class_path.rsplit(".", 1)
                module = __import__(module_path, fromlist=[class_name])
                cls = getattr(module, class_name)

                init_kwargs = {'config': cfg}

                # Pass memory and network_manager if constructor accepts them
                if 'memory' in cls.__init__.__code__.co_varnames:
                    init_kwargs['memory'] = self.memory
                if 'network_manager' in cls.__init__.__code__.co_varnames:
                    init_kwargs['network_manager'] = self.network_manager


                if 'ai' in cls.__init__.__code__.co_varnames:
                    init_kwargs['ai'] = self.ai_controller
                if 'network_config' in cls.__init__.__code__.co_varnames:
                    init_kwargs['network_config'] = self.config.get('networks', {})

                scanner = cls(**init_kwargs)

                # Wrap ScannerBase-derived classes to provide scan_network if they only have scan
                if not hasattr(scanner, "scan_network") and hasattr(scanner, "scan"):
                    async def _scan_network_wrapper(self, chain):
                        return await self.scan(chain)
                    scanner.scan_network = _scan_network_wrapper.__get__(scanner)

                scanners.append(scanner)
                logger.info(f"✅ Loaded scanner: {name}")

            except Exception as e:
                logger.error(f"❌ Failed to load scanner {name}: {e}", exc_info=True)

        logger.info(f"🔍 Total scanners loaded: {len(scanners)}")
        return scanners

    # #region agent log
    _DEBUG_LOG_PATH = "/home/damien/ecosystem/.cursor/debug.log"
    # #endregion
    
    def _check_scanner_capability_gating(self, scanner_name: str) -> bool:
        """
        Check if a scanner should be enabled based on chain capabilities and token availability.

        Returns True if at least one enabled network supports the scanner's requirements
        and token memory has sufficient data.
        """
        # #region agent log
        import json as _json
        def _dbg(msg, data, hyp):
            try:
                with open(self._DEBUG_LOG_PATH, "a") as f:
                    f.write(_json.dumps({"location":"scan_director.py:_check_scanner_capability_gating","message":msg,"data":data,"hypothesisId":hyp,"timestamp":__import__("time").time(),"sessionId":"debug-session"})+"\n")
            except: pass
        # #endregion
        
        if not hasattr(self.network_manager, 'is_chain_compatible_with_scanner'):
            logger.warning("Network manager doesn't support capability checking, allowing all scanners")
            # #region agent log
            _dbg("capability_gating_no_check", {"scanner": scanner_name, "reason": "no_is_chain_compatible_with_scanner"}, "C")
            # #endregion
            return True

        # Check token availability first
        if hasattr(self.memory, 'get_token_availability_status'):
            token_status = self.memory.get_token_availability_status()
            # #region agent log
            _dbg("token_availability_check", {"scanner": scanner_name, "token_status": token_status}, "C")
            # #endregion
            
            # Allow scanners to run even without tokens for discovery scanners
            discovery_scanners = ['dex_screener', 'onchain_scanner_ultra', 'mempool_scanner']
            if scanner_name not in discovery_scanners:
                if not token_status.get('has_tokens', False):
                    logger.warning(f"Scanner {scanner_name} disabled: No tokens available in memory")
                    # #region agent log
                    _dbg("scanner_disabled_no_tokens", {"scanner": scanner_name}, "C")
                    # #endregion
                    return False

                # Some scanners require recent tokens
                token_requiring_scanners = ['hybrid_scanner', 'ai_discovery_scanner', 'd3_scanner']
                if scanner_name in token_requiring_scanners and token_status.get('recent_tokens', 0) == 0:
                    logger.warning(f"Scanner {scanner_name} disabled: No recent tokens available (requires token data)")
                    # #region agent log
                    _dbg("scanner_disabled_no_recent_tokens", {"scanner": scanner_name, "recent_tokens": token_status.get('recent_tokens', 0)}, "C")
                    # #endregion
                    return False

        # Check compatibility with each enabled network
        compatible_networks = []
        incompatible_networks = []

        for chain in self.enabled_networks:
            is_compatible, reason = self.network_manager.is_chain_compatible_with_scanner(chain, scanner_name)
            if is_compatible:
                compatible_networks.append(chain)
            else:
                incompatible_networks.append(f"{chain} ({reason})")

        if compatible_networks:
            logger.debug(f"Scanner {scanner_name} compatible with networks: {', '.join(compatible_networks)}")
            return True
        else:
            logger.warning(f"Scanner {scanner_name} incompatible with all networks: {', '.join(incompatible_networks)}")
            return False

    def _get_enabled_networks(self) -> List[str]:
        """Get list of enabled networks for scanning from NetworkConfig or network manager."""
        # Check if we have NetworkConfig with NETWORKS
        if hasattr(self.network_manager, 'NETWORKS') and self.network_manager.NETWORKS:
            all_networks = list(self.network_manager.NETWORKS.keys())
            
            # Check if scanners have priority chains configured
            priority_chains = []
            for scanner in self.scanners:
                if hasattr(scanner, 'config') and scanner.config.get('priority_chains'):
                    priority_chains.extend(scanner.config['priority_chains'])
            
            # Remove duplicates and check if we should use priority chains only
            priority_chains = list(set(priority_chains))
            use_priority_only = any(
                hasattr(scanner, 'config') and not scanner.config.get('scan_all_chains', True)
                for scanner in self.scanners
            )
            
            if priority_chains and use_priority_only:
                # Filter to only priority chains that exist in NetworkConfig
                enabled_networks = [chain for chain in priority_chains if chain in all_networks]
                logger.info(f"🔗 ScanDirector using {len(enabled_networks)} priority chains: {', '.join(enabled_networks)}")
                return enabled_networks
            else:
                logger.info(f"🔗 ScanDirector using {len(all_networks)} networks from NetworkConfig: {', '.join(all_networks)}")
                return all_networks
        
        # Fallback to network manager with clients
        if hasattr(self.network_manager, "clients") and self.network_manager.clients:
            all_networks = list(self.network_manager.clients.keys())
            logger.info(f"🔗 ScanDirector using {len(all_networks)} connected networks for scanning: {', '.join(all_networks)}")
            return all_networks

        # No working network clients - cannot scan anything
        logger.error("❌ No working network clients available - scanners cannot operate")
        logger.error("This usually means RPC endpoints are failing or network manager initialization failed")
        return []

    # ============================================================
    # SCAN EXECUTION
    # ============================================================

    async def scan_all_networks(self) -> Dict[str, List[Dict]]:
        self.last_scan_time = datetime.now(timezone.utc)
        start = time.time()
        results: Dict[str, List[Dict]] = {}

        if not self.enabled_networks:
            logger.warning("⚠️ No enabled networks available for scanning")
            return {}

        logger.info(
            f"🧭 ScanDirector starting scan: chains={len(self.enabled_networks)}, "
            f"scanners={len(self.scanners)}, "
            f"concurrency={self.max_concurrent_chains}, "
            f"per_chain_timeout_s={self.per_chain_timeout_s}, "
            f"per_scanner_timeout_s={self.per_scanner_timeout_s}"
        )

        sem = asyncio.Semaphore(max(1, self.max_concurrent_chains))

        async def _scan_chain_with_limits(chain: str) -> tuple[str, List[Dict]]:
            async with sem:
                try:
                    # Use scanner-specific timeout if available, otherwise use global timeout
                    timeout = self._get_effective_timeout_for_chain(chain)
                    tokens = await asyncio.wait_for(self._scan_single_chain(chain), timeout=timeout)
                    return chain, tokens
                except asyncio.TimeoutError:
                    logger.info(f"⏱️ Scanner timeout on {chain} after {timeout}s (non-failure)")
                    return chain, []
                except Exception as e:
                    logger.error(f"❌ Scan failed for {chain}: {e}", exc_info=True)
                    return chain, []

        tasks = [asyncio.create_task(_scan_chain_with_limits(chain), name=f"scan.chain.{chain}") for chain in self.enabled_networks]
        chain_results = await asyncio.gather(*tasks, return_exceptions=True)

        for item in chain_results:
            self.total_scans += 1
            if isinstance(item, Exception):
                logger.error(f"❌ Chain scan task failed unexpectedly: {item}", exc_info=True)
                continue
            chain, tokens = item
            results[chain] = tokens
            if tokens:
                self.successful_scans += 1

        self.scan_duration = time.time() - start
        return results

    async def scan_all(self) -> List[Dict]:
        """
        Scan all networks and process results.
        Implements backpressure: pauses if decision queue is too full.
        """
        if self.ai_controller and hasattr(self.ai_controller, 'decision_queue'):
            queue = self.ai_controller.decision_queue
            if queue.qsize() > 0:
                queue_depth = queue.qsize() / queue.maxsize
                
                if queue_depth > 0.8:
                    logger.warning(
                        f"BACKPRESSURE: Decision queue {queue_depth:.0%} full "
                        f"({queue.qsize()}/{queue.maxsize}) - throttling scanners"
                    )
                    await asyncio.sleep(5)
                    return []
                
                elif queue_depth > 0.5:
                    logger.debug(
                        f"Queue pressure: {queue_depth:.0%} full - brief pause"
                    )
                    await asyncio.sleep(1)
        
        network_results = await self.scan_all_networks()
        
        # Flatten and deduplicate all tokens across all networks
        all_tokens = [token for tokens in network_results.values() for token in tokens]
        
        # Apply global deduplication (lazy import to avoid circular imports)
        from trading.token_pipeline.token_deduplicator import token_deduplicator
        unique_tokens = token_deduplicator.add_tokens(all_tokens, "scan_director")
        
        logger.info(f"🔍 Global deduplication: {len(unique_tokens)} unique from {len(all_tokens)} total tokens")
        
        # Send tokens to ingestion pipeline for processing
        if unique_tokens:
            try:
                from trading.token_pipeline import ingest_scan_results
                pipeline_result = await ingest_scan_results("scan_director", unique_tokens)
                logger.info(f"📊 Token ingestion: {pipeline_result.get('enqueued', 0)} enqueued, {pipeline_result.get('rejected', 0)} rejected")
            except Exception as e:
                logger.error(f"❌ Failed to ingest tokens into pipeline: {e}")
                # Return tokens directly if pipeline fails
                return unique_tokens
        
        return unique_tokens

    def _get_effective_timeout_for_chain(self, chain: str) -> float:
        """
        Get effective timeout for a chain based on scanner configurations.
        Uses the maximum timeout among all scanners for that chain.
        """
        max_timeout = self.per_chain_timeout_s  # Default to global timeout
        
        for scanner in self.scanners:
            if hasattr(scanner, 'config') and scanner.config:
                scanner_timeout = scanner.config.get('timeout_seconds')
                if scanner_timeout and scanner_timeout > max_timeout:
                    max_timeout = scanner_timeout
                    logger.debug(f"Using scanner timeout {scanner_timeout}s for {chain} from {scanner.__class__.__name__}")
        
        return max_timeout

    async def _scan_single_chain(self, chain: str) -> List[Dict]:
        logger.info(f"🔍 Scanning {chain} with {len(self.scanners)} scanners")
        if len(self.scanners) == 0:
            logger.warning(f"⚠️ No scanners available for {chain} - check scanner configuration")
        results: List[Dict] = []

        tasks = []
        scanner_map = {}  # Map task index to scanner for proper error tracking
        
        for scanner in self.scanners:
            # Check if scanner is ready and supports this chain
            if hasattr(scanner, 'running') and not scanner.running:
                logger.debug(f"Skipping {scanner.__class__.__name__} - not running")
                continue
                
            if hasattr(scanner, 'supports_chain') and not scanner.supports_chain(chain):
                logger.debug(f"Skipping {scanner.__class__.__name__} - doesn't support {chain}")
                continue

            task = asyncio.create_task(
                scanner.scan_network(chain) if hasattr(scanner, "scan_network") 
                else scanner.protected_scan(chain),
                name=f"scanner.{scanner.__class__.__name__}"
            )
            tasks.append(task)
            scanner_map[len(tasks) - 1] = scanner  # Store scanner reference by task index
        
        if not tasks:
            logger.warning(f"No ready scanners for {chain}")
            return []

        # Add timeout handling to prevent hanging scanners
        scanner_results = await asyncio.gather(
            *[asyncio.wait_for(task, timeout=self.per_scanner_timeout_s) for task in tasks],
            return_exceptions=True
        )
        
        # #region agent log
        import json as _json
        def _dbg_res(msg, data, hyp):
            try:
                with open(self._DEBUG_LOG_PATH, "a") as f:
                    f.write(_json.dumps({"location":"scan_director.py:_scan_single_chain","message":msg,"data":data,"hypothesisId":hyp,"timestamp":__import__("time").time(),"sessionId":"debug-session"})+"\n")
            except: pass
        _dbg_res("scanner_results_gather", {"chain": chain, "num_results": len(scanner_results), "result_types": [type(r).__name__ for r in scanner_results]}, "E")
        # #endregion
        
        for i, result in enumerate(scanner_results):
            scanner = scanner_map.get(i)
            if not scanner:
                logger.warning(f"Scanner index {i} not found in scanner_map - skipping result")
                continue
                
            scanner_name = scanner.__class__.__name__
            
            if isinstance(result, Exception):
                error_msg = str(result)
                # #region agent log
                _dbg_res("scanner_exception", {"scanner": scanner_name, "chain": chain, "error": error_msg, "error_type": type(result).__name__}, "E")
                # #endregion
                logger.error(f"❌ {scanner_name} failed on {chain}: {error_msg}", exc_info=result if isinstance(result, BaseException) else None)
                self.scanner_health.setdefault(scanner_name, {'consecutive_failures': 0, 'disabled': False})
                self.scanner_health[scanner_name]['consecutive_failures'] += 1
                
                # Disable scanner after too many consecutive failures
                if self.scanner_health[scanner_name]['consecutive_failures'] >= 5:
                    self.scanner_health[scanner_name]['disabled'] = True
                    logger.warning(f"⚠️ {scanner_name} disabled after 5 consecutive failures")
            elif isinstance(result, list):
                token_count = len(result)
                # #region agent log
                _dbg_res("scanner_list_result", {"scanner": scanner_name, "chain": chain, "token_count": token_count}, "E")
                # #endregion
                if token_count > 0:
                    logger.info(f"✅ {scanner_name} found {token_count} tokens on {chain}")
                else:
                    logger.debug(f"ℹ️ {scanner_name} found 0 tokens on {chain} (no matches)")
                results.extend(result)
                # Reset consecutive failures on success
                self.scanner_health.setdefault(scanner_name, {'consecutive_failures': 0, 'disabled': False})
                self.scanner_health[scanner_name]['consecutive_failures'] = 0
            else:
                # #region agent log
                _dbg_res("scanner_unexpected_type", {"scanner": scanner_name, "chain": chain, "result_type": str(type(result)), "result_repr": repr(result)[:200]}, "E")
                # #endregion
                logger.warning(f"⚠️ {scanner_name} returned unexpected result type: {type(result)}")

        # Safely commit memory changes if connection is open
        if self.memory and hasattr(self.memory, 'conn'):
            try:
                # Check if connection is still open before committing
                if hasattr(self.memory.conn, 'execute'):
                    self.memory.conn.commit()
                    logger.debug(f"✅ Memory sync successful for {chain}")
                else:
                    logger.warning(f"⚠️ Database connection closed for {chain}, attempting to reconnect...")
                    if hasattr(self.memory, 'reconnect') and self.memory.reconnect():
                        self.memory.conn.commit()
                        logger.info(f"✅ Memory sync successful after reconnection for {chain}")
                    else:
                        logger.error(f"❌ Failed to reconnect database for {chain}, skipping commit")
            except Exception as e:
                logger.error(f"❌ Memory sync failed for {chain}: {e}", exc_info=True)
                # Don't fail the scan, but log the error prominently

        return results

    async def shutdown(self):
        """Gracefully shutdown ScanDirector and all scanners."""
        logger.info("🛑 Shutting down ScanDirector...")
        
        # Cleanup all scanners that have a cleanup method
        for scanner in self.scanners:
            try:
                if hasattr(scanner, 'cleanup') and callable(scanner.cleanup):
                    if asyncio.iscoroutinefunction(scanner.cleanup):
                        await scanner.cleanup()
                        logger.debug(f"Cleaned up scanner: {scanner.__class__.__name__}")
                    else:
                        scanner.cleanup()
                        logger.debug(f"Cleaned up scanner: {scanner.__class__.__name__}")
                elif hasattr(scanner, 'stop') and callable(scanner.stop):
                    if asyncio.iscoroutinefunction(scanner.stop):
                        await scanner.stop()
                    else:
                        scanner.stop()
                    logger.debug(f"Stopped scanner: {scanner.__class__.__name__}")
                elif hasattr(scanner, 'shutdown') and callable(scanner.shutdown):
                    if asyncio.iscoroutinefunction(scanner.shutdown):
                        await scanner.shutdown()
                    else:
                        scanner.shutdown()
                    logger.debug(f"Shutdown scanner: {scanner.__class__.__name__}")
            except Exception as e:
                logger.warning(f"Error cleaning up scanner {scanner.__class__.__name__}: {e}", exc_info=True)
        
        # Clear scanner list
        self.scanners.clear()
        self.scanner_health.clear()
        
        logger.info("✅ ScanDirector shutdown complete")
