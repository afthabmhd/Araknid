from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QWidget, 
                            QVBoxLayout, QGraphicsRectItem, QMenu, QGraphicsProxyWidget,
                            QGraphicsEllipseItem, QFrame, QLabel, QHBoxLayout, QPushButton,
                            QLineEdit, QTextEdit, QPlainTextEdit, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QEvent
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QIcon

from blocks.base import Block

class BlockCanvas(QWidget):
    """Canvas for displaying and interacting with code blocks"""
    
    # Signals
    block_selected = pyqtSignal(Block)
    
    def __init__(self, block_manager, code_generator):
        super().__init__()
        
        self.block_manager = block_manager
        self.code_generator = code_generator
        
        # Create UI components
        self._setup_ui()
        
        # Setup undo/redo history
        self.undo_stack = []
        self.redo_stack = []
        
        # Track state
        self.current_scale = 1.0
        
    def _setup_ui(self):
        """Set up the UI components with Flyde-style design"""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # Add header with canvas tools - Flyde dark theme style
        header = QFrame()
        header.setFrameShape(QFrame.NoFrame)
        header.setStyleSheet("background-color: #252526;")  # Dark background to match theme
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 5, 12, 5)
        
        # Add zoom controls with themed styling
        zoom_label = QLabel("Zoom:")
        zoom_label.setFont(QFont("Segoe UI", 9))
        zoom_label.setStyleSheet("color: #e0e0e0;")  # Light text for dark background
        header_layout.addWidget(zoom_label)
        
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedSize(28, 28)
        zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
        """)
        zoom_out_btn.clicked.connect(self.zoom_out)
        header_layout.addWidget(zoom_out_btn)
        
        self.zoom_display = QLabel("100%")
        self.zoom_display.setFont(QFont("Segoe UI", 9))
        self.zoom_display.setFixedWidth(50)
        self.zoom_display.setAlignment(Qt.AlignCenter)
        self.zoom_display.setStyleSheet("color: #e0e0e0;")  # Light text for dark background
        header_layout.addWidget(self.zoom_display)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(28, 28)
        zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
        """)
        zoom_in_btn.clicked.connect(self.zoom_in)
        header_layout.addWidget(zoom_in_btn)
        
        zoom_reset_btn = QPushButton("Reset")
        zoom_reset_btn.setFixedSize(60, 28)
        zoom_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
        """)
        zoom_reset_btn.clicked.connect(self.reset_zoom)
        header_layout.addWidget(zoom_reset_btn)
        
        # Add spacing
        header_layout.addStretch()
        
        # Add canvas controls
        center_btn = QPushButton("Center View")
        center_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
        """)
        center_btn.clicked.connect(lambda: self.view.centerOn(0, 0))
        header_layout.addWidget(center_btn)
        
        # Add header to main layout
        layout.addWidget(header)
        
        # Create graphics scene - Much larger for infinite scrolling
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QColor("#f8f9fa"))  # Light gray background
        
        # Set a large initial scene rect that will grow as needed
        self.scene.setSceneRect(-10000, -10000, 20000, 20000)
        
        # Add origin marker for reference - more subtle in Flyde style
        origin_marker = QGraphicsEllipseItem(-4, -4, 8, 8)
        origin_marker.setBrush(QBrush(QColor(120, 170, 255, 150)))  # Semi-transparent blue
        origin_marker.setPen(QPen(Qt.NoPen))
        self.scene.addItem(origin_marker)
        
        # Create graphics view with infinite scrolling support
        self.view = InfiniteCanvasView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setStyleSheet("""
            QGraphicsView {
                border: none;
                background-color: #f8f9fa;
            }
        """)
        layout.addWidget(self.view)
        
        # Connect signals
        self.scene.selectionChanged.connect(self._handle_selection_changed)
    
    def add_block(self, block, position=None):
        """Add a block to the canvas"""
        # Add the block to the scene
        self.scene.addItem(block)
        
        # Position the block
        if position:
            block.setPos(position)
        else:
            # Center in view if no position specified
            view_center = self.view.mapToScene(self.view.viewport().rect().center())
            block.setPos(view_center - QPointF(block.width / 2, block.height / 2))
        
        # Add to block manager
        self.block_manager.add_block(block)
        
        # Save state for undo
        self._save_state()
        
        return block
    
    def delete_selected(self):
        """Delete the selected blocks"""
        selected_items = self.scene.selectedItems()
        
        if not selected_items:
            return
            
        # Save state for undo
        self._save_state()
        
        for item in selected_items:
            if isinstance(item, Block):
                # First, disconnect all connections
                for name, point in item.connection_points.items():
                    if point.connection_line and point.connected_to:
                        # Remove the connection line from scene
                        self.scene.removeItem(point.connection_line)
                        
                        # Clear references in the connected point
                        if point.connected_to:
                            point.connected_to.connection_line = None
                            point.connected_to.connected_to = None
                            
                        # Clear references in this point
                        point.connection_line = None
                        point.connected_to = None
                
                # Now remove the block
                self.block_manager.remove_block(item)
                self.scene.removeItem(item)
    
    def clear(self):
        """Clear all blocks from the canvas"""
        # Save state for undo
        self._save_state()
        
        # Clear all blocks
        for item in list(self.scene.items()):  # Create a copy of the list to safely iterate
            if isinstance(item, Block):
                # First, disconnect all connections
                for name, point in item.connection_points.items():
                    if point.connection_line and point.connected_to:
                        # Remove the connection line from scene
                        self.scene.removeItem(point.connection_line)
                        
                        # Clear references in the connected point
                        if point.connected_to:
                            point.connected_to.connection_line = None
                            point.connected_to.connected_to = None
                            
                        # Clear references in this point
                        point.connection_line = None
                        point.connected_to = None
                
                # Now remove the block
                self.scene.removeItem(item)
                
        # Clear block manager
        self.block_manager.clear()
    
    def load_blocks(self, blocks):
        """Load blocks onto the canvas"""
        # Save state for undo
        self._save_state()
        
        # Clear existing blocks
        self.clear()
        
        # Add blocks to scene
        for block in blocks:
            self.scene.addItem(block)
            
        # Trigger update
        self.scene.update()
    
    def zoom_in(self):
        """Zoom in the view - Flyde style with smooth scaling"""
        scale_factor = 1.2
        self.current_scale *= scale_factor
        self.view.scale(scale_factor, scale_factor)
        
        # Update zoom display - Flyde style
        zoom_percent = int(self.current_scale * 100)
        self.zoom_display.setText(f"{zoom_percent}%")
    
    def zoom_out(self):
        """Zoom out the view - Flyde style with smooth scaling"""
        scale_factor = 1 / 1.2
        self.current_scale *= scale_factor
        self.view.scale(scale_factor, scale_factor)
        
        # Update zoom display - Flyde style
        zoom_percent = int(self.current_scale * 100)
        self.zoom_display.setText(f"{zoom_percent}%")
    
    def reset_zoom(self):
        """Reset zoom to 100% - Flyde style"""
        self.view.resetTransform()
        self.current_scale = 1.0
        
        # Update zoom display - Flyde style
        self.zoom_display.setText("100%")
    
    def undo(self):
        """Undo the last action"""
        if not self.undo_stack:
            return
            
        # Save current state to redo stack
        current_blocks = self.block_manager.get_all_blocks()
        self.redo_stack.append(current_blocks)
        
        # Restore previous state
        previous_blocks = self.undo_stack.pop()
        self.load_blocks(previous_blocks)
    
    def redo(self):
        """Redo the last undone action"""
        if not self.redo_stack:
            return
            
        # Save current state to undo stack
        current_blocks = self.block_manager.get_all_blocks()
        self.undo_stack.append(current_blocks)
        
        # Restore next state
        next_blocks = self.redo_stack.pop()
        self.load_blocks(next_blocks)
    
    def _save_state(self):
        """Save the current state for undo/redo"""
        current_blocks = self.block_manager.get_all_blocks()
        self.undo_stack.append(current_blocks)
        self.redo_stack.clear()  # Clear redo stack when a new action is performed
    
    def _handle_selection_changed(self):
        """Handle selection changes in the scene"""
        selected_items = self.scene.selectedItems()
        
        if selected_items:
            for item in selected_items:
                if isinstance(item, Block):
                    self.block_selected.emit(item)
                    break


