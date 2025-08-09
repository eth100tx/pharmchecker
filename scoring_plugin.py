#!/usr/bin/env python3
"""
PharmChecker Address Scoring Plugin

Adapted from the address_matcher.py implementation to work with PharmChecker's
database schema and provide the expected API for lazy scoring.

Key adaptations:
- Works with individual database fields (address, suite, city, state, zip)
- Returns scores on 0-100 scale for database storage
- Matches the API expected by the lazy scoring engine
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple
from rapidfuzz import fuzz
import logging

logger = logging.getLogger(__name__)

@dataclass
class Address:
    """Address data structure matching PharmChecker database fields"""
    address: Optional[str] = None
    suite: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

class AddressNormalizer:
    """Address normalization for consistent comparison"""
    
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
    
    def normalize(self, text: Optional[str]) -> str:
        """Normalize address component for comparison"""
        if not text:
            return ""
        
        # Convert to lowercase and strip whitespace
        text = text.lower().strip()
        
        # Apply abbreviation replacements
        tokens = text.split()
        normalized_tokens = []
        
        for token in tokens:
            # Remove punctuation from token for matching
            clean_token = re.sub(r'[^\w]', '', token)
            
            # Check for direction abbreviations
            if clean_token in self.DIRECTIONS:
                normalized_tokens.append(self.DIRECTIONS[clean_token])
            # Check for street suffix abbreviations
            elif clean_token in self.STREET_SUFFIXES:
                normalized_tokens.append(self.STREET_SUFFIXES[clean_token])
            else:
                # Keep original token but clean punctuation
                normalized_tokens.append(clean_token)
        
        # Join back and do final cleanup
        normalized = ' '.join(normalized_tokens)
        
        # Remove any remaining punctuation and extra spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def normalize_state(self, state: Optional[str]) -> str:
        """Normalize state name or abbreviation"""
        if not state:
            return ""
        
        state = state.lower().strip()
        
        # If it's a full state name, convert to abbreviation
        if len(state) > 2:
            return self.STATE_ABBR.get(state, state)
        
        return state
    
    def normalize_zip(self, zip_code: Optional[str]) -> str:
        """Normalize ZIP code (first 5 digits only)"""
        if not zip_code:
            return ""
        
        # Extract first 5 digits
        digits = re.findall(r'\d', str(zip_code))
        return ''.join(digits[:5])

# Global normalizer instance
_normalizer = AddressNormalizer()

def _calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity between two strings using RapidFuzz"""
    if not str1 or not str2:
        return 1.0 if (not str1 and not str2) else 0.0
    
    # Use multiple fuzzy algorithms from RapidFuzz
    simple = fuzz.ratio(str1, str2)
    partial = fuzz.partial_ratio(str1, str2)
    token_sort = fuzz.token_sort_ratio(str1, str2)
    token_set = fuzz.token_set_ratio(str1, str2)
    
    # Weighted average (convert to 0-1 scale)
    score = (simple * 0.2 + partial * 0.2 + token_sort * 0.3 + token_set * 0.3) / 100.0
    return score

def match_addresses(state_addr: Address, pharmacy_addr: Address) -> Tuple[float, float, float]:
    """
    Compare addresses and return match scores.
    
    This is the main API function expected by the lazy scoring engine.
    
    Args:
        state_addr: Address from state board search results
        pharmacy_addr: Address from pharmacy database
    
    Returns:
        Tuple of (street_score, city_state_zip_score, overall_score)
        Each score is between 0.0 and 100.0 (ready for database storage)
    
    Algorithm:
        - Street Score (70% weight): Fuzzy matching of address with abbreviation normalization
        - City/State/ZIP Score (30% weight): Exact matching of location components  
        - Overall Score: Weighted combination, scaled 0-100
    """
    
    # Normalize all components
    state_street = _normalizer.normalize(state_addr.address)
    pharm_street = _normalizer.normalize(pharmacy_addr.address)
    
    state_suite = _normalizer.normalize(state_addr.suite)
    pharm_suite = _normalizer.normalize(pharmacy_addr.suite)
    
    state_city = _normalizer.normalize(state_addr.city)
    pharm_city = _normalizer.normalize(pharmacy_addr.city)
    
    state_state = _normalizer.normalize_state(state_addr.state)
    pharm_state = _normalizer.normalize_state(pharmacy_addr.state)
    
    state_zip = _normalizer.normalize_zip(state_addr.zip)
    pharm_zip = _normalizer.normalize_zip(pharmacy_addr.zip)
    
    # Calculate street score
    street_score = 0.0
    if state_street and pharm_street:
        # Base similarity using fuzzy matching
        street_similarity = _calculate_similarity(state_street, pharm_street)
        
        # Bonus for exact match
        if state_street == pharm_street:
            street_score = 1.0
        else:
            street_score = street_similarity * 0.95  # Slight penalty for non-exact
        
        # Suite matching consideration
        if state_suite and pharm_suite:
            suite_similarity = _calculate_similarity(state_suite, pharm_suite)
            if suite_similarity >= 0.8:  # Good suite match
                street_score = min(1.0, street_score + 0.05)
            else:  # Poor suite match
                street_score *= 0.9
        elif state_suite or pharm_suite:
            # One has suite, other doesn't - small penalty
            street_score *= 0.95
    
    # Calculate city/state/zip score
    csz_score = 0.0
    csz_components = 0
    csz_total = 0.0
    
    # City component (40% of CSZ score)
    if state_city and pharm_city:
        csz_components += 1
        city_sim = _calculate_similarity(state_city, pharm_city)
        csz_total += city_sim * 0.4
    
    # State component (30% of CSZ score)
    if state_state and pharm_state:
        csz_components += 1
        if state_state == pharm_state:
            csz_total += 0.3  # Exact match required for states
        # else: no points for state mismatch
    
    # ZIP component (30% of CSZ score)
    if state_zip and pharm_zip:
        csz_components += 1
        if state_zip == pharm_zip:
            csz_total += 0.3  # Exact match required for ZIP
        # else: no points for ZIP mismatch
    
    # Calculate final CSZ score
    if csz_components > 0:
        csz_score = csz_total
    
    # Calculate overall score
    # Weight street address more heavily (70%) than city/state/zip (30%)
    if state_street and pharm_street:
        overall_score = (0.7 * street_score) + (0.3 * csz_score)
    else:
        # No street address to compare, rely on city/state/zip only
        overall_score = csz_score * 0.6  # Max 60% without street comparison
    
    # Convert to 0-100 scale for database storage
    street_score_scaled = street_score * 100.0
    csz_score_scaled = csz_score * 100.0
    overall_score_scaled = overall_score * 100.0
    
    logger.debug(f"Address match: street={street_score_scaled:.1f}, csz={csz_score_scaled:.1f}, overall={overall_score_scaled:.1f}")
    
    return (street_score_scaled, csz_score_scaled, overall_score_scaled)

