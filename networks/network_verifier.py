#!/usr/bin/env python3
"""
Network Verification Utility
---------------------------
Verifies connectivity and configuration for all configured networks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from web3 import Web3

logger = logging.getLogger("network_verifier")


class SimplePathManager:
    """Simple path manager for network operations."""

    def __init__(self, base_path: str = "/tmp/ecosystem"):
        self.base_path = Path(base_path)

    def get_path(self, name: str) -> Path:
        return self.base_path / name

    def get_config_path(self, name: str) -> Path:
        """Default config path."""
        return self.get_path(f"{name}.yaml")


class NetworkVerifier:
    """Verifies network connectivity and configuration."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        path_manager: Optional[SimplePathManager] = None,
    ):
        """Initialize with optional path to config file."""
        if path_manager is None:
            path_manager = SimplePathManager()

        self.path_manager = path_manager
        self.config_path = Path(config_path) if config_path else self.path_manager.get_config_path("main")

        self.network_status: Dict[str, Dict[str, Any]] = {}
        self.last_verified: float = 0

    async def verify_all_networks(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        """Verify all networks in the configuration."""

        if config is None:
            import yaml

            if not self.config_path.exists():
                logger.error("Config file not found: %s", self.config_path)
                return {}

            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
                config = config_data if config_data else {}

        networks = config.get("networks", {}) or {}

        tasks = [self._verify_network(name, cfg) for name, cfg in networks.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions safely
        final_status: Dict[str, Dict[str, Any]] = {}
        for r in results:
            if isinstance(r, Exception):
                logger.error("Network verification task failed: %s", str(r))
                continue
            if isinstance(r, tuple) and len(r) == 2:
                final_status[r[0]] = r[1]

        self.network_status = final_status
        self.last_verified = time.time()
        return self.network_status

    async def _verify_network(self, name: str, config: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Verify a single network's connectivity and configuration."""
        if not config.get("chain_id"):
            return name, {
                "name": name,
                "status": "invalid",
                "error": "Missing chain_id in config",
            }

        if not config.get("rpc"):
            return name, {
                "name": name,
                "status": "invalid",
                "error": "Missing RPC endpoint in config",
            }

        status = {
            "name": name,
            "chain_id": config.get("chain_id"),
            "rpc": config.get("rpc", ""),
            "status": "offline",
            "block_number": 0,
            "latency_ms": 0,
            "error": None,
            "last_checked": time.time(),
            "fallbacks_tested": 0,
            "fallbacks_working": 0,
        }

        # Test primary RPC
        try:
            primary = await asyncio.to_thread(self._test_rpc, status["rpc"], expected_chain_id=status["chain_id"])
            status.update(primary)
        except Exception as e:
            status["error"] = str(e)

        # Test fallback RPCs if primary fails
        if status["status"] != "online" and "fallback_rpcs" in config:
            fallback_results = await self._test_fallbacks(config["fallback_rpcs"], status["chain_id"])
            status.update({
                "fallbacks_tested": len(fallback_results),
                "fallbacks_working": sum(1 for r in fallback_results if r["status"] == "online")
            })

            working_fallbacks = [r for r in fallback_results if r["status"] == "online"]
            if working_fallbacks:
                best = min(working_fallbacks, key=lambda x: x["latency_ms"])
                status.update({
                    "status": "online (fallback)",
                    "rpc": best["rpc"],
                    "latency_ms": best["latency_ms"],
                    "block_number": best["block_number"],
                    "error": None
                })

        return name, status

    async def _test_fallbacks(self, rpcs: List[str], expected_chain_id: int) -> List[Dict[str, Any]]:
        """Test all fallback RPCs for a network."""
        tasks = [asyncio.to_thread(self._test_rpc, rpc, expected_chain_id=expected_chain_id) for rpc in rpcs]
        return await asyncio.gather(*tasks)

    def _test_rpc(self, rpc: str, expected_chain_id: Optional[int] = None) -> Dict[str, Any]:
        """Test a single RPC connection synchronously (run in thread)."""
        result = {
            "rpc": rpc,
            "status": "offline",
            "latency_ms": 0,
            "block_number": 0,
            "error": None,
        }

        start_time = time.monotonic()
        try:
            web3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 5}))
            if not web3.is_connected():
                result["error"] = "Failed to connect"
                return result

            chain_id = web3.eth.chain_id
            if expected_chain_id and chain_id != expected_chain_id:
                result["error"] = f"Chain ID mismatch (expected {expected_chain_id}, got {chain_id})"
                return result

            result.update({
                "status": "online",
                "block_number": web3.eth.block_number,
                "latency_ms": int((time.monotonic() - start_time) * 1000),
            })
        except Exception as e:
            result["error"] = str(e)

        return result

    def get_status_summary(self) -> str:
        """Get a formatted status summary."""
        if not self.network_status:
            return "No network status available. Run verify_all_networks() first."

        online = sum(1 for s in self.network_status.values() if s["status"].startswith("online"))
        total = len(self.network_status)

        summary = [
            f"\n{'=' * 50}",
            "NETWORK STATUS SUMMARY",
            f"Last Verified: {time.ctime(self.last_verified)}",
            f"Networks: {online}/{total} online",
            "=" * 50,
        ]

        sorted_networks = sorted(
            self.network_status.items(),
            key=lambda x: (not x[1]["status"].startswith("online"), x[0].lower())
        )

        for name, status in sorted_networks:
            status_icon = "✅" if status["status"].startswith("online") else "❌"
            summary.append(
                f"{status_icon} {name.upper():<15} | {status['status']:<18} | "
                f"Block: {status.get('block_number', 0):<10} | "
                f"Latency: {status.get('latency_ms', 0)}ms"
            )
            summary.append(f"   Chain ID: {status.get('chain_id', 'unknown')}")
            if status.get("rpc"):
                summary.append(f"   RPC: {status['rpc']}")
            if status.get("error"):
                summary.append(f"   Error: {status['error']}")
            if status.get("fallbacks_tested", 0) > 0:
                summary.append(
                    f"   Fallbacks: {status['fallbacks_working']}/{status['fallbacks_tested']} working"
                )

        return "\n".join(summary)


async def main():
    """Run network verification as a standalone script."""
    verifier = NetworkVerifier()
    await verifier.verify_all_networks()
    print(verifier.get_status_summary())


if __name__ == "__main__":
    asyncio.run(main())

