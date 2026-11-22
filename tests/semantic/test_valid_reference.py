"""
tests/semantic/test_valid_reference.py
Prueba del caso de referencia completo y válido para StatQL.
Valida el flujo semántico integral:
- Carga de datasets CSV
- Declaración y asignación de todos los tipos primitivos
- Promociones válidas entero -> decimal (I2D)
- Expresiones aritméticas, relacionales y lógicas complejas
- Estructuras de control (si/sino, para cada, mientras)
- Acceso a columnas válidas de tablas y filas
- Entrenamiento de árboles de decisión ML
- Decoración completa del AST y generación de tablas de direcciones simbólicas
"""

import unittest
import os
import sys

# Asegurar importación del paquete raíz
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from statql.lexer import Lexer
from statql.parser import Parser
from statql.semantic_analyzer import SemanticAnalyzer
from statql.ast_nodes import I2DNode, DeclaracionNode, AsignacionNode, ProgramNode


class TestValidReference(unittest.TestCase):

    def setUp(self):
        self.analyzer = SemanticAnalyzer(base_dir=BASE_DIR)
        # Esquema simulado representativo de estudiantes
        self.analyzer.register_mock_schema("estudiantes.csv", {
            "id": "entero",
            "edad": "entero",
            "promedio": "decimal",
            "carrera": "texto",
            "activo": "booleano",
            "aprobado": "booleano"
        })

    def test_full_valid_program(self):
        code = """
        // 1. Carga de datos tabulares
        cargar "estudiantes.csv" como est

        // 2. Declaración de variables de todos los tipos primitivos
        entero total_alumnos = 0
        decimal umbral_aprobado = 7.0
        texto mensaje_proceso = "Iniciando analisis de rendimiento..."
        booleano hay_destacados = falso

        // 3. Promoción explícita I2D en declaración
        decimal ponderador = 10

        mostrar mensaje_proceso

        // 4. Bucle para cada e inspección de fila
        para cada alumno en est {
            si (alumno.promedio >= umbral_aprobado y alumno.activo) {
                total_alumnos = total_alumnos + 1
                hay_destacados = verdadero
            } sino {
                mostrar "Alumno no cumple criterio de aprobacion"
            }
        }

        // 5. Expresiones aritméticas mixtas con promoción I2D y asignación
        decimal indice_calidad = 0.0
        indice_calidad = total_alumnos * ponderador + 0.5

        // 6. Bucle mientras con condición booleana compuesta
        mientras (total_alumnos < 100 y hay_destacados) {
            total_alumnos = total_alumnos + 10
        }

        // 7. Entrenamiento de modelo de Machine Learning
        entrenar arbol con est objetivo "aprobado" como clasificador_estudiantes

        mostrar indice_calidad
        """

        tokens = Lexer(code).tokenize()
        ast = Parser(tokens).parse()
        self.assertIsInstance(ast, ProgramNode)

        # Ejecutar análisis semántico
        table = self.analyzer.analyze(ast)

        # 1. Verificar registro correcto de variables en la tabla global
        self.assertIsNotNone(table.lookup("est"))
        self.assertEqual(table.lookup("est").type, "tabla")

        self.assertIsNotNone(table.lookup("total_alumnos"))
        self.assertEqual(table.lookup("total_alumnos").type, "entero")

        self.assertIsNotNone(table.lookup("umbral_aprobado"))
        self.assertEqual(table.lookup("umbral_aprobado").type, "decimal")

        self.assertIsNotNone(table.lookup("mensaje_proceso"))
        self.assertEqual(table.lookup("mensaje_proceso").type, "texto")

        self.assertIsNotNone(table.lookup("hay_destacados"))
        self.assertEqual(table.lookup("hay_destacados").type, "booleano")

        self.assertIsNotNone(table.lookup("ponderador"))
        self.assertEqual(table.lookup("ponderador").type, "decimal")

        self.assertIsNotNone(table.lookup("indice_calidad"))
        self.assertEqual(table.lookup("indice_calidad").type, "decimal")

        self.assertIsNotNone(table.lookup("clasificador_estudiantes"))
        self.assertEqual(table.lookup("clasificador_estudiantes").type, "modelo")

        # 2. Verificar inserción de nodo I2D en la declaración 'decimal ponderador = 10'
        # Buscar la declaración de ponderador en los statements del AST
        decl_ponderador = None
        for stmt in ast.statements:
            if isinstance(stmt, DeclaracionNode) and stmt.name == "ponderador":
                decl_ponderador = stmt
                break
        self.assertIsNotNone(decl_ponderador)
        self.assertIsInstance(decl_ponderador.expr, I2DNode)
        self.assertEqual(decl_ponderador.expr.inferred_type, "decimal")

        # 3. Verificar metadatos del modelo entrenado
        modelo_sym = table.lookup("clasificador_estudiantes")
        self.assertEqual(modelo_sym.metadata.get("target_col"), "aprobado")
        self.assertEqual(modelo_sym.metadata.get("dataset"), "est")
        # Features deben ser todas las columnas excepto el target
        features = modelo_sym.metadata.get("features", [])
        self.assertNotIn("aprobado", features)
        self.assertIn("edad", features)
        self.assertIn("promedio", features)

        # 4. Verificar interfaces desacopladas para Integrantes 2 y 3
        ir_ctx = self.analyzer.get_intermediate_code_context()
        self.assertIn("ast", ir_ctx)
        self.assertIn("global_table", ir_ctx)
        self.assertIn("reference_table", ir_ctx)
        self.assertEqual(len(ir_ctx["errors"]), 0)

        opt_ctx = self.analyzer.get_optimization_context()
        self.assertIn("unused_symbols", opt_ctx)
        self.assertIn("symbol_usage_counts", opt_ctx)
        # La tabla de direcciones simbólicas debe tener direcciones generadas
        ref_table = self.analyzer.reference_table
        self.assertGreater(len(ref_table.addresses), 0)

    def test_csv_loader_boolean_mapping_and_real_dataset(self):
        # Valida la inspección real de CSV con mapeo de 'verdadero'/'falso' a 'booleano'
        csv_path = os.path.join(BASE_DIR, "samples", "estudiantes.csv").replace("\\", "/")
        if os.path.exists(csv_path):
            code = f'cargar "{csv_path}" como dataset_real\n'
            ast = Parser(Lexer(code).tokenize()).parse()
            table = self.analyzer.analyze(ast)
            sym = table.lookup("dataset_real")
            self.assertIsNotNone(sym)
            schema = sym.metadata.get("columns", {})
            self.assertEqual(schema.get("nombre"), "texto")
            self.assertEqual(schema.get("edad"), "entero")
            self.assertEqual(schema.get("promedio"), "decimal")
            self.assertEqual(schema.get("horas_estudio"), "entero")
            # Mapeo explícito de 'verdadero' / 'falso' a 'booleano'
            self.assertEqual(schema.get("aprobado"), "booleano")



if __name__ == "__main__":
    unittest.main()
