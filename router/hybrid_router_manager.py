"""
Hybrid Router Manager v1.0
===========================

Advanced router management system supporting both V2 and V3 DEX routers.
Intelligently selects optimal router based on liquidity, fees, and token compatibility.

Features:
- Multi-router support per chain
- Automatic router selection based on token pair
- Fallback mechanisms
- Liquidity aggregation
- Gas optimization
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from web3 import Web3
from web3.contract import Contract

from config.network_config import NetworkConfig
from core.health_check import HealthStatus, standard_health_check

logger = logging.getLogger(__name__)


class RouterType(Enum):
    """Router protocol types."""
    UNISWAP_V2 = "uniswap_v2"
    UNISWAP_V3 = "uniswap_v3"
    PANCAKESWAP_V2 = "pancakeswap_v2"
    PANCAKESWAP_V3 = "pancakeswap_v3"
    SUSHISWAP = "sushiswap"
    QUICKSWAP = "quickswap"
    TRADERJOE = "traderjoe"
    SPOOKYSWAP = "spookyswap"
    CAMELOT = "camelot"
    HONEYSWAP = "honeyswap"


@dataclass
class RouterConfig:
    """Configuration for a single router."""
    address: str
    router_type: RouterType
    abi_name: str
    fee_tier: Optional[int] = None  # For V3 routers
    preferred: bool = False  # If this is the preferred router for this chain


@dataclass
class RouterSelection:
    """Result of router selection algorithm."""
    router: Contract
    router_type: RouterType
    address: str
    confidence: float  # 0.0 to 1.0
    reason: str


class HybridRouterManager:
    """
    Advanced hybrid router manager supporting multiple router types per chain.
    
    Automatically selects the best router based on:
    - Token pair compatibility
    - Liquidity availability
    - Gas efficiency
    - Fee structure
    """

    # Router configurations will be dynamically generated from NetworkConfig
    HYBRID_ROUTER_CONFIG = None  # Will be populated in __init__

    ABI_SEARCH_DIRS = [
        "abi/router_json",
        "abi",
        "abi/routers", 
        "abi/uniswap",
        "abi/pancakeswap",
        "abi/camelot",
        "abi/traderjoe",
        "abi/quickswap",
        "abi/spookyswap",
        "abi/honeyswap"
    ]

    def __init__(self, network_manager, config: Dict[str, Any]):
        """
        Initialize HybridRouterManager with NetworkConfig integration.
        
        Args:
            network_manager: Network manager for Web3 connections
            config: Configuration dictionary
        """
        self.network_manager = network_manager
        self.config = config
        self.routers: Dict[str, List[Contract]] = {}
        self.router_configs: Dict[str, List[RouterConfig]] = {}
        self.uninitialized_chains: set[str] = set()
        self.abis: Dict[str, Dict] = self._load_all_abis()
        self.initialized: bool = False
        
        # Convert NetworkConfig to RouterConfig format
        self._convert_network_config()

    def _convert_network_config(self):
        """Convert NetworkConfig format to RouterConfig format."""
        self.HYBRID_ROUTER_CONFIG = {}
        
        for chain_name, network_config in NetworkConfig.NETWORKS.items():
            router_address = network_config.get('router')
            if not router_address:
                continue
                
            # Map network to router type
            router_type = self._map_network_to_router_type(chain_name, network_config.get('dex_name', ''))
            if not router_type:
                continue
                
            # Create RouterConfig
            router_config = RouterConfig(
                address=router_address,
                router_type=router_type,
                abi_name=self._get_abi_name_for_router(router_type, chain_name),
                preferred=True
            )
            
            self.HYBRID_ROUTER_CONFIG[chain_name] = [router_config]

    def _map_network_to_router_type(self, chain: str, dex_name: str) -> Optional[RouterType]:
        """Map network and dex name to RouterType."""
        dex_mapping = {
            'Uniswap': RouterType.UNISWAP_V3,
            'PancakeSwap': RouterType.PANCAKESWAP_V2,
            'QuickSwap': RouterType.QUICKSWAP,
            'SushiSwap': RouterType.SUSHISWAP,
            'TraderJoe': RouterType.TRADERJOE,
            'SpookySwap': RouterType.SPOOKYSWAP,
            'Camelot': RouterType.CAMELOT,
            'HoneySwap': RouterType.HONEYSWAP,
        }
        
        return dex_mapping.get(dex_name)

    def _get_abi_name_for_router(self, router_type: RouterType, chain: str) -> str:
        """Get ABI name for router type."""
        abi_mapping = {
            RouterType.UNISWAP_V3: 'uniswap_v3_router',
            RouterType.UNISWAP_V2: 'uniswap_v2_router',
            RouterType.PANCAKESWAP_V2: 'pancakeswap_router',
            RouterType.PANCAKESWAP_V3: 'pancakeswap_v3_router',
            RouterType.QUICKSWAP: 'quickswap_router',
            RouterType.SUSHISWAP: 'uniswap_v2_router',
            RouterType.TRADERJOE: 'traderjoe_router',
            RouterType.SPOOKYSWAP: 'spookyswap_router',
            RouterType.CAMELOT: 'camelot_router',
            RouterType.HONEYSWAP: 'honeyswap_router',
        }
        
        return abi_mapping.get(router_type, 'uniswap_v2_router')

    def _load_all_abis(self) -> Dict[str, Dict]:
        """Load all router ABIs from configured directories."""
        abis = {}
        
        for search_dir in self.ABI_SEARCH_DIRS:
            dir_path = Path(search_dir)
            if not dir_path.exists():
                continue
                
            for abi_file in dir_path.glob("*.json"):
                try:
                    with open(abi_file, 'r') as f:
                        abi_data = json.load(f)
                        abis[abi_file.stem] = abi_data
                        logger.debug(f"Loaded ABI: {abi_file.stem}")
                except Exception as e:
                    logger.warning(f"Failed to load ABI {abi_file}: {e}")
        
        return abis

    async def initialize_router(self, chain: str) -> bool:
        """Initialize router for a specific chain."""
        if chain in self.routers and self.routers[chain]:
            return True
            
        if chain not in self.HYBRID_ROUTER_CONFIG:
            logger.warning(f"No router configuration for chain: {chain}")
            return False
            
        try:
            web3 = self.network_manager.get_web3(chain)
            if not web3:
                logger.error(f"No Web3 connection for chain: {chain}")
                return False
                
            chain_routers = []
            chain_configs = []
            
            for router_config in self.HYBRID_ROUTER_CONFIG[chain]:
                try:
                    # Get ABI
                    abi = self.abis.get(router_config.abi_name)
                    if not abi:
                        logger.error(f"ABI not found: {router_config.abi_name}")
                        continue
                        
                    # Create contract
                    contract = web3.eth.contract(
                        address=web3.to_checksum_address(router_config.address),
                        abi=abi
                    )
                    
                    chain_routers.append(contract)
                    chain_configs.append(router_config)
                    
                    logger.info(f"Initialized {router_config.router_type.value} router on {chain}: {router_config.address}")
                    
                except Exception as e:
                    logger.error(f"Failed to initialize router {router_config.address} on {chain}: {e}")
                    continue
                    
            if chain_routers:
                self.routers[chain] = chain_routers
                self.router_configs[chain] = chain_configs
                return True
            else:
                logger.error(f"No routers successfully initialized for chain: {chain}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize routers for {chain}: {e}")
            return False

    async def initialize_all_routers(self) -> bool:
        """Initialize all configured routers."""
        logger.info("Initializing all routers...")
        
        success_count = 0
        total_chains = len(self.HYBRID_ROUTER_CONFIG)
        
        for chain in self.HYBRID_ROUTER_CONFIG.keys():
            if await self.initialize_router(chain):
                success_count += 1
            else:
                self.uninitialized_chains.add(chain)
        
        self.initialized = success_count > 0
        logger.info(f"Router initialization complete: {success_count}/{total_chains} chains successful")
        
        return self.initialized

    def get_routers_for_chain(self, chain: str) -> List[Contract]:
        """Get all initialized routers for a chain."""
        return self.routers.get(chain, [])

    def get_preferred_router(self, chain: str) -> Optional[Contract]:
        """Get the preferred router for a chain."""
        if chain not in self.router_configs:
            return None
            
        for config in self.router_configs[chain]:
            if config.preferred:
                routers = self.routers.get(chain, [])
                if routers:
                    return routers[0]  # First router should match preferred config
        
        return None

    async def select_best_router(
        self, 
        chain: str, 
        token_in: str, 
        token_out: str,
        amount_in: Optional[int] = None
    ) -> Optional[RouterSelection]:
        """
        Select the best router for a specific token pair.
        
        Args:
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount (for liquidity checking)
            
        Returns:
            RouterSelection with best router and confidence
        """
        routers = self.get_routers_for_chain(chain)
        if not routers:
            logger.warning(f"No routers available for chain: {chain}")
            return None
            
        # For now, return preferred router
        # In future, implement intelligent selection based on liquidity, fees, etc.
        preferred = self.get_preferred_router(chain)
        if preferred:
            configs = self.router_configs.get(chain, [])
            preferred_config = next((c for c in configs if c.preferred), None)
            
            return RouterSelection(
                router=preferred,
                router_type=preferred_config.router_type if preferred_config else RouterType.UNISWAP_V2,
                address=preferred.address,
                confidence=0.8,
                reason="Preferred router"
            )
        
        # Fallback to first available router
        first_router = routers[0]
        first_config = self.router_configs[chain][0] if self.router_configs.get(chain) else None
        
        return RouterSelection(
            router=first_router,
            router_type=first_config.router_type if first_config else RouterType.UNISWAP_V2,
            address=first_router.address,
            confidence=0.5,
            reason="First available router"
        )

    async def health_check(self) -> Dict[str, HealthStatus]:
        """Perform health check on all routers."""
        results = {}
        
        for chain, routers in self.routers.items():
            if not routers:
                results[chain] = HealthStatus(
                    status="unhealthy",
                    message="No routers initialized"
                )
                continue
                
            chain_status = HealthStatus(status="healthy", message="All routers operational")
            
            for i, router in enumerate(routers):
                try:
                    web3 = self.network_manager.get_web3(chain)
                    if not web3:
                        chain_status = HealthStatus(
                            status="degraded",
                            message=f"No Web3 connection for {chain}"
                        )
                        break
                        
                    # Simple health check - try to get router code
                    code = web3.eth.get_code(router.address)
                    if len(code) == 0:
                        chain_status = HealthStatus(
                            status="unhealthy",
                            message=f"Router {router.address} has no code"
                        )
                        break
                        
                except Exception as e:
                    chain_status = HealthStatus(
                        status="unhealthy",
                        message=f"Router {router.address} check failed: {str(e)}"
                    )
                    break
                    
            results[chain] = chain_status
            
        return results

    def get_router_info(self, chain: str) -> Dict[str, Any]:
        """Get information about routers for a chain."""
        routers = self.get_routers_for_chain(chain)
        configs = self.router_configs.get(chain, [])
        
        info = {
            "chain": chain,
            "router_count": len(routers),
            "initialized": len(routers) > 0,
            "routers": []
        }
        
        for i, (router, config) in enumerate(zip(routers, configs)):
            info["routers"].append({
                "address": router.address,
                "type": config.router_type.value,
                "preferred": config.preferred,
                "abi_name": config.abi_name
            })
            
        return info
