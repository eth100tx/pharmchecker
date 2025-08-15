"""
SHA256-based image storage with deduplication support.

This module provides utilities for storing images with content-based deduplication
using SHA256 hashes. Supports both local filesystem and Supabase Storage backends.
"""

import hashlib
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, BinaryIO
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class ImageStorage:
    """Manages image storage with SHA256-based deduplication."""
    
    def __init__(self, backend_type: str = 'local', base_cache_dir: str = 'imagecache'):
        """
        Initialize ImageStorage.
        
        Args:
            backend_type: 'local' or 'supabase'
            base_cache_dir: Base directory for local image cache
        """
        self.backend_type = backend_type
        self.base_cache_dir = Path(base_cache_dir)
        self.supabase_client = None
        
        if backend_type == 'local':
            # Ensure local cache directory exists
            self.base_cache_dir.mkdir(parents=True, exist_ok=True)
        elif backend_type == 'supabase':
            self._init_supabase()
    
    def _init_supabase(self):
        """Initialize Supabase client for storage operations."""
        try:
            from supabase import create_client
            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_SERVICE_KEY')  # Use service key for storage
            if url and key:
                self.supabase_client = create_client(url, key)
            else:
                logger.warning("Supabase credentials not found, falling back to local storage")
                self.backend_type = 'local'
        except ImportError:
            logger.warning("Supabase client not available, falling back to local storage")
            self.backend_type = 'local'
    
    def compute_sha256(self, file_path: Path) -> str:
        """
        Compute SHA256 hash of file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 hash as hex string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def compute_sha256_from_bytes(self, data: bytes) -> str:
        """
        Compute SHA256 hash of byte data.
        
        Args:
            data: File content as bytes
            
        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(data).hexdigest()
    
    def get_storage_path(self, content_hash: str, extension: str = '.png') -> str:
        """
        Generate storage path with 2-level directory structure.
        
        Args:
            content_hash: SHA256 hash
            extension: File extension (with dot)
            
        Returns:
            Storage path: sha256/ab/cd/abcd1234...5678.png
        """
        if not extension.startswith('.'):
            extension = '.' + extension
        return f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}{extension}"
    
    def store_local(self, source_path: Path, content_hash: str) -> str:
        """
        Store image in local filesystem with SHA256-based path.
        
        Args:
            source_path: Source file path
            content_hash: SHA256 hash of content
            
        Returns:
            Storage path relative to base cache directory
        """
        storage_path = self.get_storage_path(content_hash, source_path.suffix)
        full_path = self.base_cache_dir / storage_path
        
        # Create directories
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file if not exists (deduplication)
        if not full_path.exists():
            shutil.copy2(source_path, full_path)
            logger.info(f"Stored new image: {content_hash[:8]}... -> {storage_path}")
        else:
            logger.info(f"Image already exists (deduplicated): {content_hash[:8]}...")
        
        return storage_path
    
    def store_supabase(self, source_path: Path, content_hash: str) -> str:
        """
        Store image in Supabase Storage with SHA256-based path.
        
        Args:
            source_path: Source file path
            content_hash: SHA256 hash of content
            
        Returns:
            Storage path in Supabase bucket
        """
        storage_path = self.get_storage_path(content_hash, source_path.suffix)
        
        # Check if file already exists (deduplication)
        try:
            existing = self.supabase_client.storage.from_('imagecache').list(
                path=storage_path
            )
            if existing:
                logger.info(f"Image already exists in Supabase (deduplicated): {content_hash[:8]}...")
                return storage_path
        except Exception as e:
            logger.debug(f"Error checking existing file (likely doesn't exist): {e}")
        
        # Upload to Supabase bucket
        try:
            with open(source_path, 'rb') as f:
                content_type = self._get_content_type(source_path.suffix)
                response = self.supabase_client.storage.from_('imagecache').upload(
                    storage_path, f, file_options={'content-type': content_type}
                )
            logger.info(f"Uploaded new image to Supabase: {content_hash[:8]}... -> {storage_path}")
            return storage_path
        except Exception as e:
            logger.error(f"Failed to upload to Supabase: {e}")
            # Fallback to local storage
            logger.info("Falling back to local storage")
            return self.store_local(source_path, content_hash)
    
    def _get_content_type(self, extension: str) -> str:
        """Get MIME type for file extension."""
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return content_types.get(extension.lower(), 'application/octet-stream')
    
    def get_image_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract image metadata.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Dictionary with metadata (file_size, content_type, etc.)
        """
        stat = file_path.stat()
        metadata = {
            'file_size': stat.st_size,
            'content_type': self._get_content_type(file_path.suffix),
        }
        
        # Try to get image dimensions (optional)
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                metadata['width'] = img.width
                metadata['height'] = img.height
        except (ImportError, Exception) as e:
            logger.debug(f"Could not extract image dimensions: {e}")
        
        return metadata
    
    def store_image(self, source_path: Path) -> Tuple[str, str, Dict[str, Any]]:
        """
        Store image and return hash, storage path, and metadata.
        
        Args:
            source_path: Path to source image file
            
        Returns:
            Tuple of (content_hash, storage_path, metadata)
        """
        # Compute hash
        content_hash = self.compute_sha256(source_path)
        
        # Store based on backend type
        if self.backend_type == 'supabase':
            storage_path = self.store_supabase(source_path, content_hash)
        else:
            storage_path = self.store_local(source_path, content_hash)
        
        # Get metadata
        metadata = self.get_image_metadata(source_path)
        
        return content_hash, storage_path, metadata
    
    def get_local_path(self, content_hash: str, extension: str = '.png') -> Path:
        """
        Get local filesystem path for a content hash.
        
        Args:
            content_hash: SHA256 hash
            extension: File extension
            
        Returns:
            Full local path
        """
        storage_path = self.get_storage_path(content_hash, extension)
        return self.base_cache_dir / storage_path
    
    def delete_image(self, content_hash: str, storage_path: str, storage_type: str) -> bool:
        """
        Delete image from storage.
        
        Args:
            content_hash: SHA256 hash
            storage_path: Storage path
            storage_type: 'local' or 'supabase'
            
        Returns:
            True if deleted successfully
        """
        try:
            if storage_type == 'local':
                full_path = self.base_cache_dir / storage_path
                if full_path.exists():
                    full_path.unlink()
                    logger.info(f"Deleted local image: {content_hash[:8]}...")
                    return True
            elif storage_type == 'supabase' and self.supabase_client:
                self.supabase_client.storage.from_('imagecache').remove([storage_path])
                logger.info(f"Deleted Supabase image: {content_hash[:8]}...")
                return True
        except Exception as e:
            logger.error(f"Failed to delete image {content_hash[:8]}...: {e}")
        
        return False
    
    def cleanup_local_directory(self, content_hash: str):
        """
        Clean up empty directories after file deletion.
        
        Args:
            content_hash: SHA256 hash to determine directory structure
        """
        if self.backend_type != 'local':
            return
        
        try:
            # Try to remove directories if empty (bottom-up)
            storage_path = self.get_storage_path(content_hash, '')  # No extension
            path_parts = Path(storage_path).parts[:-1]  # Remove filename
            
            for i in range(len(path_parts), 0, -1):
                dir_path = self.base_cache_dir / Path(*path_parts[:i])
                if dir_path.exists() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    logger.debug(f"Removed empty directory: {dir_path}")
                else:
                    break  # Stop if directory not empty
        except Exception as e:
            logger.debug(f"Error cleaning up directories: {e}")


def create_image_storage(backend_type: str = None) -> ImageStorage:
    """
    Factory function to create ImageStorage instance.
    
    Args:
        backend_type: Override backend type ('local' or 'supabase')
        
    Returns:
        ImageStorage instance
    """
    if backend_type is None:
        # Auto-detect based on environment
        if os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_KEY'):
            backend_type = 'supabase'
        else:
            backend_type = 'local'
    
    return ImageStorage(backend_type)