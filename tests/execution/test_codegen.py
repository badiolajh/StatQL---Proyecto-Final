import os
import shutil
import subprocess
import tempfile
import unittest

from statql import (
    Lexer,
    Parser,
    SemanticAnalyzer,
    IntermediateCodeGenerator,
    QuadrupleOptimizer,
    ObjectCodeGenerator,
)


def compile_source_to_asm(source_code: str, base_dir: str = ".") -> tuple[str, ObjectCodeGenerator]:
    tokens = Lexer(source_code).tokenize()
    ast = Parser(tokens).parse()
    analyzer = SemanticAnalyzer(base_dir=base_dir)
    analyzer.analyze(ast)

    ir_gen = IntermediateCodeGenerator(analyzer.get_intermediate_code_context())
    ir_gen.generate()

    optimizer = QuadrupleOptimizer(
        ir_gen.get_optimizer_input_context(),
        analyzer.get_optimization_context(),
    )
    optimizer.optimize()

    codegen = ObjectCodeGenerator(optimizer.get_codegen_input_context())
    asm = codegen.generate()
    return asm, codegen


def assemble_link_and_run(asm_code: str, name: str = "prog") -> str:
    """Ensambla con NASM (elf32), enlaza con GNU ld (elf_i386) y ejecuta el binario nativo."""
    with tempfile.TemporaryDirectory() as tmpdir:
        asm_path = os.path.join(tmpdir, f"{name}.asm")
        obj_path = os.path.join(tmpdir, f"{name}.o")
        bin_path = os.path.join(tmpdir, name)

        with open(asm_path, "w", encoding="utf-8") as f:
            f.write(asm_code)

        subprocess.run(["nasm", "-f", "elf32", asm_path, "-o", obj_path], check=True)
        subprocess.run(["ld", "-m", "elf_i386", obj_path, "-o", bin_path], check=True)
        res = subprocess.run([bin_path], capture_output=True, text=True, check=True)
        return res.stdout.strip()


class TestObjectCodeGeneration(unittest.TestCase):
    def test_memory_segments_and_stack_frame(self):
        code = """
        entero a = 10;
        entero b = 20;
        entero z = a + b * 2;
        mostrar z;
        """
        asm, codegen = compile_source_to_asm(code)

        self.assertIn("section .data", asm)
        self.assertIn("section .bss", asm)
        self.assertIn("section .text", asm)
        self.assertIn("global _start", asm)
        self.assertIn("push ebp", asm)
        self.assertIn("mov ebp, esp", asm)
        self.assertIn("call _statql_print_int", asm)
        self.assertGreater(len(codegen.allocator.history), 0)

        if shutil.which("nasm") and shutil.which("ld"):
            output = assemble_link_and_run(asm, "segments_test")
            self.assertEqual(output, "50")

    def test_factorial_algorithm_execution(self):
        """Algoritmo Clasico 1: Factorial iterativo (6! = 720)."""
        code = """
        entero n = 6;
        entero fact = 1;
        entero i = 1;
        mientras (i <= n) {
            fact = fact * i;
            i = i + 1;
        }
        mostrar fact;
        """
        asm, _ = compile_source_to_asm(code)

        self.assertIn("imul eax, edx", asm)
        self.assertIn("setle al", asm)
        self.assertIn("L_while_start_", asm)
        self.assertIn("L_while_end_", asm)

        if shutil.which("nasm") and shutil.which("ld"):
            output = assemble_link_and_run(asm, "factorial")
            self.assertEqual(output, "720")

    def test_fibonacci_series_execution(self):
        """Algoritmo Clasico 2: Serie de Fibonacci (primeros 8 terminos: 0, 1, 1, 2, 3, 5, 8, 13)."""
        code = """
        entero limite = 8;
        entero a = 0;
        entero b = 1;
        entero cont = 0;
        entero siguiente = 0;
        mientras (cont < limite) {
            mostrar a;
            siguiente = a + b;
            a = b;
            b = siguiente;
            cont = cont + 1;
        }
        """
        asm, _ = compile_source_to_asm(code)
        self.assertIn("add eax, edx", asm)

        if shutil.which("nasm") and shutil.which("ld"):
            output = assemble_link_and_run(asm, "fibonacci")
            self.assertEqual(output.splitlines(), ["0", "1", "1", "2", "3", "5", "8", "13"])

    def test_calculator_operations_execution(self):
            """Algoritmo Clasico 3: Calculadora aritmetica, unaria, relacional y condicional."""
            code = """
            entero op1 = 42;
            entero op2 = 5;
            entero k = 0;
            mientras (k < 1) {
                op2 = op2 + 1;
                k = k + 1;
            }
            entero suma = op1 + op2;
            entero resta = op1 - op2;
            entero mult = op1 * op2;
            entero divi = op1 / op2;
            entero negado = -op2 + 10;

            mostrar suma;
            mostrar resta;
            mostrar mult;
            mostrar divi;
            mostrar negado;

            si (divi == 7 y suma > 40) {
                mostrar "CALC_OK";
            } sino {
                mostrar "CALC_ERR";
            }
            """
            asm, _ = compile_source_to_asm(code)
            self.assertIn("idiv ecx", asm)
            self.assertIn("neg eax", asm)

            if shutil.which("nasm") and shutil.which("ld"):
                output = assemble_link_and_run(asm, "calculadora")
                self.assertEqual(output.splitlines(), ["48", "36", "252", "7", "4", "CALC_OK"])

    def test_euclid_gcd_algorithm_execution(self):
        """Algoritmo Clasico 4: Maximo Comun Divisor (Algoritmo de Euclides por restas)."""
        code = """
        entero a = 48;
        entero b = 18;
        mientras (a != b) {
            si (a > b) {
                a = a - b;
            } sino {
                b = b - a;
            }
        }
        mostrar a;
        """
        asm, _ = compile_source_to_asm(code)

        if shutil.which("nasm") and shutil.which("ld"):
            output = assemble_link_and_run(asm, "euclides_mcd")
            self.assertEqual(output, "6")

    def test_register_spilling_under_pressure(self):
        code = """
        entero a = 1;
        entero b = 2;
        entero c = 3;
        entero d = 4;
        entero e = 5;
        entero f = 6;
        entero i = 0;
        mientras (i < 1) {
            a = a + 1;
            b = b + 1;
            c = c + 1;
            d = d + 1;
            e = e + 1;
            f = f + 1;
            i = i + 1;
        }
        entero res = a + b + c + d + e + f;
        mostrar res;
        """
        _, codegen = compile_source_to_asm(code)
        self.assertGreaterEqual(len(codegen.allocator.spilled_variables), 2)


if __name__ == "__main__":
    unittest.main()
