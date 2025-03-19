import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, QFileDialog, QAction, QMessageBox
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon, QFont

from ui.canvas import BlockCanvas
from ui.code_view import CodeView
from ui.toolbox import Toolbox
from core.block_manager import BlockManager
from core.code_generator import CodeGenerator
from core.file_manager import FileManager


class MainWindow(QMainWindow):
    """Main window for Araknid with Flyde-style UI"""
    
    def __init__(self):
        super().__init__()
        
        # Setup window properties
        self.setWindowTitle("Araknid - Visual Block-Based C Programming")
        self.setGeometry(100, 100, 1400, 900)  # Larger default size for better visibility
        
        # Initialize managers
        self.block_manager = BlockManager()
        self.code_generator = CodeGenerator()
        self.file_manager = FileManager()
        
        # Setup UI
        self._setup_ui()
        self._setup_menu()
        
        # Apply Flyde-style theme to the entire application
        self._apply_theme()
        
        # Load settings
        self._load_settings()
        
    def _setup_ui(self):
        """Set up the main UI components - Flyde style"""
        # Create main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.main_splitter)
        
        # Create toolbox (left panel) - Flyde style with fixed width
        self.toolbox = Toolbox(self.block_manager)
        self.toolbox.setFixedWidth(280)  # Fixed width for toolbox panel
        self.main_splitter.addWidget(self.toolbox)
        
        # Create right panel splitter (canvas and code view)
        self.right_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.right_splitter)
        
        # Create block canvas
        self.canvas = BlockCanvas(self.block_manager, self.code_generator)
        self.right_splitter.addWidget(self.canvas)
        
        # Create code view
        self.code_view = CodeView()
        self.right_splitter.addWidget(self.code_view)
        
        # Set initial splitter sizes
        self.main_splitter.setSizes([280, 1120])  # Adjusted for new fixed toolbox width
        self.right_splitter.setSizes([600, 300])  # More space for canvas by default
        
        # Connect signals
        self.block_manager.blocks_changed.connect(self._update_code)
        self.canvas.block_selected.connect(self.toolbox.highlight_block_category)
        
    def _setup_menu(self):
        """Set up the application menu - Flyde style"""
        # Create menu bar with custom styling
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #252526;
                color: #ffffff;
                border-bottom: 1px solid #333333;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 8px 12px;
            }
            QMenuBar::item:selected {
                background-color: #2d2d2d;
            }
            QMenu {
                background-color: #252526;
                color: #ffffff;
                border: 1px solid #333333;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 25px 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #2d2d2d;
            }
            QMenu::separator {
                height: 1px;
                background-color: #333333;
                margin: 5px 0px;
            }
        """)
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # New action
        new_action = QAction("&New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)
        
        # Open action
        open_action = QAction("&Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)
        
        # Save action
        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)
        
        # Save As action
        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # Export Code action
        export_action = QAction("&Export C Code", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_code)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        # Undo action
        undo_action = QAction("&Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.canvas.undo)
        edit_menu.addAction(undo_action)
        
        # Redo action
        redo_action = QAction("&Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self.canvas.redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        # Delete action
        delete_action = QAction("&Delete", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.canvas.delete_selected)
        edit_menu.addAction(delete_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Zoom In action
        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.canvas.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        # Zoom Out action
        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.canvas.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        # Reset Zoom action
        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.setShortcut("Ctrl+0")
        reset_zoom_action.triggered.connect(self.canvas.reset_zoom)
        view_menu.addAction(reset_zoom_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        # About action
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
    def _apply_theme(self):
        """Apply Flyde-style theme to the application"""
        # Set application font
        self.setFont(QFont("Segoe UI", 9))
        
        # Set main window style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #252526;
            }
            QSplitter::handle {
                background-color: #333333;
            }
            QSplitter::handle:horizontal {
                width: 2px;
            }
            QSplitter::handle:vertical {
                height: 2px;
            }
        """)
        
    def _update_code(self):
        """Update the code view with generated code"""
        code = self.code_generator.generate_code(self.block_manager.get_root_blocks())
        self.code_view.set_code(code)
        
    def _new_project(self):
        """Create a new project"""
        reply = QMessageBox.question(self, "New Project", 
                                    "Are you sure you want to start a new project? Unsaved changes will be lost.",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.canvas.clear()
            self.code_view.clear()
            self.file_manager.current_file = None
            self.setWindowTitle("Araknid - Visual Block-Based C Programming")
            
    def _open_project(self):
        """Open an existing project"""
        filename, _ = QFileDialog.getOpenFileName(self, "Open Project", "", 
                                                "Araknid Project Files (*.ark);;All Files (*)")
        
        if filename:
            try:
                blocks = self.file_manager.load_project(filename)
                self.block_manager.set_blocks(blocks)
                self.canvas.load_blocks(blocks)
                self._update_code()
                
                self.setWindowTitle(f"Araknid - {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project: {str(e)}")
                
    def _save_project(self):
        """Save the current project"""
        if self.file_manager.current_file:
            self._save_to_file(self.file_manager.current_file)
        else:
            self._save_project_as()
            
    def _save_project_as(self):
        """Save the current project to a new file"""
        filename, _ = QFileDialog.getSaveFileName(self, "Save Project", "", 
                                                "Araknid Project Files (*.ark);;All Files (*)")
        
        if filename:
            self._save_to_file(filename)
            
    def _save_to_file(self, filename):
        """Save the project to the specified file"""
        try:
            blocks = self.block_manager.get_all_blocks()
            self.file_manager.save_project(filename, blocks)
            self.setWindowTitle(f"Araknid - {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project: {str(e)}")
            
    def _export_code(self):
        """Export the generated C code to a file"""
        filename, _ = QFileDialog.getSaveFileName(self, "Export C Code", "", 
                                                "C Source Files (*.c);;All Files (*)")
        
        if filename:
            try:
                code = self.code_generator.generate_code(self.block_manager.get_root_blocks())
                self.file_manager.export_code(filename, code)
                
                QMessageBox.information(self, "Export Successful", 
                                       f"Code exported successfully to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export code: {str(e)}")
                
    def _show_about(self):
        """Show the about dialog - Flyde style"""
        about_box = QMessageBox(self)
        about_box.setWindowTitle("About Araknid")
        about_box.setText("<h2>Araknid</h2>")
        about_box.setInformativeText(
            "<p>A modern, Flyde-inspired block-based C programming environment for learning algorithms.</p>"
            "<p>Created with PyQt5.</p>"
        )
        about_box.setStandardButtons(QMessageBox.Ok)
        
        # Apply Flyde-style to message box
        about_box.setStyleSheet("""
            QMessageBox {
                background-color: #252526;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
        """)
        
        about_box.exec_()
        
    def _load_settings(self):
        """Load application settings"""
        settings = QSettings("Araknid", "Araknid")
        
        # Restore window geometry
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        # Restore window state
        state = settings.value("windowState")
        if state:
            self.restoreState(state)
            
        # Restore splitter settings
        main_sizes = settings.value("mainSplitter")
        if main_sizes:
            # Convert to integers if needed
            if isinstance(main_sizes[0], str):
                main_sizes = [int(size) for size in main_sizes]
            self.main_splitter.setSizes(main_sizes)
            
        right_sizes = settings.value("rightSplitter")
        if right_sizes:
            # Convert to integers if needed
            if isinstance(right_sizes[0], str):
                right_sizes = [int(size) for size in right_sizes]
            self.right_splitter.setSizes(right_sizes)
            
    def _save_settings(self):
        """Save application settings"""
        settings = QSettings("Araknid", "Araknid")
        
        # Save window geometry and state
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        
        # Save splitter settings
        settings.setValue("mainSplitter", self.main_splitter.sizes())
        settings.setValue("rightSplitter", self.right_splitter.sizes())
        
    def closeEvent(self, event):
        """Handle application close event"""
        self._save_settings()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())