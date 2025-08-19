#!/usr/bin/env python3
"""
Resilient API-based importer with parallel processing and resume capability
Implements the Fast and Safe Upload Plan for PharmChecker state imports
"""

import asyncio
import aiohttp
import json
import gc
import hashlib
import shutil
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import requests
import time
import logging
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('resilient_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WorkItemStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed" 
    FAILED = "failed"
    SKIPPED = "skipped"


class ProcessingPhase(Enum):
    PLANNING = "planning"
    SHA256 = "sha256"
    UPLOAD = "upload"
    IMPORT = "import"


@dataclass
class WorkItem:
    """Represents a single file to be processed"""
    work_id: str
    json_path: str
    png_path: str
    directory: str
    pharmacy_name: str
    search_state: str
    search_timestamp: Optional[str]
    dedup_key: str
    estimated_size: int
    status: WorkItemStatus = WorkItemStatus.PENDING
    sha256_hash: Optional[str] = None
    image_exists: Optional[bool] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    last_attempt: Optional[str] = None


@dataclass
class WorkState:
    """Tracks overall import progress and state"""
    dataset_id: int
    tag: str
    total_files: int
    total_images: int
    start_time: str
    phases: Dict[str, Dict[str, Any]]
    work_items: List[WorkItem]
    failed_items: List[str]
    completed_items: List[str]
    last_update: str
    current_phase: ProcessingPhase = ProcessingPhase.PLANNING


class WorkStateManager:
    """Manages work state persistence and resume capability"""
    
    def __init__(self, state_file: str = "work_state.json"):
        self.state_file = Path(state_file)
        self.state: Optional[WorkState] = None
    
    def save_state(self, state: WorkState):
        """Save current work state to file"""
        state.last_update = datetime.now(timezone.utc).isoformat()
        
        # Convert to serializable format
        state_dict = asdict(state)
        state_dict['work_items'] = [asdict(item) for item in state.work_items]
        
        # Convert enums to strings
        state_dict['current_phase'] = state.current_phase.value
        for item in state_dict['work_items']:
            item['status'] = item['status'].value
        
        with open(self.state_file, 'w') as f:
            json.dump(state_dict, f, indent=2)
        
        logger.info(f"💾 Work state saved to {self.state_file}")
    
    def load_state(self) -> Optional[WorkState]:
        """Load work state from file"""
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, 'r') as f:
                state_dict = json.load(f)
            
            # Convert work items back
            work_items = []
            for item_dict in state_dict['work_items']:
                item_dict['status'] = WorkItemStatus(item_dict['status'])
                work_items.append(WorkItem(**item_dict))
            
            state_dict['work_items'] = work_items
            state_dict['current_phase'] = ProcessingPhase(state_dict['current_phase'])
            
            self.state = WorkState(**state_dict)
            logger.info(f"📂 Loaded work state from {self.state_file}")
            return self.state
            
        except Exception as e:
            logger.error(f"❌ Failed to load work state: {e}")
            return None


