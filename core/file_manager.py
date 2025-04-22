import os
import json
import pickle
import time
import datetime
import shutil
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QByteArray, QDataStream, QIODevice

class FileManager:
    """Simplified manager for file operations in the application"""
    
    def __init__(self):
        # Current file path
        self.current_file = None
        
        # Recent files list
        self.recent_files = self._load_recent_files()
        
        # Last save time for determining if there are unsaved changes
        self.last_save_time = 0
    
    def _load_recent_files(self):
        """Load the list of recent files"""
        recent_files_path = os.path.join(os.path.expanduser("~"), ".araknid", "recent_files.json")
        
        if os.path.exists(recent_files_path):
            try:
                with open(recent_files_path, 'r') as f:
                    recent_files = json.load(f)
                    # Filter to only include files that still exist
                    recent_files = [f for f in recent_files if os.path.exists(f)]
                    return recent_files
            except:
                return []
        else:
            return []
    
    def _save_recent_files(self):
        """Save the list of recent files"""
        # Create directory if it doesn't exist
        os.makedirs(os.path.join(os.path.expanduser("~"), ".araknid"), exist_ok=True)
        
        recent_files_path = os.path.join(os.path.expanduser("~"), ".araknid", "recent_files.json")
        
        try:
            with open(recent_files_path, 'w') as f:
                json.dump(self.recent_files, f)
        except:
            pass
    
    def add_to_recent_files(self, filepath):
        """Add a file to the recent files list"""
        # Normalize path to handle different path formats
        filepath = os.path.normpath(filepath)
        
        # Remove if already exists (to move it to the top)
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
            
        # Add to the beginning of the list
        self.recent_files.insert(0, filepath)
        
        # Keep only the 10 most recent files
        self.recent_files = self.recent_files[:10]
        
        # Save the updated list
        self._save_recent_files()
    
    def get_recent_files(self):
        """Get the list of recent files"""
        return self.recent_files
    
    def save_project(self, filename, blocks):
        """Save the project to a file using JSON serialization"""
        # Make sure the filename has the correct extension
        if not filename.endswith('.ark'):
            filename += '.ark'
            
        try:
            # Create a JSON serializable representation of each block
            serializable_blocks = []
            
            for block in blocks:
                block_data = {
                    'type': block.__class__.__name__,
                    'position': {'x': block.x(), 'y': block.y()},
                    'inputs': {}
                }
                
                # Serialize inputs
                if hasattr(block, 'inputs'):
                    for name, input_field in block.inputs.items():
                        if hasattr(input_field, 'text'):
                            block_data['inputs'][name] = input_field.text()
                        elif hasattr(input_field, 'currentText'):
                            block_data['inputs'][name] = input_field.currentText()
                
                serializable_blocks.append(block_data)
                
            # Write to file
            with open(filename, 'w') as f:
                json.dump(serializable_blocks, f, indent=2)
                
            # Store the current filename
            self.current_file = filename
            
            # Update last save time
            self.last_save_time = time.time()
            
            # Add to recent files
            self.add_to_recent_files(filename)
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to save project: {str(e)}"
            QMessageBox.critical(None, "Save Error", error_msg)
            return False
        
    def load_project(self, filename):
        """Load a project from a file"""
        # This is a placeholder that will return an empty list
        # The actual loading will be handled by MainWindow._open_project_file
        # which will recreate the blocks based on the saved data
        
        self.current_file = filename
        self.last_save_time = time.time()
        self.add_to_recent_files(filename)
        
        # Return the filename so the caller can do the actual loading
        return filename
    
    def export_code(self, filename, code):
        """Export generated code to a file"""
        try:
            # Make sure the filename has the correct extension
            if not filename.endswith('.c'):
                filename += '.c'
                
            # Write code to file
            with open(filename, 'w') as f:
                f.write(code)
                
            return True
        except Exception as e:
            error_msg = f"Failed to export code: {str(e)}"
            QMessageBox.critical(None, "Export Error", error_msg)
            return False
    
    def check_unsaved_changes(self, last_modified_time):
        """Check if there are unsaved changes by comparing times"""
        return last_modified_time > self.last_save_time
