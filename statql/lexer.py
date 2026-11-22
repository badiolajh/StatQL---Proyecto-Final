"""
Analizador Léxico para StatQL (lexer.py)
Soporte UTF-8 completo, manejo de comentarios, saltos de línea e inyección automática de NL final.
"""

from enum import Enum, auto
from typing import List, Optional, Any


class TokenType(Enum):
    # Palabras reservadas
    CARGAR = "cargar"
    COMO = "como"
    TIPO_ENTERO = "entero"
    TIPO_DECIMAL = "decimal"
    TIPO_TEXTO = "texto"
    TIPO_BOOLEANO = "booleano"
    SI = "si"
    SINO = "sino"
    PARA = "para"
    CADA = "cada"
    EN = "en"
    MIENTRAS = "mientras"
    Y = "y"
    O = "o"
    NO = "no"
    VERDADERO = "verdadero"
    FALSO = "falso"
    MOSTRAR = "mostrar"
    ENTRENAR = "entrenar"
    ARBOL = "arbol"
    CON = "con"
    OBJETIVO = "objetivo"

    # Literales
    ENTERO = "ENTERO"
    DECIMAL = "DECIMAL"
    CADENA = "CADENA"

    # Identificadores
    ID = "ID"

    # Operadores
    OP_REL = "OP_REL"        # ==, !=, >=, <=, >, <
    ASIGNA = "ASIGNA"        # =
    OP_ARIT = "OP_ARIT"      # +, -, *, /

    # Delimitadores
    PAREN_ABRE = "PAREN_ABRE"     # (
    PAREN_CIERRA = "PAREN_CIERRA" # )
    LLAVE_ABRE = "LLAVE_ABRE"     # {
    LLAVE_CIERRA = "LLAVE_CIERRA" # }
    PUNTO = "PUNTO"               # .
    PUNTO_COMA = "PUNTO_COMA"     # ;
    NL = "NL"                     # \n, \r\n, \r

    # Fin de archivo
    EOF = "EOF"


RESERVED_WORDS = {
    "cargar": TokenType.CARGAR,
    "como": TokenType.COMO,
    "entero": TokenType.TIPO_ENTERO,
    "decimal": TokenType.TIPO_DECIMAL,
    "texto": TokenType.TIPO_TEXTO,
    "booleano": TokenType.TIPO_BOOLEANO,
    "si": TokenType.SI,
    "sino": TokenType.SINO,
    "para": TokenType.PARA,
    "cada": TokenType.CADA,
    "en": TokenType.EN,
    "mientras": TokenType.MIENTRAS,
    "y": TokenType.Y,
    "o": TokenType.O,
    "no": TokenType.NO,
    "verdadero": TokenType.VERDADERO,
    "falso": TokenType.FALSO,
    "mostrar": TokenType.MOSTRAR,
    "entrenar": TokenType.ENTRENAR,
    "arbol": TokenType.ARBOL,
    "con": TokenType.CON,
    "objetivo": TokenType.OBJETIVO,
}


class Token:
    def __init__(self, type: TokenType, value: Any, line: int, column: int):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.column})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Token):
            return False
        return (self.type == other.type and
                self.value == other.value and
                self.line == other.line and
                self.column == other.column)


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"Error léxico en línea {line}, columna {column}: {message}")
        self.line = line
        self.column = column
        self.raw_message = message


