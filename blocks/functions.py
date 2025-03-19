from blocks.base import Block

class FunctionDeclarationBlock(Block):
    """Block for function declarations"""
    
    def __init__(self):
        super().__init__(Block.C_BLOCK, Block.FUNCTION, "Function Declaration")
        self.width = 260
        self.height = 120
        
        # Add input fields
        self.add_input_field("return", "Return", "combo", 
                           ["void", "int", "float", "char", "double"], "void")
        self.add_input_field("name", "Name", "text", default_value="myFunction")
        self.add_input_field("params", "Params", "text", default_value="int x, int y")
        
        # Enable nested connection point for function body
        self.connection_defs['nested']['enabled'] = True
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this function declaration block, with placeholders for body"""
        return_type = self.get_input_value("return")
        name = self.get_input_value("name")
        params = self.get_input_value("params")
        
        code = " " * indent + f"{return_type} {name}({params}) {{\n"
        code += "{{INNER_CODE}}"
        code += " " * indent + "}\n\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class FunctionCallBlock(Block):
    """Block for function calls"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.FUNCTION, "Function Call")
        self.width = 220
        self.height = 80
        
        # Add input fields
        self.add_input_field("function", "Function", "text", default_value="myFunction")
        self.add_input_field("arguments", "Arguments", "text", default_value="x, y")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this function call block, with placeholders for connected code"""
        name = self.get_input_value("function")
        args = self.get_input_value("arguments")
        
        code = " " * indent + f"{name}({args});\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class ReturnBlock(Block):
    """Block for return statements"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.FUNCTION, "Return")
        self.width = 200
        self.height = 60
        
        # Add input field
        self.add_input_field("value", "Value", "text", default_value="0")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this return block, with placeholders for connected code"""
        value = self.get_input_value("value")
        
        # Handle empty return value (void functions)
        if value:
            code = " " * indent + f"return {value};\n"
        else:
            code = " " * indent + "return;\n"
        
        code += "{{BOTTOM_CODE}}"
        
        return code

class MainFunctionBlock(Block):
    """Block for main function"""
    
    def __init__(self):
        super().__init__(Block.C_BLOCK, Block.FUNCTION, "Main Function")
        self.width = 260
        self.height = 60
        
        # No input fields needed for simple main function
        
        # Enable nested connection point for function body
        self.connection_defs['nested']['enabled'] = True
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this main function block, with placeholders for body"""
        code = " " * indent + "int main() {\n"
        code += "{{INNER_CODE}}"
        
        # Add return 0 if no return statement is found (this will be checked at runtime)
        if not self._has_return_statement():
            code += " " * (indent + 4) + "return 0;\n"
            
        code += " " * indent + "}\n\n"
        code += "{{BOTTOM_CODE}}"
        
        return code
    
    def _has_return_statement(self):
        """Check if the function already has a return statement"""
        # Start from the first block inside the function
        current = self.connected_blocks[self.INNER]
        
        while current:
            if isinstance(current, ReturnBlock):
                return True
                
            # Check blocks connected below
            current = current.connected_blocks[current.BOTTOM]
            
        return False