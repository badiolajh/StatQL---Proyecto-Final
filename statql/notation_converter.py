from typing import List
from .ast_nodes import (
    ExpressionNode, BinaryOpNode, UnaryOpNode,
    LiteralNode, VariableNode, PropertyAccessNode, I2DNode
)
from .lexer import Lexer
from .parser import Parser


class NotationConverter:

    @staticmethod
    def _format_literal(node: LiteralNode) -> str:
        if node.raw_type == "texto":
            return f'"{node.value}"'
        if node.raw_type == "booleano":
            return "verdadero" if node.value else "falso"
        return str(node.value)

    @classmethod
    def ast_to_infix(cls, node: ExpressionNode) -> str:
        if isinstance(node, LiteralNode):
            return cls._format_literal(node)
        if isinstance(node, VariableNode):
            return node.name
        if isinstance(node, PropertyAccessNode):
            return f"{node.obj_name}.{node.property_name}"
        if isinstance(node, I2DNode):
            return f"I2D({cls.ast_to_infix(node.expr)})"
        if isinstance(node, UnaryOpNode):
            op = "no " if node.op == "no" else node.op
            return f"({op}{cls.ast_to_infix(node.operand)})"
        if isinstance(node, BinaryOpNode):
            left_str = cls.ast_to_infix(node.left)
            right_str = cls.ast_to_infix(node.right)
            return f"({left_str} {node.op} {right_str})"
        raise ValueError(f"Nodo de expresión no soportado: {type(node).__name__}")

    @classmethod
    def ast_to_postfix_tokens(cls, node: ExpressionNode) -> List[str]:
        if isinstance(node, LiteralNode):
            return [cls._format_literal(node)]
        if isinstance(node, VariableNode):
            return [node.name]
        if isinstance(node, PropertyAccessNode):
            return [f"{node.obj_name}.{node.property_name}"]
        if isinstance(node, I2DNode):
            return cls.ast_to_postfix_tokens(node.expr) + ["I2D"]
        if isinstance(node, UnaryOpNode):
            op_token = "u-" if node.op == "-" else ("u+" if node.op == "+" else node.op)
            return cls.ast_to_postfix_tokens(node.operand) + [op_token]
        if isinstance(node, BinaryOpNode):
            return (
                cls.ast_to_postfix_tokens(node.left)
                + cls.ast_to_postfix_tokens(node.right)
                + [node.op]
            )
        raise ValueError(f"Nodo de expresión no soportado: {type(node).__name__}")

    @classmethod
    def ast_to_prefix_tokens(cls, node: ExpressionNode) -> List[str]:
        if isinstance(node, LiteralNode):
            return [cls._format_literal(node)]
        if isinstance(node, VariableNode):
            return [node.name]
        if isinstance(node, PropertyAccessNode):
            return [f"{node.obj_name}.{node.property_name}"]
        if isinstance(node, I2DNode):
            return ["I2D"] + cls.ast_to_prefix_tokens(node.expr)
        if isinstance(node, UnaryOpNode):
            op_token = "u-" if node.op == "-" else ("u+" if node.op == "+" else node.op)
            return [op_token] + cls.ast_to_prefix_tokens(node.operand)
        if isinstance(node, BinaryOpNode):
            return (
                [node.op]
                + cls.ast_to_prefix_tokens(node.left)
                + cls.ast_to_prefix_tokens(node.right)
            )
        raise ValueError(f"Nodo de expresión no soportado: {type(node).__name__}")

    @classmethod
    def ast_to_postfix(cls, node: ExpressionNode) -> str:
        return " ".join(cls.ast_to_postfix_tokens(node))

    @classmethod
    def ast_to_prefix(cls, node: ExpressionNode) -> str:
        return " ".join(cls.ast_to_prefix_tokens(node))

    @classmethod
    def infix_str_to_postfix(cls, infix_expr: str) -> str:
        tokens = Lexer(infix_expr).tokenize()
        expr_node = Parser(tokens).parse_expresion()
        return cls.ast_to_postfix(expr_node)

    @classmethod
    def infix_str_to_prefix(cls, infix_expr: str) -> str:
        tokens = Lexer(infix_expr).tokenize()
        expr_node = Parser(tokens).parse_expresion()
        return cls.ast_to_prefix(expr_node)