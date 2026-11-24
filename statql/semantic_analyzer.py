"""
statql/semantic_analyzer.py
Analizador Semántico para el lenguaje StatQL (Módulo 1).
Implementa:
- Verificación estática de tipos
- Casting y coerción implícita controlada (I2D)
- Validación de esquemas CSV e inspección de variables
- Control estricto de ámbitos léxicos (scoping)
- Registro estructurado de errores y trazas
- Interfaces limpias y desacopladas para Código Intermedio (Integrante 2) y Optimización (Integrante 3)
"""

import os
from typing import Dict, Optional, List, Any, Tuple
from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode,
    CargaNode, DeclaracionNode, AsignacionNode, MostrarNode, EntrenarNode,
    SiNode, ParaCadaNode, MientrasNode,
    BinaryOpNode, UnaryOpNode, LiteralNode, VariableNode, PropertyAccessNode,
    ExpressionNode, I2DNode
)
from .symbol_table import Symbol, SymbolTable, ReferenceTable
from .semantic_stack import SemanticStack
from .csv_loader import CSVLoader, CSVSchema, CSVLoadError


class SemanticErrorCode:
    """Códigos de error semántico estandarizados para StatQL."""
    ERR_UNDECLARED_VAR = "SEM_001_UNDECLARED_VAR"
    ERR_DUPLICATE_DECL = "SEM_002_DUPLICATE_DECL"
    ERR_INCOMPATIBLE_TYPES = "SEM_003_INCOMPATIBLE_TYPES"
    ERR_INVALID_CAST = "SEM_004_INVALID_CAST"
    ERR_CSV_COLUMN_NOT_FOUND = "SEM_005_CSV_COLUMN_NOT_FOUND"
    ERR_NON_BOOLEAN_CONDITION = "SEM_006_NON_BOOLEAN_CONDITION"
    ERR_IMMUTABLE_OBJECT = "SEM_007_IMMUTABLE_OBJECT"
    ERR_CSV_FILE_NOT_FOUND = "SEM_008_CSV_FILE_NOT_FOUND"


class SemanticError(Exception):
    """
    Excepción formal emitida ante cualquier violación de reglas semánticas en StatQL.
    Almacena código de error, mensaje explícito, línea y columna.
    """
    def __init__(self, message: str, line: int = 1, column: int = 1,
                 code: str = SemanticErrorCode.ERR_INCOMPATIBLE_TYPES):
        formatted = f"Error semántico [{code}] en línea {line}, columna {column}: {message}"
        super().__init__(formatted)
        self.message = formatted
        self.raw_message = message
        self.line = line
        self.column = column
        self.code = code

    def __repr__(self) -> str:
        return f"<SemanticError {self.code} at L{self.line}:C{self.column} - {self.raw_message}>"