class Lexer:
    """
    Analizador léxico para el lenguaje StatQL.
    Convierte código fuente UTF-8 en un flujo de Tokens.
    """

    def __init__(self, source_code: str):
        self.source = source_code
        self.length = len(source_code)
        self.pos = 0
        self.line = 1
        self.column = 1

    def _peek(self, offset: int = 0) -> Optional[str]:
        idx = self.pos + offset
        if idx < self.length:
            return self.source[idx]
        return None

    def _advance(self) -> Optional[str]:
        if self.pos < self.length:
            char = self.source[self.pos]
            self.pos += 1
            if char == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            return char
        return None

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []

        while self.pos < self.length:
            char = self.source[self.pos]
            start_line = self.line
            start_col = self.column

            # 1. COMENTARIO_LINEA: //[^\r\n]*
            if char == '/' and self._peek(1) == '/':
                self.pos += 2
                self.column += 2
                while self.pos < self.length and self.source[self.pos] not in ('\r', '\n'):
                    self.pos += 1
                    self.column += 1
                continue

            # 2. COMENTARIO_BLOQUE: /* ... */
            if char == '/' and self._peek(1) == '*':
                self.pos += 2
                self.column += 2
                block_closed = False
                while self.pos < self.length:
                    if self.source[self.pos] == '*' and self._peek(1) == '/':
                        self.pos += 2
                        self.column += 2
                        block_closed = True
                        break
                    elif self.source[self.pos] == '\r':
                        if self._peek(1) == '\n':
                            self.pos += 2
                        else:
                            self.pos += 1
                        tokens.append(Token(TokenType.NL, "\n", self.line, self.column))
                        self.line += 1
                        self.column = 1
                    elif self.source[self.pos] == '\n':
                        self.pos += 1
                        tokens.append(Token(TokenType.NL, "\n", self.line, self.column))
                        self.line += 1
                        self.column = 1
                    else:
                        self.pos += 1
                        self.column += 1

                if not block_closed:
                    raise LexerError("Comentario de bloque no cerrado", start_line, start_col)
                continue

            # 3. BLANCOS: [ \t]+
            if char in (' ', '\t'):
                self.pos += 1
                self.column += 1
                continue

            # 4. NL: \r\n | \n | \r
            if char in ('\r', '\n'):
                if char == '\r' and self._peek(1) == '\n':
                    self.pos += 2
                else:
                    self.pos += 1
                tokens.append(Token(TokenType.NL, "\n", start_line, start_col))
                self.line += 1
                self.column = 1
                continue

            # 5 & 6. NÚMEROS: DECIMAL o ENTERO
            if char.isdigit():
                num_str = ""
                has_dot = False
                while self.pos < self.length:
                    c = self.source[self.pos]
                    if c.isdigit():
                        num_str += c
                        self.pos += 1
                        self.column += 1
                    elif c == '.' and not has_dot:
                        # Verificar si tras el punto hay un dígito (para ser DECIMAL)
                        next_char = self._peek(1)
                        if next_char is not None and next_char.isdigit():
                            has_dot = True
                            num_str += c
                            self.pos += 1
                            self.column += 1
                        else:
                            # Es un punto operador o acceso a miembro
                            break
                    else:
                        break

                if has_dot:
                    tokens.append(Token(TokenType.DECIMAL, float(num_str), start_line, start_col))
                else:
                    tokens.append(Token(TokenType.ENTERO, int(num_str), start_line, start_col))
                continue

            # 7. CADENA: "(?:[^"\\\r\n]|\\["\\nt])*"
            if char == '"':
                self.pos += 1
                self.column += 1
                string_val = []
                closed = False

                while self.pos < self.length:
                    c = self.source[self.pos]
                    if c in ('\r', '\n'):
                        raise LexerError("Salto de línea no permitido dentro de una cadena literal", self.line, self.column)
                    elif c == '"':
                        self.pos += 1
                        self.column += 1
                        closed = True
                        break
                    elif c == '\\':
                        # Secuencia de escape
                        esc_col = self.column
                        self.pos += 1
                        self.column += 1
                        if self.pos >= self.length:
                            raise LexerError("Secuencia de escape incompleta al final del archivo", self.line, esc_col)
                        esc_char = self.source[self.pos]
                        self.pos += 1
                        self.column += 1
                        if esc_char == '"':
                            string_val.append('"')
                        elif esc_char == '\\':
                            string_val.append('\\')
                        elif esc_char == 'n':
                            string_val.append('\n')
                        elif esc_char == 't':
                            string_val.append('\t')
                        else:
                            raise LexerError(f"Secuencia de escape inválida '\\{esc_char}'", self.line, esc_col)
                    else:
                        string_val.append(c)
                        self.pos += 1
                        self.column += 1

                if not closed:
                    raise LexerError("Cadena literal no cerrada", start_line, start_col)

                tokens.append(Token(TokenType.CADENA, "".join(string_val), start_line, start_col))
                continue

            # 8. OP_REL: == | != | >= | <= | > | <
            if char == '=' and self._peek(1) == '=':
                tokens.append(Token(TokenType.OP_REL, "==", start_line, start_col))
                self.pos += 2
                self.column += 2
                continue
            if char == '!' and self._peek(1) == '=':
                tokens.append(Token(TokenType.OP_REL, "!=", start_line, start_col))
                self.pos += 2
                self.column += 2
                continue
            if char == '>' and self._peek(1) == '=':
                tokens.append(Token(TokenType.OP_REL, ">=", start_line, start_col))
                self.pos += 2
                self.column += 2
                continue
            if char == '<' and self._peek(1) == '=':
                tokens.append(Token(TokenType.OP_REL, "<=", start_line, start_col))
                self.pos += 2
                self.column += 2
                continue
            if char == '>':
                tokens.append(Token(TokenType.OP_REL, ">", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue
            if char == '<':
                tokens.append(Token(TokenType.OP_REL, "<", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue

            # 9. ASIGNA: =
            if char == '=':
                tokens.append(Token(TokenType.ASIGNA, "=", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue

            # 10. OP_ARIT: [+\-*/]
            if char in ('+', '-', '*', '/'):
                tokens.append(Token(TokenType.OP_ARIT, char, start_line, start_col))
                self.pos += 1
                self.column += 1
                continue

            # 11. PAREN_ABRE / PAREN_CIERRA: (, )
            if char == '(':
                tokens.append(Token(TokenType.PAREN_ABRE, "(", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue
            if char == ')':
                tokens.append(Token(TokenType.PAREN_CIERRA, ")", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue

            # 12. LLAVE_ABRE / LLAVE_CIERRA: {, }
            if char == '{':
                tokens.append(Token(TokenType.LLAVE_ABRE, "{", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue
            if char == '}':
                tokens.append(Token(TokenType.LLAVE_CIERRA, "}", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue

            # 13. PUNTO: .
            if char == '.':
                tokens.append(Token(TokenType.PUNTO, ".", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue

            # 14. PUNTO_COMA: ;
            if char == ';':
                tokens.append(Token(TokenType.PUNTO_COMA, ";", start_line, start_col))
                self.pos += 1
                self.column += 1
                continue

            # 15. ID: [A-Za-z_ÁÉÍÓÚÜÑáéíóúüñ][A-Za-z0-9_ÁÉÍÓÚÜÑáéíóúüñ]*
            if self._is_id_start(char):
                id_str = ""
                while self.pos < self.length and self._is_id_part(self.source[self.pos]):
                    id_str += self.source[self.pos]
                    self.pos += 1
                    self.column += 1

                # Comprobar si es palabra reservada (estrictamente en minúsculas)
                if id_str in RESERVED_WORDS:
                    tokens.append(Token(RESERVED_WORDS[id_str], id_str, start_line, start_col))
                else:
                    tokens.append(Token(TokenType.ID, id_str, start_line, start_col))
                continue

            # Carácter desconocido
            raise LexerError(f"Carácter no reconocido: '{char}' (U+{ord(char):04X})", start_line, start_col)

        # Regla: Si el archivo no termina en NL o ';', inyectar NL final automáticamente
        if tokens:
            last_type = tokens[-1].type
            if last_type not in (TokenType.NL, TokenType.PUNTO_COMA):
                tokens.append(Token(TokenType.NL, "\n", self.line, self.column))

        # Token final EOF
        tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return tokens

    @staticmethod
    def _is_id_start(char: str) -> bool:
        if 'a' <= char <= 'z' or 'A' <= char <= 'Z' or char == '_':
            return True
        # Caracteres con tilde y eñe en español
        return char in "ÁÉÍÓÚÜÑáéíóúüñ"

    @staticmethod
    def _is_id_part(char: str) -> bool:
        return Lexer._is_id_start(char) or ('0' <= char <= '9')
