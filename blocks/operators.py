from blocks.base import Block
from PyQt5.QtWidgets import QLineEdit, QComboBox

class OperatorBlock(Block):
    """Block for arithmetic and comparison operators"""
    
    def __init__(self):
        super().__init__(Block.OVAL, Block.OPERATOR, "Operator")
        self.width = 200
        self.height = 60
        
        # Enable left and right connection points for operands
        self.connection_defs['left']['enabled'] = True
        self.connection_defs['right']['enabled'] = True
        
        # Add input fields
        self.add_input_field("operator", "operator", "combo", 
                            ["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="], "+")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this operator block, with placeholders for operands"""
        operator = self.get_input_value("operator")
        
        # Create code with placeholders for left and right operands
        code = f"({{LEFT_CODE}} {operator} {{RIGHT_CODE}})"
        
        # Add placeholder for bottom code if this is used in a sequence
        if self.connected_blocks[self.BOTTOM]:
            code += "\n" + " " * indent + "{{BOTTOM_CODE}}"
            
        return code

class LogicalOperatorBlock(Block):
    """Block for logical operators (AND, OR, NOT)"""
    
    def __init__(self):
        super().__init__(Block.OVAL, Block.OPERATOR, "Logical Operator")
        self.width = 200
        self.height = 60
        
        # Enable left and right connection points for operands
        self.connection_defs['left']['enabled'] = True
        self.connection_defs['right']['enabled'] = True
        
        # Add input fields
        self.add_input_field("operator", "operator", "combo", ["&&", "||", "!"], "&&")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this logical operator block, with placeholders for operands"""
        operator = self.get_input_value("operator")
        
        # Unary operator (NOT) vs Binary operator (AND, OR)
        if operator == "!":
            code = f"(!{{LEFT_CODE}})"
        else:
            code = f"({{LEFT_CODE}} {operator} {{RIGHT_CODE}})"
        
        # Add placeholder for bottom code if this is used in a sequence
        if self.connected_blocks[self.BOTTOM]:
            code += "\n" + " " * indent + "{{BOTTOM_CODE}}"
            
        return code

class AssignmentOperatorBlock(Block):
    """Block for various assignment operators"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.OPERATOR, "Assignment")
        self.width = 200
        self.height = 80
        
        # Add input fields
        self.add_input_field("variable", "variable", "text", default_value="x")
        self.add_input_field("value", "value", "text", default_value="0")
        
        # Create the connection points (only top and bottom enabled by default)
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this assignment block, with placeholders for connected code"""
        variable = self.get_input_value("variable")
        value = self.get_input_value("value")
        
        code = " " * indent + f"{variable} = {value};\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class IncrementDecrementBlock(Block):
    """Block for increment and decrement operators"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.OPERATOR, "Inc/Dec")
        self.width = 180
        self.height = 60
        
        # Add input fields
        self.add_input_field("variable", "variable", "text", default_value="i")
        self.add_input_field("operator", "operator", "combo", ["++", "--"], "++")
        
        # Create the connection points (only top and bottom enabled by default)
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this increment/decrement block, with placeholders for connected code"""
        variable = self.get_input_value("variable")
        operator = self.get_input_value("operator")
        
        # Default to postfix increment/decrement (i++)
        code = " " * indent + f"{variable}{operator};\n"
        code += "{{BOTTOM_CODE}}"
        
        return code

class ArrayAccessBlock(Block):
    """Block for accessing array elements"""
    
    def __init__(self):
        super().__init__(Block.OVAL, Block.OPERATOR, "Array Access")
        self.width = 180
        self.height = 60
        
        # Add input fields
        self.add_input_field("array", "array", "text", default_value="arr")
        self.add_input_field("index", "index", "text", default_value="i")
        
        # Enable left and right connection points for use in expressions
        self.connection_defs['left']['enabled'] = True
        self.connection_defs['right']['enabled'] = True
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this array access block, with placeholders for connected code"""
        array = self.get_input_value("array")
        index = self.get_input_value("index")
        
        code = f"{array}[{index}]"
        
        # Add placeholder for bottom code if this is used in a sequence
        if self.connected_blocks[self.BOTTOM]:
            code += "\n" + " " * indent + "{{BOTTOM_CODE}}"
            
        return code

class TernaryOperatorBlock(Block):
    """Block for ternary conditional operator (? :)"""
    
    def __init__(self):
        super().__init__(Block.OVAL, Block.OPERATOR, "Ternary")
        self.width = 220
        self.height = 80
        
        # Add input fields
        self.add_input_field("condition", "condition", "text", default_value="x > 0")
        self.add_input_field("true_value", "true", "text", default_value="1")
        self.add_input_field("false_value", "false", "text", default_value="0")
        
        # Enable left and right connection points for use in expressions
        self.connection_defs['left']['enabled'] = True
        self.connection_defs['right']['enabled'] = True
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this ternary operator block, with placeholders for connected code"""
        condition = self.get_input_value("condition")
        true_value = self.get_input_value("true_value")
        false_value = self.get_input_value("false_value")
        
        code = f"({condition} ? {true_value} : {false_value})"
        
        # Add placeholder for bottom code if this is used in a sequence
        if self.connected_blocks[self.BOTTOM]:
            code += "\n" + " " * indent + "{{BOTTOM_CODE}}"
            
        return code