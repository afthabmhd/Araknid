from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QToolBox, QScrollArea, 
                             QGroupBox, QGridLayout, QPushButton, QLabel, QFrame,
                             QHBoxLayout, QLineEdit, QTreeWidget, QTreeWidgetItem)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QDrag, QColor
from PyQt5.QtCore import QMimeData, QPoint

# Import block classes
from blocks.base import Block

# Import specific block types
from blocks.include import IncludeBlock
from blocks.variables import VariableDeclarationBlock, VariableAssignmentBlock, ArrayDeclarationBlock
from blocks.control import IfBlock, ElseBlock, ForLoopBlock, WhileLoopBlock, BreakBlock, ContinueBlock
from blocks.io import PrintBlock, ScanBlock, PrintStringBlock, PrintfNewlineBlock
from blocks.operators import (OperatorBlock, LogicalOperatorBlock, AssignmentOperatorBlock, 
                           IncrementDecrementBlock, ArrayAccessBlock, TernaryOperatorBlock)
from blocks.functions import (FunctionDeclarationBlock, FunctionCallBlock, ReturnBlock, 
                            MainFunctionBlock)

class BlockButton(QPushButton):
    """Custom button for block creation in the toolbox - Flyde style"""
    
    def __init__(self, block_class, block_name, category_color, parent=None):
        super().__init__(parent)
        self.block_class = block_class
        self.category_color = category_color
        
        # Set button text and appearance - Flyde style
        self.setText(block_name)
        self.setFont(QFont("Segoe UI", 9))
        self.setFixedHeight(36)
        
        # Set button style - Flyde style
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                color: #343a40;
                border: 1px solid #dee2e6;
                border-left: 4px solid {self.category_color.name()};
                border-radius: 4px;
                padding: 4px 8px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #f8f9fa;
                border: 1px solid #ced4da;
                border-left: 4px solid {self.category_color.name()};
            }}
            QPushButton:pressed {{
                background-color: #e9ecef;
            }}
        """)
        
        # Enable drag and drop
        self.setMouseTracking(True)
    
    def mouseMoveEvent(self, event):
        """Handle mouse movement for drag and drop - Flyde style"""
        if event.buttons() == Qt.LeftButton:
            # Only start drag after moving a certain distance
            if not hasattr(self, '_drag_start_pos') or (event.pos() - self._drag_start_pos).manhattanLength() < 10:
                return
                
            # Start drag
            drag = QDrag(self)
            mime_data = QMimeData()
            
            # Store block class name for drop handling
            mime_data.setText(self.block_class.__name__)
            drag.setMimeData(mime_data)
            
            # Set drag position relative to button
            drag.setHotSpot(QPoint(event.pos().x(), event.pos().y()))
            
            # Execute drag operation
            drag.exec_(Qt.CopyAction)
    
    def mousePressEvent(self, event):
        """Handle mouse press to prepare for drag and drop"""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)


class Toolbox(QWidget):
    """Toolbox containing all available block types - Flyde style"""
    
    def __init__(self, block_manager):
        super().__init__()
        
        self.block_manager = block_manager
        
        # Flyde-style category colors
        self.category_colors = {
            Block.VARIABLE: QColor("#4a9df3"),     # Blue (Variables)
            Block.CONTROL: QColor("#e6b422"),      # Gold/Amber (Control)
            Block.IO: QColor("#9c3fb3"),           # Purple (IO)
            Block.OPERATOR: QColor("#4cb32b"),     # Green (Operators)
            Block.FUNCTION: QColor("#df71df"),     # Pink (Functions)
            Block.ALGORITHM: QColor("#8254d8")     # BlueViolet (Algorithms)
        }
        
        # Setup UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI components - Flyde style"""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # Set white background for the entire toolbox
        self.setStyleSheet("background-color: #ffffff;")
        
        # Title header - Flyde style
        header = QFrame()
        header.setStyleSheet("background-color: #1e1e1e;")
        header.setFixedHeight(50)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        
        title_label = QLabel("Node Library")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_label.setStyleSheet("color: white;")
        header_layout.addWidget(title_label)
        
        layout.addWidget(header)
        
        # Search box - Flyde style
        search_frame = QFrame()
        search_frame.setStyleSheet("background-color: #252526;")
        search_frame.setFixedHeight(50)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 8, 16, 8)
        
        search_box = QLineEdit()
        search_box.setPlaceholderText("Search nodes...")
        search_box.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
            }
        """)
        search_layout.addWidget(search_box)
        
        layout.addWidget(search_frame)
        
        # Create scrollable container
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #252526;
                border: none;
            }
            QScrollBar:vertical {
                background: #2d2d2d;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #5a5a5a;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Create container widget for categories
        container = QWidget()
        container.setStyleSheet("background-color: #252526;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(12)
        
        # Add block categories
        self._add_category_section(container_layout, "VARIABLES", Block.VARIABLE, [
            (VariableDeclarationBlock, "Variable Declaration"),
            (VariableAssignmentBlock, "Variable Assignment"),
            (ArrayDeclarationBlock, "Array Declaration")
        ])
        
        self._add_category_section(container_layout, "CONTROL FLOW", Block.CONTROL, [
            (IfBlock, "If"),
            (ElseBlock, "Else"),
            (ForLoopBlock, "For Loop"),
            (WhileLoopBlock, "While Loop"),
            (BreakBlock, "Break"),
            (ContinueBlock, "Continue")
        ])
        
        self._add_category_section(container_layout, "INPUT/OUTPUT", Block.IO, [
            (PrintBlock, "Print"),
            (ScanBlock, "Input"),
            (PrintStringBlock, "Print String"),
            (PrintfNewlineBlock, "Print Newline")
        ])
        
        self._add_category_section(container_layout, "OPERATORS", Block.OPERATOR, [
            (OperatorBlock, "Operator"),
            (LogicalOperatorBlock, "Logical Operator"),
            (AssignmentOperatorBlock, "Assignment"),
            (IncrementDecrementBlock, "Inc/Dec"),
            (ArrayAccessBlock, "Array Access"),
            (TernaryOperatorBlock, "Ternary")
        ])
        
        self._add_category_section(container_layout, "FUNCTIONS", Block.FUNCTION, [
            (FunctionDeclarationBlock, "Function Declaration"),
            (FunctionCallBlock, "Function Call"),
            (ReturnBlock, "Return"),
            (MainFunctionBlock, "Main Function")
        ])
        
        self._add_category_section(container_layout, "INCLUDES", Block.VARIABLE, [
            (IncludeBlock, "Include")
        ])
        
        # Add spacer at bottom for aesthetics
        container_layout.addStretch()
        
        # Add container to scroll area
        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)
        
    def _add_category_section(self, parent_layout, title, category, blocks):
        """Add a category section with blocks - Flyde style"""
        # Get category color
        color = self.category_colors.get(category, QColor(100, 100, 100))
        
        # Create category frame
        category_frame = QFrame()
        category_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #2d2d2d;
                border-radius: 4px;
            }}
        """)
        category_layout = QVBoxLayout(category_frame)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(0)
        
        # Category header
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: #333333;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
        """)
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 4)
        
        # Category color indicator
        color_indicator = QFrame()
        color_indicator.setFixedSize(16, 16)
        color_indicator.setStyleSheet(f"""
            QFrame {{
                background-color: {color.name()};
                border-radius: 8px;
            }}
        """)
        header_layout.addWidget(color_indicator)
        
        # Category title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title_label.setStyleSheet("color: white;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        category_layout.addWidget(header)
        
        # Blocks container
        blocks_container = QFrame()
        blocks_container.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
            }
        """)
        blocks_layout = QVBoxLayout(blocks_container)
        blocks_layout.setContentsMargins(8, 8, 8, 8)
        blocks_layout.setSpacing(6)
        
        # Add block buttons
        for block_class, block_name in blocks:
            button = BlockButton(block_class, block_name, color)
            button.clicked.connect(lambda checked, cls=block_class: self._create_block(cls))
            blocks_layout.addWidget(button)
        
        category_layout.addWidget(blocks_container)
        parent_layout.addWidget(category_frame)
        
    def _create_block(self, block_class):
        """Create a new block and add it to the canvas"""
        # Find the parent (MainWindow) to access the canvas
        parent = self.parent()
        while parent and not hasattr(parent, "canvas"):
            parent = parent.parent()
            
        if parent and hasattr(parent, "canvas"):
            # Create block
            block = block_class()
            
            # Add to canvas
            parent.canvas.add_block(block)
    
    def highlight_block_category(self, block):
        """Highlight the category in the toolbox based on the selected block"""
        # This would be implemented differently with the new UI structure
        # For now, we're not implementing this feature since we've moved away from QToolBox
        pass