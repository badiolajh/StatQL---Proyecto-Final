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

    def test_factorial_algorithm_generation(self):
        code = """
        entero n = 5;
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

        # Ejecucion nativa real si nasm y ld estan disponibles en Linux
        if shutil.which("nasm") and shutil.which("ld"):
            with tempfile.TemporaryDirectory() as tmpdir:
                asm_path = os.path.join(tmpdir, "fact.asm")
                obj_path = os.path.join(tmpdir, "fact.o")
                bin_path = os.path.join(tmpdir, "fact")
                with open(asm_path, "w", encoding="utf-8") as f:
                    f.write(asm)

                subprocess.run(["nasm", "-f", "elf32", asm_path, "-o", obj_path], check=True)
                subprocess.run(["ld", "-m", "elf_i386", obj_path, "-o", bin_path], check=True)
                res = subprocess.run([bin_path], capture_output=True, text=True, check=True)
                self.assertEqual(res.stdout.strip(), "120")

    def test_fibonacci_algorithm_generation(self):
        code = """
        entero n = 7;
        entero a = 0;
        entero b = 1;
        entero cont = 0;
        entero temp = 0;
        mientras (cont < n) {
            temp = a + b;
            a = b;
            b = temp;
            cont = cont + 1;
        }
        mostrar a;
        """
        asm, _ = compile_source_to_asm(code)
        self.assertIn("add eax, edx", asm)

        if shutil.which("nasm") and shutil.which("ld"):
            with tempfile.TemporaryDirectory() as tmpdir:
                asm_path = os.path.join(tmpdir, "fib.asm")
                obj_path = os.path.join(tmpdir, "fib.o")
                bin_path = os.path.join(tmpdir, "fib")
                with open(asm_path, "w", encoding="utf-8") as f:
                    f.write(asm)

                subprocess.run(["nasm", "-f", "elf32", asm_path, "-o", obj_path], check=True)
                subprocess.run(["ld", "-m", "elf_i386", obj_path, "-o", bin_path], check=True)
                res = subprocess.run([bin_path], capture_output=True, text=True, check=True)
                self.assertEqual(res.stdout.strip(), "13")

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
        # Con 4 registros asignables (EBX, ECX, ESI, EDI) y 7 variables modificadas en ciclo, debe haber spill
        self.assertGreaterEqual(len(codegen.allocator.spilled_variables), 2)

if __name__ == "__main__":
    unittest.main()
