#!/usr/bin/env python3
"""
Simple scoring test script to verify the scoring system works correctly
with the loaded pharmacy and state search data.
"""

from config import get_db_config
from scoring_plugin import Address, match_addresses, match_addresses_debug
import psycopg2
from psycopg2.extras import RealDictCursor
import json

def get_sample_data():
    """Get sample pharmacy and search result data for testing"""
    conn = psycopg2.connect(**get_db_config())
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get pharmacies
        cur.execute("""
            SELECT id, name, address, suite, city, state, zip, state_licenses
            FROM pharmacies 
            ORDER BY id
            LIMIT 10
        """)
        pharmacies = cur.fetchall()
        
        # Get search results
        cur.execute("""
            SELECT id, search_name, search_state, address, city, state, zip,
                   license_number, license_status, result_status
            FROM search_results
            WHERE result_status != 'no_results_found'
            ORDER BY search_name, search_state
            LIMIT 20
        """)
        results = cur.fetchall()
    
    conn.close()
    return pharmacies, results

def test_scoring():
    """Test scoring with real data"""
    print("PharmChecker Scoring Test")
    print("=" * 50)
    
    # Get sample data
    pharmacies, results = get_sample_data()
    
    print(f"Found {len(pharmacies)} pharmacies and {len(results)} search results")
    print()
    
    # Test specific combinations
    test_cases = []
    
    # Find some good test cases by matching names
    for pharm in pharmacies:
        pharm_name = pharm['name'].lower()
        state_licenses = pharm['state_licenses'] if pharm['state_licenses'] else []
        
        for result in results:
            result_name = result['search_name'].lower()
            result_state = result['search_state']
            
            # If the pharmacy name is similar to search name and state matches
            if (pharm_name in result_name or result_name in pharm_name) and result_state in state_licenses:
                test_cases.append((pharm, result))
                if len(test_cases) >= 5:  # Limit to 5 good test cases
                    break
        if len(test_cases) >= 5:
            break
    
    # Add a few random cases too
    if len(pharmacies) > 0 and len(results) > 0:
        test_cases.append((pharmacies[0], results[0]))  # Random case
        if len(results) > 5:
            test_cases.append((pharmacies[-1], results[5]))  # Another random case
    
    print(f"Testing {len(test_cases)} pharmacy/result combinations:")
    print()
    
    for i, (pharm, result) in enumerate(test_cases, 1):
        print(f"Test Case {i}")
        print("-" * 20)
        
        # Create Address objects
        pharmacy_addr = Address(
            address=pharm['address'],
            suite=pharm['suite'], 
            city=pharm['city'],
            state=pharm['state'],
            zip=pharm['zip']
        )
        
        state_addr = Address(
            address=result['address'],
            suite=None,
            city=result['city'],
            state=result['state'], 
            zip=result['zip']
        )
        
        # Get detailed debug info
        debug_info = match_addresses_debug(state_addr, pharmacy_addr)
        scores = debug_info['scores']
        
        # Print comparison
        print(f"Pharmacy: {pharm['name']} ({pharm['state']})")
        print(f"  Address: {pharm['address']}")
        print(f"  City/State/ZIP: {pharm['city']}, {pharm['state']} {pharm['zip']}")
        print()
        
        print(f"Search Result: {result['search_name']} ({result['search_state']})")
        print(f"  Address: {result['address'] or 'N/A'}")
        print(f"  City/State/ZIP: {result['city'] or 'N/A'}, {result['state'] or 'N/A'} {result['zip'] or 'N/A'}")
        print(f"  License: {result['license_number']} ({result['license_status']})")
        print()
        
        # Normalized for comparison
        norm = debug_info['normalized']
        print(f"Normalized Comparison:")
        print(f"  Street: '{norm['pharmacy_street']}' vs '{norm['state_street']}'")
        print(f"  City: '{norm['pharmacy_city']}' vs '{norm['state_city']}'")
        print(f"  State: '{norm['pharmacy_state']}' vs '{norm['state_state']}'")
        print(f"  ZIP: '{norm['pharmacy_zip']}' vs '{norm['state_zip']}'")
        print()
        
        # Scores
        print(f"Scores:")
        print(f"  Street Score: {scores['street']:.1f}")
        print(f"  City/State/ZIP Score: {scores['city_state_zip']:.1f}")
        print(f"  Overall Score: {scores['overall']:.1f}")
        
        # Status bucket
        if scores['overall'] >= 85:
            status = "MATCH ✅"
        elif scores['overall'] >= 60:
            status = "WEAK MATCH ⚠️"
        else:
            status = "NO MATCH ❌"
        
        print(f"  Status: {status}")
        print()
        print("=" * 50)
        print()

