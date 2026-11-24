"""
statql/ast_nodes.py
Definición de Nodos del Árbol de Sintaxis Abstracta (AST) para StatQL.
Soporta anotación estática de tipos, inserción explícita de nodos de casting (I2D),
direcciones simbólicas para código intermedio y visualización jerárquica del AST.
"""

from typing import List, Optional, Any, Tuple


class ASTNode:
    """Clase base para todos los nodos del Árbol de Sintaxis Abstracta (AST)."""
    def __init__(self, line: int = 1, column: int = 1):
        self.line = line
        self.column = column

    def accept(self, visitor: Any, *args: Any, **kwargs: Any) -> Any:
        """Patrón Visitor para recorridos desacoplados del AST."""
        method_name = f"visit_{self.__class__.__name__}"
        visitor_fn = getattr(visitor, method_name, visitor.generic_visit)
        return visitor_fn(self, *args, **kwargs)

    def pretty_format(self, indent: str = "", is_last: bool = True) -> str:
        """Formatea el nodo y sus ramas descendientes como un árbol visual Unicode."""
        connector = "└── " if is_last else "├── "
        result = indent + connector + self._node_label() + "\n"
        child_indent = indent + ("    " if is_last else "│   ")

        children = self._get_children()
        for i, child in enumerate(children):
            is_child_last = (i == len(children) - 1)
            if isinstance(child, ASTNode):
                result += child.pretty_format(child_indent, is_child_last)
            elif isinstance(child, tuple) and len(child) == 2 and isinstance(child[1], ASTNode):
                label, node = child
                conn = "└── " if is_child_last else "├── "
                result += child_indent + conn + f"[{label}]\n"
                next_indent = child_indent + ("    " if is_child_last else "│   ")
                result += node.pretty_format(next_indent, True)
        return result

    def _node_label(self) -> str:
        return f"{self.__class__.__name__} (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return []


class ExpressionNode(ASTNode):
    """
    Clase base para expresiones evaluables.
    Contiene la anotación estática de tipo y dirección simbólica generada por el Módulo Semántico.
    """
    def __init__(self, line: int = 1, column: int = 1):
        super().__init__(line, column)
        # Tipo inferido durante el análisis semántico: 'entero', 'decimal', 'texto', 'booleano'
        self.inferred_type: Optional[str] = None
        # Gancho / Hook para Integrante 2: dirección simbólica, registro temporal o ubicación
        self.address: Optional[str] = None


