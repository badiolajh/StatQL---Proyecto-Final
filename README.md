# StatQL — Compilador para un lenguaje de análisis de datos

Proyecto integrador de Lenguajes y Autómatas II  
Ingeniería en Sistemas Computacionales · Instituto Tecnológico de Oaxaca · Tecnológico Nacional de México

---

## Presentación

StatQL es un lenguaje de dominio específico (DSL) orientado a la manipulación y el análisis de datos tabulares en formato CSV, con construcciones para expresar operaciones de aprendizaje automático mediante árboles de decisión.

El proyecto integra un pipeline de compilación que parte del código fuente `.statql`, construye un árbol de sintaxis abstracta, realiza verificaciones semánticas, genera y optimiza código intermedio y emite ensamblador x86 de 32 bits con sintaxis NASM para Linux.

| Característica | Descripción |
| :--- | :--- |
| Lenguaje de implementación | Python 3.12 o posterior |
| Entorno de desarrollo reportado | Manjaro Linux x86_64 con Python 3.14 |
| Arquitectura destino | IA-32 · x86 de 32 bits |
| Ensamblador | NASM |
| Formato de objeto | ELF32 |
| Enlazador | GNU `ld`, emulación `elf_i386` |
| Interfaz con Linux | Llamadas al sistema mediante `int 0x80` |
| Representación intermedia | Código de tres direcciones representado en cuádruplos |
| Pruebas automatizadas | 60 pruebas reportadas por el proyecto |

> El alcance del lenguaje y el del backend nativo no deben confundirse: la existencia de una operación en el análisis semántico o en los cuádruplos no demuestra por sí sola su ejecución funcional completa en el ensamblador generado. Consulta las limitaciones al final de este documento.

## Contenido

