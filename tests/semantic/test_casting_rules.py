"""
tests/semantic/test_casting_rules.py
Pruebas exhaustivas de las reglas de casting y coerción en StatQL.
Verifica:
- Promociones válidas entero -> decimal (I2D) en declaraciones
- Promociones válidas entero -> decimal (I2D) en asignaciones
- Promociones automáticas en expresiones aritméticas binarias mixtas
- Promociones automáticas en comparaciones relacionales mixtas
- Demociones inválidas decimal -> entero (prohibidas) en declaraciones y asignaciones
- Conversiones inválidas cruzadas (texto -> número, booleano -> número)
- Verificación estructural de los nodos I2D en el AST resultante
"""

import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from statql.lexer import Lexer
from statql.parser import Parser
from statql.semantic_analyzer import SemanticAnalyzer, SemanticError, SemanticErrorCode
from statql.ast_nodes import I2DNode, DeclaracionNode, AsignacionNode, BinaryOpNode


class TestCastingRules(unittest.TestCase):

    def setUp(self):
        self.analyzer = SemanticAnalyzer(base_dir=BASE_DIR)

    # --- Casos Válidos: Promoción I2D (entero -> decimal) ---

    def test_valid_i2d_in_declaration(self):
        code = "decimal d = 42\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        self.analyzer.analyze(ast)

        decl = ast.statements[0]
        self.assertIsInstance(decl, DeclaracionNode)
        self.assertIsInstance(decl.expr, I2DNode)
        self.assertEqual(decl.expr.inferred_type, "decimal")
        self.assertEqual(decl.expr.expr.value, 42)

    def test_valid_i2d_in_assignment(self):
        code = """
        decimal d = 3.14
        d = 100
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        self.analyzer.analyze(ast)

        asig = ast.statements[1]
        self.assertIsInstance(asig, AsignacionNode)
        self.assertIsInstance(asig.expr, I2DNode)
        self.assertEqual(asig.expr.inferred_type, "decimal")

    def test_valid_i2d_in_addition_int_plus_decimal(self):
        # entero + decimal -> I2D en el lado izquierdo
        code = """
        entero a = 5
        decimal b = 2.5
        decimal resultado = a + b
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        self.analyzer.analyze(ast)

        decl_res = ast.statements[2]
        self.assertIsInstance(decl_res.expr, BinaryOpNode)
        self.assertEqual(decl_res.expr.inferred_type, "decimal")
        # El hijo izquierdo debe haber sido envuelto en un I2DNode
        self.assertIsInstance(decl_res.expr.left, I2DNode)
        self.assertEqual(decl_res.expr.left.inferred_type, "decimal")

    def test_valid_i2d_in_multiplication_decimal_times_int(self):
        # decimal * entero -> I2D en el lado derecho
        code = """
        decimal d = 1.5
        entero n = 4
        decimal total = d * n
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        self.analyzer.analyze(ast)

        decl_tot = ast.statements[2]
        self.assertIsInstance(decl_tot.expr, BinaryOpNode)
        self.assertEqual(decl_tot.expr.inferred_type, "decimal")
        self.assertIsInstance(decl_tot.expr.right, I2DNode)
        self.assertEqual(decl_tot.expr.right.inferred_type, "decimal")

    def test_valid_i2d_in_relational_comparison(self):
        # entero < decimal -> promoción para comparar homogéneamente
        code = """
        entero edad = 18
        booleano es_mayor = edad >= 18.0
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        self.analyzer.analyze(ast)

        decl_cmp = ast.statements[1]
        self.assertIsInstance(decl_cmp.expr, BinaryOpNode)
        self.assertEqual(decl_cmp.expr.inferred_type, "booleano")
        self.assertIsInstance(decl_cmp.expr.left, I2DNode)

    # --- Casos Inválidos: Democión Prohibida (decimal -> entero) ---

    def test_invalid_demotion_in_declaration(self):
        code = "entero e = 3.14159\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INVALID_CAST)
        self.assertIn("No se permite la democión implícita de decimal a entero", ctx.exception.raw_message)

    def test_invalid_demotion_in_assignment(self):
        code = """
        entero contador = 10
        contador = 9.99
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INVALID_CAST)
        self.assertIn("la variable destino es de tipo 'entero', pero la expresión evaluada es 'decimal'", ctx.exception.raw_message)

    # --- Conversiones Inválidas Cruzadas ---

    def test_invalid_text_to_integer(self):
        code = 'entero x = "42"\n'
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_invalid_text_to_decimal(self):
        code = 'decimal d = "3.14"\n'
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_invalid_boolean_to_integer(self):
        code = "entero e = verdadero\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_invalid_integer_to_boolean(self):
        code = "booleano b = 1\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)


if __name__ == "__main__":
    unittest.main()
