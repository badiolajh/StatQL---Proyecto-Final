import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from statql.lexer import Lexer
from statql.parser import Parser
from statql.semantic_analyzer import SemanticAnalyzer
from statql.ir_generator import IntermediateCodeGenerator
from statql.optimizer import QuadrupleOptimizer


class TestQuadrupleOptimizer(unittest.TestCase):

    def setUp(self):
        self.analyzer = SemanticAnalyzer(base_dir=BASE_DIR)
        self.analyzer.register_mock_schema("estudiantes.csv", {
            "id": "entero",
            "edad": "entero",
            "promedio": "decimal",
            "carrera": "texto",
            "activo": "booleano",
            "aprobado": "booleano"
        })

    def _optimize_code(self, code: str):
        tokens = Lexer(code).tokenize()
        ast = Parser(tokens).parse()
        self.analyzer.analyze(ast)
        self.assertEqual(self.analyzer.errors, [])

        ir_gen = IntermediateCodeGenerator(self.analyzer.get_intermediate_code_context())
        raw_quads = ir_gen.generate()

        optimizer = QuadrupleOptimizer(
            ir_gen.get_optimizer_input_context(),
            self.analyzer.get_optimization_context()
        )
        opt_quads = optimizer.optimize()
        return raw_quads, opt_quads, optimizer

    def test_constant_folding_and_propagation(self):
        code = """
        entero a = 10
        entero b = 20
        decimal factor = 2.5
        decimal resultado = (a + b) * factor
        mostrar resultado
        """
        raw_quads, opt_quads, opt = self._optimize_code(code)
        raw_tuples = [q.to_tuple() for q in opt_quads]

        self.assertIn(("PRINT", "75.0", None, None), raw_tuples)
        self.assertLess(len(opt_quads), len(raw_quads))
        self.assertGreater(opt.stats.constants_folded, 0)
        self.assertGreater(opt.stats.constants_propagated, 0)

    def test_algebraic_simplification_and_strength_reduction(self):
        code = """
        cargar "estudiantes.csv" como datos
        para cada fila en datos {
            entero x = fila.edad + 0
            entero val_y = x * 1
            entero doble = val_y * 2
            entero cero = doble - doble
            mostrar cero
        }
        """
        _, opt_quads, opt = self._optimize_code(code)
        ops = [q.op for q in opt_quads]
        raw_tuples = [q.to_tuple() for q in opt_quads]

        self.assertNotIn("*", ops)
        self.assertNotIn("-", ops)
        self.assertIn(("PRINT", "0", None, None), raw_tuples)
        self.assertGreater(opt.stats.algebraic_simplifications, 0)

    def test_peephole_temp_fusion_and_constant_branch(self):
        code = """
        cargar "estudiantes.csv" como datos
        entero cont = 0
        para cada fila en datos {
            si (10 > 2 y verdadero) {
                cont = cont + 1
            } sino {
                mostrar 999
            }
        }
        mostrar cont
        """
        _, opt_quads, opt = self._optimize_code(code)
        raw_tuples = [q.to_tuple() for q in opt_quads]

        self.assertNotIn(("PRINT", "999", None, None), raw_tuples)
        self.assertIn(("+", "sym_global_cont_1", "1", "sym_global_cont_1"), raw_tuples)
        self.assertGreater(opt.stats.peephole_optimizations, 0)

    def test_loop_invariant_code_motion(self):
        code = """
        entero base = 4
        entero multiplicador = 3
        entero i = 0
        entero acum = 0
        mientras (i < 5) {
            entero constante_ciclo = base * multiplicador + 2
            acum = acum + constante_ciclo
            i = i + 1
        }
        mostrar acum
        """
        _, opt_quads, opt = self._optimize_code(code)
        raw_tuples = [q.to_tuple() for q in opt_quads]

        ops = [q.op for q in opt_quads]
        self.assertNotIn("*", ops)
        idx_inv = raw_tuples.index(("=", "14", None, "t2"))
        idx_label = raw_tuples.index(("LABEL", None, None, "L_while_start_0"))
        self.assertLess(idx_inv, idx_label)
        self.assertGreater(opt.stats.loop_invariants_moved, 0)

    def test_loop_invariant_hoisting_with_runtime_column(self):
        code = """
        cargar "estudiantes.csv" como datos
        entero ajuste = 10
        entero total = 0
        para cada alumno en datos {
            total = total + (alumno.edad + (ajuste * 2))
        }
        mostrar total
        """
        _, opt_quads, opt = self._optimize_code(code)
        raw_tuples = [q.to_tuple() for q in opt_quads]

        idx_inv = raw_tuples.index(("=", "20", None, "t2"))
        idx_label = raw_tuples.index(("LABEL", None, None, "L_foreach_start_0"))
        self.assertLess(idx_inv, idx_label)
        self.assertGreater(opt.stats.loop_invariants_moved, 0)

    def test_dead_code_elimination_unused_variables(self):
        code = """
        entero usada = 10
        entero muerta_1 = 500
        decimal muerta_2 = 99.9
        texto muerta_3 = "nunca se lee"
        mostrar usada
        """
        raw_quads, opt_quads, opt = self._optimize_code(code)
        all_targets = [q.result for q in opt_quads if q.result]

        self.assertNotIn("sym_global_muerta_1_1", all_targets)
        self.assertNotIn("sym_global_muerta_2_2", all_targets)
        self.assertNotIn("sym_global_muerta_3_3", all_targets)
        self.assertGreaterEqual(opt.stats.dead_code_eliminated, 3)
        self.assertLess(len(opt_quads), len(raw_quads))

    def test_codegen_input_context_contract(self):
        code = """
        cargar "estudiantes.csv" como datos
        entrenar arbol con datos objetivo "aprobado" como modelo
        """
        _, _, opt = self._optimize_code(code)
        ctx = opt.get_codegen_input_context()

        self.assertIn("quadruples", ctx)
        self.assertIn("raw_tuples", ctx)
        self.assertIn("stats", ctx)
        self.assertIn("global_table", ctx)
        self.assertIn("reference_table", ctx)
        self.assertEqual(ctx["raw_tuples"][-1], ("HALT", None, None, None))


if __name__ == "__main__":
    unittest.main()