# utils/migrate_memory.py
import json
from pathlib import Path
from typing import Any, Dict


def migrate_old_memory(old_path: str, new_path: str) -> None:
    """Migrate from old MemoryTracker to enhanced MemoryManager format"""
    if not Path(old_path).exists():
        print(f"Old memory file not found: {old_path}")
        return
        
    try:
        with open(old_path, 'r') as f:
            old_data = json.load(f)
            
        # Convert old format to new format
        new_data = {
            'token_metadata': {},
            'token_history': {},
            'blacklist': {addr: (time.time(), 'Migrated') for addr in old_data.get('blacklist', [])},
            'positions': old_data.get('positions', {}),
            'market_snapshots': old_data.get('market_snapshots', {})
        }
        
        # Save new format
        with open(new_path, 'w') as f:
            json.dump(new_data, f, indent=2)
            
        print(f"Successfully migrated memory data to {new_path}")
        
    except Exception as e:
        print(f"Error migrating memory data: {e}")
        raise

if __name__ == "__main__":
    data_dir = Path(__file__).parent.parent / 'data'
    migrate_old_memory(
        str(data_dir / 'memory.json'),
        str(data_dir / 'memory_state.json')
    )
