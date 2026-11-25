import os
from statql import (
    Lexer,
    Parser,
    SemanticAnalyzer,
    IntermediateCodeGenerator,
    QuadrupleOptimizer,
    ObjectCodeGenerator,
)


def compilar_a_asm(nombre_archivo: str, carpeta_salida: str = "build_asm") -> None:
    ruta_samples = os.path.join(os.path.dirname(__file__), "samples")
    ruta_archivo = os.path.join(ruta_samples, nombre_archivo)
    os.makedirs(carpeta_salida, exist_ok=True)

    with open(ruta_archivo, "r", encoding="utf-8") as f:
        codigo = f.read()

    # Fase 0 y 1: Lexico, Sintactico y Semantico
    tokens = Lexer(codigo).tokenize()
    ast = Parser(tokens).parse()
    analyzer = SemanticAnalyzer(base_dir=ruta_samples)
    analyzer.analyze(ast)

    # Fase 2: Generacion de Codigo Intermedio (Cuadruplos)
    ir_gen = IntermediateCodeGenerator(analyzer.get_intermediate_code_context())
    ir_gen.generate()

    # Fase 3: Optimizacion de Codigo Intermedio
    optimizer = QuadrupleOptimizer(
        ir_gen.get_optimizer_input_context(),
        analyzer.get_optimization_context()
    )
    optimizer.optimize()

    # Fase 4: Generacion de Codigo Objeto (.asm)
    codegen = ObjectCodeGenerator(optimizer.get_codegen_input_context())
    asm_code = codegen.generate()

    nombre_base = os.path.splitext(nombre_archivo)[0]
    ruta_asm = os.path.join(carpeta_salida, f"{nombre_base}.asm")
    codegen.save_asm(ruta_asm)

    print("=" * 88)
    print(f"COMPILACION COMPLETA: {nombre_archivo} -> {ruta_asm}")
    print("-" * 88)
    print(codegen.format_register_report())
    print("\nENSAMBLADOR GENERADO (.asm):")
    print(asm_code)


if __name__ == "__main__":
    for sample in ["ejemplo1_basico.statql", "ejemplo2_analisis_datos.statql", "ejemplo3_ml.statql"]:
        compilar_a_asm(sample)