def summary_report():
    """Generate a summary report of all possible scoring combinations"""
    print("Scoring Summary Report")
    print("=" * 50)
    
    pharmacies, results = get_sample_data()
    
    # Score all combinations
    all_scores = []
    
    for pharm in pharmacies:
        pharm_name = pharm['name']
        state_licenses = pharm['state_licenses'] if pharm['state_licenses'] else []
        
        pharmacy_addr = Address(
            address=pharm['address'],
            suite=pharm['suite'],
            city=pharm['city'],
            state=pharm['state'],
            zip=pharm['zip']
        )
        
        for result in results:
            # Only score if the search state is in pharmacy's licensed states
            if result['search_state'] in state_licenses:
                state_addr = Address(
                    address=result['address'],
                    suite=None,
                    city=result['city'],
                    state=result['state'],
                    zip=result['zip']
                )
                
                street_score, csz_score, overall_score = match_addresses(state_addr, pharmacy_addr)
                
                all_scores.append({
                    'pharmacy': pharm_name,
                    'search': result['search_name'],
                    'state': result['search_state'],
                    'license': result['license_number'],
                    'street_score': street_score,
                    'csz_score': csz_score,
                    'overall_score': overall_score
                })
    
    # Sort by overall score descending
    all_scores.sort(key=lambda x: x['overall_score'], reverse=True)
    
    print(f"Scored {len(all_scores)} valid pharmacy/result combinations")
    print()
    
    # Statistics
    scores_list = [s['overall_score'] for s in all_scores]
    if scores_list:
        avg_score = sum(scores_list) / len(scores_list)
        max_score = max(scores_list)
        min_score = min(scores_list)
        
        matches = len([s for s in scores_list if s >= 85])
        weak_matches = len([s for s in scores_list if 60 <= s < 85])
        no_matches = len([s for s in scores_list if s < 60])
        
        print(f"Score Statistics:")
        print(f"  Average: {avg_score:.1f}")
        print(f"  Range: {min_score:.1f} - {max_score:.1f}")
        print(f"  Matches (≥85): {matches}")
        print(f"  Weak Matches (60-84): {weak_matches}")
        print(f"  No Matches (<60): {no_matches}")
        print()
    
    # Top 10 matches
    print("Top 10 Matches:")
    print("-" * 30)
    for i, score in enumerate(all_scores[:10], 1):
        status = "✅" if score['overall_score'] >= 85 else "⚠️" if score['overall_score'] >= 60 else "❌"
        print(f"{i:2}. {status} {score['pharmacy']} → {score['search']} ({score['state']}) = {score['overall_score']:.1f}")
        if score['license']:
            print(f"     License: {score['license']}")
    
    print()
    
    # Bottom 5 matches (lowest scores)
    if len(all_scores) > 5:
        print("Lowest 5 Scores:")
        print("-" * 20)
        for i, score in enumerate(all_scores[-5:], 1):
            print(f"{i}. ❌ {score['pharmacy']} → {score['search']} ({score['state']}) = {score['overall_score']:.1f}")

if __name__ == "__main__":
    try:
        test_scoring()
        print()
        summary_report()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()