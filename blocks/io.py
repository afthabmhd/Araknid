from blocks.base import Block

class PrintBlock(Block):
    """Block for printf statements"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.IO, "Print")
        self.width = 220
        self.height = 80
        
        # Add input fields
        self.add_input_field("format", "format", "text", default_value="\"%d\"")
        self.add_input_field("arguments", "arguments", "text", default_value="x")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this print block, with placeholders for connected code"""
        format_str = self.get_input_value("format")
        args = self.get_input_value("arguments")
        
        # Check if args is empty (for just printing a string)
        if args.strip():
            code = " " * indent + f"printf({format_str}, {args});\n"
        else:
            code = " " * indent + f"printf({format_str});\n"
        
        # Add placeholder for bottom code
        code += "{{BOTTOM_CODE}}"
        
        return code

class ScanBlock(Block):
    """Block for scanf statements"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.IO, "Input")
        self.width = 220
        self.height = 80
        
        # Add input fields
        self.add_input_field("format", "format", "text", default_value="\"%d\"")
        self.add_input_field("arguments", "arguments", "text", default_value="&x")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this scan block, with placeholders for connected code"""
        format_str = self.get_input_value("format")
        args = self.get_input_value("arguments")
        
        code = " " * indent + f"scanf({format_str}, {args});\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class PrintfNewlineBlock(Block):
    """Block for printing a newline"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.IO, "Print Newline")
        self.width = 200
        self.height = 40
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this newline block, with placeholders for connected code"""
        code = " " * indent + "printf(\"\\n\");\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class PrintStringBlock(Block):
    """Block for printing a string literal"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.IO, "Print String")
        self.width = 220
        self.height = 60
        
        # Add input field
        self.add_input_field("value", "Value", "text", default_value="\"Hello, World!\"")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this print string block, with placeholders for connected code"""
        text = self.get_input_value("value")
        
        # Check if text already includes quotes
        if not (text.startswith("\"") and text.endswith("\"")):
            text = f"\"{text}\""
            
        code = " " * indent + f"printf({text});\n"
        code += "{{BOTTOM_CODE}}"
        
        return code