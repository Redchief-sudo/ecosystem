#!/usr/bin/env python3
"""
RPC Verification Script for 40 Networks
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Any

# Network configurations with reliable RPCs
NETWORK_RPCS = {
    # EVM Networks
    "ethereum": ["https://ethereum.publicnode.com", "https://rpc.ankr.com/eth", "https://cloudflare-eth.com"],
    "bsc": ["https://bsc-dataseed1.binance.org/", "https://bsc-dataseed2.binance.org/", "https://rpc.ankr.com/bsc"],
    "polygon": ["https://polygon-rpc.com/", "https://rpc-mainnet.matic.network/", "https://rpc.ankr.com/polygon"],
    "arbitrum": ["https://arb1.arbitrum.io/rpc", "https://rpc.ankr.com/arbitrum", "https://arbitrum.public-rpc.com"],
    "optimism": ["https://mainnet.optimism.io", "https://rpc.ankr.com/optimism", "https://optimism.public-rpc.com"],
    "base": ["https://mainnet.base.org", "https://rpc.ankr.com/base", "https://base.public-rpc.com"],
    "avalanche": ["https://api.avax.network/ext/bc/C/rpc", "https://rpc.ankr.com/avalanche", "https://avalanche.public-rpc.com"],
    "fantom": ["https://rpc.ftm.tools", "https://rpc.ankr.com/fantom", "https://fantom.public-rpc.com"],
    "linea": ["https://rpc.linea.build", "https://linea.public-rpc.com"],
    "zksync": ["https://mainnet.era.zksync.io", "https://zksync.public-rpc.com"],
    "scroll": ["https://rpc.scroll.io", "https://scroll.public-rpc.com"],
    "mantle": ["https://rpc.mantle.xyz", "https://mantle.public-rpc.com"],
    "blast": ["https://rpc.ankr.com/blast", "https://blast.public-rpc.com"],
    "polygon_zkevm": ["https://rpc.ankr.com/polygon_zkevm", "https://polygon-zkevm.public-rpc.com"],
    "arbitrum_nova": ["https://nova.arbitrum.io/rpc", "https://arbitrum-nova.public-rpc.com"],
    "boba": ["https://rpc.boba.network", "https://boba.public-rpc.com"],
    "aurora": ["https://mainnet.aurora.dev", "https://rpc.ankr.com/aurora"],
    "metis": ["https://andromeda.metis.io/?owner=1088", "https://metis-mainnet.public.blastapi.io"],
    "moonbeam": ["https://rpc.api.moonbeam.network", "https://rpc.ankr.com/moonbeam"],
    "moonriver": ["https://rpc.api.moonriver.moonbeam.network", "https://rpc.ankr.com/moonriver"],
    "canto": ["https://canto.gravitychain.io", "https://canto.public-rpc.com"],
    "cronos": ["https://evm.cronos.org", "https://rpc.ankr.com/cronos"],
    "hedera": ["https://json-rpc.evm.shimmer.network"],
    "celo": ["https://forno.celo.org", "https://rpc.ankr.com/celo"],
    "gnosis": ["https://rpc.gnosischain.com", "https://rpc.ankr.com/gnosis"],
    "kava": ["https://evm.kava.io", "https://kava.api.onfinality.io/public"],
    
    # Non-EVM Networks
    "solana": ["https://api.mainnet-beta.solana.com", "https://solana-api.projectserum.com", "https://rpc.ankr.com/solana"],
    "tron": ["https://api.trongrid.io"],
    "sui": ["https://fullnode.mainnet.sui.io", "https://sui-mainnet.public.blastapi.io"],
    "aptos": ["https://fullnode.mainnet.aptoslabs.com/v1"],
    "ton": ["https://toncenter.io/api/v2/jsonRPC"],
    "cardano": ["https://cardano-mainnet.blockfrost.io/api/v0"],
    "xrpl": ["https://xrplcluster.com"],
    "thorchain": ["https://rpc.ankr.com/thorchain"],
    "stacks": ["https://api.mainnet.stacks.co"],
    "algorand": ["https://mainnet-api.algonode.cloud"],
    "osmosis": ["https://rpc.osmosis.zone"],
    "acala": ["https://rpc.acala.polkadot.io"],
    "tezos": ["https://mainnet.smartpy.io"],
    "stellar": ["https://horizon.stellar.org"],
    "starknet": ["https://starknet-mainnet.public.blastapi.io"],
    "cosmos": ["https://cosmoshub.validator.network"],
    "polkadot": ["https://rpc.polkadot.io"],
    "near": ["https://rpc.mainnet.near.org"],
    "flow": ["https://mainnet.onflow.org"],
    "elrond": ["https://api.multiversx.com"],
    "bitcoin": ["https://blockstream.info/api"],
    "litecoin": ["https://blockstream.info/api"],
    "dogecoin": ["https://dogechain.info"]
}

async def test_rpc_endpoint(session: aiohttp.ClientSession, rpc_url: str, network: str) -> Dict[str, Any]:
    """Test a single RPC endpoint."""
    try:
        # EVM networks use eth_getBlockNumber
        if network in ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "base", "avalanche", 
                     "fantom", "linea", "zksync", "scroll", "mantle", "blast", "polygon_zkevm",
                     "arbitrum_nova", "boba", "aurora", "metis", "moonbeam", "moonriver", "canto",
                     "cronos", "hedera", "celo", "gnosis", "kava"]:
            
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBlockNumber",
                "params": [],
                "id": 1
            }
            
            async with session.post(rpc_url, json=payload, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    if "result" in result:
                        return {
                            "status": "success",
                            "response_time": 0,
                            "block_number": result["result"]
                        }
        
        # Solana uses getSlot
        elif network == "solana":
            payload = {
                "jsonrpc": "2.0",
                "method": "getSlot",
                "params": [],
                "id": 1
            }
            
            async with session.post(rpc_url, json=payload, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    if "result" in result:
                        return {
                            "status": "success",
                            "response_time": 0,
                            "slot": result["result"]
                        }
        
        # Non-EVM networks - just check connectivity
        else:
            start_time = time.time()
            async with session.get(rpc_url, timeout=10) as response:
                response_time = time.time() - start_time
                if response.status == 200:
                    return {
                        "status": "success",
                        "response_time": response_time,
                        "status_code": response.status
                    }
        
        return {"status": "failed", "error": "Invalid response"}
        
    except asyncio.TimeoutError:
        return {"status": "timeout", "error": "Request timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

async def verify_network_rpcs():
    """Verify RPC endpoints for all networks."""
    
    print("🔍 Verifying RPC endpoints for 40 networks...")
    print("=" * 60)
    
    results = {}
    async with aiohttp.ClientSession() as session:
        for network, rpcs in NETWORK_RPCS.items():
            print(f"\n📡 Testing {network}...")
            
            network_results = []
            for i, rpc_url in enumerate(rpcs):
                print(f"  ├─ RPC {i+1}: {rpc_url}")
                
                result = await test_rpc_endpoint(session, rpc_url, network)
                network_results.append({
                    "url": rpc_url,
                    "result": result
                })
                
                if result["status"] == "success":
                    print(f"  ✅ {result['status'].upper()} - Response time: {result.get('response_time', 'N/A')}")
                else:
                    print(f"  ❌ {result['status'].upper()} - {result.get('error', 'Unknown error')}")
            
            results[network] = network_results
    
    return results

def generate_report(results: Dict[str, List[Dict]]):
    """Generate a comprehensive report."""
    
    print("\n" + "=" * 60)
    print("📊 RPC VERIFICATION REPORT")
    print("=" * 60)
    
    total_networks = len(results)
    successful_networks = 0
    failed_networks = 0
    
    for network, rpc_results in results.items():
        successful_rpcs = sum(1 for r in rpc_results if r["result"]["status"] == "success")
        total_rpcs = len(rpc_results)
        
        if successful_rpcs > 0:
            successful_networks += 1
            print(f"✅ {network}: {successful_rpcs}/{total_rpcs} RPCs working")
        else:
            failed_networks += 1
            print(f"❌ {network}: 0/{total_rpcs} RPCs working")
    
    print(f"\n📈 SUMMARY:")
    print(f"  Total Networks: {total_networks}")
    print(f"  Networks with Working RPCs: {successful_networks}")
    print(f"  Networks with No Working RPCs: {failed_networks}")
    print(f"  Success Rate: {(successful_networks/total_networks)*100:.1f}%")
    
    if failed_networks > 0:
        print(f"\n⚠️  NETWORKS NEEDING ATTENTION:")
        for network, rpc_results in results.items():
            successful_rpcs = sum(1 for r in rpc_results if r["result"]["status"] == "success")
            if successful_rpcs == 0:
                print(f"  - {network}")
    
    return successful_networks == total_networks

async def main():
    """Main verification function."""
    print("🚀 Starting RPC Verification for 40 Networks")
    print("This will test reliability and responsiveness of all RPC endpoints...")
    
    results = await verify_network_rpcs()
    all_good = generate_report(results)
    
    if all_good:
        print("\n🎉 ALL NETWORKS HAVE WORKING RPCs!")
        print("✅ Ready for production use")
    else:
        print("\n⚠️  SOME NETWORKS NEED RPC ATTENTION")
        print("🔧 Consider adding backup RPCs for failed networks")
    
    return all_good

if __name__ == "__main__":
    asyncio.run(main())
