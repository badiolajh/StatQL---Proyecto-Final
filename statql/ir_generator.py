from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode,
    CargaNode, DeclaracionNode, AsignacionNode, MostrarNode, EntrenarNode,
    SiNode, ParaCadaNode, MientrasNode,
    BinaryOpNode, UnaryOpNode, LiteralNode, VariableNode, PropertyAccessNode,
    I2DNode
)
from .symbol_table import SymbolTable, ReferenceTable, Symbol


@dataclass
class Quadruple:
    op: str
    arg1: Optional[Any]
    arg2: Optional[Any]
    result: Optional[Any]
    inferred_type: Optional[str] = None

    def to_tuple(self) -> Tuple[str, Optional[Any], Optional[Any], Optional[Any]]:
        return (self.op, self.arg1, self.arg2, self.result)

    def __str__(self) -> str:
        a1 = self.arg1 if self.arg1 is not None else "_"
        a2 = self.arg2 if self.arg2 is not None else "_"
        res = self.result if self.result is not None else "_"
        return f"({self.op}, {a1}, {a2}, {res})"


class IntermediateCodeGenerator:

    def __init__(self, ir_context: Dict[str, Any]):
        if ir_context.get("errors"):
            raise ValueError("No se puede generar código intermedio de un AST con errores semánticos.")

        self.ast: ProgramNode = ir_context["ast"]
        self.global_table: SymbolTable = ir_context["global_table"]
        self.reference_table: ReferenceTable = ir_context["reference_table"]
        self.csv_loader = ir_context.get("csv_loader")

        self.quadruples: List[Quadruple] = []
        self.temp_counter: int = 0
        self.label_counter: int = 0

        self.current_scope: SymbolTable = self.global_table
        self._child_scope_indices: Dict[int, int] = {}

    def new_temp(self) -> str:
        temp_name = f"t{self.temp_counter}"
        self.temp_counter += 1
        return temp_name

    def new_label(self, prefix: str = "L") -> str:
        label_name = f"{prefix}{self.label_counter}"
        self.label_counter += 1
        return label_name

    def emit(self, op: str, arg1: Optional[Any] = None, arg2: Optional[Any] = None,
             result: Optional[Any] = None, inferred_type: Optional[str] = None) -> Quadruple:
        quad = Quadruple(op=op, arg1=arg1, arg2=arg2, result=result, inferred_type=inferred_type)
        self.quadruples.append(quad)
        return quad

    def _enter_next_child_scope(self) -> SymbolTable:
        parent_id = id(self.current_scope)
        idx = self._child_scope_indices.get(parent_id, 0)
        if idx < len(self.current_scope.children):
            child = self.current_scope.children[idx]
            self._child_scope_indices[parent_id] = idx + 1
            self.current_scope = child
        return self.current_scope

    def _exit_scope(self) -> None:
        if self.current_scope.parent is not None:
            self.current_scope = self.current_scope.parent

    def _resolve_symbol_address(self, name: str) -> str:
        sym: Optional[Symbol] = self.current_scope.lookup(name)
        if sym and sym.symbolic_address:
            return sym.symbolic_address
        return name

    def generate(self) -> List[Quadruple]:
        self.quadruples.clear()
        self.temp_counter = 0
        self.label_counter = 0
        self.current_scope = self.global_table
        self._child_scope_indices.clear()

        if self.ast is not None:
            self.visit(self.ast)

        self.emit("HALT", None, None, None)
        return self.quadruples

    def get_optimizer_input_context(self) -> Dict[str, Any]:
        return {
            "quadruples": self.quadruples,
            "raw_tuples": [q.to_tuple() for q in self.quadruples],
            "temp_count": self.temp_counter,
            "label_count": self.label_counter,
            "global_table": self.global_table,
            "reference_table": self.reference_table,
            "ast": self.ast
        }

    def pretty_format(self) -> str:
        lines = [
            f"{'#':<4} | {'Operador':<14} | {'Arg1':<24} | {'Arg2':<24} | {'Resultado':<24}",
            f"{'-'*4}-+-{'-'*14}-+-{'-'*24}-+-{'-'*24}-+-{'-'*24}"
        ]
        for idx, q in enumerate(self.quadruples):
            a1 = str(q.arg1) if q.arg1 is not None else "-"
            a2 = str(q.arg2) if q.arg2 is not None else "-"
            res = str(q.result) if q.result is not None else "-"
            lines.append(f"{idx:<4} | {q.op:<14} | {a1:<24} | {a2:<24} | {res:<24}")
        return "\n".join(lines)

    def visit(self, node: ASTNode) -> Any:
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ASTNode) -> Any:
        raise NotImplementedError(f"Generación de cuádruplas no implementada para {node.__class__.__name__}.")

    def visit_ProgramNode(self, node: ProgramNode) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    def visit_BlockNode(self, node: BlockNode) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    def visit_CargaNode(self, node: CargaNode) -> None:
        target_addr = self._resolve_symbol_address(node.alias)
        self.emit("LOAD_CSV", f'"{node.path}"', None, target_addr, inferred_type="tabla")

    def visit_DeclaracionNode(self, node: DeclaracionNode) -> None:
        expr_addr = self.visit(node.expr)
        target_addr = self._resolve_symbol_address(node.name)
        self.emit("=", expr_addr, None, target_addr, inferred_type=node.tipo)

    def visit_AsignacionNode(self, node: AsignacionNode) -> None:
        expr_addr = self.visit(node.expr)
        target_addr = self._resolve_symbol_address(node.name)
        self.emit("=", expr_addr, None, target_addr, inferred_type=node.expr.inferred_type)

    def visit_MostrarNode(self, node: MostrarNode) -> None:
        expr_addr = self.visit(node.expr)
        self.emit("PRINT", expr_addr, None, None, inferred_type=node.expr.inferred_type)

    def visit_EntrenarNode(self, node: EntrenarNode) -> None:
        dataset_addr = self._resolve_symbol_address(node.dataset)
        model_addr = self._resolve_symbol_address(node.model_alias)
        self.emit("TRAIN_TREE", dataset_addr, f'"{node.target_col}"', model_addr, inferred_type="modelo")

    def visit_SiNode(self, node: SiNode) -> None:
        cond_addr = self.visit(node.condition)

        if node.else_block is not None:
            label_else = self.new_label("L_else_")
            label_end = self.new_label("L_endif_")

            self.emit("IF_FALSE", cond_addr, None, label_else)

            self._enter_next_child_scope()
            self.visit(node.then_block)
            self._exit_scope()

            self.emit("GOTO", None, None, label_end)
            self.emit("LABEL", None, None, label_else)

            self._enter_next_child_scope()
            self.visit(node.else_block)
            self._exit_scope()

            self.emit("LABEL", None, None, label_end)
        else:
            label_end = self.new_label("L_endif_")
            self.emit("IF_FALSE", cond_addr, None, label_end)

            self._enter_next_child_scope()
            self.visit(node.then_block)
            self._exit_scope()

            self.emit("LABEL", None, None, label_end)

    def visit_MientrasNode(self, node: MientrasNode) -> None:
        label_start = self.new_label("L_while_start_")
        label_end = self.new_label("L_while_end_")

        self.emit("LABEL", None, None, label_start)
        cond_addr = self.visit(node.condition)
        self.emit("IF_FALSE", cond_addr, None, label_end)

        self._enter_next_child_scope()
        self.visit(node.block)
        self._exit_scope()

        self.emit("GOTO", None, None, label_start)
        self.emit("LABEL", None, None, label_end)

    def visit_ParaCadaNode(self, node: ParaCadaNode) -> None:
        dataset_addr = self._resolve_symbol_address(node.dataset_var)
        cursor_temp = self.new_temp()
        label_start = self.new_label("L_foreach_start_")
        label_end = self.new_label("L_foreach_end_")

        self.emit("ITER_INIT", dataset_addr, None, cursor_temp)

        self._enter_next_child_scope()
        item_addr = self._resolve_symbol_address(node.item_var)

        self.emit("LABEL", None, None, label_start)
        self.emit("ITER_NEXT", cursor_temp, None, item_addr, inferred_type="fila")
        self.emit("IF_FALSE", item_addr, None, label_end)

        self.visit(node.block)

        self._exit_scope()

        self.emit("GOTO", None, None, label_start)
        self.emit("LABEL", None, None, label_end)

    def visit_LiteralNode(self, node: LiteralNode) -> str:
        if node.raw_type == "texto":
            return f'"{node.value}"'
        if node.raw_type == "booleano":
            return "verdadero" if node.value else "falso"
        return str(node.value)

    def visit_VariableNode(self, node: VariableNode) -> str:
        if node.address:
            return node.address
        return self._resolve_symbol_address(node.name)

    def visit_PropertyAccessNode(self, node: PropertyAccessNode) -> str:
        obj_addr = self._resolve_symbol_address(node.obj_name)
        temp = self.new_temp()
        node.address = temp
        self.emit("GET_COL", obj_addr, f'"{node.property_name}"', temp, inferred_type=node.inferred_type)
        return temp

    def visit_I2DNode(self, node: I2DNode) -> str:
        operand_addr = self.visit(node.expr)
        temp = self.new_temp()
        node.address = temp
        self.emit("I2D", operand_addr, None, temp, inferred_type="decimal")
        return temp

    def visit_UnaryOpNode(self, node: UnaryOpNode) -> str:
        operand_addr = self.visit(node.operand)
        temp = self.new_temp()
        node.address = temp
        op_name = "UMINUS" if node.op == "-" else ("UPLUS" if node.op == "+" else "NOT")
        self.emit(op_name, operand_addr, None, temp, inferred_type=node.inferred_type)
        return temp

    def visit_BinaryOpNode(self, node: BinaryOpNode) -> str:
        left_addr = self.visit(node.left)
        right_addr = self.visit(node.right)
        temp = self.new_temp()
        node.address = temp
        self.emit(node.op, left_addr, right_addr, temp, inferred_type=node.inferred_type)
        return temp