- [Inicio rápido](#inicio-rápido)
- [Arquitectura del compilador](#arquitectura-del-compilador)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación](#instalación)
- [Guía de uso](#guía-de-uso)
- [Uso programático](#uso-programático)
- [Pruebas automatizadas](#pruebas-automatizadas)
- [Arquitectura del código generado](#arquitectura-del-código-generado)
- [Diagnósticos semánticos](#diagnósticos-semánticos)
- [Documentación](#documentación)
- [Alcance y limitaciones](#alcance-y-limitaciones)

## Inicio rápido

Con Python, NASM y GNU Binutils instalados:

```bash
git clone [https://github.com/badiolajh/StatQL---Proyecto-Final.git](https://github.com/badiolajh/StatQL---Proyecto-Final.git)
cd StatQL---Proyecto-Final

# Generar ensamblador para los programas de ejemplo.
python3 demo_compilador_completo.py

# Examinar las optimizaciones del código intermedio.
python3 demo_optimizacion.py

# Ejecutar las pruebas.
python3 -m pytest -v
```

Los archivos ensambladores se generan en `build_asm/`. Para convertirlos en ejecutables, sigue las instrucciones de [ensamblado y enlazado](#ensamblado-enlazado-y-ejecución).

## Arquitectura del compilador

```text
Código fuente (.statql)
          │
          ▼
 Análisis léxico y sintáctico
          │
          ▼
 Árbol de sintaxis abstracta (AST)
          │
          ▼
 1. Análisis semántico
          │
          ▼
 2. Generación de cuádruplos
          │
          ▼
 3. Optimización multipasada
          │
          ▼
 4. Generación de ensamblador NASM (.asm)
          │
          ▼
 NASM: objeto ELF32 (.o)
          │
          ▼
 GNU ld: ejecutable Linux IA-32
```

### Tema 1 · Análisis semántico

La entrada del compilador utiliza tokenización UTF-8 y un parser descendente recursivo que construye el AST.

Sobre esa representación se realiza:

- Administración de ámbitos mediante `SymbolTable`.
- Asociación de símbolos y direcciones mediante `ReferenceTable`.
- Manejo de una pila semántica con `SemanticStack`.
- Verificación estática de tipos.
- Conversión implícita representada mediante `I2D`.
- Validación de esquemas CSV.
- Emisión de diagnósticos `SEM_001` a `SEM_008`.

### Tema 2 · Código intermedio

El módulo genera código de tres direcciones representado mediante cuádruplos:

```text
(operador, argumento_1, argumento_2, resultado)
```

Incluye la representación de declaraciones, expresiones, estructuras de control y operaciones del DSL.

`NotationConverter` permite trabajar con expresiones en notación infija, prefija y postfija.

### Tema 3 · Optimización

`QuadrupleOptimizer` aplica optimizaciones mediante un motor multipasada:

- Propagación de constantes.
- Plegado de constantes.
- Simplificación algebraica.
- Optimización de mirilla (*peephole*).
- Movimiento de código invariante en ciclos (*LICM*).
- Eliminación de código muerto (*DCE*).

El script de demostración permite comparar los cuádruplos originales y optimizados y consultar métricas de reducción y pasadas.

### Tema 4 · Código objeto

`ObjectCodeGenerator` traduce el código intermedio a ensamblador NASM para IA-32.

El backend incorpora:

- Asignación de registros mediante `RegisterAllocator`.
- Reemplazo LRU y desbordamiento a memoria (*spilling*).
- Sincronización del estado de registros en fronteras de control.
- Secciones `.data`, `.bss` y `.text`.
- Temporales respaldados en el marco de pila.
- Subrutinas de impresión para enteros, texto y booleanos.

El archivo `.asm` generado se convierte en un objeto binario mediante NASM y, posteriormente, en un ejecutable mediante GNU `ld`.

## Estructura del repositorio

```text
StatQL---Proyecto-Final/
├── statql/
│   ├── __init__.py               # Exportaciones públicas
│   ├── lexer.py                  # Tokenización UTF-8
│   ├── parser.py                 # Parser descendente recursivo
│   ├── ast_nodes.py              # Nodos del AST
│   ├── symbol_table.py           # Símbolos y direcciones simbólicas
│   ├── semantic_stack.py         # Pila semántica
│   ├── semantic_analyzer.py      # Tipos, ámbitos y diagnósticos
│   ├── csv_loader.py             # Lectura y validación de esquemas CSV
│   ├── notation_converter.py     # Infija, prefija y postfija
│   ├── ir_generator.py           # Generación de cuádruplos
│   ├── optimizer.py              # Optimización multipasada
│   └── codegen.py                # Registros y emisión NASM
├── samples/
│   ├── ejemplo1_basico.statql
│   ├── ejemplo2_analisis_datos.statql
│   ├── ejemplo3_ml.statql
│   └── estudiantes.csv
├── tests/
│   ├── semantic/
│   ├── intermediate/
│   ├── optimization/
│   └── execution/
├── docs/
│   ├── 01_analisis_semantico.md
│   ├── 02_codigo_intermedio.md
│   └── 03_optimizacion.md
├── demo_optimizacion.py
├── demo_compilador_completo.py
└── build_asm/                    # Salida generada
```

## Instalación

### Requisitos

- Python 3.12 o posterior.
- Git para obtener el repositorio.
- NASM para ensamblar los archivos `.asm`.
- GNU Binutils para enlazar los objetos ELF32.
- `pytest` para ejecutar la suite de pruebas.
- Linux con soporte de ejecución IA-32 para ejecutar los binarios generados.

### Manjaro / Arch Linux

```bash
sudo pacman -Syu
sudo pacman -S --needed git python python-pip nasm binutils python-pytest
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip python3-pytest nasm binutils
```

Verifica la versión disponible antes de continuar:

```bash
python3 --version
```

> La versión de Python depende de la distribución instalada. El proyecto requiere Python 3.12 o posterior.

### Clonar el proyecto

```bash
git clone [https://github.com/badiolajh/StatQL---Proyecto-Final.git](https://github.com/badiolajh/StatQL---Proyecto-Final.git)
cd StatQL---Proyecto-Final
```

### Entorno virtual recomendado

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m pip install pytest
```

Dentro del entorno virtual, utiliza `python` para ejecutar los ejemplos siguientes.

Para salir:

```bash
deactivate
```

## Guía de uso

Ejecuta los comandos desde la raíz del repositorio.

### Compilación completa

```bash
python demo_compilador_completo.py
```

El script:

1. Procesa los programas de `samples/`.
2. Ejecuta las cuatro fases del compilador.
3. Genera archivos `.asm` en `build_asm/`.
4. Imprime el reporte de asignación de registros.
5. Muestra el ensamblador generado.

### Análisis de optimización

```bash
python demo_optimizacion.py
```

Presenta los cuádruplos originales y optimizados, junto con las métricas de reducción y las pasadas realizadas.

### Ensamblado, enlazado y ejecución

Consulta primero los archivos generados:

```bash
ls build_asm/*.asm
```

Si existe `build_asm/ejemplo1_basico.asm`, puedes procesarlo así:

```bash
# 1. Ensamblar a objeto ELF32.
nasm -f elf32 build_asm/ejemplo1_basico.asm \
    -o build_asm/ejemplo1_basico.o

# 2. Enlazar como ejecutable IA-32.
ld -m elf_i386 build_asm/ejemplo1_basico.o \
    -o build_asm/ejemplo1_basico

# 3. Ejecutar.
./build_asm/ejemplo1_basico
```

Sustituye `ejemplo1_basico` por el nombre real del archivo que quieras ejecutar.

> La generación del archivo `.asm` no ejecuta automáticamente NASM, el enlazador ni el binario resultante.

## Uso programático

El siguiente ejemplo compila un programa que calcula el factorial de 5:

```python
from pathlib import Path

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

# 1. Análisis léxico, sintáctico y semántico.
tokens = Lexer(codigo_fuente).tokenize()
ast = Parser(tokens).parse()

analyzer = SemanticAnalyzer(base_dir="samples")
analyzer.analyze(ast)

# 2. Generación de código intermedio.
ir_gen = IntermediateCodeGenerator(
    analyzer.get_intermediate_code_context()
)
ir_gen.generate()

# 3. Optimización multipasada.
optimizer = QuadrupleOptimizer(
    ir_gen.get_optimizer_input_context(),
    analyzer.get_optimization_context(),
)
optimizer.optimize()

# 4. Generación de ensamblador.
codegen = ObjectCodeGenerator(
    optimizer.get_codegen_input_context()
)
asm_code = codegen.generate()

Path("build_asm").mkdir(parents=True, exist_ok=True)
codegen.save_asm("build_asm/factorial.asm")

print(codegen.format_register_report())
print(asm_code)
```

Después de ejecutar el ejemplo:

```bash
nasm -f elf32 build_asm/factorial.asm -o build_asm/factorial.o
ld -m elf_i386 build_asm/factorial.o -o build_asm/factorial

./build_asm/factorial
```

Salida esperada:

```text
120
```

## Pruebas automatizadas

El proyecto reporta una suite de 60 pruebas automatizadas que cubre análisis semántico, código intermedio, optimización y generación de código.

Los casos incluyen algoritmos clásicos, secciones del ensamblador y desbordamiento de registros.

### Ejecutar la suite

```bash
python -m pytest -v
```

### Ejecutar las pruebas de código objeto

```bash
python -m pytest tests/execution/test_codegen.py -v
```

### Consultar las pruebas descubiertas

```bash
python -m pytest --collect-only -q
```

### Descubrimiento mediante unittest

```bash
python -m unittest discover -s tests -v
```

> Comprueba el total de pruebas descubierto por cada herramienta. `unittest` y `pytest` no necesariamente ejecutan el mismo conjunto de casos; una ejecución con cero pruebas no constituye una validación.

## Arquitectura del código generado

### Registros

| Grupo | Registros | Uso |
| :--- | :--- | :--- |
| Asignables | `EBX`, `ECX`, `ESI`, `EDI` | Valores administrados por `RegisterAllocator` |
| Auxiliares | `EAX`, `EDX` | Evaluación de operaciones y preparación de resultados |
| Pila | `EBP`, `ESP` | Marco de activación y administración de la pila |

El asignador utiliza una política LRU (*Least Recently Used*) y controla los valores modificados mediante un estado sucio (*dirty*).

Cuando corresponde, sincroniza los valores con su respaldo en memoria. Las escrituras de sincronización en fronteras de bloques no deben confundirse con los desalojos por falta de registros.

### Secciones y almacenamiento

| Sección / área | Contenido |
| :--- | :--- |
| `.data` | Literales de texto, cadenas booleanas y mensajes del runtime |
| `.bss` | Variables respaldadas por etiquetas `mem_sym_*` y `num_buffer` |
| `.text` | Instrucciones del programa y subrutinas de impresión |
| Pila | Temporales como `[ebp - 4]`, argumentos y valores preservados |

El marco principal utiliza el esquema:

```asm
push ebp
mov ebp, esp
sub esp, N
```

El tamaño reservado se redondea a un múltiplo de 16 bytes, con una reserva mínima de 16 bytes. Este criterio de tamaño no implica por sí solo alineación de la pila en todas las llamadas.

### Salida estándar

El ensamblador incluye las subrutinas:

```text
_statql_print_int
_statql_print_str
_statql_print_bool
```

Reciben su argumento por pila, mediante `[ebp + 8]`.

Las llamadas al sistema utilizan la interfaz Linux i386:

| Operación | Número en `EAX` | Entrada al kernel |
| :--- | :--- | :--- |
| `sys_write` | `4` | `int 0x80` |
| `sys_exit` | `1` | `int 0x80` |

## Diagnósticos semánticos

| Código | Identificador | Descripción |
| :--- | :--- | :--- |
| `SEM_001` | `UNDECLARED_VAR` | Variable no declarada |
| `SEM_002` | `DUPLICATE_DECL` | Declaración duplicada |
| `SEM_003` | `INCOMPATIBLE_TYPES` | Tipos incompatibles |
| `SEM_004` | `INVALID_CAST` | Conversión inválida |
| `SEM_005` | `CSV_COLUMN_NOT_FOUND` | Columna CSV no encontrada |
| `SEM_006` | `NON_BOOLEAN_CONDITION` | Condición no booleana |
| `SEM_007` | `IMMUTABLE_OBJECT` | Modificación no permitida de un objeto inmutable |
| `SEM_008` | `CSV_FILE_NOT_FOUND` | Archivo CSV no encontrado |

Los identificadores completos siguen el formato `SEM_001_UNDECLARED_VAR`.

Para archivos CSV con rutas relativas, revisa el parámetro `base_dir` de `SemanticAnalyzer`.

## Documentación

Los documentos técnicos se encuentran en `docs/`:

| Documento | Contenido |
| :--- | :--- |
| [Análisis semántico](docs/01_analisis_semantico.md) | Símbolos, ámbitos, tipos y validaciones |
| [Código intermedio](docs/02_codigo_intermedio.md) | Notaciones, cuádruplos y traducción |
| [Optimización](docs/03_optimizacion.md) | Transformaciones y métricas |

## Alcance y limitaciones

- El destino del backend es Linux IA-32; no genera código nativo x86-64 ni ejecutables para Windows.
- Ejecutar binarios de 32 bits en un sistema x86_64 requiere soporte IA-32 del kernel.
- Los ejecutables mostrados utilizan llamadas directas al sistema y se enlazan sin `-lc`; no debe asumirse que requieren `lib32-glibc`.
- La traducción observada de `I2D` copia el valor al registro de destino. No debe interpretarse como una implementación completa de conversión a punto flotante IEEE-754.
- Los mensajes del runtime relacionados con CSV o entrenamiento no constituyen, por sí solos, evidencia de ejecución funcional completa de esas operaciones.
- Las palabras reservadas, como `y`, no deben utilizarse como nombres de variables.
- La generación correcta de ensamblador y su ejecución correcta son verificaciones diferentes.
- El total de pruebas corresponde al estado reportado del proyecto y puede cambiar entre revisiones.

---

Proyecto académico desarrollado para Lenguajes y Autómatas II.  
Instituto Tecnológico de Oaxaca · Tecnológico Nacional de México.
