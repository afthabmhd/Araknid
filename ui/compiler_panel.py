from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QTextEdit, QLabel, QSplitter, QProgressBar, QFrame,
                            QTabWidget, QPlainTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal, QProcess
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QColor, QTextCharFormat, QSyntaxHighlighter

class CompilerConsole(QPlainTextEdit):
    """Custom console widget for compiler and execution output"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set read-only and monospaced font for console-like appearance
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        
        # Dark theme styling
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
        """)
        
        # Maximum line count to prevent memory issues with very long outputs
        self.document().setMaximumBlockCount(5000)
        
    def append_text(self, text, color=None):
        """Append text with optional color"""
        if not text:
            return
            
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        if color:
            format = QTextCharFormat()
            format.setForeground(QColor(color))
            cursor.setCharFormat(format)
            
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        
    def append_output(self, text):
        """Append output text (white)"""
        self.append_text(text)
        
    def append_error(self, text):
        """Append error text (red)"""
        self.append_text(text, "#ff6e6e")
        
    def append_success(self, text):
        """Append success text (green)"""
        self.append_text(text, "#6eff6e")
        
    def append_info(self, text):
        """Append info text (cyan)"""
        self.append_text(text, "#6ee9ff")
        
    def clear_console(self):
        """Clear the console"""
        self.clear()

