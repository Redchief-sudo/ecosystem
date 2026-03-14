#!/usr/bin/env python3
"""
Test script to verify token output from each scanner.

Exercises:
  1. DexScreenerScanner  – scan() and scan_network()
  2. TokenScanner         – scan() (discovery and specific token) and scan_network()
  3. OnChainScannerUltra  – scan() and scan_network()
  4. SentimentScanner     – scan() and scan_network()
  5. MempoolScannerUltra  – scan() and scan_network()
  6. ScanDirector         – orchestrated multi-scanner scan
"""

import asyncio
import json
import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scanner_test")

# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────

SEPARATOR = "=" * 80
THIN_SEP = "-" * 60


def _fmt_token(idx: int, token: Dict[str, Any]) -> str:
    """Pretty-format a token dict into log lines."""
    symbol = token.get("symbol", token.get("token_symbol", "N/A"))
    name = token.get("name", token.get("token_name", "N/A"))
    address = token.get("address", token.get("token_address", token.get("contract_address", "N/A")))
    chain = token.get("chain", "N/A")
    price = token.get("price_usd", token.get("current_price_usd", None))
    liquidity = token.get("liquidity_usd", None)
    volume = token.get("volume_24h", token.get("volume_24h_usd", None))
    confidence = token.get("confidence", token.get("boost_score", None))

    lines = [f"  {idx}. {symbol} ({name})"]
    lines.append(f"     Address : {address}")
    lines.append(f"     Chain   : {chain}")
    if price is not None:
        lines.append(f"     Price   : ${float(price):,.6f}")
    if liquidity is not None:
        lines.append(f"     Liq     : ${float(liquidity):,.2f}")
    if volume is not None:
        lines.append(f"     Vol 24h : ${float(volume):,.2f}")
    if confidence is not None:
        try:
            lines.append(f"     Score   : {float(confidence):.4f}")
        except (ValueError, TypeError):
            lines.append(f"     Score   : {confidence}")
    return "\n".join(lines)


def _log_result(scanner_name: str, label: str, result: Any) -> Dict[str, Any]:
    """Log scanner result, display tokens, return summary dict."""
    logger.info("")
    logger.info(f"  [{label}]")

    # AggregatedResult (ScanDirector returns this)
    if hasattr(result, "total_scan_time_ms"):
        tokens = result.tokens or []
        logger.info(f"    success      : {result.success}")
        logger.info(f"    scan_time_ms : {result.total_scan_time_ms:.1f}")
        logger.info(f"    tokens       : {len(tokens)}")
        logger.info(f"    scanners     : {getattr(result, 'scanner_count', '?')} ({getattr(result, 'successful_scanners', '?')} ok)")
        for i, t in enumerate(tokens[:5], 1):
            if isinstance(t, dict):
                logger.info(_fmt_token(i, t))
        return {
            "success": result.success,
            "token_count": len(tokens),
            "scan_time_ms": result.total_scan_time_ms,
        }

    # ScanResult object (scan_network returns this)
    if hasattr(result, "success"):
        tokens = result.tokens or []
        logger.info(f"    success      : {result.success}")
        logger.info(f"    scan_time_ms : {result.scan_time_ms:.1f}")
        logger.info(f"    tokens       : {len(tokens)}")
        if result.error_message:
            logger.info(f"    error        : {result.error_message}")
        if hasattr(result, "metadata") and result.metadata:
            logger.info(f"    metadata     : {json.dumps(result.metadata, indent=6, default=str)}")
        for i, t in enumerate(tokens[:5], 1):
            if isinstance(t, dict):
                logger.info(_fmt_token(i, t))
        return {
            "success": result.success,
            "token_count": len(tokens),
            "scan_time_ms": result.scan_time_ms,
            "error": result.error_message,
        }

    # List[Dict] (scan() returns this)
    if isinstance(result, list):
        logger.info(f"    tokens       : {len(result)}")
        for i, t in enumerate(result[:5], 1):
            if isinstance(t, dict):
                logger.info(_fmt_token(i, t))
        return {"success": True, "token_count": len(result)}

    logger.info(f"    raw result   : {str(result)[:200]}")
    return {"success": False, "token_count": 0, "note": "unexpected type"}


# ────────────────────────────────────────────────────────────────────────
# Per-Scanner Test Functions
# ────────────────────────────────────────────────────────────────────────

