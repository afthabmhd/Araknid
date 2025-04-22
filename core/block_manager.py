from PyQt5.QtCore import QObject, pyqtSignal
from blocks.base import Block

class BlockManager(QObject):
    """Manages all blocks in the application"""
    
    # Signals
    blocks_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # Store all blocks
        self.blocks = []
        
    def add_block(self, block):
        """Add a block to the manager"""
        if block not in self.blocks:
            self.blocks.append(block)
            self.blocks_changed.emit()
    
    def remove_block(self, block):
        """Remove a block from the manager"""
        if block in self.blocks:
            self.blocks.remove(block)
            self.blocks_changed.emit()
    
    def clear(self):
        """Clear all blocks"""
        self.blocks.clear()
        self.blocks_changed.emit()
    
    def set_blocks(self, blocks):
        """Set the blocks to the given list"""
        self.blocks = blocks
        self.blocks_changed.emit()
        
    def get_all_blocks(self):
        """Get all blocks"""
        return self.blocks
    
    def get_root_blocks(self):
        """Get valid root blocks (include, function declarations)"""
        root_blocks = []
        
        for block in self.blocks:
            # Include all blocks that could be valid root blocks
            if (block.__class__.__name__ == 'IncludeBlock' or 
                block.__class__.__name__ == 'FunctionDeclarationBlock' or
                block.__class__.__name__ == 'MainFunctionBlock'):
                
                root_blocks.append(block)
        
        return root_blocks
    
    def trigger_blocks_changed(self):
        """Trigger the blocks_changed signal to update the code view"""
        self.blocks_changed.emit()
