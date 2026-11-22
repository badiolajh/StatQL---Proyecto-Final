# Compilador StatQL - Módulo 1: Análisis Semántico

StatQL es un lenguaje de dominio específico (DSL) diseñado para la manipulación y análisis estadístico de datos CSV y el entrenamiento de árboles de decisión en aprendizaje automático.

Este repositorio contiene la implementación completa y verificada del **Módulo 1 (Análisis Semántico y Base Léxica/Sintáctica)**, dejando interfaces desacopladas y contratos limpios para la conexión posterior de los **Integrantes 2 (Código Intermedio - Cuádruplas)** y **3 (Optimización)**.

---

## 1. Estructura del Repositorio

```text
statql/
├── __init__.py            # Exportaciones públicas del compilador
├── lexer.py               # Analizador léxico UTF-8 (soporte base para el parser)
├── parser.py              # Parser descendente recursivo EBNF (soporte base)
├── ast_nodes.py           # Nodos del Árbol de Expresiones y Sentencias con anotación de tipos
├── symbol_table.py        # Tabla de símbolos dinámica y tabla de referencias/direcciones simbólicas
├── semantic_stack.py      # Pila semántica explícita para validación de expresiones y control de ámbitos
├── semantic_analyzer.py   # Verificador de tipos, casting (I2D), validación de esquemas CSV y registro de errores
└── csv_loader.py          # Inspector de esquemas CSV (mapeo explícito de "verdadero"/"falso" a booleano)
tests/
└── semantic/
    ├── test_valid_reference.py       # Caso de referencia completo válido
    ├── test_undeclared_vars.py       # Variables y columnas no declaradas
    ├── test_incompatible_types.py    # Operaciones y asignaciones inválidas
    ├── test_out_of_scope.py          # Variables locales (sino) e iteradores fuera de alcance
    └── test_casting_rules.py         # Conversiones válidas e inválidas (entero -> decimal vs decimal -> entero)
docs/
└── 01_analisis_semantico.md          # Documentación formal lista para el reporte del equipo
```

---

## 2. Ejecución de la Suite de Pruebas

Para ejecutar la batería completa de pruebas unitarias automatizadas (43 tests verificando el 100% de los casos semánticos):

```bash
python -m unittest discover -s tests -v
```

---

## 3. Interfaces de Integración para el Equipo

### Para el Integrante 2 (Código Intermedio / Cuádruplas 3AC)
```python
from statql.lexer import Lexer
from statql.parser import Parser
from statql.semantic_analyzer import SemanticAnalyzer

# 1. Análisis léxico y sintáctico
ast = Parser(Lexer(codigo_fuente).tokenize()).parse()

# 2. Análisis semántico y tipado estático
analyzer = SemanticAnalyzer()
analyzer.analyze(ast)

# 3. Contexto desacoplado para generación de cuádruplas
ir_context = analyzer.get_intermediate_code_context()
ast_tipado = ir_context["ast"]                  # Expresiones con inferred_type garantizado
tabla_simbolos = ir_context["global_table"]     # Jerarquía completa de símbolos
memoria_simbolica = ir_context["reference_table"] # Direcciones simbólicas únicas asignadas
```

### Para el Integrante 3 (Optimizador de Código)
```python
opt_context = analyzer.get_optimization_context()
variables_muertas = opt_context["unused_symbols"]       # Candidatas a Dead Variable Elimination (DCE)
conteo_accesos = opt_context["symbol_usage_counts"]     # Frecuencias para asignación de registros
```

Para más detalles técnicos, consulte el reporte formal en `docs/01_analisis_semantico.md`.
