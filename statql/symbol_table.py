"""
statql/symbol_table.py
Tabla de Símbolos Dinámica y Tabla de Direcciones Simbólicas / Referencias para StatQL.
Provee gestión jerárquica de ámbitos léxicos (scoping) y una interfaz desacoplada
para asignación de memoria/direcciones simbólicas utilizada por los Integrantes 2 y 3.
"""

from typing import Dict, Optional, List, Tuple, Any, Set


class Symbol:
    """
    Representa una entidad declarada o importada en el programa StatQL.
    Almacena tipo, ámbito, posición, metadatos y registro de referencias de uso.
    """
    def __init__(self, name: str, type_name: str, scope_level: int, scope_name: str,
                 line: int = 1, column: int = 1, symbolic_address: Optional[str] = None,
                 **metadata: Any):
        self.name = name
        # Tipos primitivos: 'entero', 'decimal', 'texto', 'booleano'
        # Tipos complejos/DSL: 'tabla', 'fila', 'modelo'
        self.type = type_name
        self.scope_level = scope_level
        self.scope_name = scope_name
        self.line = line
        self.column = column
        self.symbolic_address = symbolic_address
        self.metadata: Dict[str, Any] = dict(metadata)
        # Lista de ocurrencias (línea, columna) donde el símbolo es leído/utilizado
        self.references: List[Tuple[int, int]] = []
        self.is_constant: bool = False

    @property
    def is_used(self) -> bool:
        """Determina si la variable ha sido referenciada al menos una vez."""
        return len(self.references) > 0

    def add_reference(self, line: int, column: int) -> None:
        """Registra una posición de lectura o uso de este símbolo."""
        self.references.append((line, column))

    def __repr__(self) -> str:
        addr_str = f" addr='{self.symbolic_address}'" if self.symbolic_address else ""
        meta_str = f" meta={self.metadata}" if self.metadata else ""
        refs_str = f" refs={len(self.references)}"
        return f"Symbol(name='{self.name}', type='{self.type}', scope={self.scope_name}:{self.scope_level}{addr_str}{refs_str}{meta_str})"


class SymbolTable:
    """
    Tabla de símbolos con estructura de árbol para soportar ámbitos léxicos (lexical scoping).
    Permite anidar bloques de control (si, sino, para cada, mientras) y resolver nombres
    respetando el ocultamiento y la visibilidad léxica.
    """

    def __init__(self, scope_name: str = "global", scope_level: int = 0,
                 parent: Optional['SymbolTable'] = None):
        self.scope_name = scope_name
        self.scope_level = scope_level
        self.parent = parent
        self.children: List['SymbolTable'] = []
        self.symbols: Dict[str, Symbol] = {}

    def create_child(self, scope_name: str) -> 'SymbolTable':
        """Crea y registra un sub-ámbito dependiente del actual."""
        child = SymbolTable(
            scope_name=scope_name,
            scope_level=self.scope_level + 1,
            parent=self
        )
        self.children.append(child)
        return child

    def define(self, symbol: Symbol) -> Symbol:
        """Registra un nuevo símbolo en el alcance actual."""
        symbol.scope_level = self.scope_level
        symbol.scope_name = self.scope_name
        self.symbols[symbol.name] = symbol
        return symbol

    def lookup(self, name: str, current_scope_only: bool = False) -> Optional[Symbol]:
        """
        Busca un símbolo por nombre.
        Si current_scope_only es False, asciende recursivamente por la cadena de padres.
        """
        if name in self.symbols:
            return self.symbols[name]
        if not current_scope_only and self.parent is not None:
            return self.parent.lookup(name, current_scope_only=False)
        return None

    def record_reference(self, name: str, line: int, column: int) -> Optional[Symbol]:
        """Localiza un símbolo y registra la coordenada exacta de su uso."""
        sym = self.lookup(name, current_scope_only=False)
        if sym:
            sym.add_reference(line, column)
        return sym

    def all_symbols_flat(self) -> List[Symbol]:
        """Retorna todos los símbolos definidos en este ámbito y sus descendientes."""
        result = list(self.symbols.values())
        for child in self.children:
            result.extend(child.all_symbols_flat())
        return result

    def pretty_format(self, indent: str = "") -> str:
        """Genera un reporte visual jerárquico de la tabla de símbolos."""
        header = f"{indent}┌── Ámbito: '{self.scope_name}' (Nivel {self.scope_level})\n"
        body = ""
        if not self.symbols:
            body += f"{indent}│   (sin símbolos locales)\n"
        else:
            for sym in self.symbols.values():
                meta_info = ""
                if sym.type == "tabla":
                    cols = sym.metadata.get("columns", {})
                    cols_summary = ", ".join(f"{k}: {v}" for k, v in list(cols.items())[:6])
                    if len(cols) > 6:
                        cols_summary += f", ... (+{len(cols)-6} cols)"
                    meta_info = f" -> CSV='{sym.metadata.get('csv_path')}', Esquema=[{cols_summary}]"
                elif sym.type == "fila":
                    meta_info = f" -> Fila de tabla '{sym.metadata.get('table_name')}'"
                elif sym.type == "modelo":
                    meta_info = f" -> Dataset='{sym.metadata.get('dataset')}', Objetivo='{sym.metadata.get('target_col')}'"

                addr = f" [{sym.symbolic_address}]" if sym.symbolic_address else ""
                body += f"{indent}│   • {sym.name}{addr}: {sym.type} (L{sym.line}:C{sym.column}, Usos={len(sym.references)}){meta_info}\n"

        for child in self.children:
            body += child.pretty_format(indent + "│   ")
        return header + body


