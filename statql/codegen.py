"""
statql/codegen.py
Modulo 4: Generacion de Codigo Objeto (Ensamblador x86 32-bit NASM para Linux) para StatQL.

Cumple con los requerimientos del Tema 4:
1. Asignacion y administracion de registros fisicos de CPU (EAX, EBX, ECX, EDX, ESI, EDI)
   con politica LRU y desbordamiento (spilling) a memoria/pila.
2. Traduccion de la tabla de cuadruplos optimizada a ensamblador ejecutable (.asm).
3. Administracion de memoria en tiempo de ejecucion:
   - Segmento .data (literales de texto, constantes y cadenas de formato)
   - Segmento .bss (variables globales de usuario y temporales desbordados)
   - Segmento .text y Stack Frame (EBP/ESP) para subrutinas y punto de entrada _start.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .ir_generator import Quadruple
from .symbol_table import Symbol, SymbolTable, ReferenceTable


PHYSICAL_REGISTERS: List[str] = ["EAX", "EBX", "ECX", "EDX", "ESI", "EDI"]
SCRATCH_REGISTERS: Set[str] = {"EAX", "EDX"}  # Reservados para division (idiv) y syscalls


@dataclass
class RegisterAllocationEntry:
    step: int
    quadruple_str: str
    register_map: Dict[str, Optional[str]]
    spilled_vars: List[str]
    action_note: str


class RegisterAllocator:
    """
    Administrador de registros fisicos x86 (32-bit).
    Implementa mapeo dinamico operando -> registro fisico con politica LRU
    y volcado (spill) hacia memoria (.bss / stack frame) cuando se agotan los registros.
    """

    def __init__(self, registers: Optional[List[str]] = None):
        self.registers: List[str] = list(registers or ["EBX", "ECX", "ESI", "EDI"])
        self.reg_to_var: Dict[str, Optional[str]] = {r: None for r in self.registers}
        self.var_to_reg: Dict[str, str] = {}
        self.dirty: Set[str] = set()
        self.last_used: Dict[str, int] = {r: 0 for r in self.registers}
        self.tick: int = 0
        self.spilled_variables: Set[str] = set()
        self.history: List[RegisterAllocationEntry] = []

    def _touch(self, reg: str) -> None:
        self.tick += 1
        self.last_used[reg] = self.tick

    def get_register(self, var_name: str) -> Optional[str]:
        reg = self.var_to_reg.get(var_name)
        if reg is not None:
            self._touch(reg)
        return reg

    def allocate(
        self,
        var_name: str,
        emit_asm: List[str],
        mem_operand_fn,
        load_value: bool = True,
        mark_dirty: bool = False,
    ) -> str:
        """
        Asigna un registro fisico a `var_name`. Si no hay registros libres,
        selecciona el menos recientemente usado (LRU), realiza spill a memoria
        si esta sucio y carga el nuevo operando.
        """
        if var_name in self.var_to_reg:
            reg = self.var_to_reg[var_name]
            self._touch(reg)
            if mark_dirty:
                self.dirty.add(var_name)
            return reg

        # Buscar registro libre
        free_reg: Optional[str] = None
        for r in self.registers:
            if self.reg_to_var[r] is None:
                free_reg = r
                break

        if free_reg is None:
            # Elegir victima LRU
            free_reg = min(self.registers, key=lambda r: self.last_used[r])
            victim = self.reg_to_var[free_reg]
            if victim is not None:
                self.spilled_variables.add(victim)
                if victim in self.dirty:
                    emit_asm.append(f"    mov {mem_operand_fn(victim)}, {free_reg}    ; Spill LRU de {victim}")
                    self.dirty.discard(victim)
                del self.var_to_reg[victim]
                self.reg_to_var[free_reg] = None

        self.reg_to_var[free_reg] = var_name
        self.var_to_reg[var_name] = free_reg
        self._touch(free_reg)

        if load_value:
            emit_asm.append(f"    mov {free_reg}, {mem_operand_fn(var_name)}    ; Cargar {var_name} en {free_reg}")

        if mark_dirty:
            self.dirty.add(var_name)

        return free_reg

    def flush_all(self, emit_asm: List[str], mem_operand_fn, reason: str = "Sync bloque basico") -> None:
        """
        Sincroniza todos los registros modificados (dirty) hacia memoria
        antes de saltos, etiquetas o llamadas a subrutinas.
        """
        for reg in self.registers:
            var = self.reg_to_var[reg]
            if var is not None and var in self.dirty:
                emit_asm.append(f"    mov {mem_operand_fn(var)}, {reg}    ; Flush ({reason}): {var}")
                self.dirty.discard(var)

    def invalidate_all(self, emit_asm: List[str], mem_operand_fn, reason: str = "Fin de bloque") -> None:
        """Volca registros sucios y limpia la tabla de asignacion activa."""
        self.flush_all(emit_asm, mem_operand_fn, reason=reason)
        for reg in self.registers:
            self.reg_to_var[reg] = None
        self.var_to_reg.clear()

    def snapshot(self, step: int, quad: Quadruple, note: str) -> None:
        self.history.append(
            RegisterAllocationEntry(
                step=step,
                quadruple_str=str(quad),
                register_map=dict(self.reg_to_var),
                spilled_vars=sorted(self.spilled_variables),
                action_note=note,
            )
        )


class ObjectCodeGenerator:
    """
    Generador de Codigo Objeto x86 (32-bit NASM Linux) para StatQL.
    Consume el contrato `get_codegen_input_context()` del Modulo 3 (QuadrupleOptimizer).
    """

    def __init__(self, codegen_context: Dict[str, Any]):
        self.quadruples: List[Quadruple] = list(codegen_context.get("quadruples", []))
        self.global_table: Optional[SymbolTable] = codegen_context.get("global_table")
        self.reference_table: Optional[ReferenceTable] = codegen_context.get("reference_table")
        self.opt_stats = codegen_context.get("stats")

        self.allocator = RegisterAllocator()
        self.string_literals: Dict[str, str] = {}
        self.string_counter: int = 0
        self.bss_symbols: Dict[str, str] = {}   # nombre_ir -> etiqueta_asm
        self.stack_offsets: Dict[str, int] = {} # temporales locales -> [ebp - offset]
        self.local_stack_size: int = 0

        self.data_lines: List[str] = []
        self.bss_lines: List[str] = []
        self.text_lines: List[str] = []
        self.asm_code: str = ""

    @staticmethod
    def _is_string_literal(val: Any) -> bool:
        return isinstance(val, str) and len(val) >= 2 and val.startswith('"') and val.endswith('"')

    @staticmethod
    def _parse_numeric_or_bool(val: Any) -> Tuple[bool, int]:
        """
        Convierte constantes numericas o booleanas a representacion entera x86 de 32 bits.
        Para decimales en registros enteros se aplica escalado fijo (x100) o truncamiento entero
        para compatibilidad directa con registros de proposito general (EAX..EDI).
        """
        if not isinstance(val, str):
            return False, 0
        if val == "verdadero":
            return True, 1
        if val == "falso":
            return True, 0
        if val.startswith(("t", "L_", "sym_", "ds_", "iter_", "model_", '"')):
            return False, 0
        try:
            if "." in val:
                return True, int(round(float(val)))
            return True, int(val)
        except ValueError:
            return False, 0

    @staticmethod
    def _sanitize_label(name: str) -> str:
        clean = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)
        if clean and clean[0].isdigit():
            clean = f"v_{clean}"
        return clean

    def _register_string(self, raw_quoted: str) -> str:
        content = raw_quoted[1:-1] if self._is_string_literal(raw_quoted) else str(raw_quoted)
        if content in self.string_literals:
            return self.string_literals[content]
        label = f"str_lit_{self.string_counter}"
        self.string_counter += 1
        self.string_literals[content] = label
        return label

    def _collect_memory_layout(self) -> None:
        """
        Analiza simbolos, literales y temporales para configurar:
        1. Segmento .data (cadenas literales)
        2. Segmento .bss (variables globales de usuario sym_*)
        3. Marco de pila [ebp - N] para variables temporales (t0, t1, ...)
        """
        user_vars: Set[str] = set()
        temp_vars: Set[str] = set()

        if self.reference_table is not None:
            for addr in self.reference_table.addresses.keys():
                user_vars.add(addr)

        for q in self.quadruples:
            for operand in (q.arg1, q.arg2, q.result):
                if not isinstance(operand, str):
                    continue
                if self._is_string_literal(operand):
                    self._register_string(operand)
                elif q.op in {"LABEL", "GOTO", "IF_FALSE"} and operand == q.result:
                    continue
                else:
                    is_imm, _ = self._parse_numeric_or_bool(operand)
                    if is_imm:
                        continue
                    if operand.startswith("t") and operand[1:].isdigit():
                        temp_vars.add(operand)
                    else:
                        user_vars.add(operand)

        for var in sorted(user_vars):
            self.bss_symbols[var] = f"mem_{self._sanitize_label(var)}"

        offset = 4
        for tmp in sorted(temp_vars, key=lambda x: int(x[1:])):
            self.stack_offsets[tmp] = offset
            offset += 4

        # Alinear tamano del stack frame a 16 bytes
        raw_size = offset - 4
        self.local_stack_size = ((raw_size + 15) // 16) * 16 if raw_size > 0 else 16

    def _mem_operand(self, var_name: str) -> str:
        """Devuelve la direccion efectiva en memoria (.bss para globals, [ebp-N] para temporales)."""
        if var_name in self.stack_offsets:
            return f"dword [ebp - {self.stack_offsets[var_name]}]"
        if var_name not in self.bss_symbols:
            self.bss_symbols[var_name] = f"mem_{self._sanitize_label(var_name)}"
        return f"dword [{self.bss_symbols[var_name]}]"

    def _resolve_operand_to_eax(self, operand: Any, emit: List[str]) -> str:
        """Coloca el valor de `operand` en EAX y retorna 'EAX'."""
        if operand is None:
            emit.append("    xor eax, eax")
            return "EAX"

        if self._is_string_literal(operand):
            lbl = self._register_string(operand)
            emit.append(f"    mov eax, {lbl}    ; Direccion de literal de texto")
            return "EAX"

        is_imm, imm_val = self._parse_numeric_or_bool(operand)
        if is_imm:
            emit.append(f"    mov eax, {imm_val}")
            return "EAX"

        var_str = str(operand)
        reg = self.allocator.get_register(var_str)
        if reg is not None:
            emit.append(f"    mov eax, {reg}    ; Leer {var_str} desde registro")
        else:
            reg = self.allocator.allocate(var_str, emit, self._mem_operand, load_value=True)
            emit.append(f"    mov eax, {reg}")
        return "EAX"

    def _emit_data_section(self) -> None:
        self.data_lines = [
            "section .data",
            "    newline     db 10, 0",
            "    str_true    db 'verdadero', 0",
            "    str_false   db 'falso', 0",
            "    msg_csv     db '[RUNTIME] CSV cargado en memoria', 0",
            "    msg_iter    db '[RUNTIME] Iterando registros de dataset', 0",
            "    msg_col     db '[RUNTIME] Acceso a columna de fila', 0",
            "    msg_train   db '[RUNTIME] Modelo DecisionTree entrenado', 0",
        ]
        for text_val, lbl in self.string_literals.items():
            escaped = text_val.replace("'", "', 39, '")
            self.data_lines.append(f"    {lbl:<12} db '{escaped}', 0")

    def _emit_bss_section(self) -> None:
        self.bss_lines = [
            "",
            "section .bss",
            "    num_buffer  resb 16    ; Buffer de conversion entero -> ASCII",
        ]
        for orig_name, asm_label in self.bss_symbols.items():
            sym_info = ""
            if self.reference_table:
                sym = self.reference_table.get_symbol_by_address(orig_name)
                if sym:
                    sym_info = f" ; var '{sym.name}' ({sym.type}, ambito={sym.scope_name})"
            self.bss_lines.append(f"    {asm_label:<28} resd 1{sym_info}")

    def _emit_runtime_subroutines(self) -> List[str]:
        """
        Subrutinas en ensamblador con marco de pila estandar (Stack Frame EBP/ESP)
        para impresion por consola (sys_write) y operaciones runtime de StatQL.
        """
        return [
            "",
            "; ============================================================================",
            "; SUBRUTINAS DE TIEMPO DE EJECUCION (CON STACK FRAME EBP/ESP)",
            "; ============================================================================",
            "",
            "; void _statql_print_str(char* ptr) -> [ebp + 8]",
            "_statql_print_str:",
            "    push ebp",
            "    mov ebp, esp",
            "    push ebx",
            "    push ecx",
            "    push edx",
            "    mov esi, [ebp + 8]",
            "    xor edx, edx",
            ".strlen_loop:",
            "    cmp byte [esi + edx], 0",
            "    je .strlen_done",
            "    inc edx",
            "    jmp .strlen_loop",
            ".strlen_done:",
            "    mov eax, 4          ; sys_write",
            "    mov ebx, 1          ; stdout",
            "    mov ecx, esi        ; puntero cadena",
            "    int 0x80",
            "    ; Imprimir salto de linea",
            "    mov eax, 4",
            "    mov ebx, 1",
            "    mov ecx, newline",
            "    mov edx, 1",
            "    int 0x80",
            "    pop edx",
            "    pop ecx",
            "    pop ebx",
            "    mov esp, ebp",
            "    pop ebp",
            "    ret",
            "",
            "; void _statql_print_int(int value) -> [ebp + 8]",
            "_statql_print_int:",
            "    push ebp",
            "    mov ebp, esp",
            "    push ebx",
            "    push ecx",
            "    push edx",
            "    push esi",
            "    mov eax, [ebp + 8]",
            "    mov edi, num_buffer + 14",
            "    mov byte [edi + 1], 0",
            "    xor esi, esi        ; bandera negativo",
            "    cmp eax, 0",
            "    jge .convert_loop",
            "    neg eax",
            "    mov esi, 1",
            ".convert_loop:",
            "    xor edx, edx",
            "    mov ecx, 10",
            "    div ecx",
            "    add dl, '0'",
            "    mov [edi], dl",
            "    dec edi",
            "    test eax, eax",
            "    jnz .convert_loop",
            "    cmp esi, 1",
            "    jne .print_digits",
            "    mov byte [edi], '-'",
            "    dec edi",
            ".print_digits:",
            "    inc edi",
            "    push edi",
            "    call _statql_print_str",
            "    add esp, 4",
            "    pop esi",
            "    pop edx",
            "    pop ecx",
            "    pop ebx",
            "    mov esp, ebp",
            "    pop ebp",
            "    ret",
            "",
            "; void _statql_print_bool(int bool_val) -> [ebp + 8]",
            "_statql_print_bool:",
            "    push ebp",
            "    mov ebp, esp",
            "    mov eax, [ebp + 8]",
            "    cmp eax, 0",
            "    je .is_false",
            "    push str_true",
            "    call _statql_print_str",
            "    add esp, 4",
            "    jmp .done_bool",
            ".is_false:",
            "    push str_false",
            "    call _statql_print_str",
            "    add esp, 4",
            ".done_bool:",
            "    mov esp, ebp",
            "    pop ebp",
            "    ret",
        ]

    def _translate_quadruple(self, idx: int, q: Quadruple) -> None:
        op = q.op
        self.text_lines.append(f"    ; [{idx}] {q}")

        if op == "LABEL":
            self.allocator.invalidate_all(self.text_lines, self._mem_operand, reason=f"Etiqueta {q.result}")
            self.text_lines.append(f"{q.result}:")
            self.allocator.snapshot(idx, q, f"Etiqueta {q.result}: registros sincronizados")
            return

        if op == "GOTO":
            self.allocator.invalidate_all(self.text_lines, self._mem_operand, reason=f"Salto GOTO {q.result}")
            self.text_lines.append(f"    jmp {q.result}")
            self.allocator.snapshot(idx, q, f"Salto incondicional a {q.result}")
            return

        if op == "IF_FALSE":
            self._resolve_operand_to_eax(q.arg1, self.text_lines)
            self.allocator.invalidate_all(self.text_lines, self._mem_operand, reason="Evaluacion IF_FALSE")
            self.text_lines.append("    cmp eax, 0")
            self.text_lines.append(f"    je {q.result}")
            self.allocator.snapshot(idx, q, f"Salto condicional si falso a {q.result}")
            return

        if op == "=":
            self._resolve_operand_to_eax(q.arg1, self.text_lines)
            dest = str(q.result)
            dest_reg = self.allocator.allocate(
                dest, self.text_lines, self._mem_operand, load_value=False, mark_dirty=True
            )
            self.text_lines.append(f"    mov {dest_reg}, eax")
            self.allocator.snapshot(idx, q, f"Asignacion {dest} -> {dest_reg}")
            return

        if op == "I2D":
            self._resolve_operand_to_eax(q.arg1, self.text_lines)
            dest = str(q.result)
            dest_reg = self.allocator.allocate(
                dest, self.text_lines, self._mem_operand, load_value=False, mark_dirty=True
            )
            self.text_lines.append(f"    mov {dest_reg}, eax    ; Conversion entera/decimal I2D")
            self.allocator.snapshot(idx, q, f"Cast I2D en {dest_reg}")
            return

        if op in {"UMINUS", "UPLUS", "NOT"}:
            self._resolve_operand_to_eax(q.arg1, self.text_lines)
            if op == "UMINUS":
                self.text_lines.append("    neg eax")
            elif op == "NOT":
                self.text_lines.append("    cmp eax, 0")
                self.text_lines.append("    sete al")
                self.text_lines.append("    movzx eax, al")
            dest = str(q.result)
            dest_reg = self.allocator.allocate(
                dest, self.text_lines, self._mem_operand, load_value=False, mark_dirty=True
            )
            self.text_lines.append(f"    mov {dest_reg}, eax")
            self.allocator.snapshot(idx, q, f"Operacion unaria {op} en {dest_reg}")
            return

        if op in {"+", "-", "*", "/"}:
            self._resolve_operand_to_eax(q.arg1, self.text_lines)
            self.text_lines.append("    push eax    ; Guardar operando izquierdo")
            self._resolve_operand_to_eax(q.arg2, self.text_lines)
            self.text_lines.append("    mov edx, eax    ; Operando derecho en EDX")
            self.text_lines.append("    pop eax         ; Recuperar operando izquierdo en EAX")

            if op == "+":
                self.text_lines.append("    add eax, edx")
            elif op == "-":
                self.text_lines.append("    sub eax, edx")
            elif op == "*":
                self.text_lines.append("    imul eax, edx")
            elif op == "/":
                self.text_lines.append("    mov ecx, edx")
                self.text_lines.append("    cdq")
                self.text_lines.append("    cmp ecx, 0")
                self.text_lines.append("    je .skip_div_zero")
                self.text_lines.append("    idiv ecx")
                self.text_lines.append(".skip_div_zero:")

            dest = str(q.result)
            dest_reg = self.allocator.allocate(
                dest, self.text_lines, self._mem_operand, load_value=False, mark_dirty=True
            )
            self.text_lines.append(f"    mov {dest_reg}, eax")
            self.allocator.snapshot(idx, q, f"Aritmetica ({op}) -> {dest_reg}")
            return

        if op in {"==", "!=", "<", ">", "<=", ">="}:
            self._resolve_operand_to_eax(q.arg1, self.text_lines)
            self.text_lines.append("    push eax")
            self._resolve_operand_to_eax(q.arg2, self.text_lines)
            self.text_lines.append("    mov edx, eax")
            self.text_lines.append("    pop eax")
            self.text_lines.append("    cmp eax, edx")

            set_map = {
                "==": "sete",
                "!=": "setne",
                "<": "setl",
                ">": "setg",
                "<=": "setle",
                ">=": "setge",
            }
            self.text_lines.append(f"    {set_map[op]} al")
            self.text_lines.append("    movzx eax, al")

            dest = str(q.result)
            dest_reg = self.allocator.allocate(
                dest, self.text_lines, self._mem_operand, load_value=False, mark_dirty=True
            )
            self.text_lines.append(f"    mov {dest_reg}, eax")
            self.allocator.snapshot(idx, q, f"Comparacion ({op}) -> {dest_reg}")
            return

        if op in {"y", "o"}:
            self._resolve_operand_to_eax(q.arg1, self.text_lines)
            self.text_lines.append("    cmp eax, 0")
            self.text_lines.append("    setne al")
            self.text_lines.append("    movzx eax, al")
            self.text_lines.append("    push eax")

            self._resolve_operand_to_eax(q.arg2, self.text_lines)
            self.text_lines.append("    cmp eax, 0")
            self.text_lines.append("    setne dl")
            self.text_lines.append("    movzx edx, dl")
            self.text_lines.append("    pop eax")

            if op == "y":
                self.text_lines.append("    and eax, edx")
            else:
                self.text_lines.append("    or eax, edx")

            dest = str(q.result)
            dest_reg = self.allocator.allocate(
                dest, self.text_lines, self._mem_operand, load_value=False, mark_dirty=True
            )
            self.text_lines.append(f"    mov {dest_reg}, eax")
            self.allocator.snapshot(idx, q, f"Logica ({op}) -> {dest_reg}")
            return

        if op == "PRINT":
            self.allocator.flush_all(self.text_lines, self._mem_operand, reason="Llamada PRINT")
            self._resolve_operand_to_eax(q.arg1, self.text_lines)
            self.text_lines.append("    push eax")
            if q.inferred_type == "texto" or self._is_string_literal(q.arg1):
                self.text_lines.append("    call _statql_print_str")
            elif q.inferred_type == "booleano":
                self.text_lines.append("    call _statql_print_bool")
            else:
                self.text_lines.append("    call _statql_print_int")
            self.text_lines.append("    add esp, 4")
            self.allocator.snapshot(idx, q, "Invocacion subrutina PRINT con paso por pila")
            return

        if op in {"LOAD_CSV", "ITER_INIT", "ITER_NEXT", "GET_COL", "TRAIN_TREE"}:
            # Descriptores de tiempo de ejecucion del DSL StatQL
            dest = str(q.result) if q.result else None
            if op == "LOAD_CSV":
                self.text_lines.append(f"    mov eax, {self._register_string(str(q.arg1))}")
            elif op == "ITER_INIT":
                self.text_lines.append("    mov eax, 0    ; Inicializar cursor de iteracion")
            elif op == "ITER_NEXT":
                # Simula avance de cursor (0 -> fin de iteracion en entorno nativo sin CSV externo)
                self.text_lines.append("    mov eax, 0    ; Siguiente fila del dataset")
            elif op == "GET_COL":
                self.text_lines.append("    mov eax, 0    ; Lectura de columna tabular")
            elif op == "TRAIN_TREE":
                self.text_lines.append(f"    mov eax, {self._register_string(str(q.arg2))}")

            if dest:
                dest_reg = self.allocator.allocate(
                    dest, self.text_lines, self._mem_operand, load_value=False, mark_dirty=True
                )
                self.text_lines.append(f"    mov {dest_reg}, eax")
            self.allocator.snapshot(idx, q, f"Operacion DSL {op}")
            return

        if op == "HALT":
            self.allocator.invalidate_all(self.text_lines, self._mem_operand, reason="HALT programa")
            self.text_lines.append("    jmp _statql_exit")
            self.allocator.snapshot(idx, q, "Fin de ejecucion (HALT)")
            return

        raise NotImplementedError(f"Traduccion a ensamblador no soportada para cuádruplo: {q}")

    def generate(self) -> str:
        """
        Ejecuta las 3 fases de generacion de codigo objeto:
        1. Analisis de layout de memoria (.data, .bss, stack frame)
        2. Traduccion de cuadruplos optimizados con asignacion de registros
        3. Ensamblaje del archivo .asm completo
        """
        self._collect_memory_layout()

        self.text_lines = [
            "",
            "section .text",
            "    global _start",
            "",
            "_start:",
            "    ; Prologo del Stack Frame principal",
            "    push ebp",
            "    mov ebp, esp",
            f"    sub esp, {self.local_stack_size}    ; Reserva de marco de pila para temporales",
            "",
        ]

        for idx, q in enumerate(self.quadruples):
            self._translate_quadruple(idx, q)

        self.text_lines.extend([
            "",
            "_statql_exit:",
            "    ; Epilogo del Stack Frame y salida limpia (sys_exit)",
            "    mov esp, ebp",
            "    pop ebp",
            "    mov eax, 1          ; sys_exit",
            "    xor ebx, ebx        ; codigo de retorno 0",
            "    int 0x80",
        ])

        self.text_lines.extend(self._emit_runtime_subroutines())
        self._emit_data_section()
        self._emit_bss_section()

        header = [
            "; ============================================================================",
            "; CODIGO OBJETO GENERADO POR COMPILADOR StatQL (Tema 4 - Ensamblador x86 NASM)",
            "; Arquitectura destino: IA-32 (x86 32-bit Linux ELF)",
            "; Ensamblar: nasm -f elf32 programa.asm -o programa.o",
            "; Enlazar:   ld -m elf_i386 programa.o -o programa",
            "; ============================================================================",
            "",
        ]

        full_lines = header + self.data_lines + self.bss_lines + self.text_lines
        self.asm_code = "\n".join(full_lines) + "\n"
        return self.asm_code

    def save_asm(self, output_path: str) -> str:
        if not self.asm_code:
            self.generate()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.asm_code)
        return output_path

    def format_register_report(self) -> str:
        """Genera un reporte tabular de la asignacion de registros y spills realizados."""
        lines = [
            "┌── Reporte de Asignación de Registros Físicos (x86 32-bit)",
            f"│ Registros disponibles: {', '.join(self.allocator.registers)} (Auxiliares: EAX, EDX)",
            f"│ Variables desbordadas a memoria (Spills): {sorted(self.allocator.spilled_variables) or 'Ninguna'}",
            f"│ Tamaño de Stack Frame reservado: {self.local_stack_size} bytes",
            f"│ {'Paso':<5} | {'Cuádruplo':<30} | {'EBX':<14} | {'ECX':<14} | {'ESI':<14} | {'EDI':<14}",
            f"│ {'-'*5}-+-{'-'*30}-+-{'-'*14}-+-{'-'*14}-+-{'-'*14}-+-{'-'*14}",
        ]
        for entry in self.allocator.history:
            rm = entry.register_map
            lines.append(
                f"│ {entry.step:<5} | {entry.quadruple_str:<30} | "
                f"{str(rm.get('EBX') or '-'):<14} | {str(rm.get('ECX') or '-'):<14} | "
                f"{str(rm.get('ESI') or '-'):<14} | {str(rm.get('EDI') or '-'):<14}"
            )
        return "\n".join(lines)
