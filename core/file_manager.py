import os
import json
import pickle

class FileManager:
    """Manager for file operations in the application"""
    
    def __init__(self):
        self.current_file = None
        
    def save_project(self, filename, blocks):
        """Save the project to a file"""
        # Make sure the filename has the correct extension
        if not filename.endswith('.ark'):
            filename += '.ark'
            
        # Serialize blocks using pickle
        with open(filename, 'wb') as f:
            pickle.dump(blocks, f)
            
        # Store the current filename
        self.current_file = filename
        
    def load_project(self, filename):
        """Load a project from a file"""
        # Check if file exists
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Project file not found: {filename}")
            
        # Load blocks from file
        with open(filename, 'rb') as f:
            blocks = pickle.load(f)
            
        # Store the current filename
        self.current_file = filename
        
        return blocks
    
    def export_code(self, filename, code):
        """Export generated code to a file"""
        # Make sure the filename has the correct extension
        if not filename.endswith('.c'):
            filename += '.c'
            
        # Write code to file
        with open(filename, 'w') as f:
            f.write(code)
            
    def import_code(self, filename):
        """Import code from a file (placeholder for future feature)"""
        # Check if file exists
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Code file not found: {filename}")
            
        # Read code from file
        with open(filename, 'r') as f:
            code = f.read()
            
        # TODO: Parse code into blocks (would require a C parser)
        # This is a complex feature that would be implemented in a future version
        
        # Return the code for now
        return code