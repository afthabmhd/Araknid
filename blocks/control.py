from blocks.base import Block

class IfBlock(Block):
    """Block for if statements"""
    
    def __init__(self):
        super().__init__(Block.C_BLOCK, Block.CONTROL, "If")
        self.width = 220
        self.height = 60
        
        # Enable the nested code connection point
        self.connection_defs['nested']['enabled'] = True
        
        # Add input field for condition
        self.add_input_field("condition", "condition", "text", default_value="x == 0")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this if block, with placeholders for nested code"""
        condition = self.get_input_value("condition")
        
        code = " " * indent + f"if ({condition}) {{\n"
        code += "{{INNER_CODE}}"
        code += " " * indent + "}\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class ElseBlock(Block):
    """Block for else statements"""
    
    def __init__(self):
        super().__init__(Block.C_BLOCK, Block.CONTROL, "Else")
        self.width = 220
        self.height = 60
        
        # Enable the nested code connection point
        self.connection_defs['nested']['enabled'] = True
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this else block, with placeholders for nested code"""
        code = " " * indent + "else {\n"
        code += "{{INNER_CODE}}"
        code += " " * indent + "}\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class ForLoopBlock(Block):
    """Block for for loops"""
    
    def __init__(self):
        super().__init__(Block.C_BLOCK, Block.CONTROL, "For Loop")
        self.width = 300
        self.height = 120
        
        # Enable the nested code connection point
        self.connection_defs['nested']['enabled'] = True
        
        # Add input fields for loop components
        self.add_input_field("init", "Init", "text", default_value="int i = 0")
        self.add_input_field("condition", "condition", "text", default_value="i < 10")
        self.add_input_field("update", "Update", "text", default_value="i++")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this for loop block, with placeholders for nested code"""
        init = self.get_input_value("init")
        condition = self.get_input_value("condition")
        update = self.get_input_value("update")
        
        code = " " * indent + f"for ({init}; {condition}; {update}) {{\n"
        code += "{{INNER_CODE}}"
        code += " " * indent + "}\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class WhileLoopBlock(Block):
    """Block for while loops"""
    
    def __init__(self):
        super().__init__(Block.C_BLOCK, Block.CONTROL, "While Loop")
        self.width = 220
        self.height = 60
        
        # Enable the nested code connection point
        self.connection_defs['nested']['enabled'] = True
        
        # Add input field for condition
        self.add_input_field("condition", "condition", "text", default_value="x > 0")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this while loop block, with placeholders for nested code"""
        condition = self.get_input_value("condition")
        
        code = " " * indent + f"while ({condition}) {{\n"
        code += "{{INNER_CODE}}"
        code += " " * indent + "}\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class BreakBlock(Block):
    """Block for break statements"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.CONTROL, "Break")
        self.width = 150
        self.height = 40
        
        # Only enable top and bottom connection points for stack blocks
        # (nested, left, and right are disabled by default)
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this break block, with placeholder for bottom code"""
        code = " " * indent + "break;\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class ContinueBlock(Block):
    """Block for continue statements"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.CONTROL, "Continue")
        self.width = 150
        self.height = 40
        
        # Only enable top and bottom connection points for stack blocks
        # (nested, left, and right are disabled by default)
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this continue block, with placeholder for bottom code"""
        code = " " * indent + "continue;\n"
        code += "{{BOTTOM_CODE}}"
        
        return code