class ResilientImporter:
    """Main resilient importer with parallel processing"""
    
    def __init__(self, max_workers: int = 16, 
                 max_concurrent_uploads: int = 10, batch_size: int = 25,
                 state_file: str = "work_state.json", verify_writes: bool = False,
                 debug_log: bool = False, single_file: str = None):
        self.max_workers = max_workers
        self.max_concurrent_uploads = max_concurrent_uploads
        self.batch_size = batch_size
        self.verify_writes = verify_writes
        self.debug_log = debug_log
        self.single_file = single_file
        
        # Initialize state manager
        self.state_manager = WorkStateManager(state_file)
        
        # Initialize API client
        self.session = requests.Session()
        self._setup_api_client()
        
        # Setup debug logging if requested
        if debug_log:
            debug_handler = logging.FileHandler('resilient_import_debug.log')
            debug_handler.setLevel(logging.DEBUG)
            debug_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
            debug_handler.setFormatter(debug_formatter)
            logger.addHandler(debug_handler)
            logger.setLevel(logging.DEBUG)
        
        # Performance tracking
        self.start_time = time.time()
        self.stats = {
            'files_processed': 0,
            'images_processed': 0,
            'uploads_completed': 0,
            'records_imported': 0,
            'errors': 0,
            'files_with_png': 0,
            'files_without_png': 0,
            'already_present': 0,
            'newly_uploaded': 0,
            'error_files': []
        }
        
        # CSV debug logging setup
        self.debug_csv_file = None
        self.debug_csv_writer = None
        if debug_log:
            self._setup_csv_debug_logging()
    
    def _setup_csv_debug_logging(self):
        """Setup CSV debug logging to track every parse.json file processing"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'resilient_import_debug_{timestamp}.csv'
        
        self.debug_csv_file = open(csv_filename, 'w', newline='', encoding='utf-8')
        self.debug_csv_writer = csv.DictWriter(self.debug_csv_file, fieldnames=[
            'json_file_path',
            'pharmacy_name', 
            'search_state',
            'search_timestamp',
            'png_file_exists',
            'licenses_found',
            'processing_status',
            'record_ids_inserted',
            'error_message',
            'processed_at'
        ])
        self.debug_csv_writer.writeheader()
        
        logger.info(f"📝 CSV debug logging enabled: {csv_filename}")
    
    def _log_file_processing(self, json_path: str, pharmacy_name: str, search_state: str, 
                           search_timestamp: str, png_exists: bool, licenses_count: int,
                           status: str, record_ids: List[str] = None, error_msg: str = None):
        """Log file processing details to CSV"""
        if self.debug_csv_writer:
            self.debug_csv_writer.writerow({
                'json_file_path': json_path,
                'pharmacy_name': pharmacy_name,
                'search_state': search_state, 
                'search_timestamp': search_timestamp or '',
                'png_file_exists': png_exists,
                'licenses_found': licenses_count,
                'processing_status': status,
                'record_ids_inserted': ','.join(record_ids) if record_ids else '',
                'error_message': error_msg or '',
                'processed_at': datetime.now(timezone.utc).isoformat()
            })
            self.debug_csv_file.flush()
    
    def _setup_api_client(self):
        """Setup Supabase API client"""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        base_url = os.getenv('SUPABASE_URL')
        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        if not base_url or not service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        
        self.api_url = f"{base_url}/rest/v1"
        self.session.headers.update({
            'apikey': service_key,
            'Authorization': f'Bearer {service_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        })
    
    def get_or_create_dataset(self, tag: str, description: str = None, created_by: str = None) -> Optional[int]:
        """Get existing dataset or create new one"""
        # Try to find existing dataset
        try:
            response = self.session.get(
                f"{self.api_url}/datasets",
                params={'kind': 'eq.states', 'tag': f'eq.{tag}', 'limit': '1'}
            )
            response.raise_for_status()
            
            result = response.json()
            if result:
                dataset_id = result[0]['id']
                logger.info(f"📋 Using existing dataset '{tag}' (ID: {dataset_id}) in Supabase")
                return dataset_id
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️  Could not check for existing dataset: {e}")
        
        # Create new dataset if none exists
        return self.create_dataset(tag, description, created_by)
    
    def create_dataset(self, tag: str, description: str = None, created_by: str = None) -> Optional[int]:
        """Create dataset if it doesn't exist"""
        data = {
            'kind': 'states',
            'tag': tag,
            'description': description or f"States dataset: {tag}",
            'created_by': created_by or 'resilient_importer'
        }
        
        try:
            response = self.session.post(f"{self.api_url}/datasets", json=data)
            response.raise_for_status()
            
            result = response.json()
            dataset_id = result[0]['id'] if result else None
            logger.info(f"✅ Created dataset '{tag}' (ID: {dataset_id}) in Supabase")
            return dataset_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to create dataset: {e}")
            return None
    
    def plan_work(self, states_dir: str, tag: str, created_by: str = None, 
                  description: str = None) -> WorkState:
        """Phase 1: Planning - scan directories and build work catalog"""
        logger.info("📋 Phase 1: Planning and cataloging work...")
        
        states_path = Path(states_dir)
        if not states_path.exists():
            raise ValueError(f"States directory not found: {states_path}")
        
        # Get or create dataset
        dataset_id = self.get_or_create_dataset(tag, description, created_by)
        if not dataset_id:
            raise ValueError("Failed to create dataset")
        
        # Scan for JSON files
        json_files = list(states_path.rglob("*_parse.json"))
        
        # Filter to single file if specified
        if self.single_file:
            json_files = [f for f in json_files if str(f) == self.single_file]
            if not json_files:
                raise ValueError(f"Single file not found: {self.single_file}")
            logger.info(f"🎯 Processing single file: {self.single_file}")
        else:
            logger.info(f"📊 Found {len(json_files)} JSON files to process")
        
        work_items = []
        files_without_png = []
        
        for json_file in json_files:
            try:
                # Read metadata quickly
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                metadata = data.get('metadata', {})
                pharmacy_name = metadata.get('pharmacy_name', 'Unknown')
                search_state = metadata.get('state', 'XX')
                search_timestamp = metadata.get('search_timestamp')
                
                # Find corresponding PNG from JSON metadata
                source_image_file = metadata.get('source_image_file')
                if source_image_file:
                    png_file = Path(source_image_file)
                else:
                    # Fallback to old calculation method if no source_image_file
                    png_filename = json_file.stem.replace('_parse', '') + '.png'
                    png_file = json_file.parent / png_filename
                
                # Generate work ID and dedup key
                work_id = f"{search_state}_{pharmacy_name}_{json_file.stem}"
                work_id = "".join(c for c in work_id if c.isalnum() or c in '_-')  # Clean ID
                
                # Create dedup key based on search results
                search_result = data.get('search_result', {})
                licenses = search_result.get('licenses', [])
                
                if licenses:
                    # Use first license number for dedup key when license exists
                    license_number = licenses[0].get('license_number')
                    if license_number:  # Check if license_number is not None/empty
                        dedup_key = f"{dataset_id}|{pharmacy_name}|{search_state}|{license_number}"
                    else:
                        # License object exists but license_number is null - treat as no license
                        json_filename = Path(json_file).name
                        dedup_key = f"{dataset_id}|{pharmacy_name}|{search_state}|no_license|{json_filename}"
                else:
                    # No license - use parse.json file path for uniqueness (always available and unique)
                    json_filename = Path(json_file).name
                    dedup_key = f"{dataset_id}|{pharmacy_name}|{search_state}|no_license|{json_filename}"
                
                # Track PNG analysis
                if png_file.exists():
                    estimated_size = png_file.stat().st_size
                    self.stats['files_with_png'] += 1
                else:
                    estimated_size = 0
                    self.stats['files_without_png'] += 1
                    files_without_png.append(str(json_file))
                    if self.debug_log:
                        logger.debug(f"Missing PNG for {json_file}: expected {png_file} (from metadata: {source_image_file})")
                
                work_item = WorkItem(
                    work_id=work_id,
                    json_path=str(json_file),
                    png_path=str(png_file),
                    directory=json_file.parent.name,
                    pharmacy_name=pharmacy_name,
                    search_state=search_state,
                    search_timestamp=search_timestamp,
                    dedup_key=dedup_key,
                    estimated_size=estimated_size
                )
                
                work_items.append(work_item)
                
            except Exception as e:
                logger.warning(f"⚠️  Failed to process {json_file}: {e}")
                continue
        
        # Sort by timestamp for proper conflict resolution
        work_items.sort(key=lambda x: x.search_timestamp or "")
        
        # Create work state
        total_images = sum(1 for item in work_items if Path(item.png_path).exists())
        
        # Detailed file analysis
        logger.info(f"📊 File Analysis:")
        logger.info(f"  Total JSON files: {len(work_items)}")
        logger.info(f"  Files with PNG: {self.stats['files_with_png']}")
        logger.info(f"  Files without PNG: {self.stats['files_without_png']}")
        
        if files_without_png:
            logger.warning(f"⚠️  {len(files_without_png)} files missing PNG images:")
            for missing_file in files_without_png[:5]:  # Show first 5
                logger.warning(f"    {missing_file}")
            if len(files_without_png) > 5:
                logger.warning(f"    ... and {len(files_without_png) - 5} more")
        
        work_state = WorkState(
            dataset_id=dataset_id,
            tag=tag,
            total_files=len(work_items),
            total_images=total_images,
            start_time=datetime.now(timezone.utc).isoformat(),
            phases={
                'planning': {'status': 'completed', 'duration_seconds': 0},
                'sha256': {'status': 'pending', 'processed': 0},
                'upload': {'status': 'pending', 'completed': 0, 'failed': 0, 'skipped': 0},
                'import': {'status': 'pending', 'completed_batches': 0, 'total_batches': 0}
            },
            work_items=work_items,
            failed_items=[],
            completed_items=[],
            last_update=datetime.now(timezone.utc).isoformat(),
            current_phase=ProcessingPhase.PLANNING
        )
        
        logger.info(f"✅ Planning complete: {len(work_items)} work items, {total_images} images")
        return work_state
    
    def compute_sha256_parallel(self, work_state: WorkState) -> None:
        """Phase 2: Parallel SHA256 computation"""
        logger.info(f"🔢 Phase 2: Computing SHA256 hashes with {self.max_workers} workers...")
        work_state.current_phase = ProcessingPhase.SHA256
        
        # Get items that need SHA256 computation
        items_needing_hash = [
            item for item in work_state.work_items 
            if item.sha256_hash is None and Path(item.png_path).exists()
        ]
        
        if not items_needing_hash:
            logger.info("📋 No images need SHA256 computation")
            work_state.phases['sha256']['status'] = 'completed'
            return
        
        def compute_single_hash(work_item: WorkItem) -> Tuple[str, str]:
            """Compute SHA256 for a single image"""
            try:
                sha256_hash = hashlib.sha256()
                with open(work_item.png_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256_hash.update(chunk)
                return work_item.work_id, sha256_hash.hexdigest()
            except Exception as e:
                logger.error(f"❌ SHA256 failed for {work_item.work_id}: {e}")
                return work_item.work_id, None
        
        start_time = time.time()
        completed = 0
        
        # Process in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {
                executor.submit(compute_single_hash, item): item 
                for item in items_needing_hash
            }
            
            for future in as_completed(future_to_item):
                work_id, sha256_hash = future.result()
                
                # Update work item
                for item in work_state.work_items:
                    if item.work_id == work_id:
                        item.sha256_hash = sha256_hash
                        if sha256_hash:
                            completed += 1
                        break
                
                # Progress update
                if completed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    logger.info(f"🔢 SHA256 progress: {completed}/{len(items_needing_hash)} "
                              f"({rate:.1f} files/sec)")
        
        # Update phase status
        duration = time.time() - start_time
        work_state.phases['sha256'] = {
            'status': 'completed',
            'processed': completed,
            'duration_seconds': round(duration, 2)
        }
        
        logger.info(f"✅ SHA256 computation complete: {completed} hashes in {duration:.1f}s")
    
    def check_existing_images(self, work_state: WorkState) -> None:
        """Check database for existing image assets to avoid duplicate uploads"""
        logger.info("🔍 Checking for existing image assets...")
        
        # Get all unique hashes
        hashes = {item.sha256_hash for item in work_state.work_items if item.sha256_hash}
        
        if not hashes:
            return
        
        # Query database for existing assets
        try:
            # Build query for multiple hashes
            hash_list = list(hashes)
            existing_hashes = set()
            
            # Query in batches to avoid URL length limits
            batch_size = 50
            for i in range(0, len(hash_list), batch_size):
                batch = hash_list[i:i + batch_size]
                hash_filter = ','.join(f'"{h}"' for h in batch)
                
                response = self.session.get(
                    f"{self.api_url}/image_assets",
                    params={
                        'select': 'content_hash',
                        'content_hash': f'in.({hash_filter})'
                    }
                )
                response.raise_for_status()
                
                batch_existing = {asset['content_hash'] for asset in response.json()}
                existing_hashes.update(batch_existing)
            
            # Update work items
            skipped_count = 0
            for item in work_state.work_items:
                if item.sha256_hash in existing_hashes:
                    item.image_exists = True
                    skipped_count += 1
                else:
                    item.image_exists = False
            
            logger.info(f"📋 Found {len(existing_hashes)} existing images, "
                       f"{skipped_count} uploads can be skipped")
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to check existing images: {e}")
            # Assume all need upload if check fails
            for item in work_state.work_items:
                if item.sha256_hash:
                    item.image_exists = False
    
    async def upload_images_concurrent(self, work_state: WorkState) -> None:
        """Phase 3: Concurrent image uploads"""
        logger.info(f"📤 Phase 3: Uploading images with {self.max_concurrent_uploads} concurrent uploads...")
        work_state.current_phase = ProcessingPhase.UPLOAD
        
        # Get items that need upload
        items_needing_upload = [
            item for item in work_state.work_items 
            if item.sha256_hash and not item.image_exists and Path(item.png_path).exists()
        ]
        
        if not items_needing_upload:
            logger.info("📋 No images need uploading")
            work_state.phases['upload']['status'] = 'completed'
            return
        
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=self.max_concurrent_uploads)
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(self.max_concurrent_uploads)
            
            async def upload_single_image(work_item: WorkItem) -> bool:
                """Upload a single image with retry logic"""
                async with semaphore:
                    max_retries = 3
                    retry_delay = 1.0
                    
                    for attempt in range(max_retries):
                        try:
                            # Add current directory to path for module imports
                            import sys
                            from pathlib import Path
                            current_dir = Path(__file__).parent.parent
                            if str(current_dir) not in sys.path:
                                sys.path.insert(0, str(current_dir))
                            
                            # Store image using existing image storage
                            from utils.image_storage import create_image_storage
                            storage = create_image_storage('supabase')
                            
                            png_path = Path(work_item.png_path)
                            content_hash, storage_path, metadata = storage.store_image(png_path)
                            
                            # Create asset record via API
                            asset_data = {
                                'content_hash': content_hash,
                                'storage_path': storage_path,
                                'storage_type': storage.backend_type,
                                'file_size': metadata['file_size'],
                                'content_type': metadata['content_type'],
                                'width': metadata.get('width'),
                                'height': metadata.get('height')
                            }
                            
                            # Use requests session for database operations (async aiohttp for file uploads)
                            response = self.session.post(f"{self.api_url}/image_assets", json=asset_data)
                            response.raise_for_status()
                            
                            logger.debug(f"📤 Uploaded: {work_item.work_id}")
                            return True
                            
                        except Exception as e:
                            work_item.retry_count = attempt + 1
                            work_item.error_message = str(e)
                            work_item.last_attempt = datetime.now(timezone.utc).isoformat()
                            
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                                logger.warning(f"⚠️  Upload retry {attempt + 1}/{max_retries} for {work_item.work_id}: {e}")
                            else:
                                logger.error(f"❌ Upload failed after {max_retries} attempts for {work_item.work_id}: {e}")
                                work_item.status = WorkItemStatus.FAILED
                                return False
                
                return False
            
            # Start uploads
            start_time = time.time()
            completed = 0
            failed = 0
            
            tasks = [upload_single_image(item) for item in items_needing_upload]
            
            for task in asyncio.as_completed(tasks):
                success = await task
                if success:
                    completed += 1
                else:
                    failed += 1
                
                # Progress update
                total_done = completed + failed
                if total_done % 25 == 0:
                    elapsed = time.time() - start_time
                    rate = total_done / elapsed if elapsed > 0 else 0
                    logger.info(f"📤 Upload progress: {completed} success, {failed} failed, "
                              f"{total_done}/{len(items_needing_upload)} total ({rate:.1f} uploads/sec)")
        
        # Update phase status
        duration = time.time() - start_time
        work_state.phases['upload'] = {
            'status': 'completed',
            'completed': completed,
            'failed': failed,
            'skipped': len(work_state.work_items) - len(items_needing_upload),
            'duration_seconds': round(duration, 2)
        }
        
        logger.info(f"✅ Image upload complete: {completed} uploaded, {failed} failed in {duration:.1f}s")
    
    def import_search_results_batched(self, work_state: WorkState) -> None:
        """Phase 4: Import search results in resilient batches"""
        logger.info(f"📥 Phase 4: Importing search results in batches of {self.batch_size}...")
        work_state.current_phase = ProcessingPhase.IMPORT
        
        # Prepare search results data
        search_results = []
        file_to_record_mapping = {}  # Track which files produce which records
        
        for work_item in work_state.work_items:
            try:
                with open(work_item.json_path, 'r') as f:
                    data = json.load(f)
                
                metadata = data.get('metadata', {})
                search_result = data.get('search_result', {})
                
                # Parse timestamp safely
                search_ts = None
                if work_item.search_timestamp:
                    try:
                        search_ts = datetime.fromisoformat(work_item.search_timestamp.replace('Z', '+00:00'))
                    except ValueError:
                        logger.warning(f"⚠️  Invalid timestamp for {work_item.work_id}, using current time")
                        search_ts = datetime.now(timezone.utc)
                
                # Process licenses
                licenses = search_result.get('licenses', [])
                png_exists = Path(work_item.png_path).exists()
                
                # Track this file for CSV logging
                file_record_ids = []
                
                if not licenses:
                    # No results found
                    result_status = search_result.get('result_status', 'not_found')
                    record = {
                        'dataset_id': work_state.dataset_id,
                        'search_name': work_item.pharmacy_name,
                        'search_state': work_item.search_state,
                        'search_ts': search_ts.isoformat() if search_ts else None,
                        'license_number': None,
                        'result_status': result_status,
                        'meta': json.dumps(metadata),
                        'raw': json.dumps(data),
                        'image_hash': work_item.sha256_hash
                    }
                    search_results.append(record)
                    # Generate a unique ID for this record for tracking
                    record_id = f"{work_state.dataset_id}-{work_item.pharmacy_name}-{work_item.search_state}-no_license"
                    file_record_ids.append(record_id)
                else:
                    # Process each license
                    for i, license_info in enumerate(licenses):
                        address_info = license_info.get('address', {})
                        
                        record = {
                            'dataset_id': work_state.dataset_id,
                            'search_name': work_item.pharmacy_name,
                            'search_state': work_item.search_state,
                            'search_ts': search_ts.isoformat() if search_ts else None,
                            'license_number': license_info.get('license_number'),
                            'license_status': license_info.get('license_status'),
                            'license_name': license_info.get('pharmacy_name'),
                            'license_type': license_info.get('license_type'),
                            'address': address_info.get('street'),
                            'city': address_info.get('city'),
                            'state': address_info.get('state'),
                            'zip': address_info.get('zip_code'),
                            'issue_date': self._clean_date_field(license_info.get('issue_date')),
                            'expiration_date': self._clean_date_field(license_info.get('expiration_date')),
                            'result_status': search_result.get('result_status', 'found'),
                            'meta': json.dumps(metadata),
                            'raw': json.dumps(data),
                            'image_hash': work_item.sha256_hash
                        }
                        search_results.append(record)
                        # Generate a unique ID for this record for tracking
                        license_num = license_info.get('license_number', f'license_{i}')
                        record_id = f"{work_state.dataset_id}-{work_item.pharmacy_name}-{work_item.search_state}-{license_num}"
                        file_record_ids.append(record_id)
                
                # Store mapping for later CSV logging with unique identifiers
                source_html = metadata.get('source_html_file', 'unknown')
                file_to_record_mapping[work_item.json_path] = {
                    'pharmacy_name': work_item.pharmacy_name,
                    'search_state': work_item.search_state,
                    'search_timestamp': work_item.search_timestamp,
                    'png_exists': png_exists,
                    'licenses_count': len(licenses),
                    'record_ids': file_record_ids,
                    'status': 'prepared',
                    'source_html_file': source_html,  # Add unique identifier
                    'json_path': work_item.json_path   # Store the exact path
                }
                
                # Debug: Log how many records this file will generate
                if self.debug_log:
                    source_html = metadata.get('source_html_file', 'unknown')
                    logger.debug(f"📂 FILE PREPARATION: {work_item.json_path}")
                    logger.debug(f"   🏪 Pharmacy: {work_item.pharmacy_name}")
                    logger.debug(f"   🗺️  State: {work_item.search_state}")
                    logger.debug(f"   📄 Source HTML: {source_html}")
                    logger.debug(f"   📜 Licenses found: {len(licenses)}")
                    logger.debug(f"   📋 Records to create: {len(file_record_ids)}")
                    for idx, record_id in enumerate(file_record_ids):
                        license_num = licenses[idx].get('license_number', 'no_license') if idx < len(licenses) else 'no_license'
                        logger.debug(f"     [{idx+1}] {record_id} (license: {license_num})")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Failed to prepare data for {work_item.work_id}: {e}")
                
                # Log failure to CSV
                self._log_file_processing(
                    work_item.json_path,
                    work_item.pharmacy_name,
                    work_item.search_state,
                    work_item.search_timestamp,
                    Path(work_item.png_path).exists(),
                    0,
                    'failed_preparation',
                    [],
                    error_msg
                )
                continue
        
        # Import in batches with error isolation
        if not search_results:
            logger.warning("⚠️  No search results to import")
            return
        
        total_batches = (len(search_results) + self.batch_size - 1) // self.batch_size
        completed_batches = 0
        failed_batches = 0
        total_imported = 0
        
        start_time = time.time()
        
        for i in range(0, len(search_results), self.batch_size):
            batch = search_results[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            
            # Clean batch data and normalize keys for PostgREST compatibility
            cleaned_batch = []
            
            # First pass: collect all unique keys across all records
            all_keys = set()
            for result in batch:
                all_keys.update(result.keys())
            
            # Second pass: ensure all records have the same keys
            for result in batch:
                cleaned_result = {}
                for key in all_keys:
                    value = result.get(key)
                    if value is not None and value != '':
                        cleaned_result[key] = value
                    else:
                        # Add missing keys with null for PostgREST compatibility
                        cleaned_result[key] = None
                cleaned_batch.append(cleaned_result)
            
            try:
                # Try batch insert first
                response = self.session.post(f"{self.api_url}/search_results", json=cleaned_batch)
                
                # Debug: Log batch insert attempt details
                if self.debug_log and response.status_code == 409:
                    logger.debug(f"🔍 BATCH INSERT CONFLICT - HTTP 409 Details:")
                    logger.debug(f"   Response: {response.text[:500]}...")  # First 500 chars
                    logger.debug(f"   Batch size: {len(cleaned_batch)} records")
                
                if response.status_code == 201:
                    # Success!
                    imported_records = response.json() if response.json() else []
                    imported_count = len(imported_records)
                    total_imported += imported_count
                    completed_batches += 1
                    logger.info(f"📥 Batch {batch_num}/{total_batches}: {imported_count} records imported")
                    
                    # Log successful records to CSV
                    self._log_batch_success_to_csv(batch, imported_records, file_to_record_mapping)
                    
                elif response.status_code == 409:
                    # Conflict - handle duplicates with individual UPSERT
                    logger.info(f"🔄 Batch {batch_num}/{total_batches} has conflicts, using individual UPSERT...")
                    
                    # Debug: Show what's in this conflicting batch
                    if self.debug_log:
                        logger.debug(f"🔍 CONFLICT BATCH ANALYSIS - {len(cleaned_batch)} records:")
                        seen_keys = {}
                        for i, record in enumerate(cleaned_batch):
                            key = f"{record.get('search_name')}/{record.get('search_state')}/{record.get('license_number')}"
                            if key in seen_keys:
                                logger.debug(f"   DUPLICATE KEY IN BATCH: {key}")
                                logger.debug(f"     First occurrence: record {seen_keys[key]}")
                                logger.debug(f"     Duplicate: record {i}")
                            else:
                                seen_keys[key] = i
                            logger.debug(f"   [{i}] {key}")
                    
                    batch_imported = self._handle_batch_conflicts(cleaned_batch, batch_num, file_to_record_mapping)
                    total_imported += batch_imported
                    completed_batches += 1
                    
                else:
                    # Other error - log details before raising
                    logger.error(f"💀 HTTP Status: {response.status_code}")
                    logger.error(f"💀 Error details: {response.text}")
                    
                    # Log batch details for 400 Bad Request
                    if response.status_code == 400 and cleaned_batch:
                        logger.error(f"💀 BATCH DEBUGGING - Records in failed batch: {len(cleaned_batch)}")
                        logger.error(f"💀 All field names in batch: {set().union(*(r.keys() for r in cleaned_batch))}")
                        
                        # Log first few records to identify the problem
                        for i, record in enumerate(cleaned_batch[:3]):
                            logger.error(f"💀 Record {i+1}/{len(cleaned_batch)}: {json.dumps(record, indent=2, default=str)}")
                        
                        # Check for common problems
                        for i, record in enumerate(cleaned_batch):
                            # Check for None values in required fields
                            if record.get('dataset_id') is None:
                                logger.error(f"💀 Record {i+1} has NULL dataset_id")
                            # Check for invalid JSON in meta/raw fields  
                            for json_field in ['meta', 'raw']:
                                if json_field in record and record[json_field]:
                                    try:
                                        if isinstance(record[json_field], str):
                                            json.loads(record[json_field])
                                    except json.JSONDecodeError:
                                        logger.error(f"💀 Record {i+1} has invalid JSON in {json_field}: {record[json_field][:100]}")
                    
                    response.raise_for_status()
                
            except requests.exceptions.RequestException as e:
                failed_batches += 1
                logger.error(f"❌ Batch {batch_num}/{total_batches} failed: {e}")
                
                # Log failed batch to CSV
                self._log_batch_failure_to_csv(batch, str(e), file_to_record_mapping)
                
                # Enhanced debugging for 400 errors
                if hasattr(e, 'response') and e.response:
                    logger.error(f"💀 HTTP Status: {e.response.status_code}")
                    logger.error(f"💀 Error details: {e.response.text}")
                    
                    # Log batch details for 400 Bad Request
                    if e.response.status_code == 400 and cleaned_batch:
                        logger.error(f"💀 BATCH DEBUGGING - Records in failed batch: {len(cleaned_batch)}")
                        logger.error(f"💀 All field names in batch: {set().union(*(r.keys() for r in cleaned_batch))}")
                        
                        # Log first few records to identify the problem
                        for i, record in enumerate(cleaned_batch[:3]):
                            logger.error(f"💀 Record {i+1}/{len(cleaned_batch)}: {json.dumps(record, indent=2, default=str)}")
                        
                        # Check for common problems
                        for i, record in enumerate(cleaned_batch):
                            # Check for None values in required fields
                            if record.get('dataset_id') is None:
                                logger.error(f"💀 Record {i+1} has NULL dataset_id")
                            # Check for invalid JSON in meta/raw fields  
                            for json_field in ['meta', 'raw']:
                                if json_field in record and record[json_field]:
                                    try:
                                        if isinstance(record[json_field], str):
                                            json.loads(record[json_field])
                                    except json.JSONDecodeError:
                                        logger.error(f"💀 Record {i+1} has invalid JSON in {json_field}: {record[json_field][:100]}")
                    
                    elif cleaned_batch:
                        logger.error(f"First record in failed batch: {json.dumps(cleaned_batch[0], indent=2, default=str)}")
        
        # Update phase status
        duration = time.time() - start_time
        work_state.phases['import'] = {
            'status': 'completed',
            'completed_batches': completed_batches,
            'failed_batches': failed_batches,
            'total_batches': total_batches,
            'total_imported': total_imported,
            'duration_seconds': round(duration, 2)
        }
        
        logger.info(f"✅ Import complete: {total_imported} records in {completed_batches}/{total_batches} batches "
                   f"({failed_batches} failed) in {duration:.1f}s")
        
        # Update stats with final import count
        self.stats['records_imported'] = total_imported
    
    def _log_batch_success_to_csv(self, batch: List[Dict], imported_records: List[Dict], 
                                 file_mapping: Dict) -> None:
        """Log successful batch import to CSV with actual record IDs"""
        # For each record in the batch, find the corresponding file and log success
        for i, record in enumerate(batch):
            # Find the original file that produced this record using source_html_file for precision
            matching_file = None
            record_source_html = None
            
            # Extract source_html_file from record's raw data
            try:
                if record.get('raw'):
                    raw_data = json.loads(record['raw'])
                    record_source_html = raw_data.get('metadata', {}).get('source_html_file')
            except:
                pass
            
            # Match by source_html_file first (most precise), fallback to name+state+timestamp
            for file_path, file_info in file_mapping.items():
                if record_source_html and file_info.get('source_html_file') == record_source_html:
                    matching_file = file_path
                    break
                elif (not record_source_html and 
                      file_info['pharmacy_name'] == record.get('search_name') and 
                      file_info['search_state'] == record.get('search_state') and
                      file_info['search_timestamp'] == record.get('search_ts')):
                    matching_file = file_path
                    break
            
            if matching_file:
                file_info = file_mapping[matching_file]
                # Use the imported record ID if available, otherwise use our tracked ID
                actual_record_id = str(imported_records[i].get('id', file_info['record_ids'][0])) if i < len(imported_records) else file_info['record_ids'][0]
                
                self._log_file_processing(
                    matching_file,
                    file_info['pharmacy_name'],
                    file_info['search_state'],
                    file_info['search_timestamp'],
                    file_info['png_exists'],
                    file_info['licenses_count'],
                    'imported_successfully',
                    [actual_record_id],
                    None
                )
    
    def _log_batch_failure_to_csv(self, batch: List[Dict], error_msg: str, 
                                 file_mapping: Dict) -> None:
        """Log failed batch import to CSV"""
        for record in batch:
            # Find the original file that produced this record using source_html_file for precision
            matching_file = None
            record_source_html = None
            
            # Extract source_html_file from record's raw data
            try:
                if record.get('raw'):
                    raw_data = json.loads(record['raw'])
                    record_source_html = raw_data.get('metadata', {}).get('source_html_file')
            except:
                pass
            
            # Match by source_html_file first (most precise), fallback to name+state+timestamp
            for file_path, file_info in file_mapping.items():
                if record_source_html and file_info.get('source_html_file') == record_source_html:
                    matching_file = file_path
                    break
                elif (not record_source_html and 
                      file_info['pharmacy_name'] == record.get('search_name') and 
                      file_info['search_state'] == record.get('search_state') and
                      file_info['search_timestamp'] == record.get('search_ts')):
                    matching_file = file_path
                    break
            
            if matching_file:
                file_info = file_mapping[matching_file]
                self._log_file_processing(
                    matching_file,
                    file_info['pharmacy_name'],
                    file_info['search_state'],
                    file_info['search_timestamp'],
                    file_info['png_exists'],
                    file_info['licenses_count'],
                    'import_failed',
                    [],
                    error_msg
                )
    
    def _handle_batch_conflicts(self, batch: List[Dict], batch_num: int, 
                               file_mapping: Dict) -> int:
        """Handle batch conflicts by doing individual UPSERT operations"""
        imported_count = 0
        
        for i, record in enumerate(batch):
            try:
                # Check if record exists
                filters = {
                    'dataset_id': f'eq.{record["dataset_id"]}',
                    'search_state': f'eq.{record["search_state"]}',
                    'search_name': f'eq.{record["search_name"]}',  # BUG FIX: Add search_name to filters!
                }
                
                # Handle NULL license_number case
                license_number = record.get('license_number')
                if license_number is None:
                    filters['license_number'] = 'is.null'
                else:
                    filters['license_number'] = f'eq.{license_number}'
                
                # Debug: Show what we're looking for
                if self.debug_log:
                    logger.debug(f"🔍 UPSERT [{i+1}/{len(batch)}] LOOKUP: {record['search_name']}/{record['search_state']}/{license_number}")
                    
                    # Show source file for context
                    record_source = "unknown"
                    try:
                        if record.get('raw'):
                            raw_data = json.loads(record['raw'])
                            record_source = raw_data.get('metadata', {}).get('source_html_file', 'unknown')
                    except:
                        pass
                    logger.debug(f"   📄 Source: {record_source}")
                    
                    for key, value in filters.items():
                        logger.debug(f"   🔍 {key}: {value}")
                
                # Check for existing record
                response = self.session.get(f"{self.api_url}/search_results", params=filters)
                response.raise_for_status()
                
                existing_records = response.json()
                
                # Debug: Show what we found
                if self.debug_log:
                    logger.debug(f"🔍 LOOKUP RESULTS: Found {len(existing_records)} existing records")
                    for idx, existing in enumerate(existing_records):
                        existing_source = "unknown"
                        try:
                            if existing.get('raw'):
                                existing_raw = json.loads(existing['raw'])
                                existing_source = existing_raw.get('metadata', {}).get('source_html_file', 'unknown')
                        except:
                            pass
                        logger.debug(f"   [{idx+1}] ID:{existing.get('id')} Name:'{existing.get('search_name')}' License:{existing.get('license_number')} Source:{existing_source}")
                
                # Special debug for suspected conflicts
                if existing_records and record['search_name'] != existing_records[0]['search_name']:
                    logger.warning(f"⚠️  POTENTIAL NAME MISMATCH:")
                    logger.warning(f"   New record: '{record['search_name']}'")
                    logger.warning(f"   Found existing: '{existing_records[0]['search_name']}'")
                    logger.warning(f"   License: {license_number}")
                    logger.warning(f"   This suggests database constraint doesn't include search_name!")
                
                if existing_records:
                    # Record exists - check if we should update based on timestamp
                    existing_record = existing_records[0]
                    existing_ts = existing_record.get('search_ts')
                    new_ts = record.get('search_ts')
                    
                    # Enhanced debugging for duplicate analysis
                    existing_source = "unknown"
                    new_source = "unknown"
                    try:
                        if existing_record.get('raw'):
                            existing_raw = json.loads(existing_record['raw'])
                            existing_source = existing_raw.get('metadata', {}).get('source_html_file', 'unknown')
                        if record.get('raw'):
                            new_raw = json.loads(record['raw'])
                            new_source = new_raw.get('metadata', {}).get('source_html_file', 'unknown')
                    except:
                        pass
                    
                    should_update = False
                    if new_ts and existing_ts:
                        # Compare timestamps - update if new is later
                        should_update = new_ts > existing_ts
                        timestamp_comparison = f"new={new_ts} vs existing={existing_ts} -> {'UPDATE' if should_update else 'SKIP'}"
                    elif new_ts and not existing_ts:
                        # New has timestamp, existing doesn't - update
                        should_update = True
                        timestamp_comparison = f"new={new_ts} vs existing=NULL -> UPDATE"
                    else:
                        # Skip if both null or new is null
                        should_update = False
                        timestamp_comparison = f"new={new_ts} vs existing={existing_ts} -> SKIP"
                    
                    if should_update:
                        # Update existing record
                        update_data = {k: v for k, v in record.items() if k not in ['dataset_id', 'search_state', 'license_number']}
                        response = self.session.patch(
                            f"{self.api_url}/search_results",
                            params=filters,
                            json=update_data
                        )
                        response.raise_for_status()
                        imported_count += 1
                        logger.debug(f"📝 UPDATED: {record['search_name']}/{record['search_state']}/{license_number}")
                        logger.debug(f"   🔄 {timestamp_comparison}")
                        logger.debug(f"   📄 Existing source: {existing_source}")
                        logger.debug(f"   📄 New source: {new_source}")
                        logger.debug(f"   🆔 Record ID: {existing_record.get('id', 'unknown')}")
                    else:
                        logger.debug(f"⏭️  SKIPPED: {record['search_name']}/{record['search_state']}/{license_number}")
                        logger.debug(f"   🔄 {timestamp_comparison}")
                        logger.debug(f"   📄 Existing source: {existing_source}")
                        logger.debug(f"   📄 New source: {new_source}")
                        logger.debug(f"   🆔 Record ID: {existing_record.get('id', 'unknown')}")
                else:
                    # Record doesn't exist - insert new
                    response = self.session.post(f"{self.api_url}/search_results", json=[record])
                    response.raise_for_status()
                    imported_count += 1
                    
                    # Enhanced debugging for new inserts
                    new_source = "unknown"
                    try:
                        if record.get('raw'):
                            new_raw = json.loads(record['raw'])
                            new_source = new_raw.get('metadata', {}).get('source_html_file', 'unknown')
                    except:
                        pass
                    
                    result = response.json()
                    new_record_id = result[0].get('id', 'unknown') if result else 'unknown'
                    
                    logger.debug(f"📥 INSERTED NEW: {record['search_name']}/{record['search_state']}/{license_number}")
                    logger.debug(f"   📄 Source file: {new_source}")
                    logger.debug(f"   ⏰ Timestamp: {record.get('search_ts', 'None')}")
                    logger.debug(f"   🆔 New record ID: {new_record_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to UPSERT record {i+1} in batch {batch_num}: {e}")
                continue
        
        logger.info(f"🔄 Batch {batch_num}: {imported_count}/{len(batch)} records upserted successfully")
        
        # Log upsert results to CSV
        for record in batch:
            # Find the original file that produced this record using source_html_file for precision
            matching_file = None
            record_source_html = None
            
            # Extract source_html_file from record's raw data
            try:
                if record.get('raw'):
                    raw_data = json.loads(record['raw'])
                    record_source_html = raw_data.get('metadata', {}).get('source_html_file')
            except:
                pass
            
            # Match by source_html_file first (most precise), fallback to name+state+timestamp
            for file_path, file_info in file_mapping.items():
                if record_source_html and file_info.get('source_html_file') == record_source_html:
                    matching_file = file_path
                    break
                elif (not record_source_html and 
                      file_info['pharmacy_name'] == record.get('search_name') and 
                      file_info['search_state'] == record.get('search_state') and
                      file_info['search_timestamp'] == record.get('search_ts')):
                    matching_file = file_path
                    break
            
            if matching_file:
                file_info = file_mapping[matching_file]
                record_id = f"{record.get('dataset_id')}-{record.get('search_name')}-{record.get('search_state')}-{record.get('license_number', 'no_license')}"
                self._log_file_processing(
                    matching_file,
                    file_info['pharmacy_name'],
                    file_info['search_state'],
                    file_info['search_timestamp'],
                    file_info['png_exists'],
                    file_info['licenses_count'],
                    'upserted',
                    [record_id],
                    None
                )
        
        return imported_count
    
    def check_for_duplicates(self, work_state: WorkState) -> None:
        """Check for duplicate records based on name, state, timestamp"""
        logger.info("🔍 Checking for duplicates...")
        
        try:
            response = self.session.get(
                f"{self.api_url}/search_results",
                params={
                    'dataset_id': f'eq.{work_state.dataset_id}',
                    'select': 'search_name,search_state,search_ts,raw'
                }
            )
            response.raise_for_status()
            records = response.json()
            
            # Group by search_name + search_state + timestamp
            groups = {}
            for record in records:
                key = f"{record['search_name']}|{record['search_state']}|{record.get('search_ts', '')}"
                if key not in groups:
                    groups[key] = []
                groups[key].append(record)
            
            # Check for duplicates
            duplicates = {k: v for k, v in groups.items() if len(v) > 1}
            
            if duplicates:
                logger.warning(f"⚠️  Found {len(duplicates)} duplicate groups:")
                for key, records in list(duplicates.items())[:5]:  # Show first 5
                    logger.warning(f"  {key}: {len(records)} records")
                    if self.debug_log:
                        logger.debug(f"    🔍 DUPLICATE GROUP ANALYSIS: {key}")
                        unique_sources = set()
                        for i, record in enumerate(records):
                            try:
                                raw_data = json.loads(record['raw'])
                                source_file = raw_data.get('metadata', {}).get('source_html_file', 'unknown')
                                unique_sources.add(source_file)
                                record_id = record.get('id', 'unknown')
                                search_ts = record.get('search_ts', 'None')
                                license_num = record.get('license_number', 'None')
                                logger.debug(f"      [{i+1}] ID:{record_id} License:{license_num} TS:{search_ts}")
                                logger.debug(f"           Source: {source_file}")
                            except Exception as e:
                                logger.debug(f"      [{i+1}] Error parsing record: {e}")
                        logger.debug(f"    📄 Unique source files: {len(unique_sources)}")
                        for source in unique_sources:
                            logger.debug(f"      - {source}")
            else:
                logger.info("✅ No duplicates found")
                
        except Exception as e:
            logger.error(f"❌ Duplicate check failed: {e}")
    
    def verify_write(self, search_name: str, search_state: str, source_html_file: str) -> bool:
        """Verify that a record was written correctly by reading it back"""
        try:
            response = self.session.get(
                f"{self.api_url}/search_results",
                params={
                    'search_name': f'eq.{search_name}',
                    'search_state': f'eq.{search_state}',
                    'select': 'raw'
                }
            )
            response.raise_for_status()
            records = response.json()
            
            # Find record with matching source_html_file
            for record in records:
                raw_data = json.loads(record['raw'])
                record_source = raw_data.get('metadata', {}).get('source_html_file', '')
                if record_source == source_html_file:
                    if self.debug_log:
                        logger.debug(f"✅ Verified write: {search_name}/{search_state} from {source_html_file}")
                    return True
            
            logger.warning(f"❌ Write verification failed: {search_name}/{search_state} from {source_html_file}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Write verification error: {e}")
            return False
    
    def _clean_date_field(self, date_value):
        """Clean date field values, converting invalid strings to None"""
        if not date_value:
            return None
        
        # Convert to string and strip whitespace
        date_str = str(date_value).strip()
        
        # List of invalid date strings that should become NULL
        invalid_dates = [
            'not on file',
            'not on file.',
            'not available',
            'n/a',
            'na',
            '---',
            'none',
            'unknown',
            'null',
            ''
        ]
        
        # Check if this is an invalid date string
        if date_str.lower() in invalid_dates:
            return None
            
        # Return the original value if it looks like a valid date
        return date_value
    
    def print_progress_summary(self, work_state: WorkState):
        """Print detailed progress summary"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*80)
        print(f"📊 Import Progress: {work_state.tag} (Dataset ID: {work_state.dataset_id})")
        print("="*80)
        print(f"⏱️  Elapsed: {elapsed//60:.0f}m {elapsed%60:.0f}s  |  Backend: Supabase")
        print(f"📁 Total Files: {work_state.total_files}  |  Images: {work_state.total_images}")
        
        # Show records imported count
        total_imported = work_state.phases.get('import', {}).get('total_imported', 0)
        print(f"📥 Records Imported: {total_imported}")
        
        print("\n📊 Phase Summary:")
        for phase_name, phase_data in work_state.phases.items():
            status_icon = "✅" if phase_data['status'] == 'completed' else "🟡" if phase_data['status'] == 'in_progress' else "⏳"
            duration = phase_data.get('duration_seconds', 0)
            print(f"  {status_icon} {phase_name.upper()}: {phase_data['status']} ({duration:.1f}s)")
        
        print(f"\n❌ Failed Items: {len(work_state.failed_items)}")
        if work_state.failed_items:
            for item_id in work_state.failed_items[:5]:  # Show first 5
                item = next((i for i in work_state.work_items if i.work_id == item_id), None)
                if item:
                    print(f"  - {item_id}: {item.error_message}")
            if len(work_state.failed_items) > 5:
                print(f"  ... and {len(work_state.failed_items) - 5} more")
        
        print("="*80)
    
    def run_import(self, states_dir: str, tag: str, created_by: str = None, 
                   description: str = None) -> bool:
        """Run complete import process"""
        try:
            # Phase 1: Planning
            work_state = self.plan_work(states_dir, tag, created_by, description)
            self.state_manager.save_state(work_state)
            
            # Initial duplicate check
            if not self.single_file:
                self.check_for_duplicates(work_state)
            
            # Phase 2: SHA256 computation
            self.compute_sha256_parallel(work_state)
            self.state_manager.save_state(work_state)
            
            # Pre-check existing images
            self.check_existing_images(work_state)
            self.state_manager.save_state(work_state)
            
            # Phase 3: Image uploads
            asyncio.run(self.upload_images_concurrent(work_state))
            self.state_manager.save_state(work_state)
            
            # Phase 4: Search results import
            self.import_search_results_batched(work_state)
            self.state_manager.save_state(work_state)
            
            # Final duplicate check
            if not self.single_file:
                self.check_for_duplicates(work_state)
            
            # Final summary
            self.print_progress_summary(work_state)
            
            return True
            
        except Exception as e:
            logger.error(f"💥 Import failed: {e}")
            return False
        finally:
            # Close CSV debug file if open
            if self.debug_csv_file:
                self.debug_csv_file.close()
                logger.info("📝 CSV debug log closed")
    
    def resume_import(self, state_file: str = "work_state.json") -> bool:
        """Resume import from saved state"""
        work_state = self.state_manager.load_state()
        if not work_state:
            logger.error("❌ No work state found to resume")
            return False
        
        logger.info(f"🔄 Resuming import for {work_state.tag} from {work_state.current_phase.value} phase")
        
        try:
            # Resume from current phase
            if work_state.current_phase in [ProcessingPhase.PLANNING, ProcessingPhase.SHA256]:
                if work_state.phases['sha256']['status'] != 'completed':
                    self.compute_sha256_parallel(work_state)
                    self.state_manager.save_state(work_state)
            
            if work_state.current_phase in [ProcessingPhase.PLANNING, ProcessingPhase.SHA256, ProcessingPhase.UPLOAD]:
                if work_state.phases['upload']['status'] != 'completed':
                    self.check_existing_images(work_state)
                    asyncio.run(self.upload_images_concurrent(work_state))
                    self.state_manager.save_state(work_state)
            
            if work_state.phases['import']['status'] != 'completed':
                self.import_search_results_batched(work_state)
                self.state_manager.save_state(work_state)
            
            self.print_progress_summary(work_state)
            return True
            
        except Exception as e:
            logger.error(f"💥 Resume failed: {e}")
            return False
        finally:
            # Close CSV debug file if open
            if self.debug_csv_file:
                self.debug_csv_file.close()
                logger.info("📝 CSV debug log closed")


def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Resilient PharmChecker state importer')
    parser.add_argument('--states-dir', help='Directory containing state data')
    parser.add_argument('--tag', help='Dataset tag')
    parser.add_argument('--created-by', default='resilient_importer')
    parser.add_argument('--description', default=None)
    parser.add_argument('--max-workers', type=int, default=16, help='Max workers for SHA256')
    parser.add_argument('--max-uploads', type=int, default=10, help='Max concurrent uploads')
    parser.add_argument('--batch-size', type=int, default=25, help='Import batch size')
    parser.add_argument('--state-file', default='work_state.json', help='Work state file')
    parser.add_argument('--resume', action='store_true', help='Resume from saved state')
    parser.add_argument('--verify-writes', action='store_true', help='Verify writes by reading back records')
    parser.add_argument('--debug-log', action='store_true', help='Enable detailed debug logging to file')
    parser.add_argument('--single-file', help='Process only a single JSON file (full path)')
    
    args = parser.parse_args()
    
    # Validate required args for non-resume operations
    if not args.resume and (not args.states_dir or not args.tag):
        parser.error("--states-dir and --tag are required unless using --resume")
    
    importer = ResilientImporter(
        max_workers=args.max_workers,
        max_concurrent_uploads=args.max_uploads,
        batch_size=args.batch_size,
        state_file=args.state_file,
        verify_writes=args.verify_writes,
        debug_log=args.debug_log,
        single_file=args.single_file
    )
    
    if args.resume:
        success = importer.resume_import(args.state_file)
    else:
        success = importer.run_import(
            states_dir=args.states_dir,
            tag=args.tag,
            created_by=args.created_by,
            description=args.description
        )
    
    exit(0 if success else 1)


if __name__ == '__main__':
    main()