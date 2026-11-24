"""
tests/semantic/test_undeclared_vars.py
Pruebas de detección de identificadores y columnas no declaradas en StatQL.
Cubre:
- Asignación a variables no declaradas
- Uso de variables no declaradas en expresiones
- Iteración sobre tablas no declaradas
- Entrenamiento de árboles sobre datasets inexistentes
- Acceso a columnas no existentes en el esquema CSV
- Columna objetivo inexistente en entrenamiento ML
- Acceso a propiedades en variables primitivas que no son tablas ni filas
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


class TestUndeclaredVariables(unittest.TestCase):

    def setUp(self):
        self.analyzer = SemanticAnalyzer(base_dir=BASE_DIR)
        self.analyzer.register_mock_schema("datos_muestra.csv", {
            "id": "entero",
            "edad": "entero",
            "salario": "decimal",
            "departamento": "texto"
        })

    def test_assignment_to_undeclared_variable(self):
        code = "x = 42\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("Variable no declarada 'x'", ctx.exception.raw_message)

    def test_expression_with_undeclared_variable(self):
        code = "entero a = 10\nentero b = a + variable_fantasma\n"
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("variable_fantasma", ctx.exception.raw_message)

    def test_para_cada_undeclared_dataset(self):
        code = """
        para cada fila en tabla_fantasma {
            mostrar "hola"
        }
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("tabla_fantasma", ctx.exception.raw_message)

    def test_entrenar_undeclared_dataset(self):
        code = """
        entrenar arbol con dataset_inexistente objetivo "edad" como modelo1
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("dataset_inexistente", ctx.exception.raw_message)

    def test_csv_column_not_found_in_row(self):
        code = """
        cargar "datos_muestra.csv" como empleados
        para cada emp en empleados {
            mostrar emp.columna_inventada
        }
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_CSV_COLUMN_NOT_FOUND)
        self.assertIn("columna_inventada", ctx.exception.raw_message)
        self.assertIn("Columnas disponibles", ctx.exception.raw_message)

    def test_entrenar_invalid_target_column(self):
        code = """
        cargar "datos_muestra.csv" como empleados
        entrenar arbol con empleados objetivo "objetivo_falso" como mod
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_CSV_COLUMN_NOT_FOUND)
        self.assertIn("objetivo_falso", ctx.exception.raw_message)

    def test_property_access_on_primitive_type(self):
        code = """
        entero numero = 100
        mostrar numero.longitud
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)
        self.assertIn("No se puede acceder a columnas o propiedades en un identificador de tipo 'entero'", ctx.exception.raw_message)

    def test_condition_with_undeclared_variable(self):
        code = """
        si (condicion_no_declarada) {
            mostrar 1
        }
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("condicion_no_declarada", ctx.exception.raw_message)


if __name__ == "__main__":
    unittest.main()
