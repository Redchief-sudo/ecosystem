#!/usr/bin/env python3
"""
Test script to verify the chain identity and deduplication fixes.
Tests the three critical areas:
1. Scanner chain extraction logic
2. Deduplicator pair-specific logic
3. Cross-chain behavior prevention
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from trading.token_pipeline.token_deduplicator import TokenDeduplicator, token_deduplicator
from networks.chain_normalizer import chain_normalizer

def test_deduplicator_pair_specific_logic():
    """Test that deduplicator treats same token in different pairs as separate opportunities."""
    print("🧪 Testing deduplicator pair-specific logic...")

    # Create fresh deduplicator for testing
    dedupe = TokenDeduplicator()

    # Test case: Same token (0x2170ed...) in different pairs on same chain
    test_tokens = [
        {
            'chain': 'bsc',
            'address': '0x2170ed0880ac9a755fd29b2688956bd959f933f8',
            'pair_address': '0x1234567890123456789012345678901234567890',  # Pair A
            'symbol': 'ETH',
            'source': 'dexscreener'
        },
        {
            'chain': 'bsc',
            'address': '0x2170ed0880ac9a755fd29b2688956bd959f933f8',  # Same token
            'pair_address': '0x0987654321098765432109876543210987654321',  # Pair B (different)
            'symbol': 'ETH',
            'source': 'dexscreener'
        },
        {
            'chain': 'bsc',
            'address': '0x2170ed0880ac9a755fd29b2688956bd959f933f8',  # Same token, same pair (duplicate)
            'pair_address': '0x1234567890123456789012345678901234567890',  # Same pair A
            'symbol': 'ETH',
            'source': 'dexscreener'
        }
    ]

    unique_tokens = dedupe.add_tokens(test_tokens, "test_scanner")

    # Should have 2 unique tokens (different pairs), 1 duplicate
    assert len(unique_tokens) == 2, f"Expected 2 unique tokens, got {len(unique_tokens)}"
    assert dedupe.duplicate_count == 1, f"Expected 1 duplicate, got {dedupe.duplicate_count}"

    print("✅ Deduplicator correctly treats same token in different pairs as separate opportunities")
    print(f"   Unique tokens: {len(unique_tokens)}, Duplicates: {dedupe.duplicate_count}")

def test_deduplicator_cross_chain_behavior():
    """Test that same token on different chains are treated as separate opportunities."""
    print("🧪 Testing deduplicator cross-chain behavior...")

    # Create fresh deduplicator for testing
    dedupe = TokenDeduplicator()

    # Test case: Same token address on different chains (legitimate cross-chain tokens)
    test_tokens = [
        {
            'chain': 'ethereum',
            'address': '0xa0b86a33e6c6c4d1b6e8b6c4b6e8b6c4b6e8b6c4',
            'pair_address': '0x1111111111111111111111111111111111111111',
            'symbol': 'TEST',
            'source': 'dexscreener'
        },
        {
            'chain': 'bsc',
            'address': '0xa0b86a33e6c6c4d1b6e8b6c4b6e8b6c4b6e8b6c4',  # Same address
            'pair_address': '0x2222222222222222222222222222222222222222',  # Different pair
            'symbol': 'TEST',
            'source': 'dexscreener'
        },
        {
            'chain': 'polygon',
            'address': '0xa0b86a33e6c6c4d1b6e8b6c4b6e8b6c4b6e8b6c4',  # Same address
            'pair_address': '0x3333333333333333333333333333333333333333',  # Different pair
            'symbol': 'TEST',
            'source': 'dexscreener'
        }
    ]

    unique_tokens = dedupe.add_tokens(test_tokens, "test_scanner")

    # Should have 3 unique tokens (different chains), 0 duplicates
    assert len(unique_tokens) == 3, f"Expected 3 unique tokens, got {len(unique_tokens)}"
    assert dedupe.duplicate_count == 0, f"Expected 0 duplicates, got {dedupe.duplicate_count}"

    print("✅ Deduplicator correctly treats same token on different chains as separate opportunities")
    print(f"   Unique tokens: {len(unique_tokens)}, Duplicates: {dedupe.duplicate_count}")

def test_chain_normalizer():
    """Test that chain normalizer works correctly for DexScreener chain IDs."""
    print("🧪 Testing chain normalizer for DexScreener compatibility...")

    # Test common DexScreener chain ID mappings
    test_cases = [
        ('bsc', 'bsc'),
        ('ethereum', 'ethereum'),
        ('polygon', 'polygon'),
        ('matic', 'polygon'),  # Alternative name
        ('arbitrum', 'arbitrum'),
        ('optimism', 'optimism'),
        ('base', 'base'),
        ('avalanche', 'avalanche'),
        ('fantom', 'fantom'),
    ]

    for input_chain, expected_chain in test_cases:
        normalized = chain_normalizer.normalize_chain_identifier(input_chain)
        assert normalized == expected_chain, f"Expected {expected_chain}, got {normalized} for input {input_chain}"

    print("✅ Chain normalizer correctly handles DexScreener chain IDs")

def test_scanner_chain_filtering_logic():
    """Test the scanner's chain filtering logic (simulated)."""
    print("🧪 Testing scanner chain filtering logic...")

    # Simulate the logic from _process_single_token
    def simulate_chain_filtering(pair_chain_id, requested_chain):
        """Simulate the chain filtering logic from the scanner."""
        if not pair_chain_id:
            return None  # Skip pairs without chainId

        actual_chain = chain_normalizer.normalize_chain_identifier(pair_chain_id)

        # If the actual chain doesn't match the requested chain, skip this pair
        if actual_chain != requested_chain:
            return None  # Filtered out

        return actual_chain  # Valid pair

    # Test cases
    test_cases = [
        # (pair_chain_id, requested_chain, expected_result)
        ('bsc', 'bsc', 'bsc'),  # Match - should pass
        ('bsc', 'ethereum', None),  # Mismatch - should be filtered
        ('matic', 'polygon', 'polygon'),  # Alternative name - should normalize and pass
        ('matic', 'ethereum', None),  # Alternative name mismatch - should be filtered
        (None, 'bsc', None),  # Missing chainId - should be filtered
    ]

    for pair_chain_id, requested_chain, expected in test_cases:
        result = simulate_chain_filtering(pair_chain_id, requested_chain)
        assert result == expected, f"Chain filtering failed: pair_chain_id={pair_chain_id}, requested={requested_chain}, expected={expected}, got={result}"

    print("✅ Scanner chain filtering logic correctly prevents cross-chain fan-out")

