from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsProxyWidget, 
                             QGraphicsSceneMouseEvent, QWidget, QFormLayout,
                             QLineEdit, QComboBox, QLabel, QGraphicsLineItem,
                             QGraphicsEllipseItem)
from PyQt5.QtGui import (QPainter, QPainterPath, QColor, QPen, QBrush, QFont, 
                        QLinearGradient, QPainterPathStroker, QCursor)
from PyQt5.QtCore import Qt, QRectF, QPointF, QEvent, QLineF, pyqtSignal

class ConnectionPoint(QGraphicsEllipseItem):
    """Interactive connection point for blocks"""
    
    def __init__(self, x, y, parent=None, connection_type=None, name=None):
        """
        Create a connection point
        
        Args:
            x, y: local coordinates for the point
            parent: parent block
            connection_type: the type of connection (TOP, BOTTOM, INNER, LEFT, RIGHT)
            name: name identifier for the connection point
        """
        size = 12  # Increased size for better visibility - Flyde style
        super().__init__(x - size/2, y - size/2, size, size, parent)
        
        self.connection_type = connection_type
        self.name = name
        self.parent_block = parent
        self.connected_to = None  # The connection point this is connected to
        self.connection_line = None  # Visual line showing connection
        
        # Make it interactive
        self.setAcceptHoverEvents(True)
        self.setBrush(QBrush(QColor(60, 60, 60)))  # Darker shade when inactive - Flyde style
        self.setPen(QPen(Qt.NoPen))  # No border - cleaner look like Flyde
        self.setZValue(2)  # Above blocks but below temp connection line
        
        # Track if we're currently drawing a line
        self.temp_line = None
        self.scene_pos = None
        
    def hoverEnterEvent(self, event):
        """Highlight the connection point when hovered"""
        self.setBrush(QBrush(QColor(120, 170, 255)))  # Bright blue for hover - Flyde style
        self.setCursor(QCursor(Qt.PointingHandCursor))  # Hand cursor on hover
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Remove highlight when hover ends"""
        self.setBrush(QBrush(QColor(60, 60, 60)))  # Back to original color
        self.setCursor(QCursor(Qt.ArrowCursor))  # Reset cursor
        super().hoverLeaveEvent(event)
        
    def mousePressEvent(self, event):
        """Start drawing a connection line when clicked"""
        if event.button() == Qt.LeftButton:
            # Get position in scene coordinates
            self.scene_pos = self.scenePos()
            
            # Create a temporary line for visual feedback
            end_point = self.mapToScene(event.pos())
            self.temp_line = QGraphicsLineItem(QLineF(self.scene_pos, end_point))
            
            # Flyde-style connection line
            pen = QPen(QColor(120, 170, 255), 2, Qt.SolidLine)
            pen.setCapStyle(Qt.RoundCap)
            self.temp_line.setPen(pen)
            self.scene().addItem(self.temp_line)
            
            # Take ownership of the mouse until release
            event.accept()
            
    def mouseMoveEvent(self, event):
        """Update the temporary line as mouse moves"""
        if self.temp_line:
            end_point = self.mapToScene(event.pos())
            self.temp_line.setLine(QLineF(self.scene_pos, end_point))
            event.accept()
            
    def mouseReleaseEvent(self, event):
        """Finalize the connection when mouse is released"""
        if self.temp_line and event.button() == Qt.LeftButton:
            # Remove the temporary line
            if self.scene():
                self.scene().removeItem(self.temp_line)
            self.temp_line = None
            
            # Find if we're over another connection point
            end_pos = self.mapToScene(event.pos())
            if self.scene():
                target_item = self.scene().itemAt(end_pos, self.scene().views()[0].transform())
                
                # If we found a connection point, connect to it
                if isinstance(target_item, ConnectionPoint) and target_item != self:
                    self.connect_to(target_item)
                
            event.accept()
                
    def connect_to(self, target_point):
        """Connect this point to another connection point"""
        # First, disconnect any existing connections
        # If this point is already connected to something
        if self.connected_to:
            # Clear the other point's reference to this connection
            if self.connected_to.connection_line == self.connection_line:
                self.connected_to.connection_line = None
            if self.connected_to.connected_to == self:
                self.connected_to.connected_to = None
                
            # Clear block connection if applicable
            if self.parent_block and self.connected_to.parent_block:
                self._disconnect_blocks(self.parent_block, self.connected_to.parent_block, 
                                      self.connection_type, self.connected_to.connection_type)
            
            # Remove the line visual
            if self.connection_line and self.scene():
                self.scene().removeItem(self.connection_line)
            self.connection_line = None
            self.connected_to = None
        
        # If target is already connected to something
        if target_point.connected_to:
            # Clear the other point's reference to this connection
            if target_point.connected_to.connection_line == target_point.connection_line:
                target_point.connected_to.connection_line = None
            if target_point.connected_to.connected_to == target_point:
                target_point.connected_to.connected_to = None
                
            # Clear block connection if applicable
            if target_point.parent_block and target_point.connected_to.parent_block:
                self._disconnect_blocks(target_point.parent_block, target_point.connected_to.parent_block,
                                      target_point.connection_type, target_point.connected_to.connection_type)
            
            # Remove the line visual
            if target_point.connection_line and target_point.scene():
                target_point.scene().removeItem(target_point.connection_line)
            target_point.connection_line = None
            target_point.connected_to = None
        
        # Create permanent connection line
        line = ConnectionLine(self, target_point)
        if self.scene():
            self.scene().addItem(line)
        
        # Update both points to reference each other
        self.connection_line = line
        self.connected_to = target_point
        target_point.connection_line = line
        target_point.connected_to = self
        
        # Connect the parent blocks
        if self.parent_block and target_point.parent_block:
            # The connection type depends on which points are being connected
            self.parent_block.connect_points(self, target_point)
            
        # Trigger code update
        if self.scene():
            # Notify the block manager to update the code
            scene = self.scene()
            if hasattr(scene, 'views') and scene.views():
                view = scene.views()[0]
                if hasattr(view, 'parent') and view.parent():
                    canvas = view.parent()
                    if hasattr(canvas, 'block_manager'):
                        canvas.block_manager.trigger_blocks_changed()
    
    def _disconnect_blocks(self, block1, block2, type1, type2):
        """Helper to disconnect blocks in the block model"""
        # Clear connections between blocks based on connection types
        if type1 == block1.BOTTOM and type2 == block2.TOP:
            block1.connected_blocks[block1.BOTTOM] = None
            block2.connected_blocks[block2.TOP] = None
            
        elif type1 == block1.TOP and type2 == block2.BOTTOM:
            block1.connected_blocks[block1.TOP] = None
            block2.connected_blocks[block2.BOTTOM] = None
            
        elif type1 == block1.INNER and type2 == block2.TOP:
            block1.connected_blocks[block1.INNER] = None
            block2.connected_blocks[block2.TOP] = None
            
        elif type1 == block1.LEFT and type2 == block2.RIGHT:
            block1.connected_blocks[block1.LEFT] = None
            block2.connected_blocks[block2.RIGHT] = None
            
        elif type1 == block1.RIGHT and type2 == block2.LEFT:
            block1.connected_blocks[block1.RIGHT] = None
            block2.connected_blocks[block2.LEFT] = None
            
    def update_connection_line(self):
        """Update the position of the connection line if it exists"""
        if self.connection_line:
            self.connection_line.update_position()
            
    def scenePos(self):
        """Get position in scene coordinates"""
        return self.mapToScene(self.rect().center())

class ConnectionLine(QGraphicsLineItem):
    """Visual line connecting two connection points"""
    
    def __init__(self, from_point, to_point, parent=None):
        """
        Create a connection line between two points
        
        Args:
            from_point: starting ConnectionPoint
            to_point: ending ConnectionPoint
            parent: parent item
        """
        super().__init__(parent)
        self.from_point = from_point
        self.to_point = to_point
        
        # Set line style - Flyde style with curved, animated connections
        pen = QPen(QColor(120, 170, 255), 2)
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)
        self.setZValue(-1)  # Draw below blocks and connection points
        
        # Initial position
        self.update_position()
        
    def update_position(self):
        """Update the line position based on connection points"""
        if self.from_point and self.to_point:
            self.setLine(QLineF(self.from_point.scenePos(), self.to_point.scenePos()))
            
class Block(QGraphicsItem):
    """Base class for all code blocks in Araknid"""
    
    # Block types
    STACK = 0      # Standard block with top/bottom connections
    C_BLOCK = 1    # Control structure with inner connections
    HAT = 2        # Function declaration (only bottom connection)
    OVAL = 3       # Expression/condition
    SPECIAL = 4    # Special blocks like 'else'
    
    # Block categories for coloring
    VARIABLE = 0
    CONTROL = 1
    IO = 2
    OPERATOR = 3
    FUNCTION = 4
    ALGORITHM = 5
    
    # Connection points
    TOP = 0
    BOTTOM = 1
    INNER = 2
    LEFT = 3
    RIGHT = 4
    
    def __init__(self, block_type=STACK, category=VARIABLE, text="Block"):
        super().__init__()
        
        # Block properties
        self.block_type = block_type
        self.category = category
        self.text = text
        
        # Set dimensions - Flyde style with more modern proportions and more padding
        self.width = 260  # Wider to accommodate padding
        self.height = 90  # Taller to accommodate padding
        
        # Padding settings - add more space inside blocks
        self.padding_left = 20
        self.padding_right = 20
        self.padding_top = 10
        self.padding_bottom = 10
        
        # Interactive connection points
        self.connection_points = {}
            
        # Input fields
        self.inputs = {}
        self.proxies = {}
        
        # Connection properties - which blocks this is connected to
        self.connected_blocks = {
            self.TOP: None,
            self.BOTTOM: None,
            self.INNER: None,
            self.LEFT: None,
            self.RIGHT: None
        }
        
        # Connection point definitions - Flyde-style positioning
        self.connection_defs = {
            'top': {'pos': (self.width/2, 0), 'type': self.TOP, 'enabled': True},
            'bottom': {'pos': (self.width/2, self.height), 'type': self.BOTTOM, 'enabled': True},
            'nested': {'pos': (self.width, self.height/2), 'type': self.INNER, 'enabled': False},
            'left': {'pos': (0, self.height/2), 'type': self.LEFT, 'enabled': False},
            'right': {'pos': (self.width, self.height/2), 'type': self.RIGHT, 'enabled': False}
        }
        
        # Visual properties - Flyde-inspired colors
        self.category_colors = {
            self.VARIABLE: QColor("#4a9df3"),     # Blue (Variables)
            self.CONTROL: QColor("#e6b422"),      # Gold/Amber (Control)
            self.IO: QColor("#9c3fb3"),           # Purple (IO)
            self.OPERATOR: QColor("#4cb32b"),     # Green (Operators)
            self.FUNCTION: QColor("#df71df"),     # Pink (Functions)
            self.ALGORITHM: QColor("#8254d8")     # BlueViolet (Algorithms)
        }
        
        # Setup
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
        # Properties for connection handling
        self.highlight_connection = False
        self.setFiltersChildEvents(False)  # Allow child widgets to receive events
        
    def _create_connection_points(self):
        """Create all enabled connection points"""
        for name, config in self.connection_defs.items():
            if config['enabled']:
                x, y = config['pos']
                conn_type = config['type']
                
                # Create the connection point
                point = ConnectionPoint(x, y, self, conn_type, name)
                self.connection_points[name] = point
                
    def boundingRect(self):
        """Define the bounding rectangle for the block"""
        # Add a little padding to account for shadow/highlight and connection points
        return QRectF(-12, -12, self.width + 24, self.height + 24)
    
    def paint(self, painter, option, widget):
        """Draw the block as a rectangle with connection points - Flyde style"""
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get the base color based on category
        color = self.category_colors.get(self.category, QColor(100, 100, 100))
        
        # Create slightly darker color for the border
        border_color = QColor(color)
        border_color.setAlphaF(0.7)  # Semi-transparent border
        
        # Draw the block as a rounded rectangle - Flyde style
        rect = QRectF(0, 0, self.width, self.height)
        
        # Shadow effect for depth - Flyde style
        shadow_rect = QRectF(2, 2, self.width, self.height)
        shadow_color = QColor(0, 0, 0, 40)  # Semi-transparent black
        painter.setPen(Qt.NoPen)
        painter.setBrush(shadow_color)
        painter.drawRoundedRect(shadow_rect, 8, 8)  # 8px corner radius
        
        # Main block gradient - Flyde style
        gradient = QLinearGradient(0, 0, 0, self.height)
        lighter_color = QColor(color)
        lighter_color.setAlphaF(0.2)  # Very light fill for modern look
        
        # Background with category color highlights
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(QBrush(QColor(248, 250, 252)))  # Light background
        painter.drawRoundedRect(rect, 8, 8)  # 8px corner radius
        
        # Category color indicator on left side - Flyde style
        indicator_rect = QRectF(0, 0, 8, self.height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        indicator_path = QPainterPath()
        indicator_path.addRoundedRect(indicator_rect, 8, 8)
        indicator_path.setFillRule(Qt.WindingFill)
        painter.drawPath(indicator_path)
        
        # Draw the block title - bold, modern font - Flyde style
        painter.setPen(QColor(52, 58, 64))  # Dark gray for text
        font = QFont("Segoe UI", 11, QFont.Bold)  # Modern font
        painter.setFont(font)
        
        # Text positioning - increased left padding
        text_rect = QRectF(self.padding_left, self.padding_top, self.width - self.padding_left - self.padding_right, 24)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.text)
        
        # Add separator line under title - Flyde style (with padding)
        painter.setPen(QPen(QColor(230, 230, 230), 1))
        painter.drawLine(self.padding_left, self.padding_top + 24 + 4, self.width - self.padding_right, self.padding_top + 24 + 4)
        
        # If selected, draw a highlight
        if self.isSelected():
            highlight_rect = QRectF(0, 0, self.width, self.height)
            highlight_pen = QPen(QColor(120, 170, 255), 2)  # Flyde-style blue highlight
            painter.setPen(highlight_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(highlight_rect, 8, 8)
            
        # If this block is a potential connection target, draw a connection highlight
        if hasattr(self, 'highlight_connection') and self.highlight_connection:
            highlight_rect = QRectF(0, 0, self.width, self.height)
            highlight_pen = QPen(QColor(120, 170, 255, 180), 3)  # Flyde-style blue highlight
            painter.setPen(highlight_pen)
            painter.setBrush(QColor(120, 170, 255, 30))  # Very light fill
            painter.drawRoundedRect(highlight_rect, 8, 8)
    
    def add_input_field(self, name, label="", field_type="text", options=None, default_value=""):
        """Add an input field to the block - Flyde style with improved padding"""
        input_widget = QWidget()
        layout = QFormLayout(input_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)  # Increased spacing between label and field
        
        # Calculate maximum allowed field width to ensure proper padding
        available_width = self.width - self.padding_left - self.padding_right - 20  # Reserve additional 20px padding
        
        # Set the initial field width based on available space
        field_width = min(available_width - (len(label) * 8 if label else 0), 140)
        field_width = max(field_width, 80)  # Ensure minimum width of 80px
        
        # Create appropriate field based on type
        if field_type == "text":
            field = QLineEdit(default_value)
            field.setFixedWidth(field_width)  # Fixed width to ensure proper sizing
            field.setMinimumHeight(26)  # Slightly taller fields for better usability
            # Make text editable and selectable
            field.setReadOnly(False)
            field.setFocusPolicy(Qt.StrongFocus)
            # Modern style for input fields
            field.setStyleSheet("""
                QLineEdit {
                    background-color: #f8f9fa;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 2px 8px;
                }
                QLineEdit:focus {
                    border: 1px solid #80bdff;
                }
            """)
            # Connect to change signals
            field.textChanged.connect(lambda: self._notify_input_changed())
        elif field_type == "combo" and options:
            field = QComboBox()
            field.addItems(options)
            if default_value in options:
                field.setCurrentText(default_value)
            field.setFixedWidth(field_width)  # Fixed width to ensure proper sizing
            field.setMinimumHeight(26)
            field.setFocusPolicy(Qt.StrongFocus)
            # Modern style for dropdown
            field.setStyleSheet("""
                QComboBox {
                    background-color: #f8f9fa;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 2px 8px;
                }
                QComboBox:focus {
                    border: 1px solid #80bdff;
                }
            """)
            # Connect to change signals  
            field.currentTextChanged.connect(lambda: self._notify_input_changed())
        else:
            field = QLineEdit(default_value)
            field.setFixedWidth(field_width)  # Fixed width to ensure proper sizing
            field.setMinimumHeight(26)
            field.setReadOnly(False)
            field.setFocusPolicy(Qt.StrongFocus)
            # Modern style for input fields
            field.setStyleSheet("""
                QLineEdit {
                    background-color: #f8f9fa;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 2px 8px;
                }
                QLineEdit:focus {
                    border: 1px solid #80bdff;
                }
            """)
            # Connect to change signals
            field.textChanged.connect(lambda: self._notify_input_changed())
        
        # Set the font to be modern but readable
        font = QFont("Segoe UI", 9)
        field.setFont(font)
        
        # Add to layout with or without label
        if label:
            label_widget = QLabel(label)
            label_widget.setFont(font)
            label_widget.setStyleSheet("color: #495057;")  # Dark gray for text
            layout.addRow(label_widget, field)
        else:
            layout.addWidget(field)
        
        # Store the field
        self.inputs[name] = field
        
        # Create a proxy widget for the input field
        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(input_widget)
        self.proxies[name] = proxy
        
        # Calculate position based on existing proxies
        # This ensures fields are stacked properly
        existing_proxies = len(self.proxies) - 1  # Subtract 1 for current proxy
        
        # Position all fields with Flyde-style layout - increased padding
        pos_x = self.padding_left + 4  # Indent from left edge with padding
        pos_y = self.padding_top + 36 + (existing_proxies * 32)  # Start below title separator with good spacing
        
        # Adjust the block width if necessary to accommodate fields
        total_field_width = field_width + (len(label) * 8 if label else 0) + 40  # Add extra padding
        required_width = max(self.width, total_field_width + self.padding_left + self.padding_right)
        
        if required_width > self.width:
            self.width = required_width
            # Update connection points that depend on width
            self._update_connection_points_positions()
        
        # Adjust the block height if needed
        required_height = (existing_proxies + 1) * 32 + 50 + self.padding_top + self.padding_bottom  # Base height plus fields plus padding
        if required_height > self.height:
            self.height = required_height
            
            # Update position of connection points that depend on height
            self._update_connection_points_positions()
        
        # Set the position
        proxy.setPos(pos_x, pos_y)
        
        return field
    
    def _update_connection_points_positions(self):
        """Update the positions of connection points when block height changes"""
        # Update connection definitions for Flyde-style centered connections
        if 'top' in self.connection_defs:
            self.connection_defs['top']['pos'] = (self.width/2, 0)
        if 'bottom' in self.connection_defs:
            self.connection_defs['bottom']['pos'] = (self.width/2, self.height)
        if 'left' in self.connection_defs:
            self.connection_defs['left']['pos'] = (0, self.height/2)
        if 'right' in self.connection_defs:
            self.connection_defs['right']['pos'] = (self.width, self.height/2)
        if 'nested' in self.connection_defs:
            self.connection_defs['nested']['pos'] = (self.width, self.height/2)
        
        # Update existing connection points
        for name, point in self.connection_points.items():
            if name in self.connection_defs:
                x, y = self.connection_defs[name]['pos']
                size = point.rect().width()
                point.setRect(x - size/2, y - size/2, size, size)
                
                # Update any connected lines
                point.update_connection_line()
    
    def _notify_input_changed(self):
        """Notify that an input field value has changed"""
        # Find the scene and notify it about the change
        if self.scene():
            # Signal the block manager via the scene
            scene = self.scene()
            if hasattr(scene, 'views') and scene.views():
                view = scene.views()[0]
                if hasattr(view, 'parent') and view.parent():
                    canvas = view.parent()
                    if hasattr(canvas, 'block_manager'):
                        # Trigger update in block manager
                        canvas.block_manager.trigger_blocks_changed()
    
    def get_input_value(self, name):
        """Get the value from an input field"""
        if name in self.inputs:
            field = self.inputs[name]
            if isinstance(field, QLineEdit):
                return field.text()
            elif isinstance(field, QComboBox):
                return field.currentText()
        return ""
    
    def connect_points(self, from_point, to_point):
        """
        Connect blocks based on connection point types
        
        Args:
            from_point: The connection point from this block
            to_point: The connection point from another block
        """
        # Determine connection types
        from_type = from_point.connection_type
        to_type = to_point.connection_type
        other_block = to_point.parent_block
        
        # The connection depends on which types of points are connected
        if from_type == self.BOTTOM and to_type == self.TOP:
            # Bottom of this block to top of other
            self.connected_blocks[self.BOTTOM] = other_block
            other_block.connected_blocks[other_block.TOP] = self
            
        elif from_type == self.TOP and to_type == self.BOTTOM:
            # Top of this block to bottom of other
            self.connected_blocks[self.TOP] = other_block
            other_block.connected_blocks[other_block.BOTTOM] = self
            
        elif from_type == self.INNER and to_type == self.TOP:
            # Inner connection of this block to top of other
            self.connected_blocks[self.INNER] = other_block
            other_block.connected_blocks[other_block.TOP] = self
            
        elif from_type == self.LEFT and to_type == self.RIGHT:
            # Left of this block to right of other
            self.connected_blocks[self.LEFT] = other_block
            other_block.connected_blocks[other_block.RIGHT] = self
            
        elif from_type == self.RIGHT and to_type == self.LEFT:
            # Right of this block to left of other
            self.connected_blocks[self.RIGHT] = other_block
            other_block.connected_blocks[other_block.LEFT] = self
    
    def sceneEvent(self, event):
        """Handle scene events to enable connection point interaction"""
        # Call the base implementation to handle standard events
        return super().sceneEvent(event)
    
    def itemChange(self, change, value):
        """Handle changes to the block's state"""
        if change == QGraphicsItem.ItemPositionHasChanged:
            # Update all connection lines when block position changes
            # Only update if connection_points is a dictionary of ConnectionPoint objects
            if hasattr(self, 'connection_points') and isinstance(self.connection_points, dict):
                for name, point in self.connection_points.items():
                    if hasattr(point, 'update_connection_line'):
                        point.update_connection_line()
        
        return super().itemChange(change, value)
    
    def sceneEventFilter(self, watched, event):
        """Filter scene events to properly handle input field interactions"""
        if isinstance(watched, QGraphicsProxyWidget):
            # Pass mouse events to input widgets
            if event.type() in [QEvent.GraphicsSceneMousePress, 
                               QEvent.GraphicsSceneMouseMove,
                               QEvent.GraphicsSceneMouseRelease]:
                # Allow the event to be handled by the input field
                return False
                
            # Pass key events to input widgets
            if event.type() in [QEvent.KeyPress, QEvent.KeyRelease]:
                return False
        
        # For other events, use default handling
        return super().sceneEventFilter(watched, event)
    
    def _get_all_connected_blocks(self, visited=None):
        """
        Get a list of all blocks connected to this one (to prevent circular connections)
        Uses a visited set to prevent infinite recursion
        """
        # Initialize visited set on first call to prevent infinite recursion
        if visited is None:
            visited = set()
        
        # Skip if we've already visited this block
        if self in visited:
            return []
        
        # Mark this block as visited
        visited.add(self)
        
        # This will hold all connected blocks
        connected = []
        
        # Check blocks connected above
        if self.connected_blocks[self.TOP] and self.connected_blocks[self.TOP] not in visited:
            connected.append(self.connected_blocks[self.TOP])
            connected.extend(self.connected_blocks[self.TOP]._get_all_connected_blocks(visited))
        
        # Check blocks connected below
        # Check blocks connected below
        if self.connected_blocks[self.BOTTOM] and self.connected_blocks[self.BOTTOM] not in visited:
            connected.append(self.connected_blocks[self.BOTTOM])
            connected.extend(self.connected_blocks[self.BOTTOM]._get_all_connected_blocks(visited))
        
        # Check blocks connected inside (for C-blocks)
        if self.connected_blocks[self.INNER] and self.connected_blocks[self.INNER] not in visited:
            connected.append(self.connected_blocks[self.INNER])
            connected.extend(self.connected_blocks[self.INNER]._get_all_connected_blocks(visited))
        
        # Check blocks connected to left and right (for operator blocks)
        if self.connected_blocks[self.LEFT] and self.connected_blocks[self.LEFT] not in visited:
            connected.append(self.connected_blocks[self.LEFT])
            connected.extend(self.connected_blocks[self.LEFT]._get_all_connected_blocks(visited))
        
        if self.connected_blocks[self.RIGHT] and self.connected_blocks[self.RIGHT] not in visited:
            connected.append(self.connected_blocks[self.RIGHT])
            connected.extend(self.connected_blocks[self.RIGHT]._get_all_connected_blocks(visited))
        
        return connected
    
    def _get_inner_blocks(self, visited=None):
        """Get all blocks inside this block (connected to INNER)"""
        if visited is None:
            visited = set()
            
        # Skip if we've already visited this block
        if self in visited:
            return []
            
        # Mark this block as visited
        visited.add(self)
        
        # List to hold inner blocks
        inner_blocks = []
        
        # First, add the direct inner block
        inner_block = self.connected_blocks[self.INNER]
        if inner_block and inner_block not in visited:
            inner_blocks.append(inner_block)
            visited.add(inner_block)
            
            # Follow the chain of bottom-connected blocks
            current = inner_block
            while current.connected_blocks[current.BOTTOM] and current.connected_blocks[current.BOTTOM] not in visited:
                current = current.connected_blocks[current.BOTTOM]
                inner_blocks.append(current)
                visited.add(current)
                
                # Also check any inner blocks of control structures
                if current.block_type == self.C_BLOCK:
                    inner_blocks.extend(current._get_inner_blocks(visited))
        
        return inner_blocks
    
    def generate_code_self(self, indent=0):
        """Generate code just for this block, with placeholders for nested/connected code"""
        # Base implementation - override in subclasses
        return " " * indent + "// Base block {{BOTTOM_CODE}}\n"

    def generate_code(self, indent=0, processed_blocks=None):
        """
        Generate C code for this block and all connected blocks
        
        Args:
            indent: Number of spaces to indent the code
            processed_blocks: Set of blocks that have already been processed
            
        Returns:
            Generated code string
        """
        if processed_blocks is None:
            processed_blocks = set()
            
        # Avoid processing the same block multiple times
        if self in processed_blocks:
            return ""
            
        # Mark this block as processed
        processed_blocks.add(self)
        
        # Get the code for this block with placeholders
        code = self.generate_code_self(indent)
        
        # Replace placeholders with actual code
        
        # Replace {{INNER_CODE}} placeholder with code from inner connected block
        if "{{INNER_CODE}}" in code and self.connected_blocks[self.INNER]:
            inner_block = self.connected_blocks[self.INNER]
            inner_code = inner_block.generate_code(indent + 4, processed_blocks)
            code = code.replace("{{INNER_CODE}}", inner_code)
        else:
            code = code.replace("{{INNER_CODE}}", "")
        
        # Replace {{BOTTOM_CODE}} placeholder with code from bottom connected block
        if "{{BOTTOM_CODE}}" in code and self.connected_blocks[self.BOTTOM]:
            bottom_block = self.connected_blocks[self.BOTTOM]
            bottom_code = bottom_block.generate_code(indent, processed_blocks)
            code = code.replace("{{BOTTOM_CODE}}", bottom_code)
        else:
            code = code.replace("{{BOTTOM_CODE}}", "")
            
        # Replace {{LEFT_CODE}} and {{RIGHT_CODE}} placeholders (for operator blocks)
        if "{{LEFT_CODE}}" in code and self.connected_blocks[self.LEFT]:
            left_block = self.connected_blocks[self.LEFT]
            left_code = left_block.generate_code(0, processed_blocks).strip()
            code = code.replace("{{LEFT_CODE}}", left_code or "a")
        else:
            code = code.replace("{{LEFT_CODE}}", "a")  # Default value
            
        if "{{RIGHT_CODE}}" in code and self.connected_blocks[self.RIGHT]:
            right_block = self.connected_blocks[self.RIGHT]
            right_code = right_block.generate_code(0, processed_blocks).strip()
            code = code.replace("{{RIGHT_CODE}}", right_code or "b")
        else:
            code = code.replace("{{RIGHT_CODE}}", "b")  # Default value
            
        return code
        
    def is_connected(self):
        """Check if this block is properly connected in the execution flow"""
        # For root blocks: Include and Function blocks are always valid
        if (self.__class__.__name__ == 'IncludeBlock' or 
            self.__class__.__name__ == 'FunctionDeclarationBlock' or
            self.__class__.__name__ == 'MainFunctionBlock'):
            return True
            
        # For blocks that are top-level inside a function or control structure
        if self.connected_blocks[self.TOP]:
            # Check if connected to a valid parent
            parent = self.connected_blocks[self.TOP]
            if parent and (parent.__class__.__name__ == 'FunctionDeclarationBlock' or
                           parent.__class__.__name__ == 'MainFunctionBlock' or
                           parent.__class__.__name__ == 'IfBlock' or
                           parent.__class__.__name__ == 'ElseBlock' or
                           parent.__class__.__name__ == 'ForLoopBlock' or
                           parent.__class__.__name__ == 'WhileLoopBlock'):
                return True
            
            # If parent is any other valid block
            if parent and parent.is_connected():
                return True
                
        # For blocks that are inside a C-Block (nested)
        # Check if this block is connected to the INNER connection of another block
        for block in self.blocks_from_scene():
            for connection_type in [block.INNER, block.BOTTOM, block.LEFT, block.RIGHT]:
                if block.connected_blocks[connection_type] == self and block.is_connected():
                    return True
            
        # If we reach here, the block is not properly connected
        return False
        
    def blocks_from_scene(self):
        """Get all blocks from the scene"""
        if self.scene():
            return [item for item in self.scene().items() if isinstance(item, Block)]
        return []