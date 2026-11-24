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
from statql.notation_converter import NotationConverter


class TestIntermediateCode(unittest.TestCase):

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

    def _compile_to_ir(self, code: str):
        tokens = Lexer(code).tokenize()
        ast = Parser(tokens).parse()
        self.analyzer.analyze(ast)
        ir_ctx = self.analyzer.get_intermediate_code_context()
        generator = IntermediateCodeGenerator(ir_ctx)
        quads = generator.generate()
        return generator, quads

    def test_infix_to_postfix_and_prefix_conversions(self):
        expr_str = "(a + b) * c - d / 2"
        postfix = NotationConverter.infix_str_to_postfix(expr_str)
        prefix = NotationConverter.infix_str_to_prefix(expr_str)

        self.assertEqual(postfix, "a b + c * d 2 / -")
        self.assertEqual(prefix, "- * + a b c / d 2")

    def test_postfix_prefix_from_typed_ast_with_i2d(self):
        code = """
        entero a = 4
        decimal b = 2.5
        decimal res = a + b * 2
        """
        tokens = Lexer(code).tokenize()
        ast = Parser(tokens).parse()
        self.analyzer.analyze(ast)

        decl_res = ast.statements[2]
        postfix = NotationConverter.ast_to_postfix(decl_res.expr)
        prefix = NotationConverter.ast_to_prefix(decl_res.expr)

        self.assertEqual(postfix, "a I2D b 2 I2D * +")
        self.assertEqual(prefix, "+ I2D a * b I2D 2")

    def test_complex_expressions_and_i2d_quadruples(self):
        code = """
        entero x = 10
        decimal factor = 3.5
        decimal z = (x + 2) * factor - 1
        """
        _, quads = self._compile_to_ir(code)
        raw = [q.to_tuple() for q in quads]

        self.assertIn(("=", "10", None, "sym_global_x_0"), raw)
        self.assertIn(("=", "3.5", None, "sym_global_factor_1"), raw)
        self.assertIn(("+", "sym_global_x_0", "2", "t0"), raw)
        self.assertIn(("I2D", "t0", None, "t1"), raw)
        self.assertIn(("*", "t1", "sym_global_factor_1", "t2"), raw)
        self.assertIn(("I2D", "1", None, "t3"), raw)
        self.assertIn(("-", "t2", "t3", "t4"), raw)
        self.assertIn(("=", "t4", None, "sym_global_z_2"), raw)
        self.assertEqual(raw[-1], ("HALT", None, None, None))

    def test_conditional_si_sino_and_scoped_addresses(self):
        code = """
        entero x = 5
        si (x > 3 y verdadero) {
            entero x = 100
            mostrar x
        } sino {
            entero x = 200
            mostrar x
        }
        mostrar x
        """
        _, quads = self._compile_to_ir(code)
        ops = [q.op for q in quads]

        self.assertIn("IF_FALSE", ops)
        self.assertIn("GOTO", ops)
        self.assertEqual(ops.count("LABEL"), 2)

        print_quads = [q for q in quads if q.op == "PRINT"]
        self.assertEqual(len(print_quads), 3)
        self.assertNotEqual(print_quads[0].arg1, print_quads[2].arg1)
        self.assertNotEqual(print_quads[1].arg1, print_quads[2].arg1)
        self.assertEqual(print_quads[2].arg1, "sym_global_x_0")

    def test_while_loop_quadruples(self):
        code = """
        entero i = 0
        mientras (i < 5) {
            i = i + 1
        }
        """
        _, quads = self._compile_to_ir(code)
        raw = [q.to_tuple() for q in quads]
        ops = [q.op for q in quads]

        self.assertEqual(ops.count("LABEL"), 2)
        self.assertIn(("IF_FALSE", "t0", None, "L_while_end_1"), raw)
        self.assertIn(("GOTO", None, None, "L_while_start_0"), raw)

    def test_foreach_csv_and_ml_model_quadruples(self):
        code = """
        cargar "estudiantes.csv" como datos
        entero cont = 0
        para cada alumno en datos {
            si (alumno.promedio >= 8.0 y no (alumno.activo == falso)) {
                cont = cont + 1
            }
        }
        entrenar arbol con datos objetivo "aprobado" como modelo_final
        mostrar cont
        """
        generator, quads = self._compile_to_ir(code)
        raw = [q.to_tuple() for q in quads]
        ops = [q.op for q in quads]

        self.assertEqual(raw[0], ("LOAD_CSV", '"estudiantes.csv"', None, "ds_datos_0"))
        self.assertIn("ITER_INIT", ops)
        self.assertIn("ITER_NEXT", ops)
        self.assertIn("GET_COL", ops)
        self.assertIn("NOT", ops)
        self.assertIn(("TRAIN_TREE", "ds_datos_0", '"aprobado"', "model_modelo_final_3"), raw)

        opt_ctx = generator.get_optimizer_input_context()
        self.assertIn("quadruples", opt_ctx)
        self.assertIn("raw_tuples", opt_ctx)
        self.assertGreater(opt_ctx["temp_count"], 0)


if __name__ == "__main__":
    unittest.main()