class InfiniteCanvasView(QGraphicsView):
    """Graphics view supporting infinite scrolling canvas - Flyde style"""
    
    def __init__(self, scene):
        super().__init__(scene)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Set scroll bar policies - hide scrollbars for cleaner look
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Viewport update mode for better handling of input fields
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # Add keyboard focus policy
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Support for middle-button panning
        self._panning = False
        self._pan_start_pos = None
        
        # Set a nice transition effect for smoother zooming
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
    def drawBackground(self, painter, rect):
        """Draw the infinite grid background - Flyde style"""
        super().drawBackground(painter, rect)
        
        # Define grid settings - more subtle for Flyde look
        grid_size = 20
        minor_grid_color = QColor(240, 240, 240)  # Very light gray for minor gridlines
        major_grid_color = QColor(230, 230, 230)  # Slightly darker for major gridlines
        
        # Calculate grid starting and ending points
        left = int(rect.left() - (rect.left() % grid_size))
        top = int(rect.top() - (rect.top() % grid_size))
        
        # Create a clean white/light background
        painter.fillRect(rect, QColor("#f8f9fa"))  # Light background - Flyde style
        
        # Draw the grid lines
        painter.setPen(QPen(minor_grid_color, 0.5))
        
        # Draw vertical grid lines
        for x in range(left, int(rect.right()), grid_size):
            # Make major grid lines slightly darker
            if x % (grid_size * 5) == 0:
                painter.setPen(QPen(major_grid_color, 0.8))
            else:
                painter.setPen(QPen(minor_grid_color, 0.5))
            # Convert to integers
            painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
        
        # Draw horizontal grid lines
        for y in range(top, int(rect.bottom()), grid_size):
            # Make major grid lines slightly darker
            if y % (grid_size * 5) == 0:
                painter.setPen(QPen(major_grid_color, 0.8))
            else:
                painter.setPen(QPen(minor_grid_color, 0.5))
            # Convert to integers
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
        
        # Draw origin lines with semi-transparent blue - Flyde style
        painter.setPen(QPen(QColor(120, 170, 255, 70), 1))  # Light blue, very subtle
        # Convert to integers for these lines too
        painter.drawLine(int(rect.left()), 0, int(rect.right()), 0)  # Horizontal axis
        painter.drawLine(0, int(rect.top()), 0, int(rect.bottom()))  # Vertical axis
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming - Flyde style with smooth zooming"""
        if event.modifiers() & Qt.ControlModifier:
            # Zoom with Ctrl+Wheel
            zoom_factor = 1.15  # Slightly more subtle zoom increments
            
            # Get the scene position before scaling
            old_pos = self.mapToScene(event.pos())
            
            if event.angleDelta().y() > 0:
                # Zoom in
                self.scale(zoom_factor, zoom_factor)
            else:
                # Zoom out
                self.scale(1.0 / zoom_factor, 1.0 / zoom_factor)
            
            # Get the new position and move the scene to keep the point under mouse
            new_pos = self.mapToScene(event.pos())
            delta = new_pos - old_pos
            self.translate(delta.x(), delta.y())
            
            # Update zoom level in parent widget if it exists
            parent = self.parent()
            if parent and hasattr(parent, 'current_scale'):
                if event.angleDelta().y() > 0:
                    parent.current_scale *= zoom_factor
                else:
                    parent.current_scale /= zoom_factor
                
                if hasattr(parent, 'zoom_display'):
                    zoom_percent = int(parent.current_scale * 100)
                    parent.zoom_display.setText(f"{zoom_percent}%")
                
            event.accept()
        else:
            # Normal scrolling
            super().wheelEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press events - Flyde style with improved dragging"""
        # Middle button panning
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
            
        # Check if we clicked on an input field
        item = self.itemAt(event.pos())
        if item and isinstance(item, QGraphicsProxyWidget):
            # Forward the event to the item
            super().mousePressEvent(event)
        elif item and hasattr(item, 'parentItem') and item.parentItem() and isinstance(item.parentItem(), Block):
            # The click is on a block, check if it contains input fields
            block = item.parentItem()
            if hasattr(block, 'proxies'):
                for proxy in block.proxies.values():
                    if proxy.contains(proxy.mapFromScene(self.mapToScene(event.pos()))):
                        # Forward the event to the proxy
                        super().mousePressEvent(event)
                        return
                
            # Not on an input field, handle normally
            super().mousePressEvent(event)
        else:
            # Normal handling for other items
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events - Flyde style with smooth panning"""
        if self._panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            
            # Pan the view - smoother panning for Flyde style
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            
            event.accept()
            return
            
        super().mouseMoveEvent(event)
        
        # Expand scene rect if we're getting close to the edge
        scene_pos = self.mapToScene(event.pos())
        self._expand_scene_if_needed(scene_pos)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
            
        super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event):
        """Handle key press events - simplified without spacebar drag"""
        # Just pass the event to the parent class
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        """Handle key release events - simplified without spacebar drag"""
        # Just pass the event to the parent class
        super().keyReleaseEvent(event)
    
    def _expand_scene_if_needed(self, pos):
        """Expand the scene rect if we're getting close to the edge"""
        # Get current scene rect
        scene_rect = self.scene().sceneRect()
        
        # Define a margin - we'll expand if we get this close to the edge
        margin = 500
        expanded = False
        
        # Check if we need to expand in any direction
        if pos.x() > scene_rect.right() - margin:
            scene_rect.setRight(scene_rect.right() + 1000)
            expanded = True
            
        if pos.x() < scene_rect.left() + margin:
            scene_rect.setLeft(scene_rect.left() - 1000)
            expanded = True
            
        if pos.y() > scene_rect.bottom() - margin:
            scene_rect.setBottom(scene_rect.bottom() + 1000)
            expanded = True
            
        if pos.y() < scene_rect.top() + margin:
            scene_rect.setTop(scene_rect.top() - 1000)
            expanded = True
            
        # Apply the new scene rect if expanded
        if expanded:
            self.scene().setSceneRect(scene_rect)
    
    def contextMenuEvent(self, event):
        """Show context menu - Flyde style with modern UI"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 25px 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #e9ecef;
                color: #212529;
            }
            QMenu::separator {
                height: 1px;
                background-color: #dee2e6;
                margin: 5px 0px;
            }
        """)
        
        # Check if there are selected items
        if self.scene().selectedItems():
            delete_action = menu.addAction("Delete")
            copy_action = menu.addAction("Copy")
            cut_action = menu.addAction("Cut")
        else:
            paste_action = menu.addAction("Paste")
        
        menu.addSeparator()

        zoom_in_action = menu.addAction("Zoom In")
        zoom_out_action = menu.addAction("Zoom Out")
        reset_zoom_action = menu.addAction("Reset Zoom")
        center_origin_action = menu.addAction("Go to Origin")
        
        # Show the menu and handle actions
        action = menu.exec_(event.globalPos())
        
        if action:
            if "Delete" in action.text():
                # Find parent canvas and delete selected
                canvas = self.parent()
                if hasattr(canvas, "delete_selected"):
                    canvas.delete_selected()
            elif "Zoom In" in action.text():
                # Get parent canvas for zoom handling
                canvas = self.parent()
                if hasattr(canvas, "zoom_in"):
                    canvas.zoom_in()
                else:
                    self.scale(1.2, 1.2)
            elif "Zoom Out" in action.text():
                # Get parent canvas for zoom handling
                canvas = self.parent()
                if hasattr(canvas, "zoom_out"):
                    canvas.zoom_out()
                else:
                    self.scale(1/1.2, 1/1.2)
            elif "Reset Zoom" in action.text():
                # Get parent canvas for zoom handling
                canvas = self.parent()
                if hasattr(canvas, "reset_zoom"):
                    canvas.reset_zoom()
                else:
                    self.resetTransform()
            elif "Go to Origin" in action.text():
                # Center view on origin (0,0)
                self.centerOn(0, 0)
