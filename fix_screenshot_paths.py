#!/usr/bin/env python3
"""
Fix screenshot paths in JSON files
Changes "tests/data/states_baseline" to "data/states_baseline" in all JSON files
"""
import json
from pathlib import Path

def fix_json_file(filepath: Path) -> bool:
    """Fix screenshot paths in a single JSON file"""
    try:
        # Read the JSON file
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if we need to fix the source_image_file path
        metadata = data.get('metadata', {})
        source_image_file = metadata.get('source_image_file', '')
        
        if source_image_file.startswith('tests/data/'):
            # Fix the path
            new_path = source_image_file.replace('tests/data/', 'data/')
            metadata['source_image_file'] = new_path
            
            # Write back the corrected JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"Fixed: {filepath.name} -> {new_path}")
            return True
        else:
            print(f"No fix needed: {filepath.name}")
            return False
            
    except Exception as e:
        print(f"ERROR fixing {filepath}: {e}")
        return False

def main():
    """Fix all JSON files in states_baseline and states_baseline2"""
    base_dir = Path("data")
    
    directories = [
        base_dir / "states_baseline",
        base_dir / "states_baseline2"
    ]
    
    total_files = 0
    fixed_files = 0
    
    for directory in directories:
        if not directory.exists():
            print(f"Directory not found: {directory}")
            continue
            
        print(f"\nFixing JSON files in {directory}...")
        
        # Find all *_parse.json files
        json_files = list(directory.rglob("*_parse.json"))
        print(f"Found {len(json_files)} JSON files")
        
        for json_file in json_files:
            total_files += 1
            if fix_json_file(json_file):
                fixed_files += 1
    
    print(f"\n" + "="*50)
    print(f"Summary: Fixed {fixed_files} out of {total_files} JSON files")

if __name__ == "__main__":
    main()