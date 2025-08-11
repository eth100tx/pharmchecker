#!/usr/bin/env python3
"""
PharmChecker Lazy Scoring Engine

Computes address match scores on-demand for specific dataset combinations.
Uses the scoring_plugin.py for address matching and integrates with the 
database schema to provide efficient batch scoring.

Key Features:
- Lazy computation: Only scores needed pharmacy/search pairs
- Batch processing with configurable batch sizes
- Comprehensive error handling and progress tracking
- Uses database functions to identify missing scores
- Atomic score updates with conflict resolution
"""

import json
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from .base import BaseImporter

# Import the scoring plugin
import sys
from pathlib import Path

# Add parent directory to path so we can import scoring_plugin
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from scoring_plugin import Address, match_addresses

logger = logging.getLogger(__name__)

class ScoringEngine(BaseImporter):
    """
    Lazy scoring engine that computes address match scores on-demand.
    
    The scoring engine:
    1. Uses database functions to find missing scores for dataset pairs
    2. Retrieves pharmacy and search result address data
    3. Uses scoring_plugin.py to compute match scores
    4. Batch inserts/updates scores in the database
    5. Provides progress tracking and error handling
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('ScoringEngine')
        self.scoring_version = "v1.0"  # For tracking algorithm versions
    
    def find_missing_scores(self, states_tag: str, pharmacies_tag: str, 
                           limit: int = 1000) -> List[Tuple[int, int]]:
        """
        Find pharmacy/result pairs that need scoring using database function.
        
        Args:
            states_tag: Tag for the states dataset
            pharmacies_tag: Tag for the pharmacies dataset  
            limit: Maximum number of pairs to return
            
        Returns:
            List of (pharmacy_id, result_id) tuples needing scores
        """
        with self.conn.cursor() as cur:
            # Get all comprehensive results for these datasets
            cur.execute("""
                SELECT pharmacy_id, result_id, score_overall
                FROM get_all_results_with_context(%s, %s, NULL)
                WHERE result_id IS NOT NULL
            """, (states_tag, pharmacies_tag))
            all_results = cur.fetchall()
            
        # Filter to only those without scores
        missing = [(row[0], row[1]) for row in all_results if row[2] is None]
        
        # Apply limit
        if limit and len(missing) > limit:
            missing = missing[:limit]
            
        self.logger.info(f"Found {len(missing)} pharmacy/result pairs needing scores")
        return missing
    
    def compute_scores(self, states_tag: str, pharmacies_tag: str, 
                       batch_size: int = 200, max_pairs: Optional[int] = None) -> Dict[str, Any]:
        """
        Compute missing scores for the given dataset combination.
        
        Args:
            states_tag: Tag for the states dataset
            pharmacies_tag: Tag for the pharmacies dataset
            batch_size: Number of scores to compute per batch
            max_pairs: Maximum pharmacy/search pairs to process (None for all)
            
        Returns:
            Dict with processing statistics
        """
        
        self.logger.info(f"Starting score computation for datasets: states='{states_tag}', pharmacies='{pharmacies_tag}'")
        
        # Get dataset IDs
        dataset_ids = self._get_dataset_ids(states_tag, pharmacies_tag)
        if not dataset_ids:
            return {'error': 'Dataset IDs not found', 'scores_computed': 0}
        
        states_id, pharmacies_id = dataset_ids
        
        # Find missing scores
        missing_limit = max_pairs if max_pairs else 10000  # Default reasonable limit
        missing = self.find_missing_scores(states_tag, pharmacies_tag, missing_limit)
        
        if not missing:
            self.logger.info("No missing scores found")
            return {'scores_computed': 0, 'batches_processed': 0, 'errors': 0}
        
        if max_pairs:
            missing = missing[:max_pairs]
        
        self.logger.info(f"Processing {len(missing)} pharmacy/result pairs in batches of {batch_size}")
        
        # Processing statistics
        stats = {
            'total_pairs': len(missing),
            'scores_computed': 0,
            'batches_processed': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
        # Process in batches
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            self.logger.info(f"Processing batch {batch_num}/{(len(missing) + batch_size - 1) // batch_size}")
            
            try:
                batch_scores = self._compute_batch_scores(batch, states_id, pharmacies_id)
                
                if batch_scores:
                    self._upsert_scores(batch_scores)
                    stats['scores_computed'] += len(batch_scores)
                    self.logger.info(f"Batch {batch_num}: computed {len(batch_scores)} scores")
                else:
                    self.logger.warning(f"Batch {batch_num}: no valid scores computed")
                
                stats['batches_processed'] += 1
                
            except Exception as e:
                self.logger.error(f"Failed to process batch {batch_num}: {e}")
                stats['errors'] += 1
                continue
        
        stats['end_time'] = datetime.now()
        stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()
        
        self.logger.info(f"Scoring complete: {stats['scores_computed']} scores computed in {stats['batches_processed']} batches ({stats['errors']} errors)")
        
        return stats
    
    def _get_dataset_ids(self, states_tag: str, pharmacies_tag: str) -> Optional[Tuple[int, int]]:
        """Get dataset IDs for the given tags"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    (SELECT id FROM datasets WHERE kind='states' AND tag=%s) as states_id,
                    (SELECT id FROM datasets WHERE kind='pharmacies' AND tag=%s) as pharmacies_id
            """, (states_tag, pharmacies_tag))
            
            result = cur.fetchone()
            if result and result[0] and result[1]:
                return (result[0], result[1])
            
        return None
    
    def _compute_batch_scores(self, batch: List[Tuple[int, int]], 
                             states_id: int, pharmacies_id: int) -> List[Tuple]:
        """
        Compute scores for a batch of pharmacy/result pairs.
        
        Args:
            batch: List of (pharmacy_id, result_id) tuples
            states_id: States dataset ID
            pharmacies_id: Pharmacies dataset ID
            
        Returns:
            List of score tuples ready for database insertion
        """
        batch_scores = []
        
        for pharmacy_id, result_id in batch:
            try:
                # Get pharmacy address
                pharm_addr = self._get_pharmacy_address(pharmacy_id)
                if not pharm_addr:
                    self.logger.warning(f"No pharmacy address found for pharmacy_id {pharmacy_id}")
                    continue
                
                # Get the specific result to score
                result = self._get_single_result(result_id)
                if not result:
                    self.logger.warning(f"No result found for result_id {result_id}")
                    continue
                
                # Create state address from the result
                state_addr = Address(
                    address=result['address'],
                    suite=None,  # Search results typically don't have suite info
                    city=result['city'],
                    state=result['state'],
                    zip=result['zip']
                )
                
                try:
                    street_score, csz_score, overall_score = match_addresses(state_addr, pharm_addr)
                    
                    # Create scoring metadata
                    scoring_meta = {
                        'algorithm': self.scoring_version,
                        'timestamp': datetime.now().isoformat(),
                        'pharmacy_id': pharmacy_id,
                        'result_id': result_id,
                        'search_name': result.get('search_name'),
                        'search_state': result.get('search_state')
                    }
                    
                    batch_scores.append((
                        states_id,
                        pharmacies_id,
                        pharmacy_id,
                        result_id,
                        round(overall_score, 2),   # Round to 2 decimal places
                        round(street_score, 2),
                        round(csz_score, 2),
                        json.dumps(scoring_meta)
                    ))
                    
                    self.logger.debug(f"Scored pharmacy {pharmacy_id} vs result {result_id}: {overall_score:.1f}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to score pharmacy {pharmacy_id} result {result_id}: {e}")
                    continue
                
            except Exception as e:
                self.logger.error(f"Failed to process pharmacy {pharmacy_id} result {result_id}: {e}")
                continue
        
        return batch_scores
    
    def _get_pharmacy_address(self, pharmacy_id: int) -> Optional[Address]:
        """Get pharmacy address for scoring"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT address, suite, city, state, zip 
                FROM pharmacies 
                WHERE id = %s
            """, (pharmacy_id,))
            
            row = cur.fetchone()
            if row:
                return Address(
                    address=row[0],
                    suite=row[1],
                    city=row[2],
                    state=row[3],
                    zip=row[4]
                )
            
        return None
    
    def _get_single_result(self, result_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific search result by ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, search_name, search_state, address, city, state, zip, 
                       license_number, license_status, result_status
                FROM search_results 
                WHERE id = %s
                AND result_status != 'no_results_found'
            """, (result_id,))
            
            row = cur.fetchone()
            if row:
                return {
                    'id': row[0],
                    'search_name': row[1],
                    'search_state': row[2],
                    'address': row[3],
                    'city': row[4],
                    'state': row[5],
                    'zip': row[6],
                    'license_number': row[7],
                    'license_status': row[8],
                    'result_status': row[9]
                }
            
            return None
    
    def _upsert_scores(self, scores: List[Tuple]):
        """
        Batch upsert scores to database with conflict resolution.
        
        Args:
            scores: List of score tuples for insertion
        """
        if not scores:
            return
        
        with self.conn.cursor() as cur:
            from psycopg2.extras import execute_values
            
            try:
                execute_values(
                    cur,
                    """
                    INSERT INTO match_scores 
                        (states_dataset_id, pharmacies_dataset_id, pharmacy_id, result_id,
                         score_overall, score_street, score_city_state_zip, scoring_meta)
                    VALUES %s
                    ON CONFLICT (states_dataset_id, pharmacies_dataset_id, pharmacy_id, result_id)
                    DO UPDATE SET
                        score_overall = EXCLUDED.score_overall,
                        score_street = EXCLUDED.score_street,
                        score_city_state_zip = EXCLUDED.score_city_state_zip,
                        scoring_meta = EXCLUDED.scoring_meta,
                        created_at = now()
                    """,
                    scores,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s)"
                )
                
                self.conn.commit()
                self.logger.debug(f"Upserted {len(scores)} scores to database")
                
            except Exception as e:
                self.logger.error(f"Failed to upsert scores: {e}")
                self.conn.rollback()
                raise
    
    def get_scoring_stats(self, states_tag: str, pharmacies_tag: str) -> Dict[str, Any]:
        """
        Get statistics about scoring completeness for dataset combination.
        
        Args:
            states_tag: Tag for the states dataset
            pharmacies_tag: Tag for the pharmacies dataset
            
        Returns:
            Dict with scoring statistics
        """
        with self.conn.cursor() as cur:
            # Get dataset IDs
            dataset_ids = self._get_dataset_ids(states_tag, pharmacies_tag)
            if not dataset_ids:
                return {'error': 'Dataset IDs not found'}
            
            states_id, pharmacies_id = dataset_ids
            
            # Count total possible scores needed using comprehensive results
            cur.execute("""
                SELECT COUNT(*) as total_needed
                FROM get_all_results_with_context(%s, %s, NULL)
                WHERE result_id IS NOT NULL AND score_overall IS NULL
            """, (states_tag, pharmacies_tag))
            total_needed = cur.fetchone()[0]
            
            # Count scores already computed
            cur.execute("""
                SELECT COUNT(*) as computed
                FROM match_scores ms
                WHERE ms.states_dataset_id = %s
                AND ms.pharmacies_dataset_id = %s
            """, (states_id, pharmacies_id))
            computed = cur.fetchone()[0]
            
            # Get score distribution
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN score_overall >= 85 THEN 1 END) as match_count,
                    COUNT(CASE WHEN score_overall >= 60 AND score_overall < 85 THEN 1 END) as weak_count,
                    COUNT(CASE WHEN score_overall < 60 THEN 1 END) as no_match_count,
                    AVG(score_overall) as avg_score,
                    MAX(score_overall) as max_score,
                    MIN(score_overall) as min_score
                FROM match_scores ms
                WHERE ms.states_dataset_id = %s
                AND ms.pharmacies_dataset_id = %s
            """, (states_id, pharmacies_id))
            
            dist_row = cur.fetchone()
            
            return {
                'datasets': {
                    'states_tag': states_tag,
                    'pharmacies_tag': pharmacies_tag,
                    'states_id': states_id,
                    'pharmacies_id': pharmacies_id
                },
                'completeness': {
                    'total_needed': total_needed,
                    'computed': computed,
                    'remaining': total_needed,
                    'percent_complete': (computed / (computed + total_needed) * 100) if (computed + total_needed) > 0 else 100
                },
                'score_distribution': {
                    'match_count': dist_row[0] or 0,
                    'weak_count': dist_row[1] or 0,
                    'no_match_count': dist_row[2] or 0,
                    'avg_score': round(float(dist_row[3]), 2) if dist_row[3] else None,
                    'max_score': round(float(dist_row[4]), 2) if dist_row[4] else None,
                    'min_score': round(float(dist_row[5]), 2) if dist_row[5] else None
                }
            }

# Convenience function for command-line usage
def compute_scores_for_tags(states_tag: str, pharmacies_tag: str, 
                           batch_size: int = 200, max_pairs: Optional[int] = None,
                           db_config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Standalone function to compute scores for dataset tags.
    
    Args:
        states_tag: Tag for the states dataset
        pharmacies_tag: Tag for the pharmacies dataset
        batch_size: Batch size for processing
        max_pairs: Maximum pairs to process (None for all)
        db_config: Database configuration dict (uses config.py if None)
        
    Returns:
        Processing statistics
    """
    if db_config is None:
        try:
            from config import get_db_config
            db_config = get_db_config()
        except ImportError:
            raise ValueError("No database configuration provided and config.py not available")
    
    with ScoringEngine(db_config) as engine:
        return engine.compute_scores(states_tag, pharmacies_tag, batch_size, max_pairs)

