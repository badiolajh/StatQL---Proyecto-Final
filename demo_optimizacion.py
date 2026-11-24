import os
from statql import (
    Lexer,
    Parser,
    SemanticAnalyzer,
    IntermediateCodeGenerator,
    QuadrupleOptimizer,
)


def ejecutar_demo(nombre_archivo: str) -> None:
    ruta_samples = os.path.join(os.path.dirname(__file__), "samples")
    ruta_archivo = os.path.join(ruta_samples, nombre_archivo)

    with open(ruta_archivo, "r", encoding="utf-8") as f:
        codigo = f.read()

    tokens = Lexer(codigo).tokenize()
    ast = Parser(tokens).parse()

    analyzer = SemanticAnalyzer(base_dir=ruta_samples)
    analyzer.analyze(ast)

    ir_gen = IntermediateCodeGenerator(analyzer.get_intermediate_code_context())
    ir_gen.generate()

    optimizer = QuadrupleOptimizer(
        ir_gen.get_optimizer_input_context(),
        analyzer.get_optimization_context()
    )
    optimizer.optimize()

    print("=" * 80)
    print(f"ARCHIVO: {nombre_archivo}")
    print("-" * 80)
    print("CUADRUPLAS ORIGINALES (MODULO 2):")
    print(ir_gen.pretty_format())
    print("\nCUADRUPLAS OPTIMIZADAS (MODULO 3):")
    print(optimizer.pretty_format())
    print(
        f"\nRESUMEN: {optimizer.stats.initial_quadruples} -> "
        f"{optimizer.stats.final_quadruples} cuadruplas "
        f"(Reduccion: {optimizer.stats.reduction_percentage}%, "
        f"Pasadas: {optimizer.stats.passes_executed})"
    )


if __name__ == "__main__":
    for sample in ["ejemplo1_basico.statql", "ejemplo2_analisis_datos.statql", "ejemplo3_ml.statql"]:
        ejecutar_demo(sample)