async def test_dex_screener(network_manager) -> Dict[str, Any]:
    """Test DexScreenerScanner scan() and scan_network()."""
    from scanners.discovery.dex_screener_scanner import DexScreenerScanner
    from scanners.base_scanner import ChainType

    scanner = DexScreenerScanner(
        config={"chains": ["ethereum"], "min_liquidity_usd": 25000, "min_volume_usd": 5000, "max_pairs": 10},
        network_manager=network_manager,
    )
    results: Dict[str, Any] = {}

    # scan()
    tokens = await scanner.scan(items=["ethereum"])
    results["scan()"] = _log_result("DexScreenerScanner", "scan(items=['ethereum'])", tokens)

    # scan_network()
    sr = await scanner.scan_network(ChainType.ETHEREUM)
    results["scan_network()"] = _log_result("DexScreenerScanner", "scan_network(ETHEREUM)", sr)

    return results


async def test_token_scanner(network_manager, web3_connections: Dict) -> Dict[str, Any]:
    """Test TokenScanner scan() and scan_network()."""
    from scanners.discovery.token_scanner import TokenScanner
    from scanners.base_scanner import ChainType

    scanner = TokenScanner(
        web3_connections=web3_connections,
        config={
            "chains": ["ethereum"],
            "cache_enabled": True,
            "max_concurrent": 5,
            "max_tokens_per_scan": 5,
        },
        network_manager=network_manager,
    )
    results: Dict[str, Any] = {}

    # scan() — discovery mode
    tokens = await scanner.scan("ethereum", max_tokens=3)
    results["scan(discovery)"] = _log_result("TokenScanner", "scan('ethereum', max_tokens=3)", tokens)

    # scan_network()
    sr = await scanner.scan_network(ChainType.ETHEREUM, max_tokens=3)
    results["scan_network()"] = _log_result("TokenScanner", "scan_network(ETHEREUM)", sr)

    await scanner.close()
    return results


async def test_onchain_scanner(network_manager) -> Dict[str, Any]:
    """Test OnChainScannerUltra scan() and scan_network()."""
    from scanners.discovery.onchain_scanner import OnChainScannerUltra
    from scanners.base_scanner import ChainType

    scanner = OnChainScannerUltra(
        config={"chains": ["ethereum"], "min_liquidity": 50000, "max_top_10_concentration": 0.5, "max_honeypot_probability": 0.2, "lookback_blocks": 10, "max_concurrent": 5},
        network_manager=network_manager,
    )
    results: Dict[str, Any] = {}

    # scan()
    tokens = await scanner.scan(items=["ethereum"])
    results["scan()"] = _log_result("OnChainScannerUltra", "scan(items=['ethereum'])", tokens)

    # scan_network()
    sr = await scanner.scan_network(ChainType.ETHEREUM)
    results["scan_network()"] = _log_result("OnChainScannerUltra", "scan_network(ETHEREUM)", sr)

    return results


async def test_sentiment_scanner(network_manager) -> Dict[str, Any]:
    """Test SentimentScanner scan() and scan_network()."""
    from scanners.discovery.sentiment_scanner import SentimentScanner
    from scanners.base_scanner import ChainType

    scanner = SentimentScanner(
        config={"chains": ["ethereum"], "sources": ["twitter", "reddit"], "min_mentions": 1},
    )
    results: Dict[str, Any] = {}

    # scan()
    tokens = await scanner.scan(items=["ethereum"])
    results["scan()"] = _log_result("SentimentScanner", "scan(items=['ethereum'])", tokens)

    # scan_network()
    sr = await scanner.scan_network(ChainType.ETHEREUM)
    results["scan_network()"] = _log_result("SentimentScanner", "scan_network(ETHEREUM)", sr)

    return results


async def test_mempool_scanner(network_manager) -> Dict[str, Any]:
    """Test MempoolScannerUltra scan() and scan_network()."""
    from scanners.discovery.mempool_scanner import MempoolScannerUltra
    from scanners.base_scanner import ChainType

    scanner = MempoolScannerUltra(
        config={"chains": ["ethereum"], "min_whale_value": 10.0, "min_mev_profit": 0.05, "max_slippage": 0.05, "max_concurrent": 5},
        network_manager=network_manager,
    )
    results: Dict[str, Any] = {}

    # scan()
    tokens = await scanner.scan(items=["ethereum"])
    results["scan()"] = _log_result("MempoolScannerUltra", "scan(items=['ethereum'])", tokens)

    # scan_network()
    sr = await scanner.scan_network(ChainType.ETHEREUM)
    results["scan_network()"] = _log_result("MempoolScannerUltra", "scan_network(ETHEREUM)", sr)

    return results


