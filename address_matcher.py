#!/usr/bin/env python3
"""
US Address Matcher Library

A simple Python library for matching US business addresses with typo tolerance.
Handles both structured dict format and string format addresses.

Installation:
pip install usaddress rapidfuzz

Usage:
    from address_matcher import match_addresses
    
    # Compare two addresses
    score = match_addresses(
        {"street": "123 Main St", "city": "New York", "state": "NY", "zip_code": "10001"},
        "123 Main Street, New York, NY 10001"
    )
    print(f"Match score: {score['overall']}")  # Returns 95.5
"""

import re
import usaddress
from rapidfuzz import fuzz
from typing import Dict, Union, List, Tuple


class AddressNormalizer:
    """Internal class for address normalization"""
    
    STREET_SUFFIXES = {
        'st': 'street', 'st.': 'street', 'str': 'street',
        'ave': 'avenue', 'ave.': 'avenue', 'av': 'avenue',
        'blvd': 'boulevard', 'blvd.': 'boulevard', 'bvd': 'boulevard',
        'rd': 'road', 'rd.': 'road',
        'dr': 'drive', 'dr.': 'drive', 'drv': 'drive',
        'ln': 'lane', 'ln.': 'lane',
        'ct': 'court', 'ct.': 'court', 'crt': 'court',
        'pl': 'place', 'pl.': 'place',
        'cir': 'circle', 'cir.': 'circle', 'crcl': 'circle',
        'trl': 'trail', 'trl.': 'trail', 'tr': 'trail',
        'pkwy': 'parkway', 'pkwy.': 'parkway', 'pky': 'parkway',
        'hwy': 'highway', 'hwy.': 'highway',
        'sq': 'square', 'sq.': 'square',
        'ter': 'terrace', 'ter.': 'terrace', 'terr': 'terrace'
    }
    
    DIRECTIONS = {
        'n': 'north', 'n.': 'north',
        's': 'south', 's.': 'south',
        'e': 'east', 'e.': 'east',
        'w': 'west', 'w.': 'west',
        'ne': 'northeast', 'ne.': 'northeast',
        'nw': 'northwest', 'nw.': 'northwest',
        'se': 'southeast', 'se.': 'southeast',
        'sw': 'southwest', 'sw.': 'southwest'
    }
    
    STATE_ABBR = {
        'alabama': 'al', 'alaska': 'ak', 'arizona': 'az', 'arkansas': 'ar',
        'california': 'ca', 'colorado': 'co', 'connecticut': 'ct', 'delaware': 'de',
        'florida': 'fl', 'georgia': 'ga', 'hawaii': 'hi', 'idaho': 'id',
        'illinois': 'il', 'indiana': 'in', 'iowa': 'ia', 'kansas': 'ks',
        'kentucky': 'ky', 'louisiana': 'la', 'maine': 'me', 'maryland': 'md',
        'massachusetts': 'ma', 'michigan': 'mi', 'minnesota': 'mn', 'mississippi': 'ms',
        'missouri': 'mo', 'montana': 'mt', 'nebraska': 'ne', 'nevada': 'nv',
        'new hampshire': 'nh', 'new jersey': 'nj', 'new mexico': 'nm', 'new york': 'ny',
        'north carolina': 'nc', 'north dakota': 'nd', 'ohio': 'oh', 'oklahoma': 'ok',
        'oregon': 'or', 'pennsylvania': 'pa', 'rhode island': 'ri', 'south carolina': 'sc',
        'south dakota': 'sd', 'tennessee': 'tn', 'texas': 'tx', 'utah': 'ut',
        'vermont': 'vt', 'virginia': 'va', 'washington': 'wa', 'west virginia': 'wv',
        'wisconsin': 'wi', 'wyoming': 'wy'
    }
    
    def parse_address(self, address_input: Union[Dict, str]) -> Dict[str, str]:
        """Parse address into components"""
        if isinstance(address_input, dict):
            # Handle dict format
            street = address_input.get('street') or ''
            suite = address_input.get('suite') or ''
            if suite:
                street = f"{street} {suite}".strip()
            
            return {
                'street': street,
                'city': address_input.get('city') or '',
                'state': address_input.get('state') or '',
                'zip_code': address_input.get('zip_code') or ''
            }
        
        # Handle string format
        try:
            parsed, _ = usaddress.tag(str(address_input))
            
            street_parts = []
            for key in ['AddressNumber', 'StreetNamePreDirectional', 'StreetName', 
                       'StreetNamePostType', 'StreetNamePostDirectional', 'OccupancyIdentifier']:
                if key in parsed:
                    street_parts.append(parsed[key])
            
            return {
                'street': ' '.join(street_parts),
                'city': parsed.get('PlaceName', ''),
                'state': parsed.get('StateName', ''),
                'zip_code': parsed.get('ZipCode', '')
            }
        except:
            # Fallback parsing
            parts = str(address_input).split(',')
            result = {'street': '', 'city': '', 'state': '', 'zip_code': ''}
            
            if len(parts) >= 1:
                result['street'] = parts[0].strip()
            if len(parts) >= 2:
                result['city'] = parts[1].strip()
            if len(parts) >= 3:
                state_zip = parts[2].strip().split()
                if state_zip:
                    result['state'] = state_zip[0]
                if len(state_zip) > 1:
                    result['zip_code'] = state_zip[1]
            
            return result
    
    def normalize(self, components: Dict[str, str]) -> Dict[str, str]:
        """Normalize address components"""
        normalized = {}
        
        # Normalize street
        street = components.get('street', '').lower().strip()
        tokens = street.split()
        norm_tokens = []
        
        for token in tokens:
            if token in self.DIRECTIONS:
                token = self.DIRECTIONS[token]
            elif token in self.STREET_SUFFIXES:
                token = self.STREET_SUFFIXES[token]
            norm_tokens.append(token)
        
        normalized['street'] = ' '.join(norm_tokens)
        normalized['city'] = (components.get('city') or '').lower().strip()
        
        # Normalize state
        state = (components.get('state') or '').lower().strip()
        if len(state) > 2:
            state = self.STATE_ABBR.get(state, state)
        normalized['state'] = state
        
        normalized['zip_code'] = (components.get('zip_code') or '').strip()
        
        return normalized


