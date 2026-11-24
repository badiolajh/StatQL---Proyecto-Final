# Documentación Formal: Módulo 3 - Optimización de Código Intermedio (Cuádruplas 3AC)
**Lenguaje:** StatQL (Statistical Query Language DSL)  
**Proyecto:** Compilador de Dominio Específico para Análisis Estadístico y Árboles de Decisión  
**Módulo:** 3 — Optimización Multipasada de Cuádruplas 3AC  
**Fecha:** 2026-11-19  
**Estado:** Terminado y Validado (100% de Pruebas Unitarias Aprobadas)

---

## 1. Introducción y Objetivos del Módulo 3

El presente documento constituye el reporte técnico del **Módulo 3 (Optimizador de Código Intermedio)** para el compilador **StatQL**. Consume la secuencia de cuádruplas generada por el **Módulo 2 (`IntermediateCodeGenerator`)** y el contexto de símbolos no utilizados del **Módulo 1 (`SemanticAnalyzer`)**, optimizando el código intermedio sin alterar la semántica del programa.

### Técnicas Implementadas
1. **Optimización Local por Bloques Básicos**: Plegado de constantes (*Constant Folding*), propagación de constantes/copias y simplificación algebraica con reducción de fuerza (`x * 2` $\rightarrow$ `x + x`, `x + 0` $\rightarrow$ `x`, `x * 0` $\rightarrow$ `0`).
2. **Optimización de Mirilla (*Peephole*)**: Fusión de temporales de uso único directamente hacia la variable destino, eliminación de auto-asignaciones, saltos redundantes y resolución de ramas condicionales constantes (`IF_FALSE verdadero` / `IF_FALSE falso`).
3. **Optimización de Ciclos (*Loop-Invariant Code Motion - LICM*)**: Extracción de operaciones puras invariantes fuera de bucles `mientras` y `para cada`.
4. **Eliminación de Código Muerto (*Dead Code Elimination - DCE*)**: Limpieza de variables declaradas sin lectura (`unused_symbols`), temporales muertos, instrucciones inalcanzables tras `GOTO` y etiquetas huérfanas.
5. **Convergencia Multipasada**: Ejecución iterativa hasta alcanzar punto fijo.

---

## 2. Resultados Experimentales sobre `samples/`

| Archivo de Prueba | Cuádruplas Iniciales (M2) | Cuádruplas Optimizadas (M3) | Reducción | Pasadas |
| :--- | :---: | :---: | :---: | :---: |
| `ejemplo1_basico.statql` | 29 | 14 | **51.72%** | 4 |
| `ejemplo2_analisis_datos.statql` | 34 | 32 | **5.88%** | 2 |
| `ejemplo3_ml.statql` | 5 | 5 | **0.00%** | 1 |

---

## 3. Contrato de Integración para el Generador de Código Final

```python
from statql import (
    Lexer, Parser, SemanticAnalyzer,
    IntermediateCodeGenerator, QuadrupleOptimizer
)

ast = Parser(Lexer(codigo_fuente).tokenize()).parse()
analyzer = SemanticAnalyzer(base_dir="samples")
analyzer.analyze(ast)

ir_gen = IntermediateCodeGenerator(analyzer.get_intermediate_code_context())
ir_gen.generate()

optimizer = QuadrupleOptimizer(
    ir_gen.get_optimizer_input_context(),
    analyzer.get_optimization_context()
)
optimizer.optimize()

# Entrada lista para el Generador de Código Final (Python / pandas / scikit-learn)
codegen_ctx = optimizer.get_codegen_input_context()
quads_optimizadas = codegen_ctx["quadruples"]      # List[Quadruple]
tuplas_puras      = codegen_ctx["raw_tuples"]      # List[Tuple[str, Any, Any, Any]]
estadisticas      = codegen_ctx["stats"]           # OptimizationStats
tabla_simbolos    = codegen_ctx["global_table"]    # SymbolTable
memoria_simbolica = codegen_ctx["reference_table"] # ReferenceTable