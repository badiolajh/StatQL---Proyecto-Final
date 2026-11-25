# Compilador StatQL — Proyecto Integrador (Lenguajes y Autómatas II)

**StatQL** es un lenguaje de dominio específico (DSL) diseñado para la manipulación y análisis estadístico de datos tabulares (CSV) y el entrenamiento de modelos de aprendizaje automático (árboles de decisión), compilado de principio a fin hacia **Ensamblador x86 de 32 bits (IA-32, sintaxis NASM para Linux ELF)**.

Desarrollado como Proyecto Integrador para la asignatura de **Lenguajes y Autómatas II** (Ingeniería en Sistemas Computacionales, Instituto Tecnológico de Oaxaca), este repositorio integra las **4 etapas completas del proceso de compilación** junto con una suite de **60 pruebas automatizadas** (unitarias, de optimización y de ejecución nativa en binario):

1. **Tema 1 — Análisis Léxico, Sintáctico y Semántico:** Tokenización UTF-8, análisis sintáctico descendente recursivo (EBNF $\rightarrow$ AST), tabla de símbolos jerárquica con alcance léxico (`SymbolTable`), tabla de direcciones simbólicas (`ReferenceTable`), pila semántica (`SemanticStack`), verificación estática de tipos con conversión implícita (`I2D`), validación de esquemas CSV y registro estandarizado de errores (`SEM_001` a `SEM_008`).
2. **Tema 2 — Generación de Código Intermedio:** Conversión de expresiones entre notaciones infija, prefija y postfija (`NotationConverter`) y generación de **Cuádruplos de Tres Direcciones (`Quadruple`)** para declaraciones, expresiones, estructuras de control (`si`/`sino`, `mientras`, `para cada`) y operaciones estadísticas/ML.
3. **Tema 3 — Módulo de Optimización:** Motor multipasada (`QuadrupleOptimizer`) con propagación y plegado de constantes, simplificación algebraica, optimización de mirilla (*peephole*), movimiento de código invariante en ciclos (*LICM*) y eliminación de código muerto (*DCE*), incluyendo métricas de reducción.
4. **Tema 4 — Generación de Código Objeto:** Asignador dinámico de registros físicos (`RegisterAllocator` sobre `EBX`, `ECX`, `ESI`, `EDI` con política de reemplazo LRU y desbordamiento *spilling* a memoria), administración de segmentos en tiempo de ejecución (`.data`, `.bss`, `.text` y *stack frame* `EBP`/`ESP`) y traducción a código ensamblador ejecutable `.asm` (`ObjectCodeGenerator`).

---

## 1. Arquitectura y Estructura del Proyecto