class ReferenceTable:
    """
    Tabla de Referencias y Direcciones Simbólicas.
    Diseñada como interfaz limpia y desacoplada para:
    - Integrante 2 (Código Intermedio): asignación unívoca de registros/offsets de memoria simbólica.
    - Integrante 3 (Optimización): análisis de variables muertas (Dead Code Elimination) y frecuencias de acceso.
    """

    def __init__(self):
        self.address_counter = 0
        # Mapeo: dirección_simbólica -> Symbol
        self.addresses: Dict[str, Symbol] = {}
        # Mapeo: (nombre_simbolo, nivel_alcance, nombre_alcance) -> dirección_simbólica
        self.symbol_to_address: Dict[Tuple[str, int, str], str] = {}

    def allocate_symbol(self, symbol: Symbol, custom_prefix: Optional[str] = None) -> str:
        """
        Asigna una dirección simbólica única e inmutable para un símbolo.
        Ejemplo: 'sym_global_edad_0', 'sym_si_1_x_4'.
        """
        key = (symbol.name, symbol.scope_level, symbol.scope_name)
        if key in self.symbol_to_address:
            return self.symbol_to_address[key]

        prefix = custom_prefix or f"sym_{symbol.scope_name}_{symbol.name}"
        clean_prefix = prefix.replace(" ", "_").replace("-", "_")
        address = f"{clean_prefix}_{self.address_counter}"
        self.address_counter += 1

        symbol.symbolic_address = address
        self.addresses[address] = symbol
        self.symbol_to_address[key] = address
        return address

    def get_address(self, symbol: Symbol) -> Optional[str]:
        """Recupera la dirección simbólica previamente asignada a un símbolo."""
        key = (symbol.name, symbol.scope_level, symbol.scope_name)
        return self.symbol_to_address.get(key)

    def get_symbol_by_address(self, address: str) -> Optional[Symbol]:
        """Resuelve el símbolo correspondiente a una dirección simbólica."""
        return self.addresses.get(address)

    def get_unused_symbols(self) -> List[Symbol]:
        """
        Filtro para el Módulo de Optimización (Integrante 3):
        Retorna las variables declaradas que nunca fueron leídas (candidatas a eliminación de código muerto).
        """
        return [sym for sym in self.addresses.values() if not sym.is_used and sym.type not in ("tabla", "modelo")]

    def get_symbol_usage_counts(self) -> Dict[str, int]:
        """
        Mapeo de direcciones simbólicas a número de accesos para asignación de registros (Integrante 2/3).
        """
        return {addr: len(sym.references) for addr, sym in self.addresses.items()}

    def pretty_format(self) -> str:
        """Genera un reporte tabular de todas las direcciones simbólicas y su estado."""
        lines = ["┌── Tabla de Referencias y Direcciones Simbólicas (Memoria Simbólica)"]
        lines.append(f"│ {'Dirección':<24} | {'Nombre':<15} | {'Tipo':<10} | {'Ámbito':<15} | {'Usos':<6}")
        lines.append(f"│ {'-'*24}-+-{'-'*15}-+-{'-'*10}-+-{'-'*15}-+-{'-'*6}")
        for addr, sym in self.addresses.items():
            lines.append(f"│ {addr:<24} | {sym.name:<15} | {sym.type:<10} | {sym.scope_name:<15} | {len(sym.references):<6}")
        return "\n".join(lines)