async def test_scan_director(network_manager) -> Dict[str, Any]:
    """Test ScanDirector orchestrating multiple scanners."""
    from scanners.scan_director import ScanDirector, create_scan_director
    from scanners.discovery.dex_screener_scanner import DexScreenerScanner
    from scanners.discovery.sentiment_scanner import SentimentScanner

    dex = DexScreenerScanner(
        config={"chains": ["ethereum"], "min_liquidity_usd": 25000, "min_volume_usd": 5000, "max_pairs": 5},
        network_manager=network_manager,
    )
    sent = SentimentScanner(
        config={"chains": ["ethereum"], "sources": ["twitter", "reddit"], "min_mentions": 1},
    )

    director = create_scan_director(
        config={"execution_mode": "PARALLEL", "aggregation_strategy": "DEDUPE_BY_ADDRESS", "timeout_seconds": 60},
        scanners=[dex, sent],
        network_manager=network_manager,
    )

    results: Dict[str, Any] = {}
    async with director:
        sr = await director.scan("ethereum")
        results["director.scan()"] = _log_result("ScanDirector", "scan('ethereum')", sr)

    return results


# ────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────

async def main():
    logger.info(SEPARATOR)
    logger.info("SCANNER TOKEN OUTPUT TEST")
    logger.info(f"Started at {datetime.now(timezone.utc).isoformat()}")
    logger.info(SEPARATOR)

    # ── initialise network manager ──────────────────────────────────
    network_manager = None
    web3_connections: Dict = {}
    try:
        from networks.universal_network_manager import UniversalNetworkManager

        network_manager = UniversalNetworkManager()
        await network_manager.initialize()
        logger.info("Network manager initialised")

        if hasattr(network_manager, "get_web3_connections"):
            web3_connections = network_manager.get_web3_connections()
            logger.info(f"Web3 connections available: {list(web3_connections.keys())}")
    except Exception as exc:
        logger.error(f"Could not initialise network manager: {exc}")
        logger.info("Tests will continue — scanners that require RPC will error gracefully.")

    # ── run per-scanner tests ───────────────────────────────────────
    all_results: Dict[str, Any] = {}
    tests = [
        ("DexScreenerScanner", lambda: test_dex_screener(network_manager)),
        ("TokenScanner", lambda: test_token_scanner(network_manager, web3_connections)),
        ("OnChainScannerUltra", lambda: test_onchain_scanner(network_manager)),
        ("SentimentScanner", lambda: test_sentiment_scanner(network_manager)),
        ("MempoolScannerUltra", lambda: test_mempool_scanner(network_manager)),
        ("ScanDirector", lambda: test_scan_director(network_manager)),
    ]

    for name, fn in tests:
        logger.info("")
        logger.info(SEPARATOR)
        logger.info(f"▶ {name}")
        logger.info(SEPARATOR)
        t0 = time.time()
        try:
            result = await fn()
            elapsed = time.time() - t0
            all_results[name] = {"status": "OK", "elapsed_s": round(elapsed, 2), "details": result}
            logger.info(f"✅ {name} completed in {elapsed:.2f}s")
        except Exception as exc:
            elapsed = time.time() - t0
            tb = traceback.format_exc()
            all_results[name] = {"status": "ERROR", "elapsed_s": round(elapsed, 2), "error": str(exc)}
            logger.error(f"❌ {name} failed in {elapsed:.2f}s: {exc}")
            logger.debug(tb)

    # ── summary ─────────────────────────────────────────────────────
    logger.info("")
    logger.info(SEPARATOR)
    logger.info("TEST SUMMARY")
    logger.info(SEPARATOR)

    passed = 0
    total = len(all_results)
    for name, info in all_results.items():
        status_icon = "✅" if info["status"] == "OK" else "❌"
        logger.info(f"  {status_icon} {name:30s} {info['elapsed_s']:>6.2f}s  {info['status']}")
        if info["status"] == "OK":
            passed += 1
            for sub, detail in info.get("details", {}).items():
                tc = detail.get("token_count", "?")
                ok = detail.get("success", "?")
                logger.info(f"       {sub:30s} tokens={tc}  success={ok}")
        else:
            logger.info(f"       error: {info.get('error', 'unknown')}")

    logger.info(THIN_SEP)
    logger.info(f"  {passed}/{total} scanner groups passed")
    logger.info(SEPARATOR)

    # ── cleanup ─────────────────────────────────────────────────────
    if network_manager and hasattr(network_manager, "shutdown"):
        try:
            await network_manager.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
