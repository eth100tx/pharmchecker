#!/usr/bin/env python3
"""
Pharmacy CSV Converter
Converts old pharmacy CSV format to new PharmChecker schema format.

Old format:
- address_street: Full street address including suite
- address_city_state_zip: "City, ST ZIP" format  
- Missing alias field
- Extra fields mixed in

New format:
- address: Street address only
- suite: Suite/unit number (separate field)
- city, state, zip: Separate fields
- alias: New field for alternative names
- Additional fields go to additional_info JSONB
"""

import pandas as pd
import re
import json
import sys
from pathlib import Path

def parse_address_street(address_street):
    """
    Parse address_street into address and suite components
    
    Examples:
    "7601 North Sam Houston Pkwy W Ste 100" -> ("7601 North Sam Houston Pkwy W", "Ste 100")
    "12393 Belcher Rd S. Suite 450" -> ("12393 Belcher Rd S.", "Suite 450")
    "231 Violet Street, Suite 140" -> ("231 Violet Street", "Suite 140")
    """
    if pd.isna(address_street) or not address_street.strip():
        return "", ""
    
    address_street = address_street.strip()
    
    # Common suite patterns
    suite_patterns = [
        r'\s+(Suite?\s*\d+.*?)$',  # Suite 100, Ste 100, Suite A
        r'\s+(Unit?\s*\d+.*?)$',   # Unit 5, Unit A
        r'\s+(#\s*\d+.*?)$',       # #100, # 100
        r'\s+([A-Z]?\d*[A-Z]?)$',  # Building/suite codes like "450", "B"
    ]
    
    for pattern in suite_patterns:
        match = re.search(pattern, address_street, re.IGNORECASE)
        if match:
            suite = match.group(1).strip()
            address = address_street[:match.start()].strip()
            # Clean up trailing commas and whitespace
            address = address.rstrip(',').strip()
            return address, suite
    
    # No suite found - clean up trailing commas
    address_street = address_street.rstrip(',').strip()
    return address_street, ""

def parse_city_state_zip(city_state_zip):
    """
    Parse address_city_state_zip into city, state, zip components
    
    Examples:
    "Houston, TX 77064" -> ("Houston", "TX", "77064")
    "Kirkland, WA 98034" -> ("Kirkland", "WA", "98034")
    "Egg Harbor Township, NJ 08234" -> ("Egg Harbor Township", "NJ", "08234")
    """
    if pd.isna(city_state_zip) or not city_state_zip.strip():
        return "", "", ""
    
    city_state_zip = city_state_zip.strip()
    
    # Pattern: "City Name, ST ZIPCODE"
    pattern = r'^(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$'
    match = re.match(pattern, city_state_zip)
    
    if match:
        city = match.group(1).strip()
        state = match.group(2).strip().upper()
        zip_code = match.group(3).strip()
        return city, state, zip_code
    
    # Fallback - try to extract state code at the end
    state_pattern = r'\b([A-Z]{2})\b'
    state_matches = re.findall(state_pattern, city_state_zip)
    
    if state_matches:
        state = state_matches[-1]  # Use the last state code found
        # Remove state from string to get city + zip
        remaining = re.sub(r'\b' + state + r'\b', '', city_state_zip).strip()
        
        # Try to extract ZIP
        zip_pattern = r'\b(\d{5}(?:-\d{4})?)\b'
        zip_match = re.search(zip_pattern, remaining)
        
        if zip_match:
            zip_code = zip_match.group(1)
            city = remaining.replace(zip_code, '').strip().rstrip(',').strip()
            return city, state, zip_code
        else:
            city = remaining.rstrip(',').strip()
            return city, state, ""
    
    # Last fallback - return as city only
    return city_state_zip.rstrip(',').strip(), "", ""

def generate_alias(name, notes=""):
    """
    Generate alias from name or notes
    Simple heuristics for common pharmacy naming patterns
    """
    if not name:
        return ""
    
    # If name contains "Pharmacy", remove it for alias
    if "Pharmacy" in name:
        alias = name.replace(" Pharmacy", "").replace("Pharmacy ", "").strip()
        if alias != name and len(alias) > 2:
            return alias
    
    # Check for company suffixes to create shorter alias
    suffixes = [" LLC", " Inc", " Corp", " Company", " Co", " Labs", " Health"]
    for suffix in suffixes:
        if name.endswith(suffix):
            alias = name[:-len(suffix)].strip()
            if len(alias) > 2:
                return alias
    
    # If notes mention a short name, extract it
    if notes and isinstance(notes, str):
        # Look for patterns like "also known as X" or "X pharmacy"
        alias_patterns = [
            r'also known as ([A-Za-z\s]+?)(?:\.|,|$)',
            r'known as ([A-Za-z\s]+?)(?:\.|,|$)',
            r'([A-Z][a-z]+)\s+pharmacy',
        ]
        
        for pattern in alias_patterns:
            match = re.search(pattern, notes, re.IGNORECASE)
            if match:
                potential_alias = match.group(1).strip()
                if potential_alias != name and len(potential_alias) > 2:
                    return potential_alias
    
    # No good alias found
    return ""

