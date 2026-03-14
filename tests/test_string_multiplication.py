#!/usr/bin/env python3

def test_string_multiplication():
    print('🔍 Testing String Multiplication Fixes...\n')
    
    # Test the old problematic pattern
    print('1️⃣ Testing OLD pattern (should be avoided):')
    try:
        old_pattern = '0x' + '0'*40
        print(f'   \"0x\" + \"0\"*40 = {old_pattern}')
        print(f'   Length: {len(old_pattern)}')
        print(f'   Contains 0x00x: {"0x00x" in old_pattern}')
    except Exception as e:
        print(f'   Error: {e}')
    
    # Test the new fixed pattern
    print('\n2️⃣ Testing NEW pattern (fixed):')
    try:
        new_pattern = '0x0000000000000000000000000000000000000000'
        print(f'   Fixed address: {new_pattern}')
        print(f'   Length: {len(new_pattern)}')
        print(f'   Contains 0x00x: {"0x00x" in new_pattern}')
        print(f'   Valid format: {new_pattern.startswith("0x") and len(new_pattern) == 42}')
    except Exception as e:
        print(f'   Error: {e}')
    
    # Test the original problematic multiplication
    print('\n3️⃣ Testing original multiplication (the cause):')
    try:
        mult_pattern = '0x0'*40
        print(f'   \"0x0\"*40 = {mult_pattern}')
        print(f'   Length: {len(mult_pattern)}')
        print(f'   Contains 0x00x: {"0x00x" in mult_pattern}')
        print(f'   This was the corrupted pattern!')
    except Exception as e:
        print(f'   Error: {e}')
    
    print('\n✅ All string multiplication patterns tested!')

if __name__ == "__main__":
    test_string_multiplication()
