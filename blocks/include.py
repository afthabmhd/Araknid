from blocks.base import Block

class IncludeBlock(Block):
    """Block for #include directives"""
    
    def __init__(self):
        super().__init__(Block.STACK, Block.VARIABLE, "Include")
        self.width = 220
        self.height = 60
        
        # Add input fields
        self.add_input_field("header", "header", "text", default_value="stdio.h")
        self.add_input_field("is_system", "system", "combo", ["yes", "no"], "yes")
        
        # Create the connection points
        self._create_connection_points()
        
    def generate_code_self(self, indent=0):
        """Generate code just for this include block, with placeholders for connected code"""
        header = self.get_input_value("header")
        is_system = self.get_input_value("is_system")
        
        # Format include differently based on system vs custom header
        if is_system == "yes":
            code = f"#include <{header}>\n"
        else:
            code = f"#include \"{header}\"\n"
        
        # Add placeholder for bottom code
        code += "{{BOTTOM_CODE}}"
        
        return code