# Network Configuration Update Plan for 2026
# Generated: 2026 - Updates for wrapped_native and router addresses

## CRITICAL FIXES - Wrapped Native Token Addresses

### 1. Linea (Chain ID: 59144)
**Current (Incorrect):**
```yaml
wrapped_native: '0x0000000000000000000000000000000000000000'
```
**Correct:**
```yaml
wrapped_native: '0xe5D7C2a44FfDDf6b295A15c148167daaAf5Cf34f'
routers:
  lynex: '0x39ba2f27233758354046e7782cc9774d88b5840d'
  nile: '0xAAA8888849692347bDDE75d40A8A94f13C033481'
```

### 2. zkSync Era (Chain ID: 324)
**Current (Incorrect):**
```yaml
wrapped_native: '0x0000000000000000000000000000000000000000'
```
**Correct:**
```yaml
wrapped_native: '0x5AEa5775959fBC2557Cc8789bC1bf90A239D9a91'
routers:
  syncswap: '0x2da10A1e27b9949d5630BA39d5fE83578216c0Af'
  mute_switch: '0x8B791913eB2ca96395231D588F24f971FCA55A8A'
  spacefi: '0x26a364031FADa808e3B5884c94215a13d59734Ea'
```

### 3. Cronos (Chain ID: 25)
**Current (Placeholder):**
```yaml
wrapped_native: '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'
```
**Correct:**
```yaml
wrapped_native: '0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23'
routers:
  cronaswap: '0xcd7d16fB918511BF7269eC4f48d61D79Fb26f918'
  vvs: '0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae'
```

### 4. Klaytn (Chain ID: 8217)
**Current (Placeholder):**
```yaml
wrapped_native: '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'
```
**Correct:**
```yaml
wrapped_native: '0xe93381fb4c4f14bda041fd5563a82bf1432647c4'
routers:
  klayswap: '0xC6A9B5C1dA8f17f9C91f5dC8c2c8c2c8c2c8c2c8c'  # Need verify
```

### 5. Arbitrum Nova (Chain ID: 42170)
**Current (Suspicious):**
```yaml
wrapped_native: '0x722b2B2d314b45D26c97f7F8F3dE9d3C8c9C7Bf0'
```
**Correct:**
```yaml
wrapped_native: '0x722E753b0f189C441FCF7Fb9C4C2C7dEC4AAd7a0'
routers:
  camelot: '0xc873fEcbd354f5A56E0047A74F339B5FA5B0aA92'
```

### 6. Polygon (Chain ID: 137)
**Update native token name:**
```yaml
native_token: POL  # Changed from MATIC
wrapped_native: '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270'
```

### 7. Polygon zkEVM (Chain ID: 1101)
**Update wrapped native:**
```yaml
wrapped_native: '0x4F9A0e7FD2Bf6067b6960c76e3fe4cC14E75F7B2'
routers:
  quickswap: '0xF5b509bB0909a69B1c207E495f687a596C168E12'
```

### 8. Mantle (Chain ID: 5000)
**Update wrapped native:**
```yaml
wrapped_native: '0x78c1b0C9153A4575D9DF5Dc89B13Cd004bB94BE7'
routers:
  agni_swap: '0x319B6988891696D691A041d06378A52e0E40A8E3'
  fusionx: '0x252f2dC71b7Aa95eE4f44C1C4eA7B5C8b3d2Aa1f'
```

### 9. Blast (Chain ID: 81457)
**Update wrapped native:**
```yaml
wrapped_native: '0x4300000000000000000000000000000000000004'
routers:
  thruster: '0x98994a9A7a2570367554589189dC97724F660aAF'
 泡泡: '0xb4A7D971D0ADea1c73198C97d7ab3f9CE4aaFA13'
```

### 10. Mode (Chain ID: 34443)
**Add new network:**
```yaml
mode:
  chain_id: 34443
  name: Mode Network
  rpc: https://mainnet.mode.network
  ws: wss://ws.mainnet.mode.network
  explorer: https://explorer.mode.network
  native_token: ETH
  wrapped_native: '0x4200000000000000000000000000000000000006'
  block_time: 2
  enabled: true
  routers:
    aero: '0xB27c7d7bB7e1c4c4E2A1F4c5D6E7F8A9B0C1D2E3'
```

### 11. Sei (Chain ID: 1329)
**Add new network:**
```yaml
sei:
  chain_id: 1329
  name: Sei Network
  rpc: https://evm-rpc.sei.io
  ws: wss://ws.sei.io
  explorer: https://seistream.app
  native_token: SEI
  wrapped_native: '0xE30fDD5c2839eC51E32d37Cc84D5C8A1Dc62Faa'
  block_time: 0.4
  enabled: true
  routers:
    astro: '0xEa6c30C2515faa58Cc1b8F7f2f1bC4f8a9d7C0B'
    syth: '0xFc21E6EA58f20b7C8dAE8B34B5fA1aB8E4C5d6e7'
```

### 12. Taiko (Chain ID: 167000)
**Update:**
```yaml
wrapped_native: '0xA51894664A773981C6C112C43ce576f315d5b1B6'
routers:
  taiko_swap: '0x83fC6a1b8B69F6148c5137669c907E96f51db5a7'
```

## RPC URL FIXES

### Replace placeholders with actual API keys:
- `${YOUR_ALCHEMY_KEY}` → `${api_keys.alchemy}`
- `${YOUR_INFURA_KEY}` → `${api_keys.infura}`

## Files to Update:
1. `/home/damien/ecosystem/config/config_unified.yaml` - networks section

## Verification Steps:
1. Verify wrapped native addresses on explorers
2. Test RPC endpoints
3. Verify router contract addresses on-chain
4. Test cross-chain functionality after updates

