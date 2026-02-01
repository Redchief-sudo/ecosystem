"""
MEV Protection Module
--------------------
Provides protection against front-running and sandwich attacks.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

from eth_account.signers.local import LocalAccount
from flashbots import FlashbotProvider, flashbot
from web3 import Web3
from web3.middleware import geth_poa_middleware
import logging

logger = logging.getLogger(__name__)


class MEVProtector:
    """
    Provides protection against MEV attacks and optimizes transaction execution.
    """
    
    def __init__(self, w3: Web3, private_key: str):
        """
        Initialize MEV protector with Flashbots integration.
        
        Args:
            w3: Web3 instance
            private_key: Private key for signing transactions
        """
        self.w3 = w3
        self.account: LocalAccount = w3.eth.account.from_key(private_key)
        self.private_key = private_key
        self.nonce_cache = {}
        self.flashbots_enabled = False
        
        # Try to initialize Flashbots
        try:
            # Apply Flashbots middleware
            self.w3 = flashbot(w3, self.account)
            self.flashbots_enabled = True
            logger.info("✅ Flashbots MEV protection enabled")
        except Exception as e:
            logger.warning(f"⚠️ Flashbots initialization failed: {e}. Falling back to regular transactions.")
            self.flashbots_enabled = False
        
    async def protect_transaction(self, 
                               tx: Dict[str, Any], 
                               max_priority_fee: int,
                               max_fee: int) -> Dict[str, Any]:
        """
        Add MEV protection to a transaction.
        
        Args:
            tx: Transaction dictionary
            max_priority_fee: Max priority fee in wei
            max_fee: Max fee in wei
            
        Returns:
            Protected transaction dictionary
        """
        chain_id = self.w3.eth.chain_id
        nonce = await self._get_nonce()
        
        return {
            **tx,
            'from': self.account.address,
            'maxFeePerGas': max_fee,
            'maxPriorityFeePerGas': max_priority_fee,
            'nonce': nonce,
            'chainId': chain_id,
            'type': '0x2'  # EIP-1559 transaction
        }
    
    async def send_private_transaction(self, tx: Dict[str, Any]) -> str:
        """
        Send transaction through Flashbots or fallback to regular network.
        
        Args:
            tx: Transaction dictionary
            
        Returns:
            Transaction hash
        """
        # Sign the transaction
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        
        # Try Flashbots bundle if enabled
        if self.flashbots_enabled:
            try:
                bundle = [{
                    'signed_transaction': signed_tx.rawTransaction.hex()
                }]
                
                # Target next block
                target_block = await self.w3.eth.block_number + 1
                
                # Send bundle through Flashbots
                result = await self.w3.flashbots.send_bundle(
                    bundle,
                    target_block_number=target_block
                )
                
                if 'bundleHash' in result:
                    logger.info(f"✅ Transaction sent via Flashbots: {result['bundleHash']}")
                    return result['bundleHash']
                    
            except Exception as e:
                logger.warning(f"⚠️ Flashbots bundle failed: {e}. Falling back to regular transaction.")
        
        # Fallback: send regular transaction
        try:
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"📤 Transaction sent (regular): {tx_hash.hex()}")
            return tx_hash.hex()
        except Exception as e:
            logger.error(f"❌ Failed to send transaction: {e}")
            raise Exception(f"Failed to send transaction: {e}")
    
    async def _get_nonce(self) -> int:
        """Get the next nonce, with caching to avoid nonce conflicts."""
        address = self.account.address
        if address not in self.nonce_cache:
            self.nonce_cache[address] = await self.w3.eth.get_transaction_count(address)
        else:
            self.nonce_cache[address] += 1
        return self.nonce_cache[address]
    
    def estimate_optimal_gas(self, tx: Dict[str, Any]) -> Dict[str, int]:
        """
        Estimate optimal gas parameters for a transaction.
        
        Args:
            tx: Transaction dictionary
            
        Returns:
            Dictionary with gas parameters
        """
        # Get base fee from latest block
        latest_block = self.w3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        
        # Add priority fee (tip)
        max_priority_fee = self.w3.eth.max_priority_fee
        
        # Calculate max fee (base fee + 2x priority fee for safety)
        max_fee = base_fee + (2 * max_priority_fee)
        
        return {
            'maxFeePerGas': max_fee,
            'maxPriorityFeePerGas': max_priority_fee,
            'gas': 300000  # Default gas limit
        }
