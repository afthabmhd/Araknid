import sys
import os
import time
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSplitter, QFileDialog, QAction, QMessageBox,
                           QTabWidget, QMenu, QLabel, QStatusBar)
from PyQt5.QtCore import Qt, QSettings, QTimer
from PyQt5.QtGui import QIcon, QFont

from ui.canvas import BlockCanvas
from ui.code_view import CodeView
from ui.toolbox import Toolbox
from ui.compiler_panel import CompilerPanel
from core.block_manager import BlockManager
from core.code_generator import CodeGenerator
from core.file_manager import FileManager
from core.compiler import CompilerManager


class MainWindow(QMainWindow):
    """Main window for Araknid with Flyde-style UI and integrated compiler"""
    
    def __init__(self):
        super().__init__()
        
        # Setup window properties
        self.setWindowTitle("Araknid - Visual Block-Based C Programming")
        self.setGeometry(100, 100, 1400, 900)  # Larger default size for better visibility
        
        # Initialize managers
        self.block_manager = BlockManager()
        self.code_generator = CodeGenerator()
        self.file_manager = FileManager()
        self.compiler_manager = CompilerManager()
        
        # Track last modification time for detecting unsaved changes
        self.last_modified_time = time.time()
        
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
        
        # Create right panel splitter (canvas and output panels)
        self.right_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.right_splitter)
        
        # Create block canvas
        self.canvas = BlockCanvas(self.block_manager, self.code_generator)
        self.right_splitter.addWidget(self.canvas)
        
        # Create output tab widget to contain code view and compiler panel
        self.output_tabs = QTabWidget()
        self.output_tabs.setStyleSheet("""
            QTabWidget {
                background-color: #1e1e1e;
                border: none;
            }
            QTabWidget::pane {
                background-color: #1e1e1e;
                border: none;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: none;
                padding: 6px 15px;
                margin-right: 2px;
                font-size: 10pt;
                min-width: 120px;  /* Increased minimum width for tabs */
                max-width: 200px;  /* Maximum width to prevent too wide tabs */
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-top: 2px solid #0078d7;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3d3d3d;
            }
        """)
        
        # Make tabs expand to fill available space
        self.output_tabs.tabBar().setExpanding(True)
        
        # Create code view
        self.code_view = CodeView()
        self.output_tabs.addTab(self.code_view, "Generated Code")
        
        # Create compiler panel
        self.compiler_panel = CompilerPanel(self.compiler_manager)
        self.output_tabs.addTab(self.compiler_panel, "Compiler")
        
        # Add output tabs to the right splitter
        self.right_splitter.addWidget(self.output_tabs)
        
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
        
        # Compiler menu
        compiler_menu = menubar.addMenu("&Compiler")
        
        # Compile action
        compile_action = QAction("&Compile", self)
        compile_action.setShortcut("F5")
        compile_action.triggered.connect(self._compile_code)
        compiler_menu.addAction(compile_action)
        
        # Run action
        run_action = QAction("&Run", self)
        run_action.setShortcut("F6")
        run_action.triggered.connect(self._run_code)
        compiler_menu.addAction(run_action)
        
        # Stop action
        stop_action = QAction("&Stop", self)
        stop_action.setShortcut("F7")
        stop_action.triggered.connect(self._stop_code)
        compiler_menu.addAction(stop_action)
        
        compiler_menu.addSeparator()
        
        # Show compiler panel action
        show_compiler_action = QAction("Show &Compiler Panel", self)
        show_compiler_action.triggered.connect(self._show_compiler_panel)
        compiler_menu.addAction(show_compiler_action)
        
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
            QStatusBar {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border-top: 1px solid #333333;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
        
    def _update_code(self):
        """Update the code view with generated code"""
        code = self.code_generator.generate_code(self.block_manager.get_root_blocks())
        self.code_view.set_code(code)
        
        # Update compiler panel's access to the latest code
        if hasattr(self, 'compiler_panel') and hasattr(self.compiler_panel, 'latest_code'):
            self.compiler_panel.latest_code = code
            
        # Update last modified time
        self.last_modified_time = time.time()
        
    def _new_project(self):
        """Create a new project"""
        # Create new project
        self.canvas.clear()
        self.code_view.clear()
        self.file_manager.current_file = None
        self.setWindowTitle("Araknid - Visual Block-Based C Programming")
        self.last_modified_time = time.time()
            
    def _export_code(self):
        """Export the generated C code to a file"""
        filename, _ = QFileDialog.getSaveFileName(self, "Export C Code", "", 
                                                "C Source Files (*.c);;All Files (*)")
        
        if filename:
            code = self.code_generator.generate_code(self.block_manager.get_root_blocks())
            
            if self.file_manager.export_code(filename, code):
                QMessageBox.information(self, "Export Successful", 
                                       f"Code exported successfully to {filename}")
                
    def _show_about(self):
        """Show the about dialog - Flyde style"""
        about_box = QMessageBox(self)
        about_box.setWindowTitle("About Araknid")
        about_box.setText("<h2>Araknid</h2>")
        about_box.setInformativeText(
            "<p>A modern, Flyde-inspired block-based C programming environment for learning algorithms.</p>"
            "<p>Created with PyQt5.</p>"
            "<p>Integrated with GCC compiler for immediate code execution.</p>"
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
        
    def _compile_code(self):
        """Compile the current code"""
        # Switch to the compiler tab
        self.output_tabs.setCurrentWidget(self.compiler_panel)
        
        # Trigger compile action in the compiler panel
        if hasattr(self.compiler_panel, '_compile_current_code'):
            self.compiler_panel._compile_current_code()
            
    def _run_code(self):
        """Run the compiled code"""
        # Switch to the compiler tab
        self.output_tabs.setCurrentWidget(self.compiler_panel)
        
        # Trigger run action in the compiler panel
        if hasattr(self.compiler_panel, '_run_compiled_code'):
            self.compiler_panel._run_compiled_code()
            
    def _stop_code(self):
        """Stop the running code"""
        # Switch to the compiler tab
        self.output_tabs.setCurrentWidget(self.compiler_panel)
        
        # Trigger stop action in the compiler panel
        if hasattr(self.compiler_panel, '_stop_running_program'):
            self.compiler_panel._stop_running_program()
            
    def _show_compiler_panel(self):
        """Show the compiler panel"""
        # Switch to the compiler tab
        self.output_tabs.setCurrentWidget(self.compiler_panel)
        
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
            
        # Restore last active tab
        tab_index = settings.value("outputTabIndex")
        if tab_index is not None:
            self.output_tabs.setCurrentIndex(int(tab_index))
            
    def _save_settings(self):
        """Save application settings"""
        settings = QSettings("Araknid", "Araknid")
        
        # Save window geometry and state
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        
        # Save splitter settings
        settings.setValue("mainSplitter", self.main_splitter.sizes())
        settings.setValue("rightSplitter", self.right_splitter.sizes())
        
        # Save current tab index
        settings.setValue("outputTabIndex", self.output_tabs.currentIndex())
        
    def closeEvent(self, event):
        """Handle application close event"""
        # Clean up the compiler manager
        if hasattr(self, 'compiler_manager'):
            self.compiler_manager.cleanup()
            
        self._save_settings()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Display a welcome message on the compiler panel
    if hasattr(window, 'compiler_panel') and hasattr(window.compiler_panel, 'console'):
        window.compiler_panel.console.append_info("Welcome to Araknid C Programming Environment!\n")
        window.compiler_panel.console.append_info("Create blocks in the canvas, then use this panel to compile and run your code.\n")
    
    sys.exit(app.exec_())
