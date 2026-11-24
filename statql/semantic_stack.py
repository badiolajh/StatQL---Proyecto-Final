"""
statql/semantic_stack.py
Pila Semántica Explícita para StatQL.
Implementa el mecanismo clásico de acciones semánticas y control de expresiones
(basado en Esquemas de Traducción Dirigida por la Sintaxis - SDTS).
Gestiona la validación de operandos, operadores, coerción de tipos (I2D) y delimitación de ámbitos.
"""

from typing import List, Optional, Tuple, Any, Dict
from .ast_nodes import ASTNode, ExpressionNode, I2DNode


class SemanticEntry:
    """
    Elemento individual almacenado en la Pila Semántica.
    Puede representar un operando con su tipo inferido, un operador, o un delimitador de ámbito.
    """
    def __init__(self, entry_type: str, value: Any, type_name: Optional[str] = None,
                 line: int = 1, column: int = 1, **metadata: Any):
        # entry_type: 'OPERANDO', 'OPERADOR', 'TIPO', 'MARCADOR_AMBITO', 'NODO'
        self.entry_type = entry_type
        self.value = value
        self.type_name = type_name
        self.line = line
        self.column = column
        self.metadata: Dict[str, Any] = dict(metadata)

    def __repr__(self) -> str:
        type_str = f":{self.type_name}" if self.type_name else ""
        return f"[{self.entry_type} '{self.value}'{type_str} (L{self.line}:C{self.column})]"


