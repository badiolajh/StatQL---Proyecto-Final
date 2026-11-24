"""
Analizador Sintáctico Descendente Recursivo para StatQL (parser.py)
Implementa estrictamente la gramática formal EBNF y construye el AST.
"""

from typing import List, Optional
from .lexer import Token, TokenType
from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode,
    CargaNode, DeclaracionNode, AsignacionNode, MostrarNode, EntrenarNode,
    SiNode, ParaCadaNode, MientrasNode,
    BinaryOpNode, UnaryOpNode, LiteralNode, VariableNode, PropertyAccessNode,
    ExpressionNode
)


class ParserError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(f"Error sintáctico en línea {token.line}, columna {token.column}: {message} (Token: {token.type.name} '{token.value}')")
        self.line = token.line
        self.column = token.column
        self.token = token


class Parser:
    """
    Parser descendente recursivo para el lenguaje StatQL.
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    @property
    def current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # Devuelve EOF si nos pasamos

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def _advance(self) -> Token:
        tok = self.current
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _match(self, token_type: TokenType, value: Optional[str] = None) -> bool:
        if self.current.type == token_type:
            if value is None or self.current.value == value:
                self._advance()
                return True
        return False

    def _expect(self, token_type: TokenType, value: Optional[str] = None) -> Token:
        tok = self.current
        if tok.type != token_type or (value is not None and tok.value != value):
            expected = f"{token_type.name}" + (f" '{value}'" if value else "")
            raise ParserError(f"Se esperaba {expected}, pero se encontró {tok.type.name} '{tok.value}'", tok)
        return self._advance()

    def _saltos(self) -> None:
        """Saltos = { NL | ';' } ;"""
        while self.current.type in (TokenType.NL, TokenType.PUNTO_COMA):
            self._advance()

    def _fin(self) -> None:
        """Fin = (NL | ';'), Saltos ;"""
        tok = self.current
        if tok.type in (TokenType.NL, TokenType.PUNTO_COMA):
            self._advance()
            self._saltos()
        elif tok.type == TokenType.EOF:
            # Fin de archivo tolerado al final de una sentencia
            return
        else:
            raise ParserError(f"Se esperaba fin de instrucción (salto de línea o ';'), pero se encontró '{tok.value}'", tok)

    def _peek_past_saltos(self) -> Token:
        """Busca el siguiente token no-salto sin avanzar el cursor principal."""
        idx = self.pos
        while idx < len(self.tokens) and self.tokens[idx].type in (TokenType.NL, TokenType.PUNTO_COMA):
            idx += 1
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def parse(self) -> ProgramNode:
        """Programa = Saltos, { Sentencia, Saltos } ;"""
        start_line = self.current.line
        start_col = self.current.column
        self._saltos()
        statements: List[ASTNode] = []

        while self.current.type != TokenType.EOF:
            stmt = self.parse_sentencia()
            statements.append(stmt)
            self._saltos()

        return ProgramNode(statements, line=start_line, column=start_col)

    def parse_sentencia(self) -> ASTNode:
        """Sentencia = Simple, Fin | Si | ParaCada | Mientras ;"""
        tok = self.current

        if tok.type == TokenType.SI:
            return self.parse_si()
        elif tok.type == TokenType.PARA:
            return self.parse_para_cada()
        elif tok.type == TokenType.MIENTRAS:
            return self.parse_mientras()
        else:
            simple_stmt = self.parse_simple()
            self._fin()
            return simple_stmt

    def parse_simple(self) -> ASTNode:
        """Simple = Carga | Declaracion | Asignacion | Mostrar | Entrenar ;"""
        tok = self.current

        if tok.type == TokenType.CARGAR:
            return self.parse_carga()
        elif tok.type in (TokenType.TIPO_ENTERO, TokenType.TIPO_DECIMAL,
                          TokenType.TIPO_TEXTO, TokenType.TIPO_BOOLEANO):
            return self.parse_declaracion()
        elif tok.type == TokenType.ID:
            return self.parse_asignacion()
        elif tok.type == TokenType.MOSTRAR:
            return self.parse_mostrar()
        elif tok.type == TokenType.ENTRENAR:
            return self.parse_entrenar()
        else:
            raise ParserError(f"Instrucción no válida iniciando con token '{tok.value}'", tok)

    def parse_carga(self) -> CargaNode:
        """Carga = 'cargar', CADENA, 'como', ID ;"""
        tok_cargar = self._expect(TokenType.CARGAR)
        tok_cadena = self._expect(TokenType.CADENA)
        self._expect(TokenType.COMO)
        tok_id = self._expect(TokenType.ID)
        return CargaNode(tok_cadena.value, tok_id.value, line=tok_cargar.line, column=tok_cargar.column)

    def parse_declaracion(self) -> DeclaracionNode:
        """Declaracion = Tipo, ID, '=', Expresion ;"""
        tok_tipo = self._advance()  # entero | decimal | texto | booleano
        tok_id = self._expect(TokenType.ID)
        self._expect(TokenType.ASIGNA)
        expr = self.parse_expresion()
        return DeclaracionNode(tok_tipo.value, tok_id.value, expr, line=tok_tipo.line, column=tok_tipo.column)

    def parse_asignacion(self) -> AsignacionNode:
        """Asignacion = ID, '=', Expresion ;"""
        tok_id = self._expect(TokenType.ID)
        self._expect(TokenType.ASIGNA)
        expr = self.parse_expresion()
        return AsignacionNode(tok_id.value, expr, line=tok_id.line, column=tok_id.column)

    def parse_mostrar(self) -> MostrarNode:
        """Mostrar = 'mostrar', Expresion ;"""
        tok_mostrar = self._expect(TokenType.MOSTRAR)
        expr = self.parse_expresion()
        return MostrarNode(expr, line=tok_mostrar.line, column=tok_mostrar.column)

    def parse_entrenar(self) -> EntrenarNode:
        """Entrenar = 'entrenar', 'arbol', 'con', ID, 'objetivo', CADENA, 'como', ID ;"""
        tok_entrenar = self._expect(TokenType.ENTRENAR)
        self._expect(TokenType.ARBOL)
        self._expect(TokenType.CON)
        tok_dataset = self._expect(TokenType.ID)
        self._expect(TokenType.OBJETIVO)
        tok_col = self._expect(TokenType.CADENA)
        self._expect(TokenType.COMO)
        tok_model = self._expect(TokenType.ID)
        return EntrenarNode(tok_dataset.value, tok_col.value, tok_model.value,
                            line=tok_entrenar.line, column=tok_entrenar.column)

    def parse_bloque(self) -> BlockNode:
        """Bloque = '{', Saltos, { Sentencia, Saltos }, '}' ;"""
        tok_abre = self._expect(TokenType.LLAVE_ABRE)
        self._saltos()
        statements: List[ASTNode] = []

        while self.current.type not in (TokenType.LLAVE_CIERRA, TokenType.EOF):
            stmt = self.parse_sentencia()
            statements.append(stmt)
            self._saltos()

        self._expect(TokenType.LLAVE_CIERRA)
        return BlockNode(statements, line=tok_abre.line, column=tok_abre.column)

    def parse_si(self) -> SiNode:
        """Si = 'si', '(', Expresion, ')', Bloque, [ Saltos, 'sino', Bloque ] ;"""
        tok_si = self._expect(TokenType.SI)
        self._expect(TokenType.PAREN_ABRE)
        cond = self.parse_expresion()
        self._expect(TokenType.PAREN_CIERRA)
        then_block = self.parse_bloque()

        else_block: Optional[BlockNode] = None
        # Verificar si después de posibles saltos viene 'sino'
        next_tok = self._peek_past_saltos()
        if next_tok.type == TokenType.SINO:
            self._saltos()
            self._expect(TokenType.SINO)
            else_block = self.parse_bloque()

        return SiNode(cond, then_block, else_block, line=tok_si.line, column=tok_si.column)

    def parse_para_cada(self) -> ParaCadaNode:
        """ParaCada = 'para', 'cada', ID, 'en', ID, Bloque ;"""
        tok_para = self._expect(TokenType.PARA)
        self._expect(TokenType.CADA)
        tok_item = self._expect(TokenType.ID)
        self._expect(TokenType.EN)
        tok_dataset = self._expect(TokenType.ID)
        block = self.parse_bloque()
        return ParaCadaNode(tok_item.value, tok_dataset.value, block,
                            line=tok_para.line, column=tok_para.column)

    def parse_mientras(self) -> MientrasNode:
        """Mientras = 'mientras', '(', Expresion, ')', Bloque ;"""
        tok_mientras = self._expect(TokenType.MIENTRAS)
        self._expect(TokenType.PAREN_ABRE)
        cond = self.parse_expresion()
        self._expect(TokenType.PAREN_CIERRA)
        block = self.parse_bloque()
        return MientrasNode(cond, block, line=tok_mientras.line, column=tok_mientras.column)

    # --- Expresiones ---

    def parse_expresion(self) -> ExpressionNode:
        """Expresion = Disyuncion ;"""
        return self.parse_disyuncion()

    def parse_disyuncion(self) -> ExpressionNode:
        """Disyuncion = Conjuncion, { 'o', Conjuncion } ;"""
        left = self.parse_conjuncion()
        while self.current.type == TokenType.O:
            op_tok = self._advance()
            right = self.parse_conjuncion()
            left = BinaryOpNode(left, "o", right, line=op_tok.line, column=op_tok.column)
        return left

    def parse_conjuncion(self) -> ExpressionNode:
        """Conjuncion = Negacion, { 'y', Negacion } ;"""
        left = self.parse_negacion()
        while self.current.type == TokenType.Y:
            op_tok = self._advance()
            right = self.parse_negacion()
            left = BinaryOpNode(left, "y", right, line=op_tok.line, column=op_tok.column)
        return left

    def parse_negacion(self) -> ExpressionNode:
        """Negacion = 'no', Negacion | Comparacion ;"""
        if self.current.type == TokenType.NO:
            op_tok = self._advance()
            operand = self.parse_negacion()
            return UnaryOpNode("no", operand, line=op_tok.line, column=op_tok.column)
        return self.parse_comparacion()

    def parse_comparacion(self) -> ExpressionNode:
        """Comparacion = Suma, [ OpRel, Suma ] ;"""
        left = self.parse_suma()
        if self.current.type == TokenType.OP_REL:
            op_tok = self._advance()
            right = self.parse_suma()
            return BinaryOpNode(left, op_tok.value, right, line=op_tok.line, column=op_tok.column)
        return left

    def parse_suma(self) -> ExpressionNode:
        """Suma = Producto, { ('+' | '-'), Producto } ;"""
        left = self.parse_producto()
        while self.current.type == TokenType.OP_ARIT and self.current.value in ('+', '-'):
            op_tok = self._advance()
            right = self.parse_producto()
            left = BinaryOpNode(left, op_tok.value, right, line=op_tok.line, column=op_tok.column)
        return left

    def parse_producto(self) -> ExpressionNode:
        """Producto = Unario, { ('*' | '/'), Unario } ;"""
        left = self.parse_unario()
        while self.current.type == TokenType.OP_ARIT and self.current.value in ('*', '/'):
            op_tok = self._advance()
            right = self.parse_unario()
            left = BinaryOpNode(left, op_tok.value, right, line=op_tok.line, column=op_tok.column)
        return left

    def parse_unario(self) -> ExpressionNode:
        """Unario = ('+' | '-'), Unario | Primario ;"""
        if self.current.type == TokenType.OP_ARIT and self.current.value in ('+', '-'):
            op_tok = self._advance()
            operand = self.parse_unario()
            return UnaryOpNode(op_tok.value, operand, line=op_tok.line, column=op_tok.column)
        return self.parse_primario()

    def parse_primario(self) -> ExpressionNode:
        """
        Primario = ENTERO | DECIMAL | CADENA | 'verdadero' | 'falso'
                 | ID, [ '.', ID ] | '(', Expresion, ')' ;
        """
        tok = self.current

        if tok.type == TokenType.ENTERO:
            self._advance()
            return LiteralNode(tok.value, "entero", line=tok.line, column=tok.column)

        elif tok.type == TokenType.DECIMAL:
            self._advance()
            return LiteralNode(tok.value, "decimal", line=tok.line, column=tok.column)

        elif tok.type == TokenType.CADENA:
            self._advance()
            return LiteralNode(tok.value, "texto", line=tok.line, column=tok.column)

        elif tok.type == TokenType.VERDADERO:
            self._advance()
            return LiteralNode(True, "booleano", line=tok.line, column=tok.column)

        elif tok.type == TokenType.FALSO:
            self._advance()
            return LiteralNode(False, "booleano", line=tok.line, column=tok.column)

        elif tok.type == TokenType.ID:
            id_tok = self._advance()
            # Chequear si viene '.' ID
            if self.current.type == TokenType.PUNTO:
                self._advance()
                prop_tok = self._expect(TokenType.ID)
                return PropertyAccessNode(id_tok.value, prop_tok.value, line=id_tok.line, column=id_tok.column)
            return VariableNode(id_tok.value, line=id_tok.line, column=id_tok.column)

        elif tok.type == TokenType.PAREN_ABRE:
            self._advance()
            expr = self.parse_expresion()
            self._expect(TokenType.PAREN_CIERRA)
            return expr

        else:
            raise ParserError(f"Expresión primaria inesperada: {tok.type.name} '{tok.value}'", tok)
