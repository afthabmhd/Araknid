from blocks.base import Block

class VariableDeclarationBlock(Block):
    """Block for variable declarations"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.VARIABLE, "Variable Declaration")
        self.width = 220
        self.height = 80
        
        # Add input fields
        self.add_input_field("type", "type", "combo", ["int", "float", "char", "double"], "int")
        self.add_input_field("name", "name", "text", default_value="x")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this variable declaration block, with placeholders for connected code"""
        var_type = self.get_input_value("type")
        var_name = self.get_input_value("name")
        
        code = " " * indent + f"{var_type} {var_name};\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class VariableAssignmentBlock(Block):
    """Block for variable assignment"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.VARIABLE, "Assignment")
        self.width = 220
        self.height = 80
        
        # Add input fields
        self.add_input_field("variable", "variable", "text", default_value="x")
        self.add_input_field("value", "value", "text", default_value="0")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this variable assignment block, with placeholders for connected code"""
        var_name = self.get_input_value("variable")
        value = self.get_input_value("value")
        
        code = " " * indent + f"{var_name} = {value};\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class ArrayDeclarationBlock(Block):
    """Block for array declarations"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.VARIABLE, "Array Declaration")
        self.width = 220
        self.height = 120
        
        # Add input fields
        self.add_input_field("type", "type", "combo", ["int", "float", "char", "double"], "int")
        self.add_input_field("name", "name", "text", default_value="arr")
        self.add_input_field("size", "size", "text", default_value="10")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this array declaration block, with placeholders for connected code"""
        arr_type = self.get_input_value("type")
        arr_name = self.get_input_value("name")
        arr_size = self.get_input_value("size")
        
        code = " " * indent + f"{arr_type} {arr_name}[{arr_size}];\n"
        code += "{{BOTTOM_CODE}}"
        
        return code