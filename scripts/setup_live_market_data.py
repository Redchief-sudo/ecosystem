#!/usr/bin/env python3
"""
Setup Live Market Data - Switch from Mock to Real Data
=====================================================

This script helps you set up real-time market data from CoinMarketCap.
"""

import os
import sys
from pathlib import Path


def setup_coinmarketcap_api():
    """Setup CoinMarketCap API key for live market data."""
    
    print("🔧 Setting up Live Market Data...")
    print("=" * 50)
    
    # Check if API key already exists
    existing_key = os.getenv("COINMARKETCAP_API_KEY")
    if existing_key and existing_key != "your-api-key-here":
        print(f"✅ API key already configured: {existing_key[:10]}...")
        return True
    
    print("\n📋 To get your CoinMarketCap API key:")
    print("1. Go to: https://coinmarketcap.com/api/")
    print("2. Sign up for a free account")
    print("3. Get your API key (free tier allows 10,000 calls/month)")
    print("4. Copy the key below")
    
    # Get API key from user
    api_key = input("\n🔑 Enter your CoinMarketCap API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided - keeping mock data")
        return False
    
    # Validate API key format (basic check)
    if len(api_key) < 10 or not api_key.isalnum():
        print("❌ Invalid API key format - keeping mock data")
        return False
    
    # Update .env file
    env_file = Path(".env")
    if env_file.exists():
        # Read existing .env
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Update or add API key
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("COINMARKETCAP_API_KEY="):
                lines[i] = f"COINMARKETCAP_API_KEY={api_key}\n"
                updated = True
                break
        
        if not updated:
            lines.append(f"COINMARKETCAP_API_KEY={api_key}\n")
        
        # Write back to .env
        with open(env_file, 'w') as f:
            f.writelines(lines)
        
        print(f"✅ API key saved to .env")
        return True
    else:
        print("❌ .env file not found - creating new one")
        with open(env_file, 'w') as f:
            f.write(f"COINMARKETCAP_API_KEY={api_key}\n")
        print(f"✅ Created .env with API key")
        return True

def test_live_data():
    """Test the live market data connection."""
    
    print("\n🧪 Testing Live Market Data Connection...")
    print("=" * 50)
    
    try:
        # Import and test
        sys.path.insert(0, '/home/damien/ecosystem')
        from decimal import Decimal

        from trading.market_data.coinmarketcap_provider import CoinMarketCapDataProvider

        # Get API key
        api_key = os.getenv("COINMARKETCAP_API_KEY")
        if not api_key or api_key == "your-api-key-here":
            print("❌ No valid API key found")
            return False
        
        # Create provider
        provider = CoinMarketCapDataProvider(api_key)
        
        # Test with ETH
        import asyncio
        
        async def test_connection():
            try:
                print("📊 Fetching ETH data...")
                eth_data = await provider.get_snapshot("ETH")
                
                print(f"✅ Live ETH data received:")
                print(f"   Price: ${eth_data.price:.2f}")
                print(f"   Volume: ${eth_data.volume_24h:,.0f}")
                print(f"   Liquidity: ${eth_data.liquidity:,.0f}")
                
                # Test with BTC
                print("\n📊 Fetching BTC data...")
                btc_data = await provider.get_snapshot("BTC")
                
                print(f"✅ Live BTC data received:")
                print(f"   Price: ${btc_data.price:.2f}")
                print(f"   Volume: ${btc_data.volume_24h:,.0f}")
                
                return True
                
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                return False
        
        return asyncio.run(test_connection())
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def main():
    """Main setup process."""
    
    print("🚀 Live Market Data Setup")
    print("This will switch your system from mock data to real-time CoinMarketCap data")
    print()
    
    # Step 1: Setup API key
    if setup_coinmarketcap_api():
        # Step 2: Test connection
        if test_live_data():
            print("\n" + "=" * 50)
            print("🎉 SUCCESS! Live market data is now configured!")
            print("\n📋 What happens next:")
            print("✅ Your trading engine will use real-time prices")
            print("✅ No more static mock data")
            print("✅ Real market volatility and volume")
            print("✅ Accurate execution planning")
            print("\n🔄 Restart your system to use live data:")
            print("   python3 main.py")
        else:
            print("\n❌ API key configured but connection test failed")
            print("Please check your API key and internet connection")
    else:
        print("\n⚠️ API key setup cancelled - continuing with mock data")

if __name__ == "__main__":
    main()
