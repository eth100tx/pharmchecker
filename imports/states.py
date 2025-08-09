"""
State search results importer for PharmChecker
Imports state board search results from JSON files with optional screenshot handling
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from slugify import slugify
from .base import BaseImporter

class StateImporter(BaseImporter):
    """Importer for state board search results"""
    
    def import_json(self, filepath: str, tag: str, screenshot_dir: Optional[str] = None,
                   created_by: str = None, description: str = None) -> bool:
        """
        Import state search results from JSON file
        
        Expected JSON format:
        {
            "searches": [
                {
                    "name": "Empower Pharmacy",  # Must match pharmacies.name exactly
                    "state": "TX",
                    "timestamp": "2024-01-15T10:30:00",  # Optional
                    "meta": {  # Optional metadata
                        "search_url": "https://...",
                        "user_agent": "...",
                        "any_other_info": "..."
                    },
                    "results": [
                        {
                            "license_number": "12345",
                            "license_status": "Active",
                            "license_name": "Empower TX LLC",  # Can vary from pharmacy name
                            "address": "123 Main St",
                            "city": "Houston",
                            "state": "TX", 
                            "zip": "77001",
                            "issue_date": "2020-01-01",  # YYYY-MM-DD format
                            "expiration_date": "2025-01-01",
                            "result_status": "active",
                            # Any additional fields stored in raw JSONB
                        }
                    ],
                    "screenshot": "empower_tx_20240115.png"  # Optional, filename in screenshot_dir
                }
            ]
        }
        
        Args:
            filepath: Path to JSON file
            tag: Dataset tag/version 
            screenshot_dir: Optional directory containing screenshot files
            created_by: Who is importing this data
            description: Optional description
            
        Returns:
            True if successful, False otherwise
        """
        filepath = Path(filepath)
        if not filepath.exists():
            self.logger.error(f"File not found: {filepath}")
            return False
        
        try:
            # Read JSON
            self.logger.info(f"Reading JSON file: {filepath}")
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'searches' not in data:
                self.logger.error("JSON missing 'searches' array")
                return False
            
            searches = data['searches']
            if not searches:
                self.logger.error("No searches found in JSON")
                return False
            
            # Create dataset
            if not description:
                description = f"State search results from {filepath.name}"
            
            dataset_id = self.create_dataset('states', tag, description, created_by)
            
            # Prepare screenshot directory
            screenshot_path = None
            if screenshot_dir:
                screenshot_path = Path(screenshot_dir)
                if not screenshot_path.exists():
                    self.logger.warning(f"Screenshot directory not found: {screenshot_path}")
                    screenshot_path = None
            
            # Process searches
            total_searches = 0
            total_results = 0
            search_errors = []
            
            for search_idx, search_data in enumerate(searches):
                try:
                    search_id = self._import_single_search(
                        dataset_id, search_data, screenshot_path, tag
                    )
                    
                    if search_id:
                        total_searches += 1
                        # Count results for this search
                        result_count = len(search_data.get('results', []))
                        total_results += result_count
                        
                        self.logger.info(
                            f"Search {search_idx + 1}: {search_data.get('name', 'Unknown')} "
                            f"in {search_data.get('state', 'Unknown')} -> "
                            f"{result_count} results"
                        )
                    else:
                        search_errors.append(f"Search {search_idx + 1}: Failed to import")
                        
                except Exception as e:
                    error_msg = f"Search {search_idx + 1}: {str(e)}"
                    search_errors.append(error_msg)
                    self.logger.error(error_msg)
                    continue
            
            if total_searches == 0:
                self.logger.error("No searches were successfully imported")
                self.cleanup_failed_dataset(dataset_id)
                return False
            
            # Report results
            if search_errors:
                self.logger.warning(f"{len(search_errors)} search import errors:")
                for error in search_errors[:5]:  # Show first 5 errors
                    self.logger.warning(f"  {error}")
                if len(search_errors) > 5:
                    self.logger.warning(f"  ... and {len(search_errors) - 5} more")
            
            self.logger.info(
                f"Successfully imported {total_searches} searches with {total_results} "
                f"total results using tag '{tag}'"
            )
            
            # Print dataset statistics
            stats = self.get_dataset_stats(dataset_id)
            self.logger.info(f"Dataset statistics: {stats}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Import failed: {str(e)}")
            return False
    
    def _import_single_search(self, dataset_id: int, search_data: Dict[str, Any], 
                            screenshot_path: Optional[Path], tag: str) -> Optional[int]:
        """
        Import a single search with its results
        
        Args:
            dataset_id: Dataset ID
            search_data: Search data dictionary
            screenshot_path: Path to screenshot directory
            tag: Dataset tag for organizing screenshots
            
        Returns:
            Search ID if successful, None otherwise
        """
        # Validate required fields
        if 'name' not in search_data or 'state' not in search_data:
            raise ValueError("Search missing required 'name' or 'state' field")
        
        name = search_data['name'].strip()
        state = search_data['state'].strip().upper()
        
        if len(state) != 2:
            raise ValueError(f"Invalid state code: {state}")
        
        # Parse timestamp
        timestamp = None
        if 'timestamp' in search_data:
            try:
                timestamp = datetime.fromisoformat(search_data['timestamp'].replace('Z', '+00:00'))
            except ValueError:
                self.logger.warning(f"Invalid timestamp format: {search_data['timestamp']}")
        
        # Get metadata
        meta = search_data.get('meta', {})
        
        # Insert search record
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO searches (dataset_id, search_name, search_state, search_ts, meta)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                dataset_id,
                name,
                state,
                timestamp,
                json.dumps(meta)
            ))
            search_id = cur.fetchone()[0]
            self.conn.commit()
        
        # Import results for this search
        results = search_data.get('results', [])
        if results:
            self._import_search_results(search_id, results)
        
        # Handle screenshot if present
        if screenshot_path and 'screenshot' in search_data:
            self._store_screenshot_metadata(
                dataset_id, search_id, search_data, screenshot_path, tag
            )
        
        return search_id
    
    def _import_search_results(self, search_id: int, results: List[Dict[str, Any]]) -> int:
        """
        Import search results for a search
        
        Args:
            search_id: Search ID
            results: List of result dictionaries
            
        Returns:
            Number of results imported
        """
        if not results:
            return 0
        
        results_data = []
        
        for result_idx, result in enumerate(results):
            try:
                # Parse dates
                issue_date = None
                exp_date = None
                
                if 'issue_date' in result and result['issue_date']:
                    try:
                        issue_date = datetime.strptime(result['issue_date'], '%Y-%m-%d').date()
                    except ValueError:
                        self.logger.warning(
                            f"Result {result_idx}: Invalid issue_date format: {result['issue_date']}"
                        )
                
                if 'expiration_date' in result and result['expiration_date']:
                    try:
                        exp_date = datetime.strptime(result['expiration_date'], '%Y-%m-%d').date()
                    except ValueError:
                        self.logger.warning(
                            f"Result {result_idx}: Invalid expiration_date format: {result['expiration_date']}"
                        )
                
                # Build result data
                result_data = (
                    search_id,
                    result.get('license_number'),
                    result.get('license_status'),
                    result.get('license_name'),
                    result.get('address'),
                    result.get('city'),
                    result.get('state'),
                    result.get('zip'),
                    issue_date,
                    exp_date,
                    result.get('result_status'),
                    json.dumps(result)  # Store complete result as raw data
                )
                
                results_data.append(result_data)
                
            except Exception as e:
                self.logger.warning(f"Result {result_idx} skipped: {str(e)}")
                continue
        
        if not results_data:
            return 0
        
        # Batch insert results
        columns = [
            'search_id', 'license_number', 'license_status', 'license_name',
            'address', 'city', 'state', 'zip', 'issue_date', 'expiration_date',
            'result_status', 'raw'
        ]
        
        return self.batch_insert('search_results', columns, results_data)
    
    def _store_screenshot_metadata(self, dataset_id: int, search_id: int, 
                                 search_data: Dict[str, Any], screenshot_path: Path,
                                 tag: str):
        """
        Store screenshot metadata in the images table
        
        Args:
            dataset_id: Dataset ID
            search_id: Search ID
            search_data: Search data containing screenshot info
            screenshot_path: Directory containing screenshots
            tag: Dataset tag for organizing paths
        """
        try:
            screenshot_filename = search_data['screenshot']
            screenshot_file = screenshot_path / screenshot_filename
            
            # Check if file exists
            if not screenshot_file.exists():
                self.logger.warning(f"Screenshot file not found: {screenshot_file}")
                return
            
            # Generate organized path
            search_name_slug = slugify(search_data['name'])
            timestamp = search_data.get('timestamp', datetime.now().isoformat())
            
            # Clean timestamp for filename
            timestamp_clean = timestamp.replace(':', '-').replace('T', '_').split('.')[0]
            organized_path = f"{tag}/{search_data['state']}/{search_name_slug}.{timestamp_clean}"
            
            # Get file size
            file_size = screenshot_file.stat().st_size
            
            # Insert metadata
            self.execute_statement("""
                INSERT INTO images (dataset_id, state, search_id, search_name, 
                                   organized_path, storage_type, file_size)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dataset_id, organized_path) DO UPDATE SET
                    search_id = EXCLUDED.search_id,
                    file_size = EXCLUDED.file_size
            """, (
                dataset_id,
                search_data['state'],
                search_id,
                search_data['name'],
                organized_path,
                'local',  # TODO: Support 'supabase' storage type
                file_size
            ))
            
            self.logger.info(f"Screenshot metadata stored: {organized_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to store screenshot metadata: {str(e)}")
    
    def validate_json_format(self, filepath: str) -> Dict[str, Any]:
        """
        Validate JSON format without importing
        
        Args:
            filepath: Path to JSON file
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                results['errors'].append(f"File not found: {filepath}")
                return results
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check top-level structure
            if 'searches' not in data:
                results['errors'].append("JSON missing 'searches' array")
                return results
            
            searches = data['searches']
            if not isinstance(searches, list):
                results['errors'].append("'searches' must be an array")
                return results
            
            # Analyze searches
            results['stats']['total_searches'] = len(searches)
            
            valid_searches = 0
            total_results = 0
            missing_names = 0
            missing_states = 0
            invalid_states = 0
            
            for idx, search in enumerate(searches):
                if not isinstance(search, dict):
                    results['warnings'].append(f"Search {idx}: Not an object")
                    continue
                
                # Check required fields
                if 'name' not in search or not search['name']:
                    missing_names += 1
                    continue
                
                if 'state' not in search or not search['state']:
                    missing_states += 1
                    continue
                
                state = str(search['state']).strip().upper()
                if len(state) != 2:
                    invalid_states += 1
                    results['warnings'].append(f"Search {idx}: Invalid state code '{state}'")
                    continue
                
                valid_searches += 1
                
                # Count results
                if 'results' in search and isinstance(search['results'], list):
                    total_results += len(search['results'])
            
            results['stats']['valid_searches'] = valid_searches
            results['stats']['total_results'] = total_results
            results['stats']['missing_names'] = missing_names
            results['stats']['missing_states'] = missing_states
            results['stats']['invalid_states'] = invalid_states
            
            if missing_names > 0:
                results['warnings'].append(f"{missing_names} searches missing 'name' field")
            if missing_states > 0:
                results['warnings'].append(f"{missing_states} searches missing 'state' field")
            if invalid_states > 0:
                results['warnings'].append(f"{invalid_states} searches have invalid state codes")
            
            results['valid'] = len(results['errors']) == 0 and valid_searches > 0
            
        except json.JSONDecodeError as e:
            results['errors'].append(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            results['errors'].append(f"Validation error: {str(e)}")
        
        return results
    
    def import_directory(self, directory_path: str, tag: str = None, 
                        created_by: str = None, description: str = None) -> bool:
        """
        Import state search results from directory structure
        
        Expected structure:
        directory/
          FL/
            Pharmacy_01_parse.json
            Pharmacy_02_parse.json
            Pharmacy_no_results_parse.json
          PA/
            Pharmacy_01_parse.json
            ...
        
        Each JSON contains:
        {
          "metadata": {
            "pharmacy_name": "Belmar",
            "search_timestamp": "2025-08-03T14:03:10.115999",
            "state": "FL",
            ...
          },
          "search_result": {
            "licenses": [...],
            "result_status": "found|no_results_found",
            "search_query": "Belmar"
          }
        }
        
        Args:
            directory_path: Path to directory containing state subdirectories
            tag: Dataset tag (defaults to directory name)
            created_by: Who is importing this data
            description: Optional description
            
        Returns:
            True if successful, False otherwise
        """
        directory_path = Path(directory_path)
        if not directory_path.exists():
            self.logger.error(f"Directory not found: {directory_path}")
            return False
        
        # Use directory name as tag if not provided
        if not tag:
            tag = directory_path.name
        
        if not description:
            description = f"State search results from {directory_path.name}"
        
        self.logger.info(f"Importing state search results from: {directory_path}")
        
        try:
            # Create dataset
            dataset_id = self.create_dataset('states', tag, description, created_by)
            
            # Find all *_parse.json files
            json_files = list(directory_path.rglob("*_parse.json"))
            if not json_files:
                self.logger.error("No *_parse.json files found in directory")
                self.cleanup_failed_dataset(dataset_id)
                return False
            
            self.logger.info(f"Found {len(json_files)} JSON files to process")
            
            # Group files by pharmacy name for processing
            search_groups = self._group_files_by_search(json_files)
            
            total_searches = 0
            total_results = 0
            import_errors = []
            
            for pharmacy_name, files in search_groups.items():
                try:
                    # Process all files for this pharmacy+state combination
                    for state_code, state_files in files.items():
                        search_id = self._import_pharmacy_state_search(
                            dataset_id, pharmacy_name, state_code, state_files, directory_path
                        )
                        
                        if search_id:
                            total_searches += 1
                            # Count total results from all files
                            result_count = sum(
                                self._count_results_in_file(f) for f in state_files
                            )
                            total_results += result_count
                            
                            self.logger.info(
                                f"Search: {pharmacy_name} in {state_code} -> "
                                f"{len(state_files)} files, {result_count} results"
                            )
                        else:
                            import_errors.append(f"{pharmacy_name} in {state_code}: Failed to import")
                            
                except Exception as e:
                    error_msg = f"{pharmacy_name}: {str(e)}"
                    import_errors.append(error_msg)
                    self.logger.error(error_msg)
                    continue
            
            if total_searches == 0:
                self.logger.error("No searches were successfully imported")
                self.cleanup_failed_dataset(dataset_id)
                return False
            
            # Report results
            if import_errors:
                self.logger.warning(f"{len(import_errors)} import errors:")
                for error in import_errors[:5]:  # Show first 5 errors
                    self.logger.warning(f"  {error}")
                if len(import_errors) > 5:
                    self.logger.warning(f"  ... and {len(import_errors) - 5} more")
            
            self.logger.info(
                f"Successfully imported {total_searches} searches with {total_results} "
                f"total results using tag '{tag}'"
            )
            
            # Print dataset statistics
            stats = self.get_dataset_stats(dataset_id)
            self.logger.info(f"Dataset statistics: {stats}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Import failed: {str(e)}")
            return False
    
    def _group_files_by_search(self, json_files: List[Path]) -> Dict[str, Dict[str, List[Path]]]:
        """
        Group JSON files by pharmacy name and state
        
        Args:
            json_files: List of JSON file paths
            
        Returns:
            Dictionary: {pharmacy_name: {state: [files]}}
        """
        groups = {}
        
        for filepath in json_files:
            # Extract pharmacy name from filename (before first underscore or _no_results)
            filename = filepath.stem  # Remove .json extension
            
            if filename.endswith('_parse'):
                filename = filename[:-6]  # Remove _parse suffix
                
            # Handle no_results files: "Pharmacy_no_results" -> "Pharmacy"
            if filename.endswith('_no_results'):
                pharmacy_name = filename[:-11]  # Remove _no_results
            else:
                # Regular files: "Pharmacy_01" -> "Pharmacy"
                parts = filename.split('_')
                if len(parts) > 1 and parts[-1].isdigit():
                    pharmacy_name = '_'.join(parts[:-1])
                else:
                    pharmacy_name = filename
            
            # Get state from parent directory
            state_code = filepath.parent.name.upper()
            
            if pharmacy_name not in groups:
                groups[pharmacy_name] = {}
            if state_code not in groups[pharmacy_name]:
                groups[pharmacy_name][state_code] = []
                
            groups[pharmacy_name][state_code].append(filepath)
        
        return groups
    
    def _import_pharmacy_state_search(self, dataset_id: int, pharmacy_name: str, 
                                    state_code: str, files: List[Path], 
                                    base_dir: Path) -> Optional[int]:
        """
        Import all files for a single pharmacy+state search
        
        Args:
            dataset_id: Dataset ID
            pharmacy_name: Pharmacy name being searched
            state_code: State code
            files: List of JSON files for this search
            base_dir: Base directory for organizing screenshot paths
            
        Returns:
            Search ID if successful, None otherwise
        """
        # Use the first file to get search metadata
        first_file = files[0]
        
        try:
            with open(first_file, 'r', encoding='utf-8') as f:
                first_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to read {first_file}: {e}")
            return None
        
        metadata = first_data.get('metadata', {})
        search_result = first_data.get('search_result', {})
        
        # Parse timestamp
        timestamp = None
        if 'search_timestamp' in metadata:
            try:
                timestamp_str = metadata['search_timestamp']
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError as e:
                self.logger.warning(f"Invalid timestamp format: {metadata.get('search_timestamp')}")
        
        # Build metadata for search
        search_meta = {
            'scraper_version': metadata.get('scraper_version'),
            'search_result_type': metadata.get('search_result_type'),
            'file_count': len(files),
            'files': [f.name for f in files]
        }
        
        # Insert search record
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO searches (dataset_id, search_name, search_state, search_ts, meta)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                dataset_id,
                pharmacy_name,
                state_code,
                timestamp,
                json.dumps(search_meta)
            ))
            search_id = cur.fetchone()[0]
            self.conn.commit()
        
        # Import results from all files
        total_results = 0
        for file_path in files:
            result_count = self._import_results_from_file(search_id, file_path)
            total_results += result_count
        
        # Store screenshot metadata using paths from JSON metadata
        for file_path in files:
            self._store_screenshot_from_json_metadata(
                dataset_id, search_id, file_path, base_dir
            )
        
        return search_id
    
    def _import_results_from_file(self, search_id: int, file_path: Path) -> int:
        """
        Import search results from a single JSON file
        
        Args:
            search_id: Search ID
            file_path: Path to JSON file
            
        Returns:
            Number of results imported
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to read {file_path}: {e}")
            return 0
        
        search_result = data.get('search_result', {})
        licenses = search_result.get('licenses', [])
        result_status = search_result.get('result_status', 'unknown')
        
        if not licenses:
            self.logger.debug(f"No licenses found in {file_path.name}")
            return 0
        
        results_data = []
        
        for license_idx, license_data in enumerate(licenses):
            try:
                # Parse dates from various possible formats
                issue_date = self._parse_date(license_data.get('issue_date'))
                exp_date = self._parse_date(license_data.get('expiration_date'))
                
                # Extract address components
                address_data = license_data.get('address', {})
                street = address_data.get('street') if isinstance(address_data, dict) else license_data.get('address')
                city = address_data.get('city') if isinstance(address_data, dict) else license_data.get('city')
                state = address_data.get('state') if isinstance(address_data, dict) else license_data.get('state')
                zip_code = address_data.get('zip_code') if isinstance(address_data, dict) else license_data.get('zip')
                
                # Build result data
                result_data = (
                    search_id,
                    license_data.get('license_number'),
                    license_data.get('license_status'),
                    license_data.get('pharmacy_name'),  # license_name in schema
                    street,
                    city,
                    state,
                    zip_code,
                    issue_date,
                    exp_date,
                    result_status,
                    json.dumps(license_data)  # Store complete license data as raw
                )
                
                results_data.append(result_data)
                
            except Exception as e:
                self.logger.warning(f"License {license_idx} in {file_path.name} skipped: {str(e)}")
                continue
        
        if not results_data:
            return 0
        
        # Batch insert results
        columns = [
            'search_id', 'license_number', 'license_status', 'license_name',
            'address', 'city', 'state', 'zip', 'issue_date', 'expiration_date',
            'result_status', 'raw'
        ]
        
        return self.batch_insert('search_results', columns, results_data)
    
    def _parse_date(self, date_str) -> Optional[datetime.date]:
        """Parse date from various formats"""
        if not date_str:
            return None
        
        # Common date formats
        formats = [
            '%Y-%m-%d',      # 2024-01-01
            '%m/%d/%Y',      # 01/01/2024 or 5/21/2001
            '%m/%d/%y',      # 01/01/24
            '%d/%m/%Y',      # 01/01/2024
            '%Y-%m-%dT%H:%M:%S',  # ISO format
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(str(date_str), fmt).date()
            except ValueError:
                continue
        
        self.logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _count_results_in_file(self, file_path: Path) -> int:
        """Count results in a single JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return len(data.get('search_result', {}).get('licenses', []))
        except:
            return 0
    
    def _store_screenshot_metadata_from_parse_file(self, dataset_id: int, search_id: int,
                                                  json_file: Path, png_file: Path, 
                                                  base_dir: Path):
        """Store screenshot metadata from parse file structure"""
        try:
            # Generate organized path: tag/state/pharmacy_name_file.png
            relative_path = json_file.relative_to(base_dir)
            state_dir = relative_path.parent.name
            
            # Extract pharmacy name from filename
            filename = json_file.stem
            if filename.endswith('_parse'):
                filename = filename[:-6]
            
            organized_path = f"{base_dir.name}/{state_dir}/{filename}.png"
            
            # Get file size
            file_size = png_file.stat().st_size
            
            # Extract pharmacy name for search_name
            if filename.endswith('_no_results'):
                pharmacy_name = filename[:-11]
            else:
                parts = filename.split('_')
                if len(parts) > 1 and parts[-1].isdigit():
                    pharmacy_name = '_'.join(parts[:-1])
                else:
                    pharmacy_name = filename
            
            # Insert metadata
            self.execute_statement("""
                INSERT INTO images (dataset_id, state, search_id, search_name, 
                                   organized_path, storage_type, file_size)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dataset_id, organized_path) DO UPDATE SET
                    search_id = EXCLUDED.search_id,
                    file_size = EXCLUDED.file_size
            """, (
                dataset_id,
                state_dir,
                search_id,
                pharmacy_name,
                organized_path,
                'local',
                file_size
            ))
            
            self.logger.debug(f"Screenshot metadata stored: {organized_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to store screenshot metadata for {png_file}: {str(e)}")

    def _store_screenshot_from_json_metadata(self, dataset_id: int, search_id: int,
                                           json_file: Path, base_dir: Path):
        """Store screenshot metadata using path from JSON metadata"""
        try:
            # Read JSON to get screenshot path from metadata
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = data.get('metadata', {})
            source_image_file = metadata.get('source_image_file')
            
            if not source_image_file:
                self.logger.debug(f"No source_image_file in {json_file.name}")
                return
            
            # Convert to Path and check if file exists
            screenshot_file = Path(source_image_file)
            if not screenshot_file.exists():
                self.logger.warning(f"Screenshot file not found: {screenshot_file}")
                return
            
            # Generate organized path using the JSON metadata path structure
            # This maintains the original path structure for organized storage
            organized_path = str(screenshot_file)
            
            # Get file size
            file_size = screenshot_file.stat().st_size
            
            # Extract pharmacy name from JSON metadata (more reliable than filename parsing)
            pharmacy_name = metadata.get('pharmacy_name', 'Unknown')
            state_code = metadata.get('state', 'Unknown')
            
            # Insert metadata
            self.execute_statement("""
                INSERT INTO images (dataset_id, state, search_id, search_name, 
                                   organized_path, storage_type, file_size)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dataset_id, organized_path) DO UPDATE SET
                    search_id = EXCLUDED.search_id,
                    file_size = EXCLUDED.file_size
            """, (
                dataset_id,
                state_code,
                search_id,
                pharmacy_name,
                organized_path,
                'local',
                file_size
            ))
            
            self.logger.debug(f"Screenshot metadata stored: {organized_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to store screenshot metadata from {json_file}: {str(e)}")

    def export_sample_json(self, output_path: str) -> bool:
        """
        Export a sample JSON format for reference
        
        Args:
            output_path: Where to save the sample JSON
            
        Returns:
            True if successful
        """
        try:
            sample_data = {
                "searches": [
                    {
                        "name": "Empower Pharmacy",
                        "state": "TX",
                        "timestamp": "2024-01-15T10:30:00",
                        "meta": {
                            "search_url": "https://pharmacy.texas.gov/search",
                            "user_agent": "PharmChecker/1.0",
                            "search_type": "automated"
                        },
                        "results": [
                            {
                                "license_number": "12345",
                                "license_status": "Active",
                                "license_name": "Empower Pharmacy of Texas LLC",
                                "address": "123 Main Street",
                                "city": "Houston",
                                "state": "TX",
                                "zip": "77001",
                                "issue_date": "2020-01-01",
                                "expiration_date": "2025-01-01",
                                "result_status": "active",
                                "owner": "John Smith, PharmD",
                                "phone": "(555) 123-4567"
                            }
                        ],
                        "screenshot": "empower_tx_20240115.png"
                    },
                    {
                        "name": "MedPoint Compounding",
                        "state": "TX", 
                        "timestamp": "2024-01-15T10:35:00",
                        "meta": {
                            "search_url": "https://pharmacy.texas.gov/search",
                            "search_type": "automated"
                        },
                        "results": [
                            {
                                "license_number": "67890",
                                "license_status": "Active",
                                "license_name": "MedPoint Compounding Pharmacy",
                                "address": "456 Oak Avenue",
                                "city": "Dallas",
                                "state": "TX",
                                "zip": "75201",
                                "issue_date": "2019-06-01",
                                "expiration_date": "2024-06-01",
                                "result_status": "active"
                            }
                        ]
                    }
                ]
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(sample_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Sample JSON exported to: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export sample JSON: {e}")
            return False