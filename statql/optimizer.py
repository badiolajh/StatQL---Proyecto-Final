"""
statql/optimizer.py
Modulo 3: Optimizador de Codigo Intermedio (Cuadruplas 3AC) para StatQL.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .ir_generator import Quadruple
from .symbol_table import Symbol, SymbolTable, ReferenceTable


PURE_OPS: Set[str] = {
    "+", "-", "*", "/",
    "UMINUS", "UPLUS", "NOT",
    "==", "!=", "<", ">", "<=", ">=",
    "y", "o",
    "I2D", "="
}

JUMP_OPS: Set[str] = {"GOTO", "IF_FALSE"}


@dataclass
class OptimizationStats:
    initial_quadruples: int = 0
    final_quadruples: int = 0
    passes_executed: int = 0
    constants_folded: int = 0
    constants_propagated: int = 0
    algebraic_simplifications: int = 0
    peephole_optimizations: int = 0
    loop_invariants_moved: int = 0
    dead_code_eliminated: int = 0
    pass_details: List[str] = field(default_factory=list)

    @property
    def removed_count(self) -> int:
        return max(0, self.initial_quadruples - self.final_quadruples)

    @property
    def reduction_percentage(self) -> float:
        if self.initial_quadruples == 0:
            return 0.0
        return round((self.removed_count / self.initial_quadruples) * 100.0, 2)


class QuadrupleOptimizer:
    """
    Optimizador multipasada sobre representaciones intermedias en Cuadruplas 3AC.
    Consume los contratos del Modulo 1 (get_optimization_context)
    y del Modulo 2 (get_optimizer_input_context).
    """

    def __init__(
        self,
        ir_context: Dict[str, Any],
        semantic_opt_context: Optional[Dict[str, Any]] = None,
        max_passes: int = 5
    ):
        self.original_quadruples: List[Quadruple] = deepcopy(ir_context.get("quadruples", []))
        self.global_table: Optional[SymbolTable] = ir_context.get("global_table")
        self.reference_table: Optional[ReferenceTable] = ir_context.get("reference_table")
        self.ast = ir_context.get("ast")
        self.max_passes: int = max_passes

        self.unused_addresses: Set[str] = set()
        self.usage_counts: Dict[str, int] = {}

        if semantic_opt_context:
            for sym in semantic_opt_context.get("unused_symbols", []):
                if isinstance(sym, Symbol) and sym.symbolic_address:
                    self.unused_addresses.add(sym.symbolic_address)
                elif isinstance(sym, str):
                    self.unused_addresses.add(sym)
            self.usage_counts = dict(semantic_opt_context.get("symbol_usage_counts", {}))

        self.optimized_quadruples: List[Quadruple] = []
        self.stats = OptimizationStats(initial_quadruples=len(self.original_quadruples))

    @staticmethod
    def _parse_constant(val: Any) -> Tuple[bool, Any, Optional[str]]:
        if val is None or not isinstance(val, str):
            return False, None, None

        if val == "verdadero":
            return True, True, "booleano"
        if val == "falso":
            return True, False, "booleano"

        if len(val) >= 2 and val.startswith('"') and val.endswith('"'):
            return True, val[1:-1], "texto"

        if val.startswith(("t", "L_", "sym_", "ds_", "iter_", "model_")):
            return False, None, None

        try:
            if "." in val:
                return True, float(val), "decimal"
            return True, int(val), "entero"
        except ValueError:
            return False, None, None

    @staticmethod
    def _format_constant(value: Any, target_type: Optional[str] = None) -> str:
        if isinstance(value, bool):
            return "verdadero" if value else "falso"
        if isinstance(value, str):
            return f'"{value}"'
        if target_type == "decimal" or isinstance(value, float):
            return str(float(value))
        return str(int(value))

    @staticmethod
    def _is_temp(name: Any) -> bool:
        return isinstance(name, str) and name.startswith("t") and name[1:].isdigit()

    @staticmethod
    def _is_user_var(name: Any) -> bool:
        return isinstance(name, str) and name.startswith("sym_")

    def _split_basic_blocks(self, quads: List[Quadruple]) -> List[List[Quadruple]]:
        if not quads:
            return []

        leaders: Set[int] = {0}
        for i, q in enumerate(quads):
            if q.op == "LABEL":
                leaders.add(i)
            elif q.op in JUMP_OPS or q.op == "HALT":
                if i + 1 < len(quads):
                    leaders.add(i + 1)

        sorted_leaders = sorted(leaders)
        blocks: List[List[Quadruple]] = []
        for idx, start in enumerate(sorted_leaders):
            end = sorted_leaders[idx + 1] if idx + 1 < len(sorted_leaders) else len(quads)
            blocks.append(quads[start:end])
        return blocks

    def _evaluate_binary_const(
        self, op: str, v1: Any, t1: str, v2: Any, t2: str, inferred_type: Optional[str]
    ) -> Optional[Tuple[str, str]]:
        if op in {"+", "-", "*", "/"} and t1 in {"entero", "decimal"} and t2 in {"entero", "decimal"}:
            if op == "/" and v2 == 0:
                return None
            res_type = (
                "decimal"
                if (op == "/" or t1 == "decimal" or t2 == "decimal" or inferred_type == "decimal")
                else "entero"
            )
            if op == "+":
                val = v1 + v2
            elif op == "-":
                val = v1 - v2
            elif op == "*":
                val = v1 * v2
            else:
                val = v1 / v2
            return self._format_constant(val, res_type), res_type

        if op == "+" and t1 == "texto" and t2 == "texto":
            return self._format_constant(v1 + v2, "texto"), "texto"

        if op in {"==", "!=", "<", ">", "<=", ">="}:
            if op == "==":
                res = (v1 == v2)
            elif op == "!=":
                res = (v1 != v2)
            elif op == "<":
                res = (v1 < v2)
            elif op == ">":
                res = (v1 > v2)
            elif op == "<=":
                res = (v1 <= v2)
            else:
                res = (v1 >= v2)
            return self._format_constant(res, "booleano"), "booleano"

        if op in {"y", "o"} and t1 == "booleano" and t2 == "booleano":
            res = (v1 and v2) if op == "y" else (v1 or v2)
            return self._format_constant(res, "booleano"), "booleano"

        return None

    def _try_algebraic_simplification(self, q: Quadruple) -> Optional[Quadruple]:
        is_c1, v1, t1 = self._parse_constant(q.arg1)
        is_c2, v2, t2 = self._parse_constant(q.arg2)
        zero_lit = "0.0" if q.inferred_type == "decimal" else "0"

        if q.op == "+":
            if is_c2 and t2 in {"entero", "decimal"} and v2 == 0:
                return Quadruple("=", q.arg1, None, q.result, q.inferred_type)
            if is_c1 and t1 in {"entero", "decimal"} and v1 == 0:
                return Quadruple("=", q.arg2, None, q.result, q.inferred_type)

        elif q.op == "-":
            if is_c2 and t2 in {"entero", "decimal"} and v2 == 0:
                return Quadruple("=", q.arg1, None, q.result, q.inferred_type)
            if q.arg1 is not None and q.arg1 == q.arg2:
                return Quadruple("=", zero_lit, None, q.result, q.inferred_type)

        elif q.op == "*":
            if (is_c1 and t1 in {"entero", "decimal"} and v1 == 0) or (
                is_c2 and t2 in {"entero", "decimal"} and v2 == 0
            ):
                return Quadruple("=", zero_lit, None, q.result, q.inferred_type)
            if is_c2 and t2 in {"entero", "decimal"} and v2 == 1:
                return Quadruple("=", q.arg1, None, q.result, q.inferred_type)
            if is_c1 and t1 in {"entero", "decimal"} and v1 == 1:
                return Quadruple("=", q.arg2, None, q.result, q.inferred_type)
            if q.inferred_type == "entero":
                if is_c2 and t2 == "entero" and v2 == 2:
                    return Quadruple("+", q.arg1, q.arg1, q.result, q.inferred_type)
                if is_c1 and t1 == "entero" and v1 == 2:
                    return Quadruple("+", q.arg2, q.arg2, q.result, q.inferred_type)

        elif q.op == "/":
            if is_c2 and t2 in {"entero", "decimal"} and v2 == 1:
                return Quadruple("=", q.arg1, None, q.result, q.inferred_type)

        elif q.op == "y":
            if is_c1 and t1 == "booleano":
                return Quadruple("=", "falso" if not v1 else q.arg2, None, q.result, "booleano")
            if is_c2 and t2 == "booleano":
                return Quadruple("=", "falso" if not v2 else q.arg1, None, q.result, "booleano")

        elif q.op == "o":
            if is_c1 and t1 == "booleano":
                return Quadruple("=", "verdadero" if v1 else q.arg2, None, q.result, "booleano")
            if is_c2 and t2 == "booleano":
                return Quadruple("=", "verdadero" if v2 else q.arg1, None, q.result, "booleano")

        return None

    def _optimize_local_blocks(self, quads: List[Quadruple]) -> List[Quadruple]:
        blocks = self._split_basic_blocks(quads)
        new_quads: List[Quadruple] = []

        for block in blocks:
            known_values: Dict[str, str] = {}

            for q in block:
                op = q.op
                arg1 = q.arg1
                arg2 = q.arg2
                result = q.result

                if op not in {"LABEL", "GOTO", "LOAD_CSV", "ITER_INIT", "TRAIN_TREE", "HALT"}:
                    if isinstance(arg1, str) and arg1 in known_values:
                        arg1 = known_values[arg1]
                        self.stats.constants_propagated += 1
                    if op not in {"GET_COL"} and isinstance(arg2, str) and arg2 in known_values:
                        arg2 = known_values[arg2]
                        self.stats.constants_propagated += 1

                current = Quadruple(op, arg1, arg2, result, q.inferred_type)

                is_c1, v1, t1 = self._parse_constant(current.arg1)
                if current.op == "I2D" and is_c1 and t1 in {"entero", "decimal"}:
                    folded = self._format_constant(float(v1), "decimal")
                    current = Quadruple("=", folded, None, current.result, "decimal")
                    self.stats.constants_folded += 1
                elif current.op == "UMINUS" and is_c1 and t1 in {"entero", "decimal"}:
                    folded = self._format_constant(-v1, t1)
                    current = Quadruple("=", folded, None, current.result, t1)
                    self.stats.constants_folded += 1
                elif current.op == "UPLUS" and is_c1 and t1 in {"entero", "decimal"}:
                    folded = self._format_constant(+v1, t1)
                    current = Quadruple("=", folded, None, current.result, t1)
                    self.stats.constants_folded += 1
                elif current.op == "NOT" and is_c1 and t1 == "booleano":
                    folded = self._format_constant(not v1, "booleano")
                    current = Quadruple("=", folded, None, current.result, "booleano")
                    self.stats.constants_folded += 1

                is_c1, v1, t1 = self._parse_constant(current.arg1)
                is_c2, v2, t2 = self._parse_constant(current.arg2)
                if is_c1 and is_c2 and current.op in {"+", "-", "*", "/", "==", "!=", "<", ">", "<=", ">=", "y", "o"}:
                    evaluated = self._evaluate_binary_const(current.op, v1, t1, v2, t2, current.inferred_type)
                    if evaluated is not None:
                        val_str, res_type = evaluated
                        current = Quadruple("=", val_str, None, current.result, res_type)
                        self.stats.constants_folded += 1

                simplified = self._try_algebraic_simplification(current)
                if simplified is not None:
                    current = simplified
                    self.stats.algebraic_simplifications += 1

                if current.result and current.op not in {"LABEL", "GOTO", "IF_FALSE", "PRINT", "HALT"}:
                    dest = current.result
                    stale_keys = [k for k, v in known_values.items() if k == dest or v == dest]
                    for k in stale_keys:
                        del known_values[k]

                    if current.op == "=" and isinstance(current.arg1, str):
                        is_src_const, _, _ = self._parse_constant(current.arg1)
                        if is_src_const or self._is_temp(current.arg1):
                            known_values[dest] = current.arg1

                new_quads.append(current)

        return new_quads

    def _count_reads(self, quads: List[Quadruple]) -> Dict[str, int]:
        reads: Dict[str, int] = {}
        for q in quads:
            if q.op not in {"LABEL", "GOTO", "LOAD_CSV", "HALT"}:
                if isinstance(q.arg1, str):
                    reads[q.arg1] = reads.get(q.arg1, 0) + 1
            if q.op not in {
                "LABEL", "GOTO", "IF_FALSE", "LOAD_CSV", "ITER_INIT", "ITER_NEXT",
                "GET_COL", "TRAIN_TREE", "PRINT", "I2D", "UMINUS", "UPLUS", "NOT", "=", "HALT"
            }:
                if isinstance(q.arg2, str):
                    reads[q.arg2] = reads.get(q.arg2, 0) + 1
        return reads

    def _optimize_peephole(self, quads: List[Quadruple]) -> List[Quadruple]:
        reads = self._count_reads(quads)
        result: List[Quadruple] = []
        i = 0
        n = len(quads)

        while i < n:
            q = quads[i]

            if q.op == "=" and q.arg1 == q.result:
                self.stats.peephole_optimizations += 1
                i += 1
                continue

            if q.op == "IF_FALSE":
                is_c, val, t = self._parse_constant(q.arg1)
                if is_c and t == "booleano":
                    if val is True:
                        self.stats.peephole_optimizations += 1
                        i += 1
                        continue
                    else:
                        result.append(Quadruple("GOTO", None, None, q.result))
                        self.stats.peephole_optimizations += 1
                        i += 1
                        continue

            if q.op == "GOTO" and i + 1 < n and quads[i + 1].op == "LABEL" and q.result == quads[i + 1].result:
                self.stats.peephole_optimizations += 1
                i += 1
                continue

            if (
                i + 1 < n
                and self._is_temp(q.result)
                and reads.get(q.result, 0) == 1
                and quads[i + 1].op == "="
                and quads[i + 1].arg1 == q.result
            ):
                next_q = quads[i + 1]
                fused = Quadruple(q.op, q.arg1, q.arg2, next_q.result, next_q.inferred_type or q.inferred_type)
                result.append(fused)
                self.stats.peephole_optimizations += 1
                i += 2
                continue

            result.append(q)
            i += 1

        return result

    def _optimize_loops(self, quads: List[Quadruple]) -> List[Quadruple]:
        label_positions: Dict[str, int] = {
            q.result: idx for idx, q in enumerate(quads) if q.op == "LABEL" and isinstance(q.result, str)
        }

        loops: List[Tuple[int, int]] = []
        for idx, q in enumerate(quads):
            if q.op == "GOTO" and q.result in label_positions:
                start_idx = label_positions[q.result]
                if start_idx < idx:
                    loops.append((start_idx, idx))

        if not loops:
            return quads

        loops.sort(key=lambda r: (r[1] - r[0]))
        current = list(quads)

        for start_idx, end_idx in loops:
            if start_idx >= len(current) or end_idx >= len(current):
                continue
            if current[start_idx].op != "LABEL":
                continue

            modified_in_loop: Set[str] = set()
            for k in range(start_idx + 1, end_idx):
                inst = current[k]
                if inst.result and inst.op not in {"LABEL", "GOTO", "IF_FALSE", "PRINT", "HALT"}:
                    modified_in_loop.add(inst.result)

            invariants: List[Quadruple] = []
            remaining_body: List[Quadruple] = []

            for k in range(start_idx + 1, end_idx):
                inst = current[k]
                can_hoist = False
                if inst.op in PURE_OPS and inst.result and self._is_temp(inst.result):
                    arg1_ok = (inst.arg1 is None) or (inst.arg1 not in modified_in_loop)
                    arg2_ok = (inst.arg2 is None) or (inst.arg2 not in modified_in_loop)
                    prior_jumps = [
                        current[m] for m in range(start_idx + 1, k) if current[m].op in JUMP_OPS
                    ]
                    safe_exit_only = all(
                        j.op == "IF_FALSE" and isinstance(j.result, str) and "_end_" in j.result
                        for j in prior_jumps
                    )
                    if arg1_ok and arg2_ok and safe_exit_only:
                        can_hoist = True

                if can_hoist:
                    invariants.append(inst)
                    modified_in_loop.discard(inst.result)
                    self.stats.loop_invariants_moved += 1
                else:
                    remaining_body.append(inst)

            if invariants:
                current = (
                    current[:start_idx]
                    + invariants
                    + [current[start_idx]]
                    + remaining_body
                    + current[end_idx:]
                )
                break

        return current

    def _eliminate_dead_code(self, quads: List[Quadruple]) -> List[Quadruple]:
        reachable: List[Quadruple] = []
        unreachable = False
        for q in quads:
            if q.op in {"LABEL", "HALT"}:
                unreachable = False
                reachable.append(q)
            elif unreachable:
                self.stats.dead_code_eliminated += 1
            else:
                reachable.append(q)
                if q.op == "GOTO":
                    unreachable = True

        referenced_labels: Set[str] = {
            q.result for q in reachable if q.op in JUMP_OPS and isinstance(q.result, str)
        }
        after_labels: List[Quadruple] = []
        for q in reachable:
            if q.op == "LABEL" and q.result not in referenced_labels:
                self.stats.dead_code_eliminated += 1
                continue
            after_labels.append(q)

        reads = self._count_reads(after_labels)
        final_quads: List[Quadruple] = []
        for q in after_labels:
            if q.op in PURE_OPS and isinstance(q.result, str):
                if self._is_temp(q.result) and reads.get(q.result, 0) == 0:
                    self.stats.dead_code_eliminated += 1
                    continue
                if self._is_user_var(q.result) and (
                    q.result in self.unused_addresses or reads.get(q.result, 0) == 0
                ):
                    self.stats.dead_code_eliminated += 1
                    continue
            final_quads.append(q)

        return final_quads

    def optimize(self) -> List[Quadruple]:
        current = deepcopy(self.original_quadruples)
        self.stats = OptimizationStats(initial_quadruples=len(current))

        for p in range(1, self.max_passes + 1):
            before_tuples = [q.to_tuple() for q in current]

            current = self._optimize_local_blocks(current)
            current = self._optimize_peephole(current)
            current = self._optimize_loops(current)
            current = self._eliminate_dead_code(current)

            after_tuples = [q.to_tuple() for q in current]
            self.stats.passes_executed = p
            self.stats.pass_details.append(
                f"Pasada {p}: {len(before_tuples)} -> {len(after_tuples)} cuadruplas"
            )

            if before_tuples == after_tuples:
                break

        self.optimized_quadruples = current
        self.stats.final_quadruples = len(current)
        return self.optimized_quadruples

    def get_codegen_input_context(self) -> Dict[str, Any]:
        """
        Contrato de salida del Modulo 3 hacia el Generador de Codigo Final.
        """
        return {
            "quadruples": self.optimized_quadruples,
            "raw_tuples": [q.to_tuple() for q in self.optimized_quadruples],
            "stats": self.stats,
            "global_table": self.global_table,
            "reference_table": self.reference_table,
            "ast": self.ast
        }

    def pretty_format(self) -> str:
        lines = [
            f"{'#':<4} | {'Operador':<14} | {'Arg1':<24} | {'Arg2':<24} | {'Resultado':<24}",
            f"{'-'*4}-+-{'-'*14}-+-{'-'*24}-+-{'-'*24}-+-{'-'*24}"
        ]
        for idx, q in enumerate(self.optimized_quadruples):
            a1 = str(q.arg1) if q.arg1 is not None else "-"
            a2 = str(q.arg2) if q.arg2 is not None else "-"
            res = str(q.result) if q.result is not None else "-"
            lines.append(f"{idx:<4} | {q.op:<14} | {a1:<24} | {a2:<24} | {res:<24}")
        return "\n".join(lines)