class InputConsole(QPlainTextEdit):
    """Custom input widget for program stdin"""
    
    input_submitted = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set monospaced font
        self.setFont(QFont("Consolas", 10))
        
        # Dark theme styling
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
        """)
        
    def keyPressEvent(self, event):
        """Handle Enter key to submit input"""
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            # Ctrl+Enter submits input
            text = self.toPlainText()
            self.input_submitted.emit(text)
            event.accept()
        else:
            super().keyPressEvent(event)

class CompilerPanel(QWidget):
    """Panel for compiler and execution output"""
    
    def __init__(self, compiler_manager):
        super().__init__()
        
        self.compiler_manager = compiler_manager
        self.latest_code = ""  # Store the latest code for direct access
        self.compilation_in_progress = False
        self.execution_in_progress = False
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals from compiler manager
        self.compiler_manager.compilation_started.connect(self._on_compilation_started)
        self.compiler_manager.compilation_finished.connect(self._on_compilation_finished)
        self.compiler_manager.execution_started.connect(self._on_execution_started)
        self.compiler_manager.execution_output.connect(self._on_execution_output)
        self.compiler_manager.execution_finished.connect(self._on_execution_finished)
        
    def _setup_ui(self):
        """Set up the UI components"""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # Header frame - Flyde style
        header = QFrame()
        header.setStyleSheet("background-color: #1e1e1e; border: none;")
        header.setFixedHeight(50)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        
        # Compiler label
        compiler_label = QLabel("Compiler Output")
        compiler_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        compiler_label.setStyleSheet("color: white;")
        header_layout.addWidget(compiler_label)
        
        # Add space between title and buttons
        header_layout.addStretch(1)
        
        # Compile button
        self.compile_button = QPushButton("Compile")
        self.compile_button.setToolTip("Compile the code")
        self.compile_button.setStyleSheet("""
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
            QPushButton:pressed {
                background-color: #5c5c5c;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #808080;
            }
        """)
        self.compile_button.clicked.connect(self._compile_current_code)
        header_layout.addWidget(self.compile_button)
        
        # Run button
        self.run_button = QPushButton("Run")
        self.run_button.setToolTip("Run the compiled code")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #2ea043;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #39c653;
            }
            QPushButton:pressed {
                background-color: #44dd5e;
            }
            QPushButton:disabled {
                background-color: #1e6e2c;
                color: #a0a0a0;
            }
        """)
        self.run_button.clicked.connect(self._run_compiled_code)
        self.run_button.setEnabled(False)  # Disabled until successful compilation
        header_layout.addWidget(self.run_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.setToolTip("Stop the running program")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #e64040;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #f65050;
            }
            QPushButton:pressed {
                background-color: #ff6060;
            }
            QPushButton:disabled {
                background-color: #982a2a;
                color: #a0a0a0;
            }
        """)
        self.stop_button.clicked.connect(self._stop_running_program)
        self.stop_button.setEnabled(False)  # Disabled until program is running
        header_layout.addWidget(self.stop_button)
        
        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.setToolTip("Clear the console output")
        self.clear_button.setStyleSheet("""
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
            QPushButton:pressed {
                background-color: #5c5c5c;
            }
        """)
        self.clear_button.clicked.connect(self._clear_console)
        header_layout.addWidget(self.clear_button)
        
        layout.addWidget(header)
        
        # Progress bar for compilation/execution status
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e1e;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Tab widget for output and input
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
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
                padding: 6px 10px;
                margin-right: 2px;
                min-width: 100px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: 2px solid #0078d7;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3d3d3d;
            }
        """)
        
        # Console output tab
        self.console = CompilerConsole()
        self.tab_widget.addTab(self.console, "Console Output")
        
        # Input tab
        self.input_console = InputConsole()
        self.input_console.input_submitted.connect(self._submit_input)
        self.tab_widget.addTab(self.input_console, "Program Input")
        
        layout.addWidget(self.tab_widget)
        
        # Initialize with compiler check
        self._check_compiler_status()
        
    def _check_compiler_status(self):
        """Check if the compiler is available and update UI accordingly"""
        try:
            if self.compiler_manager.is_compiler_available():
                self.console.append_info("Compiler found: " + 
                                        (self.compiler_manager.compiler_path or "gcc (from PATH)") + "\n")
                self.console.append_info("Ready to compile.\n")
                self.compile_button.setEnabled(True)
            else:
                self.console.append_error("Compiler not found.\n")
                self.console.append_info("Please install GCC compiler (via w64devkit or MinGW) and restart the application.\n")
                self.console.append_info("You can download w64devkit from https://github.com/skeeto/w64devkit/releases\n")
                self.compile_button.setEnabled(False)
        except Exception as e:
            self.console.append_error(f"Error checking compiler: {str(e)}\n")
            
    def _get_code_from_editor(self):
        """Get code from the code editor, searching through parent hierarchy if needed"""
        try:
            # First, try the direct code reference that's updated by the block manager
            if hasattr(self, 'latest_code') and self.latest_code:
                return self.latest_code
                
            # Next, try different approaches to find the code editor
            
            # 1. Check if our parent window has the code_view
            if self.window() and hasattr(self.window(), 'code_view') and hasattr(self.window().code_view, 'code_editor'):
                return self.window().code_view.code_editor.toPlainText()
                
            # 2. Try to access it from our direct parent
            if self.parent() and hasattr(self.parent(), 'code_view') and hasattr(self.parent().code_view, 'code_editor'):
                return self.parent().code_view.code_editor.toPlainText()
                
            # 3. Try to find it in parent's parent
            if (self.parent() and hasattr(self.parent(), 'parent') and 
                self.parent().parent() and hasattr(self.parent().parent(), 'code_view') and 
                hasattr(self.parent().parent().code_view, 'code_editor')):
                return self.parent().parent().code_view.code_editor.toPlainText()
                
            # 4. Try to find MainWindow in the hierarchy
            parent = self.parent()
            while parent:
                if hasattr(parent, 'code_view') and hasattr(parent.code_view, 'code_editor'):
                    return parent.code_view.code_editor.toPlainText()
                parent = parent.parent()
                
            # 5. Check if we're in a QTabWidget
            parent = self.parent()
            while parent:
                if isinstance(parent, QTabWidget):
                    # Try to find mainwindow
                    if parent.parent() and hasattr(parent.parent(), 'code_view'):
                        return parent.parent().code_view.code_editor.toPlainText()
                parent = parent.parent()
                
            # If all else fails
            return None
            
        except Exception as e:
            self.console.append_error(f"Error retrieving code: {str(e)}\n")
            return None
            
    def _compile_current_code(self):
        """Compile the current code"""
        try:
            # Prevent multiple compile operations
            if self.compilation_in_progress:
                return
                
            # Try to get the code
            code = self._get_code_from_editor()
            
            if not code or not code.strip():
                self.console.append_error("No code to compile. Please create some blocks first.\n")
                return
            
            # Show the console tab
            self.tab_widget.setCurrentIndex(0)
            
            # Log the code being compiled (for debugging)
            self.console.append_info("\n[Compiling code...]\n")
            
            # Start compilation
            self.compiler_manager.compile_code(code)
            
        except Exception as e:
            self.console.append_error(f"Compilation error: {str(e)}\n")
            self.compile_button.setEnabled(True)
            self.progress_bar.hide()
            self.compilation_in_progress = False
        
    def _run_compiled_code(self):
        """Run the compiled code"""
        try:
            # Prevent multiple execution operations
            if self.execution_in_progress:
                return
                
            # Show the console tab
            self.tab_widget.setCurrentIndex(0)
            
            # Start execution
            self.compiler_manager.run_program()
            
        except Exception as e:
            self.console.append_error(f"Execution error: {str(e)}\n")
            self.run_button.setEnabled(True)
            self.compile_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_bar.hide()
            self.execution_in_progress = False
        
    def _stop_running_program(self):
        """Stop the running program"""
        try:
            self.compiler_manager.stop_running_program()
            self.console.append_info("\n[Program execution terminated by user]\n")
        except Exception as e:
            self.console.append_error(f"Error stopping program: {str(e)}\n")
            
    def _clear_console(self):
        """Clear the console output"""
        try:
            self.console.clear_console()
        except Exception as e:
            print(f"Error clearing console: {str(e)}")  # Fallback to stdout
        
    def _submit_input(self, text):
        """Submit input to the running program"""
        try:
            # For now, we'll just support sending entire input at once
            # In a more advanced version, we could implement interactive input
            if hasattr(self.compiler_manager, 'run_process') and self.compiler_manager.run_process:
                if self.compiler_manager.run_process.state() == QProcess.Running:
                    self.compiler_manager.run_process.write((text + '\n').encode('utf-8'))
                    self.console.append_text(f"\n[Input sent: {text}]\n", "#888888")
                    
                    # Switch to console tab to see the effect
                    self.tab_widget.setCurrentIndex(0)
            else:
                self.console.append_error("\n[No running program to receive input]\n")
        except Exception as e:
            self.console.append_error(f"Error submitting input: {str(e)}\n")
            
    def _on_compilation_started(self):
        """Handle compilation starting"""
        try:
            self.progress_bar.show()
            self.compile_button.setEnabled(False)
            self.run_button.setEnabled(False)
            self.console.append_info("\n[Compiling...]\n")
            self.compilation_in_progress = True
        except Exception as e:
            self.console.append_error(f"Error updating UI on compilation start: {str(e)}\n")
        
    def _on_compilation_finished(self, success, output):
        """Handle compilation finishing"""
        try:
            self.progress_bar.hide()
            self.compile_button.setEnabled(True)
            self.compilation_in_progress = False
            
            if success:
                self.console.append_success("[Compilation successful!]\n")
                if output.strip():
                    self.console.append_output(output + "\n")
                self.run_button.setEnabled(True)
            else:
                self.console.append_error("[Compilation failed]\n")
                if output.strip():
                    self.console.append_output(output + "\n")
                self.run_button.setEnabled(False)
        except Exception as e:
            self.console.append_error(f"Error updating UI on compilation finish: {str(e)}\n")
            self.compile_button.setEnabled(True)
            self.compilation_in_progress = False
            
    def _on_execution_started(self):
        """Handle execution starting"""
        try:
            self.progress_bar.show()
            self.compile_button.setEnabled(False)
            self.run_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.console.append_info("\n[Running program...]\n\n")
            self.execution_in_progress = True
        except Exception as e:
            self.console.append_error(f"Error updating UI on execution start: {str(e)}\n")
        
    def _on_execution_output(self, output):
        """Handle output from the running program"""
        try:
            self.console.append_output(output)
        except Exception as e:
            print(f"Error displaying output: {str(e)}")  # Fallback to stdout
        
    def _on_execution_finished(self, exit_code):
        """Handle execution finishing"""
        try:
            self.progress_bar.hide()
            self.compile_button.setEnabled(True)
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.execution_in_progress = False
            
            if exit_code == 0:
                self.console.append_success(f"\n[Program executed successfully (exit code: {exit_code})]\n")
            else:
                self.console.append_error(f"\n[Program exited with error code: {exit_code}]\n")
        except Exception as e:
            self.console.append_error(f"Error updating UI on execution finish: {str(e)}\n")
            self.compile_button.setEnabled(True)
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.execution_in_progress = False