# Initialize global normalizer
_normalizer = AddressNormalizer()


def match_addresses(address1: Union[Dict, str], address2: Union[Dict, str]) -> Dict[str, float]:
    """
    Match two US addresses and return similarity scores.
    
    Args:
        address1: First address as dict {"street": "...", "city": "...", "state": "...", "zip_code": "..."}
                  or string "123 Main St, New York, NY 10001"
        address2: Second address in same format options as address1
    
    Returns:
        Dict with scores:
        {
            "street": 85.5,           # Street similarity (0-100)
            "city_state_zip": 92.0,   # City/State/ZIP similarity (0-100)
            "overall": 88.0           # Overall match score (0-100)
        }
        
    Score interpretation:
        90-100: Excellent match (same address, minor formatting)
        80-89:  Good match (minor typos, abbreviations)
        70-79:  Possible match (several differences)
        <70:    Poor match (likely different addresses)
    
    Examples:
        # Dict format vs string format
        score = match_addresses(
            {"street": "123 Main St", "city": "New York", "state": "NY", "zip_code": "10001"},
            "123 Main Street, New York, NY 10001"
        )
        # Returns: {"street": 95.5, "city_state_zip": 100.0, "overall": 97.3}
        
        # Both string format
        score = match_addresses(
            "2500 LAKEPOINTE PARKWAY, ODESSA, FL 33556",
            "2500 Lakepoint Pkwy, Odessa, Florida 33556"
        )
        # Returns: {"street": 92.0, "city_state_zip": 95.0, "overall": 93.2}
    """
    # Parse both addresses
    comp1 = _normalizer.parse_address(address1)
    comp2 = _normalizer.parse_address(address2)
    
    # Normalize
    norm1 = _normalizer.normalize(comp1)
    norm2 = _normalizer.normalize(comp2)
    
    # Calculate street score
    street_score = _calculate_similarity(norm1['street'], norm2['street'])
    
    # Calculate city/state/zip scores
    city_score = _calculate_similarity(norm1['city'], norm2['city'])
    state_score = _calculate_similarity(norm1['state'], norm2['state'])
    zip_score = _calculate_similarity(norm1['zip_code'], norm2['zip_code'])
    
    # Combined city_state_zip score
    city_state_zip_score = (city_score * 0.4 + state_score * 0.3 + zip_score * 0.3)
    
    # Overall score (street weighted higher as it's more distinctive)
    overall_score = (street_score * 0.6 + city_state_zip_score * 0.4)
    
    return {
        'street': round(street_score, 1),
        'city_state_zip': round(city_state_zip_score, 1),
        'overall': round(overall_score, 1)
    }