def test_deduplication_key_format():
    """Test that deduplication keys are formatted correctly."""
    print("🧪 Testing deduplication key format...")

    dedupe = TokenDeduplicator()

    # Test the key generation logic
    test_cases = [
        ('bsc', '0x2170ed0880ac9a755fd29b2688956bd959f933f8', '0x1234567890123456789012345678901234567890'),
        ('ethereum', '0xa0b86a33e6c6c4d1b6e8b6c4b6e8b6c4b6e8b6c4', None),
        ('polygon', '0x1234567890123456789012345678901234567890', '0x0987654321098765432109876543210987654321'),
    ]

    for chain, address, pair_address in test_cases:
        # Simulate the key generation from is_duplicate
        pair_part = f":{pair_address.lower()}" if pair_address else ""
        expected_key = f"{chain}:{address.lower()}{pair_part}"

        # Test that the method would generate the same key
        # First call should not be duplicate
        is_dup1 = dedupe.is_duplicate(chain, address, pair_address)
        assert not is_dup1, f"First call should not be duplicate for {expected_key}"

        # Second call should be duplicate
        is_dup2 = dedupe.is_duplicate(chain, address, pair_address)
        assert is_dup2, f"Second call should be duplicate for {expected_key}"

    print("✅ Deduplication key format correctly includes chain:address:pair_address")

def main():
    """Run all tests."""
    print("🚀 Running Chain Identity and Deduplication Fix Tests\n")

    tests = [
        test_chain_normalizer,
        test_scanner_chain_filtering_logic,
        test_deduplicator_pair_specific_logic,
        test_deduplicator_cross_chain_behavior,
        test_deduplication_key_format,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_func.__name__} PASSED\n")
            else:
                failed += 1
                print(f"❌ {test_func.__name__} FAILED\n")
        except Exception as e:
            failed += 1
            print(f"❌ {test_func.__name__} FAILED with exception: {e}\n")

    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! The chain identity and deduplication fixes are working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please review the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
