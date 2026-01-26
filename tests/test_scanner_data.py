#!/usr/bin/env python3
"""
Scanner Data Analysis Tool
Tests each scanner to analyze what raw data they return.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scanners.base_scanner import ScannerBase
from scanners.experimental.dexscreener_ultra_scanner import DexScreenerUltraScanner
from scanners.discovery.mempool_scanner import MempoolScannerUltra
from scanners.discovery.onchain_scanner import OnChainScannerUltra
from scanners.scanned_token import ScannedToken

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ScannerDataAnalyzer:
    """Analyzes raw data output from all scanners."""
    
    def __init__(self):
        self.scanners = {}
        self.results = {}
        
    def register_scanner(self, name: str, scanner: ScannerBase):
        """Register a scanner for testing."""
        self.scanners[name] = scanner
        
    async def test_scanner(self, name: str, scanner: ScannerBase) -> Dict[str, Any]:
        """Test a single scanner and analyze its output."""
        logger.info(f"Testing scanner: {name}")
        
        result = {
            'scanner_name': name,
            'test_time': datetime.now().isoformat(),
            'status': 'unknown',
            'error': None,
            'raw_data_samples': [],
            'field_analysis': {
                'all_fields': set(),
                'common_fields': set(),
                'missing_required_fields': [],
                'field_types': {},
                'sample_count': 0
            }
        }
        
        try:
            # Start the scanner if it has a start method
            if hasattr(scanner, 'start'):
                await scanner.start()
            
            # Try different scan methods
            scan_methods = ['scan', 'scan_network', 'protected_scan']
            raw_data = []
            
            for method_name in scan_methods:
                if hasattr(scanner, method_name):
                    try:
                        method = getattr(scanner, method_name)
                        if asyncio.iscoroutinefunction(method):
                            # For async methods, try with a test chain
                            if method_name in ['scan_network', 'protected_scan']:
                                data = await asyncio.wait_for(method('ethereum'), timeout=30)
                            else:
                                data = await asyncio.wait_for(method(), timeout=30)
                        else:
                            # For sync methods
                            if method_name in ['scan_network', 'protected_scan']:
                                data = method('ethereum')
                            else:
                                data = method()
                        
                        if data:
                            raw_data = data
                            logger.info(f"Got {len(data)} items from {name}.{method_name}()")
                            break
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout calling {name}.{method_name}()")
                        continue
                    except Exception as e:
                        logger.warning(f"Error calling {name}.{method_name}(): {e}")
                        continue
            
            if not raw_data:
                result['status'] = 'no_data'
                result['error'] = 'No scan method returned data'
                return result
            
            # Analyze the raw data
            result['raw_data_samples'] = raw_data[:3]  # Keep first 3 samples
            result['field_analysis']['sample_count'] = len(raw_data)
            
            # Collect all fields across all samples
            all_fields = set()
            field_types = {}
            required_fields = ['address', 'symbol', 'name']
            
            for i, item in enumerate(raw_data[:10]):  # Analyze first 10 items
                if isinstance(item, dict):
                    fields = set(item.keys())
                    all_fields.update(fields)
                    
                    # Track field types
                    for field, value in item.items():
                        if field not in field_types:
                            field_types[field] = set()
                        field_types[field].add(type(value).__name__)
                
                elif isinstance(item, ScannedToken):
                    # For ScannedToken objects, get all attributes
                    fields = set(item.__dict__.keys())
                    all_fields.update(fields)
                    
                    # Track field types
                    for field, value in item.__dict__.items():
                        if field not in field_types:
                            field_types[field] = set()
                        field_types[field].add(type(value).__name__)
            
            result['field_analysis']['all_fields'] = sorted(list(all_fields))
            result['field_analysis']['field_types'] = {
                field: sorted(list(types)) for field, types in field_types.items()
            }
            
            # Check for missing required fields
            missing_required = []
            for field in required_fields:
                if field not in all_fields:
                    missing_required.append(field)
            
            result['field_analysis']['missing_required_fields'] = missing_required
            
            # Find common fields (present in >80% of samples)
            if raw_data:
                field_counts = {}
                for item in raw_data[:10]:
                    if isinstance(item, dict):
                        for field in item.keys():
                            field_counts[field] = field_counts.get(field, 0) + 1
                    elif isinstance(item, ScannedToken):
                        for field in item.__dict__.keys():
                            field_counts[field] = field_counts.get(field, 0) + 1
                
                common_fields = {
                    field for field, count in field_counts.items() 
                    if count >= len(raw_data[:10]) * 0.8
                }
                result['field_analysis']['common_fields'] = sorted(list(common_fields))
            
            result['status'] = 'success'
            logger.info(f"Successfully analyzed {name}: {len(all_fields)} fields found")
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"Error testing {name}: {e}")
        
        finally:
            # Stop the scanner if it has a stop method
            if hasattr(scanner, 'stop'):
                try:
                    await scanner.stop()
                except:
                    pass
        
        return result
    
    async def test_all_scanners(self) -> Dict[str, Any]:
        """Test all registered scanners."""
        logger.info(f"Testing {len(self.scanners)} scanners...")
        
        results = {}
        for name, scanner in self.scanners.items():
            try:
                result = await self.test_scanner(name, scanner)
                results[name] = result
            except Exception as e:
                logger.error(f"Failed to test {name}: {e}")
                results[name] = {
                    'scanner_name': name,
                    'status': 'test_failed',
                    'error': str(e),
                    'test_time': datetime.now().isoformat()
                }
        
        self.results = results
        return results
    
    def print_summary(self):
        """Print a summary of all scanner results."""
        print("\n" + "="*80)
        print("SCANNER DATA ANALYSIS SUMMARY")
        print("="*80)
        
        for name, result in self.results.items():
            print(f"\n{'='*60}")
            print(f"Scanner: {name}")
            print(f"Status: {result['status']}")
            print(f"Test Time: {result['test_time']}")
            
            if result['status'] == 'error':
                print(f"Error: {result['error']}")
                continue
            
            if result['status'] == 'no_data':
                print("No data returned")
                continue
            
            field_analysis = result['field_analysis']
            print(f"Sample Count: {field_analysis['sample_count']}")
            print(f"Total Fields: {len(field_analysis['all_fields'])}")
            print(f"Common Fields: {len(field_analysis['common_fields'])}")
            
            if field_analysis['missing_required_fields']:
                print(f"Missing Required: {field_analysis['missing_required_fields']}")
            
            print(f"\nAll Fields: {', '.join(field_analysis['all_fields'])}")
            
            if result['raw_data_samples']:
                print(f"\nSample Data (first item):")
                sample = result['raw_data_samples'][0]
                if isinstance(sample, dict):
                    print(json.dumps(sample, indent=2, default=str))
                elif hasattr(sample, '__dict__'):
                    print(json.dumps(sample.__dict__, indent=2, default=str))
                else:
                    print(str(sample))
    
    def save_results(self, filename: str = 'scanner_analysis_results.json'):
        """Save analysis results to file."""
        # Convert sets to lists for JSON serialization
        serializable_results = {}
        for name, result in self.results.items():
            serializable_results[name] = result.copy()
            if 'field_analysis' in result:
                fa = result['field_analysis']
                fa['all_fields'] = list(fa['all_fields'])
                fa['common_fields'] = list(fa['common_fields'])
        
        with open(filename, 'w') as f:
            json.dump(serializable_results, f, indent=2, default=str)
        
        print(f"\nResults saved to: {filename}")

async def main():
    """Main test function."""
    analyzer = ScannerDataAnalyzer()
    
    # Register available scanners with minimal configs
    scanners_to_test = [
        ('DexScreenerUltraScanner', DexScreenerUltraScanner({})),
        ('MempoolScannerUltra', MempoolScannerUltra({
            'enabled_chains': ['ethereum'],
            'min_gas_price': 20,
            'max_transactions_per_block': 100
        })),
        ('OnChainScannerUltra', OnChainScannerUltra({
            'enabled_chains': ['ethereum'],
            'scan_interval': 60,
            'max_concurrent_scans': 5
        })),
    ]
    
    for name, scanner in scanners_to_test:
        try:
            analyzer.register_scanner(name, scanner)
            print(f"Registered scanner: {name}")
        except Exception as e:
            print(f"Failed to register {name}: {e}")
    
    # Run the tests
    results = await analyzer.test_all_scanners()
    
    # Print summary
    analyzer.print_summary()
    
    # Save results
    analyzer.save_results()
    
    return results

if __name__ == '__main__':
    try:
        results = asyncio.run(main())
        print(f"\nTest completed. Analyzed {len(results)} scanners.")
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
