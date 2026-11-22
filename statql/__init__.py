"""
statql - Statistical Query Language Compiler Package
Módulo 1: Análisis Semántico y Base Léxica / Sintáctica
"""

from .lexer import Lexer, Token, TokenType, LexerError
from .parser import Parser, ParserError
from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode,
    CargaNode, DeclaracionNode, AsignacionNode, MostrarNode, EntrenarNode,
    SiNode, ParaCadaNode, MientrasNode,
    BinaryOpNode, UnaryOpNode, LiteralNode, VariableNode, PropertyAccessNode,
    ExpressionNode, I2DNode
)
from .symbol_table import Symbol, SymbolTable, ReferenceTable
from .semantic_stack import SemanticStack, SemanticEntry
from .semantic_analyzer import SemanticAnalyzer, SemanticError, SemanticErrorCode
from .csv_loader import CSVLoader, CSVSchema, CSVLoadError

__all__ = [
    # Lexer
    "Lexer", "Token", "TokenType", "LexerError",
    # Parser
    "Parser", "ParserError",
    # AST
    "ASTNode", "ProgramNode", "BlockNode",
    "CargaNode", "DeclaracionNode", "AsignacionNode", "MostrarNode", "EntrenarNode",
    "SiNode", "ParaCadaNode", "MientrasNode",
    "BinaryOpNode", "UnaryOpNode", "LiteralNode", "VariableNode", "PropertyAccessNode",
    "ExpressionNode", "I2DNode",
    # Symbol Table
    "Symbol", "SymbolTable", "ReferenceTable",
    # Semantic Stack
    "SemanticStack", "SemanticEntry",
    # Semantic Analyzer
    "SemanticAnalyzer", "SemanticError", "SemanticErrorCode",
    # CSV Loader
    "CSVLoader", "CSVSchema", "CSVLoadError"
]
