"""
Network configurations for different blockchains
"""
from typing import Dict, List

class NetworkConfig:
    """Network configuration with real endpoints for 35+ networks"""
    
    def get_web3(self, chain_id=None):
        """Get Web3 instance for paper trading mode (returns None for paper mode)."""
        # In paper trading mode, we don't need actual Web3 connections
        return None
    
    NETWORKS = {
        # Major EVM Chains
        "ethereum": {
            "rpcs": ["https://mainnet.infura.io/v3/{infura_key}", "https://cloudflare-eth.com", "https://rpc.ankr.com/eth"],
            "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            "weth": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "chain_id": 1, "explorer": "https://etherscan.io",
            "gas_multiplier": 1.2, "native_symbol": "ETH", "dex_name": "Uniswap"
        },
        "bsc": {
            "rpcs": ["https://bsc-dataseed1.binance.org/", "https://bsc-dataseed2.binance.org/", "https://bsc-dataseed3.binance.org/"],
            "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E", "factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
            "weth": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", "chain_id": 56, "explorer": "https://bscscan.com",
            "gas_multiplier": 1.1, "native_symbol": "BNB", "dex_name": "PancakeSwap"
        },
        "polygon": {
            "rpcs": ["https://polygon-rpc.com/", "https://rpc-mainnet.matic.network/", "https://rpc.ankr.com/polygon"],
            "router": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff", "factory": "0x5757371414417b8c6caad45baef941abc7d3ab32",
            "weth": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270", "chain_id": 137, "explorer": "https://polygonscan.com",
            "gas_multiplier": 1.3, "native_symbol": "MATIC", "dex_name": "QuickSwap"
        },
        "arbitrum": {
            "rpcs": ["https://arb1.arbitrum.io/rpc", "https://rpc.ankr.com/arbitrum", "https://arbitrum.public-rpc.com"],
            "router": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506", "factory": "0xc35DADB65012eC5796536bD9864eD8773aBc74C4",
            "weth": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", "chain_id": 42161, "explorer": "https://arbiscan.io",
            "gas_multiplier": 1.1, "native_symbol": "ETH", "dex_name": "SushiSwap"
        },
        "optimism": {
            "rpcs": ["https://mainnet.optimism.io", "https://rpc.ankr.com/optimism", "https://optimism.public-rpc.com"],
            "router": "0x4A7b5Da61326A6379179b40d00F57E5bbDC962c2", "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            "weth": "0x4200000000000000000000000000000000000006", "chain_id": 10, "explorer": "https://optimistic.etherscan.io",
            "gas_multiplier": 1.1, "native_symbol": "ETH", "dex_name": "Uniswap"
        },
        "avalanche": {
            "rpcs": ["https://api.avax.network/ext/bc/C/rpc", "https://rpc.ankr.com/avalanche", "https://avalanche.public-rpc.com"],
            "router": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4", "factory": "0x9Ad6C38BE94206cA50bb0d90783181662f0Cfa10",
            "weth": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7", "chain_id": 43114, "explorer": "https://snowtrace.io",
            "gas_multiplier": 1.2, "native_symbol": "AVAX", "dex_name": "TraderJoe"
        },
        "fantom": {
            "rpcs": ["https://rpc.ftm.tools", "https://rpc.ankr.com/fantom", "https://fantom.public-rpc.com"],
            "router": "0xF491e7B69E4244ad4002BC14e878a34207E38c29", "factory": "0x152eE697f2E276fA89E96742e9bB9aB1F2E61bE3",
            "weth": "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83", "chain_id": 250, "explorer": "https://ftmscan.com",
            "gas_multiplier": 1.1, "native_symbol": "FTM", "dex_name": "SpookySwap"
        },
        "base": {
            "rpcs": ["https://mainnet.base.org", "https://rpc.ankr.com/base", "https://base.public-rpc.com"],
            "router": "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24", "factory": "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",
            "weth": "0x4200000000000000000000000000000000000006", "chain_id": 8453, "explorer": "https://basescan.org",
            "gas_multiplier": 1.1, "native_symbol": "ETH", "dex_name": "BaseSwap"
        },
        "linea": {
            "rpcs": ["https://rpc.linea.build", "https://linea.public-rpc.com"],
            "router": "0x8cFe327CEc66d1C090Dd72bd0FF11d690C33a2Eb", "factory": "0x31832f2a97Fd20664D76Cc421207669b55CE4BC0",
            "weth": "0xe5D7C2a44FfDDf6b295A15c148167daaAf5Cf34f", "chain_id": 59144, "explorer": "https://lineascan.build",
            "gas_multiplier": 1.2, "native_symbol": "ETH", "dex_name": "LineaSwap"
        },
        "zksync": {
            "rpcs": ["https://mainnet.era.zksync.io", "https://zksync.public-rpc.com"],
            "router": "0x2da10A1e27bF85cEdD8FFb1AbBe97e53391C0295", "factory": "0x40be1cBa6C5B47cDF9da7f963B6F761F4C60627D",
            "weth": "0x5AEa5775959fBC2557Cc8789bC1bf90A239D9a91", "chain_id": 324, "explorer": "https://explorer.zksync.io",
            "gas_multiplier": 1.3, "native_symbol": "ETH", "dex_name": "SyncSwap"
        },
        "cronos": {
            "rpcs": ["https://evm.cronos.org", "https://rpc.ankr.com/cronos"],
            "router": "0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae", "factory": "0x3B44B2a187a7b3824131F8db5a74194D0a42Fc15",
            "weth": "0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23", "chain_id": 25, "explorer": "https://cronoscan.com",
            "gas_multiplier": 1.1, "native_symbol": "CRO", "dex_name": "VVS Finance"
        },
        "gnosis": {
            "rpcs": ["https://rpc.gnosischain.com", "https://rpc.ankr.com/gnosis"],
            "router": "0x1C232F01118CB8B424793ae03F870aa7D0ac7f77", "factory": "0xc35DADB65012eC5796536bD9864eD8773aBc74C4",
            "weth": "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d", "chain_id": 100, "explorer": "https://gnosisscan.io",
            "gas_multiplier": 1.1, "native_symbol": "xDAI", "dex_name": "HoneySwap"
        },
        "celo": {
            "rpcs": ["https://forno.celo.org", "https://rpc.ankr.com/celo"],
            "router": "0xE3D8bd6Aed4F159bc8000a9cD47CffDb95F96121", "factory": "0x62d5b84bE28a183aBB507E125B384122D2C25fAE",
            "weth": "0x471EcE3750Da237f93B8E339c536989b8978a438", "chain_id": 42220, "explorer": "https://celoscan.io",
            "gas_multiplier": 1.1, "native_symbol": "CELO", "dex_name": "Ubeswap"
        },
        "moonbeam": {
            "rpcs": ["https://rpc.api.moonbeam.network", "https://rpc.ankr.com/moonbeam"],
            "router": "0x96b244391D98B62D19aE89b1A4dCcf0fc56970C7", "factory": "0x28f1158795A3585CaAA3cD6469CD65382b89BB70",
            "weth": "0xAcc15dC74880C9944775448304B263D191c6077F", "chain_id": 1284, "explorer": "https://moonscan.io",
            "gas_multiplier": 1.2, "native_symbol": "GLMR", "dex_name": "BeamSwap"
        },
        "moonriver": {
            "rpcs": ["https://rpc.api.moonriver.moonbeam.network", "https://rpc.ankr.com/moonriver"],
            "router": "0xAA30eF758139ae4a7f798112902Bf6d65612045f", "factory": "0x049581aEB6Fe262727f290165C29BDAB065a1B68",
            "weth": "0x98878B06940aE243284CA214f92Bb71a2b032B8A", "chain_id": 1285, "explorer": "https://moonriver.moonscan.io",
            "gas_multiplier": 1.2, "native_symbol": "MOVR", "dex_name": "SolarBeam"
        },
        "metis": {
            "rpcs": ["https://andromeda.metis.io/?owner=1088", "https://metis-mainnet.public.blastapi.io"],
            "router": "0x1E876cCe41B7b844FDe09E38Fa1cf00f213bFf56", "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            "weth": "0x75cb093E4D61d2A2e65D8e0BBb01DE8d89b53481", "chain_id": 1088, "explorer": "https://andromeda-explorer.metis.io",
            "gas_multiplier": 1.2, "native_symbol": "METIS", "dex_name": "Netswap"
        },
        "kava": {
            "rpcs": ["https://evm.kava.io", "https://kava.api.onfinality.io/public"],
            "router": "0x96b244391D98B62D19aE89b1A4dCcf0fc56970C7", "factory": "0x28f1158795A3585CaAA3cD6469CD65382b89BB70",
            "weth": "0xc86c7C0eFbd6A49B35E8714C5f59D99De09A225b", "chain_id": 2222, "explorer": "https://explorer.kava.io",
            "gas_multiplier": 1.1, "native_symbol": "KAVA", "dex_name": "Kinetix"
        },
        "aurora": {
            "rpcs": ["https://mainnet.aurora.dev", "https://rpc.ankr.com/aurora"],
            "router": "0xA32C8185EdA528B7F36EADA0FA32e9c221b35dDd", "factory": "0xc66F594268041dB60507F00703b152492fb176E7",
            "weth": "0xC9BdeEd33CD01541e1eeD10f90519d2C06Fe3feB", "chain_id": 1313161554, "explorer": "https://aurorascan.dev",
            "gas_multiplier": 1.1, "native_symbol": "ETH", "dex_name": "Trisolaris"
        },
        "harmony": {
            "rpcs": ["https://api.harmony.one", "https://rpc.ankr.com/harmony"],
            "router": "0x3C8BF7e25EBfAaFb863256A4380A8a93490d8065", "factory": "0x9014B937069918bd319f80e8B3BB4A2cf6FAA5F7",
            "weth": "0xcF664087a5bB0237a0BAd6742852ec6c8d69A27a", "chain_id": 1666600000, "explorer": "https://explorer.harmony.one",
            "gas_multiplier": 1.1, "native_symbol": "ONE", "dex_name": "SushiSwap"
        },
        "klaytn": {
            "rpcs": ["https://public-node-api.klaytnapi.com/v1/cypress", "https://klaytn.api.onfinality.io/public"],
            "router": "0xEf71750C100f7918d6Ded239Ff1CF09E81dEA92D", "factory": "0x3B54BdF0A344d18c94Bc67e5e2D8FcbE8a64dA79",
            "weth": "0xe4f05A66Ec68B54A58B17c22107b02e0232cC817", "chain_id": 8217, "explorer": "https://scope.klaytn.com",
            "gas_multiplier": 1.1, "native_symbol": "KLAY", "dex_name": "KlaySwap"
        },
        "oasis": {
            "rpcs": ["https://emerald.oasis.dev", "https://oasis.api.onfinality.io/public"],
            "router": "0xfE3d6b8DE4f830A1578FE5aB6f1E8eA8C35f8Cb7", "factory": "0x594e79239E0EBf8F734Be65e0C7DE8eb88C97465",
            "weth": "0x21C718C22D52d0F3a789b752D4c2fD5908a8A733", "chain_id": 42262, "explorer": "https://explorer.emerald.oasis.dev",
            "gas_multiplier": 1.1, "native_symbol": "ROSE", "dex_name": "YuzuSwap"
        },
        "fuse": {
            "rpcs": ["https://rpc.fuse.io", "https://fuse.api.onfinality.io/public"],
            "router": "0xFB76e9E7d88E308aB530330eD90e84a952570319", "factory": "0x1d1f1A7280D67246665Bb196F38553b469294f3a",
            "weth": "0x0BE9e53fd7EDaC9F859882AfdDa116645287C629", "chain_id": 122, "explorer": "https://explorer.fuse.io",
            "gas_multiplier": 1.1, "native_symbol": "FUSE", "dex_name": "FuseSwap"
        },
        "evmos": {
            "rpcs": ["https://eth.bd.evmos.org:8545", "https://evmos.lava.build"],
            "router": "0x2Db0AFD0045F3518c77eC6591a542e326Befd3D7", "factory": "0x6aBdDa34Fb225be4610a2d153845e09429523Cd2",
            "weth": "0xD4949664cD82660AaE99bEdc034a0deA8A0bd517", "chain_id": 9001, "explorer": "https://escan.live",
            "gas_multiplier": 1.2, "native_symbol": "EVMOS", "dex_name": "EvmoSwap"
        },
        "boba": {
            "rpcs": ["https://mainnet.boba.network", "https://boba.api.onfinality.io/public"],
            "router": "0x17C83E2B96ACfb5190d63F5E46d93c107eC0b514", "factory": "0xFB0265841C49A6b19D70055E596b212B0dA3f606",
            "weth": "0xa18bF3994C0Cc6E3b63ac420308E5383f53120D7", "chain_id": 288, "explorer": "https://bobascan.com",
            "gas_multiplier": 1.1, "native_symbol": "ETH", "dex_name": "OolongSwap"
        },
        "syscoin": {
            "rpcs": ["https://rpc.syscoin.org", "https://rpc.ankr.com/syscoin"],
            "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            "weth": "0xd3e822f3ef011Ca5f17D82C956D952D8d7C3A1BB", "chain_id": 57, "explorer": "https://explorer.syscoin.org",
            "gas_multiplier": 1.1, "native_symbol": "SYS", "dex_name": "Pegasys"
        },
        "velas": {
            "rpcs": ["https://evmexplorer.velas.com/rpc", "https://velas.api.onfinality.io/public"],
            "router": "0xC6A1dBa9Bb63C45DE9FD42e83FC6de4E659CcAd7", "factory": "0x97a05E99F7B6C3b3704Ef6e6870158c53Fc1D3D5",
            "weth": "0xc579D1f3CF86749E05CD06f7ADe17856c2CE3126", "chain_id": 106, "explorer": "https://evmexplorer.velas.com",
            "gas_multiplier": 1.1, "native_symbol": "VLX", "dex_name": "WagyuSwap"
        },
        "telos": {
            "rpcs": ["https://mainnet.telos.net/evm", "https://rpc1.us.telos.net/evm"],
            "router": "0xB132b58B587A7F6B7A98aC5B1c1776f89Fe12E6d", "factory": "0xaF61Bb1D976ADf4c3A59FB9F5fb8E0BF57de2e1D",
            "weth": "0xD102cE6A4dB07D247fcc28F366A623Df0938CA9E", "chain_id": 40, "explorer": "https://teloscan.io",
            "gas_multiplier": 1.1, "native_symbol": "TLOS", "dex_name": "Omnidex"
        },
        "thundercore": {
            "rpcs": ["https://mainnet-rpc.thundercore.com", "https://thundercore.api.onfinality.io/public"],
            "router": "0x4a3D0B5c4C7E5fDc24a6b3d8C57b72D1e7E8c5F2", "factory": "0x8a9c67fee641579deba04928c4bc45f66e26343a",
            "weth": "0x413cEFeA29F2d07B8F2acFA69d92466B9535f717", "chain_id": 108, "explorer": "https://viewblock.io/thundercore",
            "gas_multiplier": 1.1, "native_symbol": "TT", "dex_name": "TTSwap"
        },
        "palm": {
            "rpcs": ["https://palm-mainnet.infura.io/v3/{infura_key}", "https://palm-mainnet.public.blastapi.io"],
            "router": "0xA32C8185EdA528B7F36EADA0FA32e9c221b35dDd", "factory": "0xc66F594268041dB60507F00703b152492fb176E7",
            "weth": "0xF98cABF0a963452C5536330408B2590567611a71", "chain_id": 11297108109, "explorer": "https://explorer.palm.io",
            "gas_multiplier": 1.2, "native_symbol": "PALM", "dex_name": "PalmSwap"
        },
        "scroll": {
            "rpcs": ["https://rpc.scroll.io", "https://scroll.public-rpc.com"],
            "router": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4", "factory": "0x70C62C8b8e801124A4Aa81ce07b637A3e83cb919",
            "weth": "0x5300000000000000000000000000000000000004", "chain_id": 534352, "explorer": "https://scrollscan.com",
            "gas_multiplier": 1.2, "native_symbol": "ETH", "dex_name": "ScrollSwap"
        },
        "manta": {
            "rpcs": ["https://pacific-rpc.manta.network/http", "https://manta.api.onfinality.io/public"],
            "router": "0x2db0afd0045f3518c77ec6591a542e326befd3d7", "factory": "0x6abdda34fb225be4610a2d153845e09429523cd2",
            "weth": "0x0Dc808adcE2099A9F62AA87D9670745AbA741746", "chain_id": 169, "explorer": "https://pacific-explorer.manta.network",
            "gas_multiplier": 1.2, "native_symbol": "ETH", "dex_name": "ApertureSwap"
        },
        "mantle": {
            "rpcs": ["https://rpc.mantle.xyz", "https://mantle.public-rpc.com"],
            "router": "0x319B69888b0d11cEC22caA5034e25FfFBDc88421", "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            "weth": "0x78c1b0C915c4FAA5FffA6CAbf0219DA63d7f4cb8", "chain_id": 5000, "explorer": "https://explorer.mantle.xyz",
            "gas_multiplier": 1.2, "native_symbol": "MNT", "dex_name": "MantleSwap"
        },
        "polygonzkevm": {
            "rpcs": ["https://zkevm-rpc.com", "https://rpc.ankr.com/polygon_zkevm"],
            "router": "0x8cFe327CEc66d1C090Dd72bd0FF11d690C33a2Eb", "factory": "0xC532a74256D3Db42D0Bf7a0400fEFDbad7694008",
            "weth": "0x4F9A0e7FD2Bf6067db6994CF12E4495Df938E6e9", "chain_id": 1101, "explorer": "https://zkevm.polygonscan.com",
            "gas_multiplier": 1.3, "native_symbol": "ETH", "dex_name": "QuickSwap"
        },
        "opbnb": {
            "rpcs": ["https://opbnb-mainnet-rpc.bnbchain.org", "https://opbnb.publicnode.com"],
            "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E", "factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
            "weth": "0x4200000000000000000000000000000000000006", "chain_id": 204, "explorer": "https://opbnbscan.com",
            "gas_multiplier": 1.1, "native_symbol": "BNB", "dex_name": "PancakeSwap"
        },
        "blast": {
            "rpcs": ["https://rpc.blast.io", "https://blast.public-rpc.com"],
            "router": "0x98994a9A7a2570367554589189dC9772241650f6", "factory": "0x5C346464d33F90bABaf70dB6388507CC889C1070",
            "weth": "0x4300000000000000000000000000000000000004", "chain_id": 81457, "explorer": "https://blastscan.io",
            "gas_multiplier": 1.2, "native_symbol": "ETH", "dex_name": "BlastSwap"
        }
    }
    
    # Map network names to DEXScreener chain identifiers  
    DEXSCREENER_CHAINS = {
        'ethereum': 'ethereum', 'bsc': 'bsc', 'polygon': 'polygon', 'arbitrum': 'arbitrum',
        'optimism': 'optimism', 'avalanche': 'avalanche', 'fantom': 'fantom', 'base': 'base',
        'linea': 'linea', 'zksync': 'zksync', 'cronos': 'cronos', 'gnosis': 'gnosis',
        'celo': 'celo', 'moonbeam': 'moonbeam', 'moonriver': 'moonriver', 'metis': 'metis',
        'kava': 'kava', 'aurora': 'aurora', 'harmony': 'harmony', 'klaytn': 'klaytn',
        'oasis': 'oasis', 'fuse': 'fuse', 'evmos': 'evmos', 'boba': 'boba',
        'syscoin': 'syscoin', 'velas': 'velas', 'telos': 'telos', 'thundercore': 'thundercore',
        'palm': 'palm', 'scroll': 'scroll', 'manta': 'manta', 'mantle': 'mantle',
        'polygonzkevm': 'polygonzkevm', 'opbnb': 'opbnb', 'blast': 'blast'
    }
    
    # Map network names to CoinGecko platform IDs
    COINGECKO_PLATFORMS = {
        'ethereum': 'ethereum', 'bsc': 'binance-smart-chain', 'polygon': 'polygon-pos',
        'arbitrum': 'arbitrum-one', 'optimism': 'optimistic-ethereum', 'avalanche': 'avalanche',
        'fantom': 'fantom', 'base': 'base', 'cronos': 'cronos', 'gnosis': 'xdai',
        'celo': 'celo', 'moonbeam': 'moonbeam', 'moonriver': 'moonriver', 'metis': 'metis-andromeda',
        'kava': 'kava', 'aurora': 'aurora', 'harmony': 'harmony-shard-0', 'klaytn': 'klay-token',
        'oasis': 'oasis', 'fuse': 'fuse', 'evmos': 'evmos', 'boba': 'boba',
        'syscoin': 'syscoin', 'velas': 'velas', 'telos': 'telos', 'palm': 'palm',
        'scroll': 'scroll', 'manta': 'manta-pacific', 'mantle': 'mantle',
        'polygonzkevm': 'polygon-zkevm', 'opbnb': 'opbnb', 'blast': 'blast'
    }
    
    # Estimated native token prices (should be fetched in real implementation)
    NATIVE_PRICES_USD = {
        'ethereum': 2000.0, 'bsc': 300.0, 'polygon': 0.8, 'arbitrum': 2000.0,
        'optimism': 2000.0, 'avalanche': 25.0, 'fantom': 0.3, 'base': 2000.0,
        'linea': 2000.0, 'zksync': 2000.0, 'cronos': 0.08, 'gnosis': 1.0,
        'celo': 0.5, 'moonbeam': 0.3, 'moonriver': 5.0, 'metis': 30.0,
        'kava': 0.6, 'aurora': 2000.0, 'harmony': 0.015, 'klaytn': 0.15,
        'oasis': 0.06, 'fuse': 0.04, 'evmos': 0.05, 'boba': 2000.0,
        'syscoin': 0.1, 'velas': 0.02, 'telos': 0.2, 'thundercore': 0.005,
        'palm': 0.01, 'scroll': 2000.0, 'manta': 2000.0, 'mantle': 0.6,
        'polygonzkevm': 2000.0, 'opbnb': 300.0, 'blast': 2000.0
    }
    
    @classmethod
    def get_network_config(cls, network_name: str) -> Dict:
        """Get configuration for specific network"""
        return cls.NETWORKS.get(network_name)
    
    @classmethod
    def get_enabled_networks(cls, settings: Dict) -> Dict:
        """Get only enabled networks based on settings"""
        enabled = {}
        for network_name, config in cls.NETWORKS.items():
            if settings.get('networks', {}).get(network_name, {}).get('enabled', False):
                enabled[network_name] = config
        return enabled
    
    @classmethod
    def format_rpc_urls(cls, network_name: str, infura_key: str = 'demo') -> List[str]:
        """Format RPC URLs with API keys"""
        config = cls.NETWORKS.get(network_name)
        if not config:
            return []
        
        rpcs = []
        for rpc in config['rpcs']:
            if '{infura_key}' in rpc:
                rpcs.append(rpc.format(infura_key=infura_key))
            else:
                rpcs.append(rpc)
        
        return rpcs
    
    @classmethod
    def get_router_abi(cls) -> List[Dict]:
        """Get simplified router ABI for DEX interactions"""
        return [
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "swapExactETHForTokens",
                "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
                "stateMutability": "payable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "swapExactTokensForETH",
                "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"}
                ],
                "name": "getAmountsOut",
                "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