class ProgramNode(ASTNode):
    """Nodo raíz del programa StatQL."""
    def __init__(self, statements: List[ASTNode], line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.statements = statements

    def _node_label(self) -> str:
        return f"Programa ({len(self.statements)} sentencias)"

    def _get_children(self) -> List[Any]:
        return self.statements


class BlockNode(ASTNode):
    """Bloque de sentencias delimitado por llaves { }."""
    def __init__(self, statements: List[ASTNode], line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.statements = statements

    def _node_label(self) -> str:
        return f"Bloque ({len(self.statements)} sentencias) (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return self.statements


# --- Sentencias Simples ---

class CargaNode(ASTNode):
    """Sentencia: 'cargar CADENA como ID'."""
    def __init__(self, path: str, alias: str, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.path = path
        self.alias = alias

    def _node_label(self) -> str:
        return f"Carga: '{self.path}' como '{self.alias}' (L{self.line}:C{self.column})"


class DeclaracionNode(ASTNode):
    """Sentencia: 'Tipo ID = Expresion'."""
    def __init__(self, tipo: str, name: str, expr: ExpressionNode, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.tipo = tipo
        self.name = name
        self.expr = expr

    def _node_label(self) -> str:
        return f"Declaracion: {self.tipo} {self.name} (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return [self.expr]


class AsignacionNode(ASTNode):
    """Sentencia: 'ID = Expresion'."""
    def __init__(self, name: str, expr: ExpressionNode, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.name = name
        self.expr = expr

    def _node_label(self) -> str:
        return f"Asignacion: {self.name} = (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return [self.expr]


class MostrarNode(ASTNode):
    """Sentencia: 'mostrar Expresion'."""
    def __init__(self, expr: ExpressionNode, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.expr = expr

    def _node_label(self) -> str:
        return f"Mostrar (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return [self.expr]


class EntrenarNode(ASTNode):
    """Sentencia: 'entrenar arbol con ID objetivo CADENA como ID'."""
    def __init__(self, dataset: str, target_col: str, model_alias: str, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.dataset = dataset
        self.target_col = target_col
        self.model_alias = model_alias

    def _node_label(self) -> str:
        return (f"Entrenar: arbol con '{self.dataset}' objetivo '{self.target_col}' "
                f"como '{self.model_alias}' (L{self.line}:C{self.column})")


# --- Sentencias de Control de Flujo ---

class SiNode(ASTNode):
    """Sentencia: 'si (Expresion) Bloque [sino Bloque]'."""
    def __init__(self, condition: ExpressionNode, then_block: BlockNode,
                 else_block: Optional[BlockNode] = None, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block

    def _node_label(self) -> str:
        return f"Si (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        children: List[Any] = [("condición", self.condition), ("entonces", self.then_block)]
        if self.else_block:
            children.append(("sino", self.else_block))
        return children


class ParaCadaNode(ASTNode):
    """Sentencia: 'para cada ID en ID Bloque'."""
    def __init__(self, item_var: str, dataset_var: str, block: BlockNode, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.item_var = item_var
        self.dataset_var = dataset_var
        self.block = block

    def _node_label(self) -> str:
        return f"ParaCada: {self.item_var} en {self.dataset_var} (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return [("cuerpo", self.block)]


class MientrasNode(ASTNode):
    """Sentencia: 'mientras (Expresion) Bloque'."""
    def __init__(self, condition: ExpressionNode, block: BlockNode, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.condition = condition
        self.block = block

    def _node_label(self) -> str:
        return f"Mientras (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return [("condición", self.condition), ("cuerpo", self.block)]


# --- Expresiones ---

class BinaryOpNode(ExpressionNode):
    """Operación binaria: aritmética (+, -, *, /), relacional (==, !=, <, >, <=, >=) o lógica (y, o)."""
    def __init__(self, left: ExpressionNode, op: str, right: ExpressionNode, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.left = left
        self.op = op
        self.right = right

    def _node_label(self) -> str:
        type_str = f" : {self.inferred_type}" if self.inferred_type else ""
        return f"OpBinaria('{self.op}'){type_str} (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return [self.left, self.right]


class UnaryOpNode(ExpressionNode):
    """Operación unaria: '+', '-', 'no'."""
    def __init__(self, op: str, operand: ExpressionNode, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.op = op
        self.operand = operand

    def _node_label(self) -> str:
        type_str = f" : {self.inferred_type}" if self.inferred_type else ""
        return f"OpUnaria('{self.op}'){type_str} (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return [self.operand]


class LiteralNode(ExpressionNode):
    """Literal con valor constante: entero, decimal, texto o booleano."""
    def __init__(self, value: Any, raw_type: str, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.value = value
        self.raw_type = raw_type
        self.inferred_type = raw_type

    def _node_label(self) -> str:
        val_repr = repr(self.value)
        return f"Literal({val_repr} : {self.inferred_type}) (L{self.line}:C{self.column})"


class VariableNode(ExpressionNode):
    """Referencia a un identificador simple."""
    def __init__(self, name: str, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.name = name

    def _node_label(self) -> str:
        type_str = f" : {self.inferred_type}" if self.inferred_type else ""
        return f"Variable({self.name}{type_str}) (L{self.line}:C{self.column})"


class PropertyAccessNode(ExpressionNode):
    """Acceso a propiedad o columna tabular: ID.ID (e.g. fila.edad o datos.promedio)."""
    def __init__(self, obj_name: str, property_name: str, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.obj_name = obj_name
        self.property_name = property_name

    def _node_label(self) -> str:
        type_str = f" : {self.inferred_type}" if self.inferred_type else ""
        return f"Propiedad({self.obj_name}.{self.property_name}{type_str}) (L{self.line}:C{self.column})"


class I2DNode(ExpressionNode):
    """
    Nodo explícito de coerción / casting de tipos: entero a decimal (Integer-to-Double/Decimal).
    Insertado automáticamente por el analizador semántico para garantizar que los módulos de
    código intermedio y optimización no requieran lógica de coerción implícita.
    """
    def __init__(self, expr: ExpressionNode, line: int = 1, column: int = 1):
        super().__init__(line, column)
        self.expr = expr
        self.inferred_type = "decimal"

    def _node_label(self) -> str:
        return f"I2D (Casting explícito entero -> decimal) (L{self.line}:C{self.column})"

    def _get_children(self) -> List[Any]:
        return [self.expr]
