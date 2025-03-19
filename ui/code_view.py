from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QTextEdit, QLabel, QSplitter, QComboBox, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QIcon
import re  # For regular expressions

class CodeView(QWidget):
    """Widget for displaying generated C code - Flyde style"""
    
    def __init__(self):
        super().__init__()
        
        # Setup the UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI components - Flyde style with improved alignment"""
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
        
        # Code label
        code_label = QLabel("Generated Code")
        code_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        code_label.setStyleSheet("color: white;")
        header_layout.addWidget(code_label)
        
        # Add space between title and language selector
        header_layout.addStretch(1)
        
        # Add language selector in its own container for better alignment
        language_container = QWidget()
        language_container.setStyleSheet("background-color: transparent;")
        language_layout = QHBoxLayout(language_container)
        language_layout.setContentsMargins(0, 0, 0, 0)
        language_layout.setSpacing(8)
        
        # Add language label and selector
        language_label = QLabel("Language:")
        language_label.setStyleSheet("color: #aaaaaa;")
        language_layout.addWidget(language_label)
        
        language_combo = QComboBox()
        language_combo.addItem("C")
        language_combo.setFixedWidth(80)
        language_combo.setStyleSheet("""
            QComboBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox:hover {
                background-color: #4c4c4c;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 0px;
            }
        """)
        language_layout.addWidget(language_combo)
        
        # Add the language container to header
        header_layout.addWidget(language_container)
        
        # Add a bit more space before the Copy button
        header_layout.addStretch(1)
        
        # Copy button only (no Compile or Run buttons)
        copy_button = QPushButton("Copy")
        copy_button.setToolTip("Copy code to clipboard")
        copy_button.setStyleSheet("""
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
        copy_button.clicked.connect(self._copy_code)
        header_layout.addWidget(copy_button)
        
        layout.addWidget(header)
        
        # Code editor - Flyde style with dark theme
        self.code_editor = CSyntaxHighlightedEditor()
        self.code_editor.setReadOnly(True)  # Make it read-only for now
        self.code_editor.setFont(QFont("Consolas", 11))
        self.code_editor.setLineWrapMode(QTextEdit.NoWrap)
        self.code_editor.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
        """)
        layout.addWidget(self.code_editor)
        
    def set_code(self, code):
        """Set the code text in the editor"""
        self.code_editor.setPlainText(code)
        
    def clear(self):
        """Clear the code editor"""
        self.code_editor.clear()
        
    def _copy_code(self):
        """Copy the code to clipboard"""
        self.code_editor.selectAll()
        self.code_editor.copy()
        # Deselect after copying
        cursor = self.code_editor.textCursor()
        cursor.clearSelection()
        self.code_editor.setTextCursor(cursor)


class CSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for C code - Flyde style with VS Code-like theme"""
    
    def __init__(self, document):
        super().__init__(document)
        
        # Define highlighting rules
        self.highlighting_rules = []
        
        # Keywords format - blue like VS Code
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)
        
        # C keywords
        keywords = [
            "auto", "break", "case", "char", "const", "continue", "default", "do", "double", 
            "else", "enum", "extern", "float", "for", "goto", "if", "int", "long", "register", 
            "return", "short", "signed", "sizeof", "static", "struct", "switch", "typedef", 
            "union", "unsigned", "void", "volatile", "while"
        ]
        
        # Add keyword patterns
        for word in keywords:
            pattern = f"\\b{word}\\b"
            self.highlighting_rules.append((pattern, keyword_format))
        
        # Types format - green like VS Code
        type_format = QTextCharFormat()
        type_format.setForeground(QColor("#4EC9B0"))
        types = ["int", "char", "double", "float", "void", "unsigned", "long", "short"]
        for word in types:
            pattern = f"\\b{word}\\b"
            self.highlighting_rules.append((pattern, type_format))
        
        # Number format - light green like VS Code
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self.highlighting_rules.append((r'\b[0-9]+\b', number_format))
        
        # String format - orange like VS Code
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((r'"[^"]*"', string_format))
        
        # Single-line comment format - green like VS Code
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((r'//[^\n]*', comment_format))
        
        # Function format - yellow like VS Code
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#DCDCAA"))
        self.highlighting_rules.append((r'\b[A-Za-z0-9_]+(?=\()', function_format))
        
        # Preprocessor format - purple like VS Code
        preprocessor_format = QTextCharFormat()
        preprocessor_format.setForeground(QColor("#C586C0"))
        self.highlighting_rules.append((r'#[^\n]*', preprocessor_format))
        
        # Multi-line comment formats - VS Code style
        self.multi_line_comment_format = QTextCharFormat()
        self.multi_line_comment_format.setForeground(QColor("#6A9955"))
        
        self.comment_start_expression = r'/\*'
        self.comment_end_expression = r'\*/'
        
    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text"""
        # Apply regular expression based rules
        for pattern, format in self.highlighting_rules:
            # Use re.finditer instead of text.findall
            for match in re.finditer(pattern, text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, format)
        
        # Handle multi-line comments
        self.setCurrentBlockState(0)
        
        # Find start of comment using regex
        start_index = 0
        if self.previousBlockState() != 1:
            match = re.search(r'/\*', text)
            if match:
                start_index = match.start()
            else:
                start_index = -1
            
        while start_index >= 0:
            # Find end of comment
            end_match = re.search(r'\*/', text[start_index:])
            
            if end_match:
                comment_length = end_match.end() + start_index - start_index
                self.setFormat(start_index, comment_length, self.multi_line_comment_format)
                start_match = re.search(r'/\*', text[start_index + comment_length:])
                if start_match:
                    start_index = start_index + comment_length + start_match.start()
                else:
                    start_index = -1
            else:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
                self.setFormat(start_index, comment_length, self.multi_line_comment_format)
                start_index = -1


class CSyntaxHighlightedEditor(QTextEdit):
    """Text editor with C syntax highlighting - Flyde style"""
    
    def __init__(self):
        super().__init__()
        
        # Set up the highlighter
        self.highlighter = CSyntaxHighlighter(self.document())
        
        # Set editor styling - Flyde style
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                padding: 10px;
            }
        """)
        
        # Set fixed width font
        font = QFont("Consolas", 11)
        self.setFont(font)