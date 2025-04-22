class CodeGenerator:
    """Generator for C code from blocks"""
    
    def __init__(self):
        # Track includes for generated code
        self.includes = set()
        
    def generate_code(self, root_blocks):
        """Generate C code from the given root blocks"""
        # Clear includes - start with NO default includes
        self.includes = set()
        
        # We'll organize the code into sections
        include_section = []
        function_section = []
        global_section = []
        
        # For tracking processed blocks to avoid duplicates
        processed_blocks = set()
        
        # Process each root block
        for block in root_blocks:
            if block in processed_blocks:
                continue
                
            if block.__class__.__name__ == 'IncludeBlock':
                # Add to include section
                include_code = block.generate_code(0, processed_blocks)
                if include_code:  # Only add if code is generated
                    include_section.append(include_code)
                
            elif (block.__class__.__name__ == 'FunctionDeclarationBlock' or 
                  block.__class__.__name__ == 'MainFunctionBlock'):
                # Add to function section
                function_code = block.generate_code(0, processed_blocks)
                if function_code:  # Only add if code is generated
                    function_section.append(function_code)
            else:
                # Global section for any other valid root blocks
                global_code = block.generate_code(0, processed_blocks)
                if global_code:  # Only add if code is generated
                    global_section.append(global_code)
        
        # Join everything together
        code = ""
        
        # Add include blocks section first
        for include_code in include_section:
            if include_code and any(line.strip() for line in include_code.split('\n')):
                code += include_code
                
        # Add global section
        if global_section:
            for global_code in global_section:
                if global_code and any(line.strip() for line in global_code.split('\n')):
                    code += global_code
            code += "\n"
            
        # Add function section
        for function_code in function_section:
            if function_code and any(line.strip() for line in function_code.split('\n')):
                code += function_code
                # Functions already add their own newlines, but add one more for spacing
                if not function_code.endswith("\n\n"):
                    code += "\n"
        
        return code
        
    def add_include(self, include):
        """Add an include statement to the generated code"""
        self.includes.add(include)
        
    def format_code(self, code):
        """Format C code with proper indentation and style"""
        # This is a simple formatter, a more sophisticated one could be implemented
        # For example, using a library like clang-format via subprocess
        
        lines = code.split("\n")
        indent_level = 0
        formatted_lines = []
        
        for line in lines:
            # Remove leading/trailing whitespace
            stripped = line.strip()
            
            # Handle indentation changes
            if stripped.endswith("{"):
                formatted_lines.append("  " * indent_level + stripped)
                indent_level += 1
            elif stripped.startswith("}"):
                indent_level = max(0, indent_level - 1)
                formatted_lines.append("  " * indent_level + stripped)
            else:
                formatted_lines.append("  " * indent_level + stripped)
                
        return "\n".join(formatted_lines)