```text
StatQL---Proyecto-Final/
├── statql/
│   ├── __init__.py               # Exportaciones públicas de los 4 módulos del compilador
│   ├── lexer.py                  # Analizador léxico UTF-8 y reconocimiento de tokens
│   ├── parser.py                 # Parser descendente recursivo EBNF -> AST
│   ├── ast_nodes.py              # Nodos del Árbol Sintáctico Abstracto con inferencia de tipos
│   ├── symbol_table.py           # Tabla de símbolos dinámica (SymbolTable) y direcciones (ReferenceTable)
│   ├── semantic_stack.py         # Pila semántica explícita para validación de expresiones y ámbitos
│   ├── semantic_analyzer.py      # Verificador de tipos, casting (I2D) y catálogo SEM_001..SEM_008
│   ├── csv_loader.py             # Inspector de esquemas CSV (mapeo "verdadero"/"falso" -> booleano)
│   ├── notation_converter.py     # Convertidor de expresiones (infija, prefija, postfija)
│   ├── ir_generator.py           # Generador de código intermedio en Cuádruplos 3AC
│   ├── optimizer.py              # Optimizador multipasada de cuádruplos y reporte de métricas
│   └── codegen.py                # Asignador de registros LRU y traductor a ensamblador x86 NASM
├── samples/
│   ├── ejemplo1_basico.statql
│   ├── ejemplo2_analisis_datos.statql
│   ├── ejemplo3_ml.statql
│   └── estudiantes.csv
├── tests/
│   ├── semantic/                 # 38 tests: tipos, ámbitos, casting I2D y errores SEM_001..008
│   ├── intermediate/             # 6 tests: notaciones y generación de cuádruplos
│   ├── optimization/             # 7 tests: plegado, mirilla, LICM, código muerto y contratos
│   └── execution/                # 4 tests: código objeto .asm, spills, Factorial y Fibonacci nativos
├── docs/
│   ├── 01_analisis_semantico.md
│   ├── 02_codigo_intermedio.md
│   └── 03_optimizacion.md
├── demo_optimizacion.py          # Demostración comparativa: Cuádruplas Originales vs. Optimizadas
└── demo_compilador_completo.py   # Pipeline completo: Fuente (.statql) -> Ensamblador (.asm)

2. Requisitos del Sistema e Instalación
Requisitos

    Sistema Operativo: Linux x86_64 (probado en Manjaro / Arch Linux y compatible con Ubuntu / Debian).

    Intérprete: Python 3.12+ (sin dependencias externas para el núcleo del compilador).

    Herramientas de Ensamblado y Enlazado: nasm (Netwide Assembler, formato elf32) y GNU ld (emulación elf_i386).

    Pruebas: pytest (opcional, también compatible con unittest estándar de Python).

Instalación en Arch Linux / Manjaro
Bash

sudo pacman -S python nasm binutils python-pytest
git clone [https://github.com/badiolajh/StatQL---Proyecto-Final.git](https://github.com/badiolajh/StatQL---Proyecto-Final.git)
cd StatQL---Proyecto-Final

Instalación en Ubuntu / Debian
Bash

sudo apt update && sudo apt install -y python3 nasm binutils python3-pytest
git clone [https://github.com/badiolajh/StatQL---Proyecto-Final.git](https://github.com/badiolajh/StatQL---Proyecto-Final.git)
cd StatQL---Proyecto-Final

3. Guía de Uso y Compilación Nativa
A. Compilar programas de ejemplo a Ensamblador (.asm)

Ejecuta el pipeline completo (Fases 1 a 4) sobre los programas en samples/, generando los archivos .asm dentro de build_asm/ e imprimiendo en consola la tabla de asignación de registros físicos:
Bash

python demo_compilador_completo.py

B. Ensamblar, Enlazar y Ejecutar Binarios x86 en Linux

Para transformar cualquier archivo .asm generado en un ejecutable nativo ELF de 32 bits y correrlo:
Bash

nasm -f elf32 build_asm/ejemplo1_basico.asm -o build_asm/ejemplo1_basico.o
ld -m elf_i386 build_asm/ejemplo1_basico.o -o build_asm/ejemplo1_basico
./build_asm/ejemplo1_basico

C. Analizar la Optimización de Código Intermedio (Tema 2 vs. Tema 3)
Bash

python demo_optimizacion.py

4. Ejecución de la Suite de Pruebas (60 Tests)

La suite valida todas las fases del compilador, incluyendo la compilación y ejecución real en binario x86 de algoritmos clásicos (Factorial 5! = 120 y Fibonacci F(7) = 13) y pruebas de desbordamiento de registros (register spilling):
Bash

pytest -v

(Alternativa sin pytest):
Bash

python -m unittest discover -s tests -v

5. Uso Programático (API Interna del Compilador)
Python

from statql import (
    Lexer,
    Parser,
    SemanticAnalyzer,
    IntermediateCodeGenerator,
    QuadrupleOptimizer,
    ObjectCodeGenerator,
)

codigo_fuente = """
entero n = 5;
entero fact = 1;
entero i = 1;
mientras (i <= n) {
    fact = fact * i;
    i = i + 1;
}
mostrar fact;
"""

# 1. Análisis Léxico, Sintáctico y Semántico
tokens = Lexer(codigo_fuente).tokenize()
ast = Parser(tokens).parse()
analyzer = SemanticAnalyzer(base_dir="samples")
analyzer.analyze(ast)

# 2. Generación de Código Intermedio (Cuádruplos 3AC)
ir_gen = IntermediateCodeGenerator(analyzer.get_intermediate_code_context())
ir_gen.generate()

# 3. Optimización Multipasada
optimizer = QuadrupleOptimizer(
    ir_gen.get_optimizer_input_context(),
    analyzer.get_optimization_context()
)
optimizer.optimize()

# 4. Generación de Código Objeto x86 NASM (.asm)
codegen = ObjectCodeGenerator(optimizer.get_codegen_input_context())
asm_code = codegen.generate()
codegen.save_asm("build_asm/factorial.asm")
print(codegen.format_register_report())

6. Convenciones de Arquitectura del Código Objeto (Tema 4)

    Asignación de Registros (RegisterAllocator): Utiliza EBX, ECX, ESI y EDI como registros de propósito general con reemplazo LRU (Least Recently Used) y bandera de modificación (dirty flag), reservando EAX y EDX como registros auxiliares para operaciones aritméticas (imul, cdq, idiv), comparaciones y llamadas al sistema (int 0x80).

    Segmentos de Memoria:

        .data: Almacena literales de texto dinámicos (str_lit_0, str_lit_1, ...), cadenas booleanas (verdadero/falso) y descriptores en tiempo de ejecución.

        .bss: Reserva espacio estático (resd 1) para variables globales de usuario (mem_sym_*) y el buffer de conversión ASCII (num_buffer).

        .text y Stack Frame: Construye un marco de pila estándar (push ebp / mov ebp, esp / sub esp, N alineado a 16 bytes) para variables temporales locales ([ebp - 4], [ebp - 8], ...) y subrutinas de salida estándar (_statql_print_int, _statql_print_str, _statql_print_bool) con paso de parámetros por pila ([ebp + 8]).


### Cómo actualizarlo en tu repositorio
1. Sustituye el contenido de `README.md` por este texto.
2. Guarda y súbelo a GitHub:
   ```bash
   git add README.md
   git commit -m "docs: actualizar README con arquitectura completa de las 4 etapas y guia NASM"
   git push origin main