# Example usage and testing
if __name__ == "__main__":
    import os
    from pathlib import Path
    
    # Add config to path for testing
    config_path = Path(__file__).parent.parent
    if str(config_path) not in sys.path:
        sys.path.insert(0, str(config_path))
    
    try:
        from config import get_db_config
        
        # Test with sample data (modify tags as needed)
        states_tag = "states_baseline"
        pharmacies_tag = "pharmacies_sample"
        
        print(f"PharmChecker Scoring Engine Test")
        print(f"States: {states_tag}, Pharmacies: {pharmacies_tag}")
        print("="*50)
        
        with ScoringEngine(get_db_config()) as engine:
            # Get current stats
            stats = engine.get_scoring_stats(states_tag, pharmacies_tag)
            print(f"Current Statistics:")
            print(f"  Scores needed: {stats.get('completeness', {}).get('total_needed', 'N/A')}")
            print(f"  Scores computed: {stats.get('completeness', {}).get('computed', 'N/A')}")
            print(f"  Completion: {stats.get('completeness', {}).get('percent_complete', 0):.1f}%")
            
            if stats.get('completeness', {}).get('total_needed', 0) > 0:
                print(f"\nComputing missing scores...")
                result = engine.compute_scores(states_tag, pharmacies_tag, batch_size=50, max_pairs=10)
                print(f"Result: {result}")
        
    except ImportError as e:
        print(f"Could not import config: {e}")
        print("Run this from the project directory with proper database configuration.")
    except Exception as e:
        print(f"Error: {e}")