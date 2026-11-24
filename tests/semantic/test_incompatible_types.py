"""
tests/semantic/test_incompatible_types.py
Pruebas exhaustivas de operaciones, asignaciones y condiciones incompatibles en StatQL.
Cubre:
- Asignación y declaración con tipos no coincidentes
- Operaciones aritméticas inválidas (texto - entero, booleano + decimal, etc.)
- Operaciones lógicas inválidas (enteros en 'y'/'o', 'no' con texto)
- Comparaciones relacionales no soportadas (texto con números, ordenamiento en booleanos)
- Condiciones no booleanas en 'si' y 'mientras'
- Reasignación ilegal de objetos protegidos (tabla, modelo)
- Entrenamiento ML con variable que no es de tipo tabla
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


class TestIncompatibleTypes(unittest.TestCase):

    def setUp(self):
        self.analyzer = SemanticAnalyzer(base_dir=BASE_DIR)
        self.analyzer.register_mock_schema("test_schema.csv", {
            "id": "entero",
            "etiqueta": "texto",
            "valor": "decimal"
        })

    def test_decl_text_to_integer(self):
        code = 'entero x = "cadena no valida"\n'
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_decl_boolean_to_decimal(self):
        code = "decimal d = verdadero\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_assignment_type_mismatch(self):
        code = """
        entero contador = 0
        contador = "ahora soy texto"
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_arithmetic_subtraction_text_integer(self):
        code = 'texto t = "hola" - 5\n'
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_arithmetic_addition_boolean_decimal(self):
        code = "decimal res = verdadero + 3.14\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_logical_and_with_integer(self):
        code = "booleano b = 10 y verdadero\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_logical_or_with_text(self):
        code = 'booleano b = falso o "verdadero"\n'
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_unary_not_with_number(self):
        code = "booleano b = no 100\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_relational_text_and_decimal(self):
        code = 'booleano cmp = "cadena" < 10.5\n'
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_relational_ordering_on_booleans(self):
        code = "booleano cmp = verdadero < falso\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)

    def test_non_boolean_condition_in_si(self):
        code = """
        entero puntuacion = 10
        si (puntuacion) {
            mostrar "positivo"
        }
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_NON_BOOLEAN_CONDITION)
        self.assertIn("debe ser de tipo 'booleano'", ctx.exception.raw_message)

    def test_non_boolean_condition_in_mientras(self):
        code = """
        mientras ("bucle infinito") {
            mostrar 1
        }
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_NON_BOOLEAN_CONDITION)

    def test_reassignment_of_table_object(self):
        code = """
        cargar "test_schema.csv" como mi_tabla
        mi_tabla = 99
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_IMMUTABLE_OBJECT)
        self.assertIn("No se permite reasignar directamente el identificador protegido 'mi_tabla'", ctx.exception.raw_message)

    def test_train_on_non_table_symbol(self):
        code = """
        entero numero = 500
        entrenar arbol con numero objetivo "col" como modelo_erroneo
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)
        self.assertIn("debe ser de tipo 'tabla'", ctx.exception.raw_message)


if __name__ == "__main__":
    unittest.main()
