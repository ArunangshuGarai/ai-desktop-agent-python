import os
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Any, Union, Optional
import re
import datetime
import asyncio

class FileService:
    """Service for file-related operations."""
    
    def __init__(self):
        """Initialize the FileService."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    async def create_file(self, file_path: str, content: str = '') -> Dict[str, Any]:
        """
        Create a new file with content.
        
        Args:
            file_path: Path to the file to create.
            content: Content to write to the file.
            
        Returns:
            Dictionary with success status and path or error.
        """
        try:
            # Handle different parameter formats
            if isinstance(file_path, dict) and 'filename' in file_path:
                content = file_path.get('content', '')
                file_path = file_path.get('filename')
            
            # Convert to Path object
            path = Path(file_path)
            
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file with content
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"File created successfully: {file_path}")
            return {'success': True, 'path': str(path)}
        except Exception as error:
            self.logger.error(f"Error creating file: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def read_file(self, file_path: str) -> Dict[str, Any]:
        """
        Read a file's content.
        
        Args:
            file_path: Path to the file to read.
            
        Returns:
            Dictionary with success status and content or error.
        """
        try:
            # Convert to Path object
            path = Path(file_path)
            
            # Read file content
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {'success': True, 'content': content}
        except Exception as error:
            self.logger.error(f"Error reading file: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def update_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Update existing file content.
        
        Args:
            file_path: Path to the file to update.
            content: New content for the file.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            # Convert to Path object
            path = Path(file_path)
            
            # Write content to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {'success': True}
        except Exception as error:
            self.logger.error(f"Error updating file: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def delete_file(self, file_path: str) -> Dict[str, Any]:
        """
        Delete a file or directory.
        
        Args:
            file_path: Path to the file or directory to delete.
            
        Returns:
            Dictionary with success status or error.
        """
        try:
            # Convert to Path object
            path = Path(file_path)
            
            # Remove file or directory
            if path.is_dir():
                shutil.rmtree(path)
            else:
                os.remove(path)
            
            return {'success': True}
        except Exception as error:
            self.logger.error(f"Error deleting file: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def list_files(self, directory_path: str = '.') -> Dict[str, Any]:
        """
        List files in a directory.
        
        Args:
            directory_path: Path to the directory to list.
            
        Returns:
            Dictionary with success status and files or error.
        """
        try:
            # Convert to Path object
            path = Path(directory_path)
            
            # List files in directory
            files = [f.name for f in path.iterdir()]
            self.logger.info(f"Files in {directory_path}: {files}")
            return {'success': True, 'files': files}
        except Exception as error:
            self.logger.error(f"Error listing files: {str(error)}")
            return {'success': False, 'error': str(error)}
    
    async def search_files(self, directory_path: str, options: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Search for files matching criteria.
        
        Args:
            directory_path: Path to the directory to search.
            options: Search options (pattern, recursive).
            
        Returns:
            Dictionary with success status and matching files or error.
        """
        try:
            pattern = options.get('pattern')
            recursive = options.get('recursive', True)
            
            # Convert to Path object
            path = Path(directory_path)
            
            # Compile pattern regex if provided
            pattern_regex = None
            if pattern:
                pattern_regex = re.compile(pattern, re.IGNORECASE)
            
            # List of found files
            all_files = []
            
            # Scan directory function
            async def scan_directory(dir_path):
                # List items in directory
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    stats = os.stat(item_path)
                    
                    if os.path.isdir(item_path) and recursive:
                        # Recursively scan subdirectories
                        await scan_directory(item_path)
                    elif pattern_regex and pattern_regex.search(item):
                        # If pattern is provided and matches
                        all_files.append({
                            'name': item,
                            'path': item_path,
                            'size': stats.st_size,
                            'modified': datetime.datetime.fromtimestamp(stats.st_mtime).isoformat()
                        })
                    elif not pattern:
                        # If no pattern is provided, include all files
                        all_files.append({
                            'name': item,
                            'path': item_path,
                            'size': stats.st_size,
                            'modified': datetime.datetime.fromtimestamp(stats.st_mtime).isoformat()
                        })
            
            # Start scanning
            await scan_directory(path)
            return {'success': True, 'files': all_files}
        except Exception as error:
            self.logger.error(f"Error searching files: {str(error)}")
            return {'success': False, 'error': str(error)}

# Export singleton instance
file_service = FileService()