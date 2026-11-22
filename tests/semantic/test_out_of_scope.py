"""
tests/semantic/test_out_of_scope.py
Pruebas de alcance léxico (scoping) y visibilidad de variables en StatQL.
Cubre:
- Variables declaradas en bloque 'sino' accedidas fuera del condicional
- Variables declaradas en bloque 'si' accedidas dentro de 'sino'
- Variables declaradas en bloque 'si' accedidas fuera del condicional
- Variable iteradora de 'para cada' accedida fuera del bucle
- Variables locales a un bucle 'para cada' o 'mientras' accedidas fuera de ellos
- Sombreamiento de variables (shadowing) y ámbitos hermanos aislados
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


class TestOutOfScope(unittest.TestCase):

    def setUp(self):
        self.analyzer = SemanticAnalyzer(base_dir=BASE_DIR)
        self.analyzer.register_mock_schema("dataset_scope.csv", {
            "id": "entero",
            "valor": "decimal"
        })

    def test_variable_in_sino_accessed_outside(self):
        code = """
        booleano bandera = falso
        si (bandera) {
            mostrar "rama entonces"
        } sino {
            entero secreta = 999
        }
        mostrar secreta
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("secreta", ctx.exception.raw_message)

    def test_variable_in_si_accessed_in_sino(self):
        code = """
        booleano cond = verdadero
        si (cond) {
            entero solo_en_then = 10
        } sino {
            mostrar solo_en_then
        }
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("solo_en_then", ctx.exception.raw_message)

    def test_variable_in_si_accessed_outside(self):
        code = """
        si (verdadero) {
            texto saludo = "hola"
        }
        mostrar saludo
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("saludo", ctx.exception.raw_message)

    def test_iterator_variable_out_of_scope_after_para_cada(self):
        code = """
        cargar "dataset_scope.csv" como tabla_datos
        para cada item en tabla_datos {
            mostrar item.id
        }
        // 'item' no debe existir fuera del bucle
        mostrar item
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("item", ctx.exception.raw_message)

    def test_local_var_in_para_cada_out_of_scope(self):
        code = """
        cargar "dataset_scope.csv" como tabla_datos
        para cada row en tabla_datos {
            entero temp = 50
        }
        temp = 10
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("temp", ctx.exception.raw_message)

    def test_local_var_in_mientras_out_of_scope(self):
        code = """
        entero c = 0
        mientras (c < 3) {
            entero acumulador = c * 2
            c = c + 1
        }
        mostrar acumulador
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        with self.assertRaises(SemanticError) as ctx:
            self.analyzer.analyze(ast)
        self.assertEqual(ctx.exception.code, SemanticErrorCode.ERR_UNDECLARED_VAR)
        self.assertIn("acumulador", ctx.exception.raw_message)

    def test_sibling_scopes_allow_same_identifier(self):
        # Es completamente válido declarar 'var_local' en 'si' y también en 'sino'
        code = """
        booleano test = verdadero
        si (test) {
            entero var_local = 1
            mostrar var_local
        } sino {
            texto var_local = "otra rama"
            mostrar var_local
        }
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        table = self.analyzer.analyze(ast)
        self.assertIsNotNone(table)
        # Pero no debe existir en la tabla global
        self.assertIsNone(table.lookup("var_local", current_scope_only=True))

    def test_variable_shadowing(self):
        # Una variable interna puede ocultar una externa con tipo distinto
        code = """
        entero x = 100
        si (verdadero) {
            texto x = "ahora soy texto en este ambito"
            mostrar x
        }
        mostrar x
        """
        ast = Parser(Lexer(code).tokenize()).parse()
        table = self.analyzer.analyze(ast)
        # La variable global sigue siendo entero
        self.assertEqual(table.lookup("x").type, "entero")


if __name__ == "__main__":
    unittest.main()