# Convenience function for testing and debugging
def match_addresses_debug(state_addr: Address, pharmacy_addr: Address) -> dict:
    """
    Same as match_addresses but returns detailed debugging information.
    
    Returns:
        Dict with scores and normalized components for debugging
    """
    # Get normalized components
    state_street = _normalizer.normalize(state_addr.address)
    pharm_street = _normalizer.normalize(pharmacy_addr.address)
    
    state_city = _normalizer.normalize(state_addr.city)
    pharm_city = _normalizer.normalize(pharmacy_addr.city)
    
    state_state = _normalizer.normalize_state(state_addr.state)
    pharm_state = _normalizer.normalize_state(pharmacy_addr.state)
    
    state_zip = _normalizer.normalize_zip(state_addr.zip)
    pharm_zip = _normalizer.normalize_zip(pharmacy_addr.zip)
    
    # Get scores
    street_score, csz_score, overall_score = match_addresses(state_addr, pharmacy_addr)
    
    return {
        'scores': {
            'street': street_score,
            'city_state_zip': csz_score,
            'overall': overall_score
        },
        'normalized': {
            'state_street': state_street,
            'pharmacy_street': pharm_street,
            'state_city': state_city,
            'pharmacy_city': pharm_city,
            'state_state': state_state,
            'pharmacy_state': pharm_state,
            'state_zip': state_zip,
            'pharmacy_zip': pharm_zip
        },
        'raw': {
            'state_address': {
                'address': state_addr.address,
                'suite': state_addr.suite,
                'city': state_addr.city,
                'state': state_addr.state,
                'zip': state_addr.zip
            },
            'pharmacy_address': {
                'address': pharmacy_addr.address,
                'suite': pharmacy_addr.suite,
                'city': pharmacy_addr.city,
                'state': pharmacy_addr.state,
                'zip': pharmacy_addr.zip
            }
        }
    }

# Example usage and testing
if __name__ == "__main__":
    import json
    
    print("PharmChecker Address Scoring Plugin Test\n" + "="*50)
    
    # Example 1: Good match
    state_addr = Address(
        address="2500 LAKEPOINTE PARKWAY",
        suite=None,
        city="ODESSA",
        state="FL",
        zip="33556"
    )
    
    pharmacy_addr = Address(
        address="2500 Lakepoint Pkwy",
        suite="Suite 100",
        city="Odessa",
        state="Florida",
        zip="33556-1234"
    )
    
    scores = match_addresses(state_addr, pharmacy_addr)
    debug_info = match_addresses_debug(state_addr, pharmacy_addr)
    
    print("Example 1 - Good Match:")
    print(f"  Street Score: {scores[0]:.1f}")
    print(f"  City/State/ZIP Score: {scores[1]:.1f}")
    print(f"  Overall Score: {scores[2]:.1f}")
    print(f"  Normalized Street: '{debug_info['normalized']['state_street']}' vs '{debug_info['normalized']['pharmacy_street']}'")
    print(f"  Status: {'MATCH' if scores[2] >= 85 else 'WEAK' if scores[2] >= 60 else 'NO MATCH'}")
    print()
    
    # Example 2: Poor match
    state_addr2 = Address(
        address="123 MAIN STREET",
        city="TAMPA",
        state="FL", 
        zip="33602"
    )
    
    scores2 = match_addresses(state_addr2, pharmacy_addr)
    
    print("Example 2 - Poor Match:")
    print(f"  Street Score: {scores2[0]:.1f}")
    print(f"  City/State/ZIP Score: {scores2[1]:.1f}")
    print(f"  Overall Score: {scores2[2]:.1f}")
    print(f"  Status: {'MATCH' if scores2[2] >= 85 else 'WEAK' if scores2[2] >= 60 else 'NO MATCH'}")
    print()
    
    # Example 3: No street address (common in some search results)
    state_addr3 = Address(
        address=None,
        city="ODESSA",
        state="FL",
        zip="33556"
    )
    
    scores3 = match_addresses(state_addr3, pharmacy_addr)
    
    print("Example 3 - No Street Address:")
    print(f"  Street Score: {scores3[0]:.1f}")
    print(f"  City/State/ZIP Score: {scores3[1]:.1f}")
    print(f"  Overall Score: {scores3[2]:.1f}")
    print(f"  Status: {'MATCH' if scores3[2] >= 85 else 'WEAK' if scores3[2] >= 60 else 'NO MATCH'}")
    print()
    
    print("Debug output for Example 1:")
    print(json.dumps(debug_info, indent=2, default=str))