def convert_pharmacy_csv(input_file, output_file):
    """
    Convert pharmacy CSV from old to new format
    """
    print(f"Converting {input_file} -> {output_file}")
    
    # Read old format CSV
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} records")
    
    # Prepare new format data
    new_data = []
    conversion_errors = []
    
    for idx, row in df.iterrows():
        try:
            # Parse address
            address, suite = parse_address_street(row.get('address_street', ''))
            
            # Parse city/state/zip
            city, state, zip_code = parse_city_state_zip(row.get('address_city_state_zip', ''))
            
            # Leave alias empty - users will add these manually
            alias = ""
            
            # Build new row maintaining original field order
            # Start with original fields in their original order
            new_row = {}
            
            # Fields we're transforming
            transformed_fields = {'address_street', 'address_city_state_zip'}
            
            # Add all original fields in order, transforming as needed
            for col, val in row.items():
                if col == 'name':
                    # Add name, then insert new address fields
                    new_row['name'] = str(row.get('name', '')).strip()
                    new_row['alias'] = alias
                    new_row['address'] = address
                    new_row['suite'] = suite  
                    new_row['city'] = city
                    new_row['state'] = state
                    new_row['zip'] = zip_code
                elif col not in transformed_fields:
                    # Keep original column and value
                    new_row[col] = val
                # Skip address_street and address_city_state_zip as they're transformed
            
            new_data.append(new_row)
            
        except Exception as e:
            error_msg = f"Row {idx} ({row.get('name', 'Unknown')}): {str(e)}"
            conversion_errors.append(error_msg)
            print(f"ERROR: {error_msg}")
            continue
    
    if not new_data:
        print("ERROR: No valid records converted!")
        return False
    
    # Create new DataFrame and save
    new_df = pd.DataFrame(new_data)
    new_df.to_csv(output_file, index=False)
    
    print(f"\nConversion completed:")
    print(f"  Input records: {len(df)}")
    print(f"  Output records: {len(new_df)}")
    print(f"  Conversion errors: {len(conversion_errors)}")
    
    if conversion_errors:
        print(f"\nFirst 5 errors:")
        for error in conversion_errors[:5]:
            print(f"  - {error}")
        if len(conversion_errors) > 5:
            print(f"  ... and {len(conversion_errors) - 5} more")
    
    # Show sample of conversions
    print(f"\nSample conversions:")
    for idx in range(min(3, len(new_df))):
        row = new_df.iloc[idx]
        orig_row = df.iloc[idx]
        print(f"\n  {idx + 1}. {row['name']}")
        print(f"     Original address: {orig_row.get('address_street', '')} | {orig_row.get('address_city_state_zip', '')}")
        print(f"     New format: {row['address']} | {row['suite']} | {row['city']}, {row['state']} {row['zip']}")
        print(f"     Alias: '{row['alias']}'")
    
    return True

def main():
    """Main conversion process"""
    data_dir = Path(__file__).parent
    
    # Input files
    input_files = [
        'pharmacies_subset.csv',
        'pharmacies_subset2.csv'
    ]
    
    # Output files 
    output_files = [
        'pharmacies_new.csv',
        'pharmacies_new2.csv'
    ]
    
    success_count = 0
    
    for input_file, output_file in zip(input_files, output_files):
        input_path = data_dir / input_file
        output_path = data_dir / output_file
        
        if not input_path.exists():
            print(f"WARNING: Input file not found: {input_path}")
            continue
        
        print(f"\n{'='*60}")
        if convert_pharmacy_csv(input_path, output_path):
            success_count += 1
            print(f"SUCCESS: Created {output_path}")
        else:
            print(f"FAILED: Could not create {output_path}")
    
    print(f"\n{'='*60}")
    print(f"Conversion summary: {success_count}/{len(input_files)} files converted successfully")
    
    if success_count > 0:
        print(f"\nNext steps:")
        print(f"1. Review the generated files: {', '.join(output_files[:success_count])}")
        print(f"2. Test import with: python -c \"from imports.pharmacies import PharmacyImporter; print('Ready!')\"")

if __name__ == '__main__':
    main()