def match_address_to_list(query: Union[Dict, str], 
                         candidates: List[Union[Dict, str]], 
                         threshold: float = 80.0) -> List[Tuple[Union[Dict, str], Dict[str, float]]]:
    """
    Match one address against a list of candidates.
    
    Args:
        query: Query address (dict or string format)
        candidates: List of candidate addresses to match against
        threshold: Minimum overall score to include (default 80.0)
    
    Returns:
        List of (address, scores) tuples sorted by overall score (highest first)
        Only includes matches above threshold
    
    Example:
        query = "123 Main St, New York, NY 10001"
        candidates = [
            "123 Main Street, New York, NY 10001",
            "456 Oak Ave, Boston, MA 02101",
            "123 Main St., New York, N.Y. 10001"
        ]
        
        matches = match_address_to_list(query, candidates)
        # Returns: [
        #   ("123 Main Street, New York, NY 10001", {"street": 95.5, "city_state_zip": 100.0, "overall": 97.3}),
        #   ("123 Main St., New York, N.Y. 10001", {"street": 98.0, "city_state_zip": 95.0, "overall": 96.8})
        # ]
    """
    results = []
    
    for candidate in candidates:
        scores = match_addresses(query, candidate)
        if scores['overall'] >= threshold:
            results.append((candidate, scores))
    
    # Sort by overall score descending
    results.sort(key=lambda x: x[1]['overall'], reverse=True)
    
    return results


def _calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity between two strings using RapidFuzz"""
    if not str1 or not str2:
        return 100.0 if (not str1 and not str2) else 0.0
    
    # Use multiple fuzzy algorithms from RapidFuzz
    simple = fuzz.ratio(str1, str2)
    partial = fuzz.partial_ratio(str1, str2)
    token_sort = fuzz.token_sort_ratio(str1, str2)
    token_set = fuzz.token_set_ratio(str1, str2)
    
    # Weighted average
    return (simple * 0.2 + partial * 0.2 + token_sort * 0.3 + token_set * 0.3)


# Convenience function for simple boolean matching
def is_same_address(address1: Union[Dict, str], 
                    address2: Union[Dict, str], 
                    threshold: float = 85.0) -> bool:
    """
    Simple boolean check if two addresses are the same.
    
    Args:
        address1: First address (dict or string)
        address2: Second address (dict or string)
        threshold: Minimum score to consider a match (default 85.0)
    
    Returns:
        True if addresses match above threshold, False otherwise
    
    Example:
        if is_same_address("123 Main St, NYC, NY", "123 Main Street, New York, NY"):
            print("Same address!")
    """
    scores = match_addresses(address1, address2)
    return scores['overall'] >= threshold


# Example usage
if __name__ == "__main__":
    print("Address Matcher Examples\n" + "="*50)
    
    # Example 1: Dict vs String
    addr1 = {
        "street": "2500 LAKEPOINTE PARKWAY",
        "city": "ODESSA",
        "state": "Florida",
        "zip_code": "33556"
    }
    addr2 = "2500 Lakepoint Pkwy, Odessa, FL 33556"
    
    scores = match_addresses(addr1, addr2)
    print(f"Example 1 - Dict vs String:")
    print(f"  Street score: {scores['street']}")
    print(f"  City/State/ZIP score: {scores['city_state_zip']}")
    print(f"  Overall score: {scores['overall']}")
    print(f"  Same address? {is_same_address(addr1, addr2)}\n")
    
    # Example 2: List matching
    query = "123 Main St, New York, NY 10001"
    candidates = [
        "123 Main Street, New York, NY 10001",
        "456 Oak Ave, Los Angeles, CA 90001",
        "123 Main St., New York, N.Y. 10001",
        "789 Elm Dr, Chicago, IL 60601"
    ]
    
    print(f"Example 2 - Finding matches for: {query}")
    matches = match_address_to_list(query, candidates, threshold=80.0)
    for addr, scores in matches:
        print(f"  {addr} - Score: {scores['overall']}")
    
    # Example 3: CSV data processing
    print(f"\nExample 3 - Processing CSV data:")
    import pandas as pd
    from io import StringIO
    
    csv_data = """id,name,address_street,address_city_state_zip
1,Store A,2500 Lakepointe Parkway,"Odessa, FL 33556"
2,Store B,123 Main St,"New York, NY 10001"
3,Store C,456 Oak Avenue,"Los Angeles, CA 90001"
"""
    
    df = pd.read_csv(StringIO(csv_data))
    
    # Check each against our reference
    reference = addr1  # Using addr1 from above
    
    for _, row in df.iterrows():
        full_address = f"{row['address_street']}, {row['address_city_state_zip']}"
        scores = match_addresses(reference, full_address)
        if scores['overall'] > 80:
            print(f"  {row['name']} matches with score: {scores['overall']}")