class SemanticAnalyzer:
    """
    Analizador Semántico de StatQL.
    Recorre el AST generado por el parser, valida declaraciones, tipos, ámbitos y esquemas CSV,
    y anota el AST con tipos inferidos y nodos de promoción I2D explícitos.
    """

    def __init__(self, base_dir: Optional[str] = None, fail_fast: bool = True):
        self.base_dir = base_dir or os.getcwd()
        self.fail_fast = fail_fast
        self.errors: List[SemanticError] = []

        # Componentes desacoplados del sistema semántico
        self.csv_loader = CSVLoader(base_dir=self.base_dir)
        self.global_table = SymbolTable(scope_name="global", scope_level=0)
        self.current_table = self.global_table
        self.reference_table = ReferenceTable()
        self.semantic_stack = SemanticStack()

        # Almacena el AST analizado para entrega a módulos posteriores
        self.analyzed_ast: Optional[ProgramNode] = None

    def register_mock_schema(self, csv_path: str, schema: Dict[str, str], row_count: int = 100) -> CSVSchema:
        """Registra un esquema CSV en memoria para pruebas sin depender de archivos en disco."""
        return self.csv_loader.register_mock_schema(csv_path, schema, row_count=row_count)

    def analyze(self, program: ProgramNode) -> SymbolTable:
        """
        Punto de entrada principal para el análisis semántico de un programa StatQL.
        Retorna la tabla de símbolos raíz completamente poblada.
        """
        self.errors.clear()
        self.semantic_stack.clear()
        self.analyzed_ast = program
        self.visit(program)

        if self.errors and self.fail_fast:
            raise self.errors[0]

        return self.global_table

    def report_error(self, message: str, line: int, column: int, code: str) -> None:
        """Registra un error semántico y lo lanza si el modo fail_fast está activo."""
        err = SemanticError(message, line, column, code)
        self.errors.append(err)
        if self.fail_fast:
            raise err

    def visit(self, node: ASTNode) -> Any:
        """Despachador del patrón Visitor según la clase del nodo AST."""
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ASTNode) -> Any:
        raise NotImplementedError(f"No existe un método de análisis semántico para el nodo {node.__class__.__name__}.")

    # --- Contrato de Interfaces para Integrantes 2 y 3 ---

    def get_intermediate_code_context(self) -> Dict[str, Any]:
        """
        Interfaz para el Integrante 2 (Generador de Código Intermedio / Cuádruplas):
        Provee el AST tipado, la tabla de símbolos y la tabla de direcciones simbólicas.
        """
        return {
            "ast": self.analyzed_ast,
            "global_table": self.global_table,
            "reference_table": self.reference_table,
            "csv_loader": self.csv_loader,
            "errors": list(self.errors)
        }

    def get_optimization_context(self) -> Dict[str, Any]:
        """
        Interfaz para el Integrante 3 (Optimizador):
        Provee variables no utilizadas (DCE), conteos de referencias y el AST decorado.
        """
        return {
            "ast": self.analyzed_ast,
            "unused_symbols": self.reference_table.get_unused_symbols(),
            "symbol_usage_counts": self.reference_table.get_symbol_usage_counts(),
            "global_table": self.global_table,
            "reference_table": self.reference_table
        }

    # --- Visitadores de Sentencias ---

    def visit_ProgramNode(self, node: ProgramNode) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    def visit_BlockNode(self, node: BlockNode) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    def visit_CargaNode(self, node: CargaNode) -> None:
        # 1. Validar que el alias no haya sido declarado previamente en el mismo ámbito
        if self.current_table.lookup(node.alias, current_scope_only=True):
            self.report_error(
                f"El identificador de tabla '{node.alias}' ya fue declarado en este ámbito.",
                node.line, node.column, SemanticErrorCode.ERR_DUPLICATE_DECL
            )
            return

        # 2. Cargar e inspeccionar el esquema del archivo CSV
        try:
            schema = self.csv_loader.load_schema(node.path, line=node.line, column=node.column)
        except CSVLoadError as err:
            self.report_error(err.raw_message, err.line, err.column, SemanticErrorCode.ERR_CSV_FILE_NOT_FOUND)
            return

        # 3. Registrar el símbolo de tabla
        sym = Symbol(
            name=node.alias,
            type_name="tabla",
            scope_level=self.current_table.scope_level,
            scope_name=self.current_table.scope_name,
            line=node.line,
            column=node.column,
            csv_path=node.path,
            schema=schema,
            columns=schema.to_dict()
        )
        self.current_table.define(sym)
        self.reference_table.allocate_symbol(sym, custom_prefix=f"ds_{node.alias}")

    def visit_DeclaracionNode(self, node: DeclaracionNode) -> None:
        # 1. Validar duplicidad en el ámbito actual
        if self.current_table.lookup(node.name, current_scope_only=True):
            self.report_error(
                f"La variable '{node.name}' ya fue declarada previamente en el ámbito actual ('{self.current_table.scope_name}').",
                node.line, node.column, SemanticErrorCode.ERR_DUPLICATE_DECL
            )
            return

        # 2. Analizar el tipo de la expresión asignada
        expr_type = self.visit(node.expr)
        if expr_type is None:
            return

        # 3. Reglas de coherencia de tipos y coerción I2D
        if node.tipo == expr_type:
            pass  # Tipos coincidentes exactos
        elif node.tipo == "decimal" and expr_type == "entero":
            # Coerción válida: promoción explícita entero -> decimal (I2D)
            promoted = I2DNode(node.expr, line=node.expr.line, column=node.expr.column)
            promoted.inferred_type = "decimal"
            node.expr = promoted
        elif node.tipo == "entero" and expr_type == "decimal":
            # Democión no permitida de decimal a entero
            self.report_error(
                f"Incompatibilidad de tipos en declaración de '{node.name}': "
                f"se declaró de tipo '{node.tipo}', pero la expresión produce un '{expr_type}'. "
                f"No se permite la democión implícita de decimal a entero.",
                node.line, node.column, SemanticErrorCode.ERR_INVALID_CAST
            )
            return
        else:
            self.report_error(
                f"Incompatibilidad de tipos en declaración de '{node.name}': "
                f"se esperaba '{node.tipo}', pero se obtuvo '{expr_type}'.",
                node.line, node.column, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES
            )
            return

        # 4. Registrar la nueva variable
        sym = Symbol(
            name=node.name,
            type_name=node.tipo,
            scope_level=self.current_table.scope_level,
            scope_name=self.current_table.scope_name,
            line=node.line,
            column=node.column
        )
        self.current_table.define(sym)
        self.reference_table.allocate_symbol(sym)

    def visit_AsignacionNode(self, node: AsignacionNode) -> None:
        # 1. Verificar existencia del identificador en la jerarquía de ámbitos
        sym = self.current_table.lookup(node.name)
        if not sym:
            self.report_error(
                f"Variable no declarada '{node.name}'. Debe declararse antes de ser asignada.",
                node.line, node.column, SemanticErrorCode.ERR_UNDECLARED_VAR
            )
            return

        # 2. Prohibir reasignación de estructuras protegidas (tabla, fila, modelo)
        if sym.type in ("tabla", "fila", "modelo"):
            self.report_error(
                f"No se permite reasignar directamente el identificador protegido '{node.name}' de tipo '{sym.type}'.",
                node.line, node.column, SemanticErrorCode.ERR_IMMUTABLE_OBJECT
            )
            return

        # 3. Analizar expresión
        expr_type = self.visit(node.expr)
        if expr_type is None:
            return

        # 4. Reglas de compatibilidad y casting
        if sym.type == expr_type:
            pass
        elif sym.type == "decimal" and expr_type == "entero":
            # Promoción explícita I2D en asignación
            promoted = I2DNode(node.expr, line=node.expr.line, column=node.expr.column)
            promoted.inferred_type = "decimal"
            node.expr = promoted
        elif sym.type == "entero" and expr_type == "decimal":
            self.report_error(
                f"Incompatibilidad de tipos en asignación a '{node.name}': "
                f"la variable destino es de tipo 'entero', pero la expresión evaluada es 'decimal'.",
                node.line, node.column, SemanticErrorCode.ERR_INVALID_CAST
            )
            return
        else:
            self.report_error(
                f"Incompatibilidad de tipos en asignación a '{node.name}': "
                f"la variable es de tipo '{sym.type}', pero se intentó asignar un valor de tipo '{expr_type}'.",
                node.line, node.column, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES
            )
            return

        # 5. Registrar referencia de modificación
        sym.add_reference(node.line, node.column)

    def visit_MostrarNode(self, node: MostrarNode) -> None:
        self.visit(node.expr)

    def visit_EntrenarNode(self, node: EntrenarNode) -> None:
        # 1. Verificar existencia de la tabla
        table_sym = self.current_table.lookup(node.dataset)
        if not table_sym:
            self.report_error(
                f"La tabla de datos '{node.dataset}' no ha sido declarada.",
                node.line, node.column, SemanticErrorCode.ERR_UNDECLARED_VAR
            )
            return

        if table_sym.type != "tabla":
            self.report_error(
                f"El identificador '{node.dataset}' debe ser de tipo 'tabla', pero es '{table_sym.type}'.",
                node.line, node.column, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES
            )
            return

        # 2. Verificar que la columna objetivo exista en el esquema
        cols = table_sym.metadata.get("columns", {})
        if node.target_col not in cols:
            avail = list(cols.keys())
            self.report_error(
                f"La columna objetivo '{node.target_col}' no existe en la tabla '{node.dataset}'. "
                f"Columnas disponibles en el dataset: {avail}",
                node.line, node.column, SemanticErrorCode.ERR_CSV_COLUMN_NOT_FOUND
            )
            return

        # 3. Validar identificador del modelo resultante
        if self.current_table.lookup(node.model_alias, current_scope_only=True):
            self.report_error(
                f"El nombre del modelo '{node.model_alias}' ya fue declarado en este ámbito.",
                node.line, node.column, SemanticErrorCode.ERR_DUPLICATE_DECL
            )
            return

        # 4. Registrar símbolo de modelo
        features = [col for col in cols.keys() if col != node.target_col]
        model_sym = Symbol(
            name=node.model_alias,
            type_name="modelo",
            scope_level=self.current_table.scope_level,
            scope_name=self.current_table.scope_name,
            line=node.line,
            column=node.column,
            dataset=node.dataset,
            target_col=node.target_col,
            features=features
        )
        self.current_table.define(model_sym)
        self.reference_table.allocate_symbol(model_sym, custom_prefix=f"model_{node.model_alias}")

    # --- Control de Flujo y Ámbitos Léxicos ---

    def visit_SiNode(self, node: SiNode) -> None:
        # 1. Validar condición booleana
        cond_type = self.visit(node.condition)
        if cond_type != "booleano":
            self.report_error(
                f"La condición de la estructura 'si' debe ser de tipo 'booleano', pero se obtuvo '{cond_type}'.",
                node.condition.line, node.condition.column, SemanticErrorCode.ERR_NON_BOOLEAN_CONDITION
            )

        # 2. Ámbito léxico para el bloque 'entonces'
        then_scope = self.current_table.create_child("si_entonces")
        prev_table = self.current_table
        self.current_table = then_scope
        self.visit(node.then_block)
        self.current_table = prev_table

        # 3. Ámbito léxico independiente para el bloque 'sino' (si existe)
        if node.else_block:
            else_scope = self.current_table.create_child("si_sino")
            self.current_table = else_scope
            self.visit(node.else_block)
            self.current_table = prev_table

    def visit_ParaCadaNode(self, node: ParaCadaNode) -> None:
        # 1. Validar dataset
        dataset_sym = self.current_table.lookup(node.dataset_var)
        if not dataset_sym:
            self.report_error(
                f"La colección tabular '{node.dataset_var}' no está declarada.",
                node.line, node.column, SemanticErrorCode.ERR_UNDECLARED_VAR
            )
            return

        if dataset_sym.type != "tabla":
            self.report_error(
                f"La colección en 'para cada' debe ser de tipo 'tabla', pero '{node.dataset_var}' es de tipo '{dataset_sym.type}'.",
                node.line, node.column, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES
            )
            return

        # 2. Registrar variable iteradora local al bloque
        loop_scope = self.current_table.create_child(f"para_cada_{node.item_var}")
        prev_table = self.current_table
        self.current_table = loop_scope

        row_sym = Symbol(
            name=node.item_var,
            type_name="fila",
            scope_level=self.current_table.scope_level,
            scope_name=self.current_table.scope_name,
            line=node.line,
            column=node.column,
            table_name=node.dataset_var,
            table_symbol=dataset_sym
        )
        self.current_table.define(row_sym)
        self.reference_table.allocate_symbol(row_sym, custom_prefix=f"iter_{node.item_var}")

        # 3. Visitar cuerpo del bucle
        self.visit(node.block)
        self.current_table = prev_table

    def visit_MientrasNode(self, node: MientrasNode) -> None:
        # 1. Validar condición booleana
        cond_type = self.visit(node.condition)
        if cond_type != "booleano":
            self.report_error(
                f"La condición del bucle 'mientras' debe ser de tipo 'booleano', pero se obtuvo '{cond_type}'.",
                node.condition.line, node.condition.column, SemanticErrorCode.ERR_NON_BOOLEAN_CONDITION
            )

        # 2. Ámbito local del bucle
        loop_scope = self.current_table.create_child("mientras")
        prev_table = self.current_table
        self.current_table = loop_scope
        self.visit(node.block)
        self.current_table = prev_table

    # --- Visitadores de Expresiones ---

    def visit_BinaryOpNode(self, node: BinaryOpNode) -> Optional[str]:
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)

        if left_type is None or right_type is None:
            return None

        try:
            res_type, coercion = self.semantic_stack.evaluate_binary_type(
                node.op, left_type, right_type, node.line, node.column
            )
        except TypeError as err:
            self.report_error(str(err), node.line, node.column, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)
            return None

        # Coerción explícita en el AST mediante nodos I2D
        if coercion == "I2D_LEFT":
            promoted = I2DNode(node.left, line=node.left.line, column=node.left.column)
            promoted.inferred_type = "decimal"
            node.left = promoted
        elif coercion == "I2D_RIGHT":
            promoted = I2DNode(node.right, line=node.right.line, column=node.right.column)
            promoted.inferred_type = "decimal"
            node.right = promoted

        node.inferred_type = res_type
        return res_type

    def visit_UnaryOpNode(self, node: UnaryOpNode) -> Optional[str]:
        operand_type = self.visit(node.operand)
        if operand_type is None:
            return None

        try:
            res_type = self.semantic_stack.evaluate_unary_type(
                node.op, operand_type, node.line, node.column
            )
        except TypeError as err:
            self.report_error(str(err), node.line, node.column, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES)
            return None

        node.inferred_type = res_type
        return res_type

    def visit_LiteralNode(self, node: LiteralNode) -> str:
        return node.inferred_type

    def visit_VariableNode(self, node: VariableNode) -> Optional[str]:
        # Búsqueda léxica en la tabla de símbolos
        sym = self.current_table.lookup(node.name)
        if not sym:
            self.report_error(
                f"Variable no declarada '{node.name}'. Debe declararse antes de usarse.",
                node.line, node.column, SemanticErrorCode.ERR_UNDECLARED_VAR
            )
            return None

        # Registrar referencia para análisis de código muerto y asignación de registros
        sym.add_reference(node.line, node.column)
        node.inferred_type = sym.type
        node.address = sym.symbolic_address
        return sym.type

    def visit_PropertyAccessNode(self, node: PropertyAccessNode) -> Optional[str]:
        # 1. Localizar objeto base (debe ser 'fila' o 'tabla')
        sym = self.current_table.lookup(node.obj_name)
        if not sym:
            self.report_error(
                f"Identificador o colección no declarada '{node.obj_name}'.",
                node.line, node.column, SemanticErrorCode.ERR_UNDECLARED_VAR
            )
            return None

        # 2. Resolver tabla asociada
        target_table_sym: Optional[Symbol] = None
        if sym.type == "fila":
            target_table_sym = sym.metadata.get("table_symbol")
        elif sym.type == "tabla":
            target_table_sym = sym
        else:
            self.report_error(
                f"No se puede acceder a columnas o propiedades en un identificador de tipo '{sym.type}' ('{node.obj_name}').",
                node.line, node.column, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES
            )
            return None

        if not target_table_sym:
            self.report_error(
                f"No se pudo determinar el esquema tabular para el identificador '{node.obj_name}'.",
                node.line, node.column, SemanticErrorCode.ERR_INCOMPATIBLE_TYPES
            )
            return None

        # 3. Validar existencia de la columna en el esquema CSV
        columns = target_table_sym.metadata.get("columns", {})
        if node.property_name not in columns:
            avail = list(columns.keys())
            self.report_error(
                f"La columna '{node.property_name}' no existe en la tabla '{target_table_sym.name}'. "
                f"Columnas disponibles: {avail}",
                node.line, node.column, SemanticErrorCode.ERR_CSV_COLUMN_NOT_FOUND
            )
            return None

        # 4. Asignar tipo estático de la columna
        col_type = columns[node.property_name]
        sym.add_reference(node.line, node.column)
        node.inferred_type = col_type
        return col_type

    def visit_I2DNode(self, node: I2DNode) -> str:
        self.visit(node.expr)
        node.inferred_type = "decimal"
        return "decimal"
