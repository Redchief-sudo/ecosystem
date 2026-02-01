#!/usr/bin/env python3
"""
Network Configuration Mapping Analysis
Maps current config networks to system canonical names and verifies chain IDs
"""

# Current config networks extracted from config_unified.yaml
current_networks = [
    {"name": "Ethereum Mainnet", "chain_id": 1, "canonical": "ethereum"},
    {"name": "Binance Smart Chain", "chain_id": 56, "canonical": "bsc"},
    {"name": "Polygon Mainnet", "chain_id": 137, "canonical": "polygon"},
    {"name": "Avalanche C-Chain", "chain_id": 43114, "canonical": "avalanche"},
    {"name": "Fantom Opera", "chain_id": 250, "canonical": "fantom"},
    {"name": "Arbitrum One", "chain_id": 42161, "canonical": "arbitrum"},
    {"name": "Optimism", "chain_id": 10, "canonical": "optimism"},
    {"name": "Base Mainnet", "chain_id": 8453, "canonical": "base"},
    {"name": "Moonbeam", "chain_id": 1284, "canonical": "moonbeam"},
    {"name": "Moonriver", "chain_id": 1285, "canonical": "moonriver"},
    {"name": "Celo Mainnet", "chain_id": 42220, "canonical": "celo"},
    {"name": "Kava EVM", "chain_id": 2222, "canonical": "kava"},
    {"name": "Evmos", "chain_id": 9001, "canonical": "evmos"},
    {"name": "Aurora", "chain_id": 1313161554, "canonical": "aurora"},
    {"name": "Klaytn Mainnet", "chain_id": 8217, "canonical": "klaytn"},
    {"name": "Arbitrum Nova", "chain_id": 42170, "canonical": "arbitrum_nova"},
    {"name": "Metis Andromeda", "chain_id": 1088, "canonical": "metis"},
    {"name": "Songbird", "chain_id": 19, "canonical": None},  # Not in ChainConstants
    {"name": "Oasis Emerald", "chain_id": 42262, "canonical": "oasis_emerald"},
    {"name": "Moonbeam Shiden (Polkadot L2 EVM)", "chain_id": 336, "canonical": None},  # Not in ChainConstants
    {"name": "OKExChain (OKC)", "chain_id": 66, "canonical": "okc"},
    {"name": "Telos EVM", "chain_id": 40, "canonical": "telos"},
    {"name": "Fuse", "chain_id": 122, "canonical": "fuse"},
    {"name": "Syscoin EVM", "chain_id": 57, "canonical": "syscoin"},
    {"name": "Theta Mainnet EVM", "chain_id": 361, "canonical": "theta"},
    {"name": "Palm Network", "chain_id": 11297108109, "canonical": "palm"},  # Duplicate entry
    {"name": "Callisto Network", "chain_id": 820, "canonical": None},  # Not in ChainConstants
    {"name": "Evrynet", "chain_id": 9000, "canonical": None},  # Not in ChainConstants
    {"name": "IoTeX EVM", "chain_id": 4689, "canonical": "iotex"},
    {"name": "Meter Mainnet", "chain_id": 82, "canonical": None},  # Not in ChainConstants
    {"name": "KCC", "chain_id": 321, "canonical": "kcc"},
    {"name": "Velas EVM", "chain_id": 106, "canonical": "velas"},
    {"name": "Energy Web Chain", "chain_id": 246, "canonical": None},  # Not in ChainConstants
    {"name": "Ronin", "chain_id": 2020, "canonical": None},  # Not in ChainConstants
]

def analyze_networks():
    """Analyze network mappings and identify issues"""
    
    print("=== Network Configuration Analysis ===\n")
    
    # Networks that match ChainConstants
    supported = [n for n in current_networks if n["canonical"]]
    print(f"✅ Supported networks ({len(supported)}):")
    for net in supported:
        print(f"  {net['name']} -> {net['canonical']} (chain_id: {net['chain_id']})")
    
    # Networks not in ChainConstants
    unsupported = [n for n in current_networks if not n["canonical"]]
    print(f"\n❌ Unsupported networks ({len(unsupported)}):")
    for net in unsupported:
        print(f"  {net['name']} (chain_id: {net['chain_id']})")
    
    # Check for duplicates
    chain_ids = [n["chain_id"] for n in current_networks]
    duplicates = [cid for cid in set(chain_ids) if chain_ids.count(cid) > 1]
    if duplicates:
        print(f"\n⚠️  Duplicate chain IDs: {duplicates}")
    
    return supported, unsupported

if __name__ == "__main__":
    analyze_networks()
