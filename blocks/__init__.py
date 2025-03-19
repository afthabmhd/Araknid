# Import classes from block modules
from blocks.base import Block, ConnectionPoint, ConnectionLine
from blocks.variables import VariableDeclarationBlock, VariableAssignmentBlock, ArrayDeclarationBlock
from blocks.control import IfBlock, ElseBlock, ForLoopBlock, WhileLoopBlock, BreakBlock, ContinueBlock
from blocks.io import PrintBlock, ScanBlock, PrintStringBlock, PrintfNewlineBlock
from blocks.operators import (OperatorBlock, LogicalOperatorBlock, AssignmentOperatorBlock, 
                           IncrementDecrementBlock, ArrayAccessBlock, TernaryOperatorBlock)
from blocks.functions import (FunctionDeclarationBlock, FunctionCallBlock, ReturnBlock, 
                            MainFunctionBlock)
from blocks.include import IncludeBlock

# Export all block classes
__all__ = [
    # Base
    'Block',
    'ConnectionPoint',
    'ConnectionLine',
    
    # Include
    'IncludeBlock',
    
    # Variables
    'VariableDeclarationBlock',
    'VariableAssignmentBlock',
    'ArrayDeclarationBlock',
    
    # Control Flow
    'IfBlock',
    'ElseBlock',
    'ForLoopBlock',
    'WhileLoopBlock',
    'BreakBlock',
    'ContinueBlock',
    
    # I/O
    'PrintBlock',
    'ScanBlock',
    'PrintStringBlock',
    'PrintfNewlineBlock',
    
    # Operators
    'OperatorBlock',
    'LogicalOperatorBlock',
    'AssignmentOperatorBlock',
    'IncrementDecrementBlock',
    'ArrayAccessBlock',
    'TernaryOperatorBlock',
    
    # Functions
    'FunctionDeclarationBlock',
    'FunctionCallBlock',
    'ReturnBlock',
    'MainFunctionBlock'
]