class SemanticStack:
    """
    Pila Semántica explícita para la verificación de tipos, promociones I2D y marcos de ámbito.
    Permite reducir expresiones mediante reglas de tipos formales y registrar la traza de ejecución.
    """

    def __init__(self):
        self._stack: List[SemanticEntry] = []
        self._trace: List[str] = []

    def push(self, entry: SemanticEntry) -> None:
        """Introduce una entrada en la cima de la pila semántica."""
        self._stack.append(entry)
        self._log(f"PUSH -> {entry}")

    def pop(self) -> SemanticEntry:
        """Extrae y retorna la entrada en la cima de la pila semántica."""
        if not self._stack:
            raise IndexError("Error interno del compilador: Subdesbordamiento (underflow) de la pila semántica.")
        entry = self._stack.pop()
        self._log(f"POP  <- {entry}")
        return entry

    def peek(self, depth: int = 0) -> Optional[SemanticEntry]:
        """Inspecciona la entrada a cierta profundidad sin extraerla (0 = cima)."""
        idx = len(self._stack) - 1 - depth
        if 0 <= idx < len(self._stack):
            return self._stack[idx]
        return None

    def is_empty(self) -> bool:
        """Verifica si la pila se encuentra vacía."""
        return len(self._stack) == 0

    def size(self) -> int:
        """Retorna la cantidad actual de elementos en la pila."""
        return len(self._stack)

    def clear(self) -> None:
        """Reinicia la pila semántica."""
        self._stack.clear()
        self._trace.clear()

    # --- Operaciones de Alto Nivel para Expresiones ---

    def push_operand(self, node: ExpressionNode, inferred_type: str) -> None:
        """Empuja un nodo de expresión junto con su tipo estático determinado."""
        entry = SemanticEntry(
            entry_type="OPERANDO",
            value=node,
            type_name=inferred_type,
            line=node.line,
            column=node.column
        )
        self.push(entry)

    def push_operator(self, op: str, line: int = 1, column: int = 1) -> None:
        """Empuja un operador aritmético, relacional o lógico a la pila."""
        entry = SemanticEntry(entry_type="OPERADOR", value=op, line=line, column=column)
        self.push(entry)

    def push_scope_marker(self, scope_name: str) -> None:
        """Introduce una marca de apertura de ámbito léxico."""
        entry = SemanticEntry(entry_type="MARCADOR_AMBITO", value=scope_name)
        self.push(entry)

    def pop_scope_marker(self, expected_name: Optional[str] = None) -> List[SemanticEntry]:
        """
        Desapila todas las entradas hasta encontrar el delimitador de ámbito correspondiente.
        Retorna las entradas que pertenecían a dicho marco de ejecución.
        """
        unwound: List[SemanticEntry] = []
        while not self.is_empty():
            top = self.pop()
            if top.entry_type == "MARCADOR_AMBITO":
                if expected_name and top.value != expected_name:
                    self._log(f"ADVERTENCIA: Cierre de ámbito esperado '{expected_name}', encontrado '{top.value}'")
                return unwound
            unwound.append(top)
        return unwound

    def evaluate_binary_type(self, op: str, left_type: str, right_type: str,
                             line: int = 1, column: int = 1) -> Tuple[str, str]:
        """
        Valida la compatibilidad de tipos para un operador binario.
        Retorna una tupla (tipo_resultado, estrategia_coercion):
        estrategia_coercion: 'NONE', 'I2D_LEFT', 'I2D_RIGHT'
        Lanza TypeError con mensaje detallado si la operación es inválida.
        """
        # 1. Operadores Lógicos: 'y', 'o'
        if op in ("y", "o"):
            if left_type != "booleano" or right_type != "booleano":
                raise TypeError(
                    f"Operador lógico '{op}' requiere operandos de tipo 'booleano', pero recibió '{left_type}' y '{right_type}'."
                )
            return "booleano", "NONE"

        # 2. Operadores Relacionales: '==', '!=', '<', '>', '<=', '>='
        if op in ("==", "!=", "<", ">", "<=", ">="):
            # Coerción entero -> decimal en comparaciones numéricas
            if left_type == "entero" and right_type == "decimal":
                return "booleano", "I2D_LEFT"
            if left_type == "decimal" and right_type == "entero":
                return "booleano", "I2D_RIGHT"

            if left_type == right_type:
                # Ordenamiento y comparación numérica o cadenas
                if left_type in ("entero", "decimal", "texto"):
                    return "booleano", "NONE"
                # Igualdad/desigualdad booleana
                if left_type == "booleano" and op in ("==", "!="):
                    return "booleano", "NONE"

            raise TypeError(
                f"Operador relacional '{op}' no es válido entre tipos incompatibles '{left_type}' y '{right_type}'."
            )

        # 3. Operadores Aritméticos: '+', '-', '*', '/'
        if op in ("+", "-", "*", "/"):
            # Sobrecarga de '+' para concatenación de texto
            if op == "+" and left_type == "texto" and right_type == "texto":
                return "texto", "NONE"

            # Coerción entera a decimal (I2D)
            if left_type == "entero" and right_type == "decimal":
                return "decimal", "I2D_LEFT"
            if left_type == "decimal" and right_type == "entero":
                return "decimal", "I2D_RIGHT"

            if left_type == "entero" and right_type == "entero":
                return "entero", "NONE"
            if left_type == "decimal" and right_type == "decimal":
                return "decimal", "NONE"

            raise TypeError(
                f"Operación aritmética '{op}' no permitida entre '{left_type}' y '{right_type}'."
            )

        raise TypeError(f"Operador binario no reconocido: '{op}'.")

    def evaluate_unary_type(self, op: str, operand_type: str,
                            line: int = 1, column: int = 1) -> str:
        """
        Valida la compatibilidad de tipos para un operador unario.
        Retorna el tipo resultante o lanza TypeError si es incompatible.
        """
        if op in ("+", "-"):
            if operand_type not in ("entero", "decimal"):
                raise TypeError(
                    f"Operador unario aritmético '{op}' requiere un tipo numérico ('entero' o 'decimal'), se obtuvo '{operand_type}'."
                )
            return operand_type

        if op == "no":
            if operand_type != "booleano":
                raise TypeError(
                    f"Operador de negación lógica 'no' requiere operando 'booleano', se obtuvo '{operand_type}'."
                )
            return "booleano"

        raise TypeError(f"Operador unario no reconocido: '{op}'.")

    def reduce_binary(self, op: str, line: int = 1, column: int = 1) -> Tuple[ExpressionNode, str]:
        """
        Ejecuta la reducción semántica de una operación binaria en la pila:
        1. Desapila operando derecho
        2. Desapila operando izquierdo
        3. Evalúa compatibilidad y determina coerción (I2D)
        4. Construye o promueve el sub-árbol AST
        5. Apila el nuevo operando reducido y retorna (nodo_resultante, tipo_inferido)
        """
        right_entry = self.pop()
        left_entry = self.pop()

        res_type, coercion = self.evaluate_binary_type(
            op, left_entry.type_name, right_entry.type_name, line, column
        )

        left_node: ExpressionNode = left_entry.value
        right_node: ExpressionNode = right_entry.value

        # Aplicar nodo de casting I2D si hubo promoción
        if coercion == "I2D_LEFT":
            promoted = I2DNode(left_node, line=left_node.line, column=left_node.column)
            promoted.inferred_type = "decimal"
            left_node = promoted
        elif coercion == "I2D_RIGHT":
            promoted = I2DNode(right_node, line=right_node.line, column=right_node.column)
            promoted.inferred_type = "decimal"
            right_node = promoted

        from .ast_nodes import BinaryOpNode
        bin_node = BinaryOpNode(left_node, op, right_node, line=line, column=column)
        bin_node.inferred_type = res_type

        # Apilar resultado
        self.push_operand(bin_node, res_type)
        return bin_node, res_type

    def _log(self, message: str) -> None:
        self._trace.append(message)

    def get_trace(self) -> List[str]:
        """Retorna la traza completa de acciones ejecutadas sobre la pila semántica."""
        return list(self._trace)
