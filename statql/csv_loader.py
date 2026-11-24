"""
statql/csv_loader.py
Inspector de esquemas CSV para StatQL.
Deduce dinámicamente o verifica esquemas tabulares con soporte explícito de tipos:
- 'booleano': mapeo estricto de 'verdadero' / 'falso' (y variantes 'true' / 'false')
- 'entero': números enteros con signo
- 'decimal': números con punto flotante o notación científica
- 'texto': cadenas alfanuméricas generales
"""

import os
import csv
from typing import Dict, List, Optional, Any


class CSVLoadError(Exception):
    """Excepción lanzada ante errores de lectura o validación de archivos CSV."""
    def __init__(self, message: str, path: str = "", line: int = 1, column: int = 1):
        super().__init__(f"Error en CSV '{path}' (L{line}:C{column}): {message}")
        self.raw_message = message
        self.path = path
        self.line = line
        self.column = column


class CSVSchema:
    """
    Representa el esquema estructural tipado de un archivo CSV inspeccionado.
    Contrato inmutable utilizado por el Analizador Semántico y Módulos posteriores.
    """
    def __init__(self, file_path: str, columns: Dict[str, str], row_count: int = 0):
        self.file_path = file_path
        self.columns = dict(columns)  # {nombre_columna: tipo ('entero', 'decimal', 'texto', 'booleano')}
        self.row_count = row_count

    def has_column(self, name: str) -> bool:
        """Indica si una columna existe en el esquema."""
        return name in self.columns

    def get_type(self, name: str) -> Optional[str]:
        """Obtiene el tipo de dato de una columna o None si no existe."""
        return self.columns.get(name)

    def column_names(self) -> List[str]:
        """Retorna la lista ordenada de nombres de columnas."""
        return list(self.columns.keys())

    def numeric_columns(self) -> List[str]:
        """Retorna las columnas numéricas ('entero' o 'decimal')."""
        return [col for col, typ in self.columns.items() if typ in ("entero", "decimal")]

    def to_dict(self) -> Dict[str, str]:
        """Exporta el esquema como diccionario nombre -> tipo."""
        return dict(self.columns)

    def __repr__(self) -> str:
        cols_repr = ", ".join(f"{k}: {v}" for k, v in self.columns.items())
        return f"CSVSchema(file='{self.file_path}', rows={self.row_count}, columns=[{cols_repr}])"


class CSVLoader:
    """
    Cargador e inspector estático de esquemas para archivos CSV.
    Permite pre-registrar esquemas simulados (mock) para pruebas herméticas y
    leer datasets reales desde disco infiriendo tipos con precisión.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.getcwd()
        self.mock_schemas: Dict[str, CSVSchema] = {}

    def register_mock_schema(self, path: str, schema: Dict[str, str], row_count: int = 100) -> CSVSchema:
        """
        Registra un esquema simulado en memoria para pruebas unitarias.
        Normaliza separadores de ruta para coincidir con rutas relativas o absolutas.
        """
        normalized_key = os.path.normpath(path).replace("\\", "/")
        csv_schema = CSVSchema(file_path=path, columns=schema, row_count=row_count)
        self.mock_schemas[path] = csv_schema
        self.mock_schemas[normalized_key] = csv_schema
        # Registrar también solo el basename para comodidad en pruebas
        self.mock_schemas[os.path.basename(path)] = csv_schema
        return csv_schema

    def load_schema(self, rel_or_abs_path: str, line: int = 1, column: int = 1) -> CSVSchema:
        """
        Inspecciona el esquema de un archivo CSV en disco o recupera un mock registrado.
        Infiere encabezados y tipos columna por columna.
        """
        # 1. Comprobar si existe en mock_schemas por ruta exacta o normalizada
        norm_req = os.path.normpath(rel_or_abs_path).replace("\\", "/")
        if rel_or_abs_path in self.mock_schemas:
            return self.mock_schemas[rel_or_abs_path]
        if norm_req in self.mock_schemas:
            return self.mock_schemas[norm_req]

        # 2. Resolver ruta en el sistema de archivos
        if os.path.isabs(rel_or_abs_path):
            full_path = rel_or_abs_path
        else:
            full_path = os.path.normpath(os.path.join(self.base_dir, rel_or_abs_path))

        # Si no existe archivo físico, verificar si se registró como mock por nombre base
        base_req = os.path.basename(rel_or_abs_path)
        if not os.path.isfile(full_path):
            if base_req in self.mock_schemas:
                return self.mock_schemas[base_req]
            raise CSVLoadError(
                f"No se encontró el archivo CSV en la ruta especificada: '{rel_or_abs_path}' (buscado en: '{full_path}')",
                path=rel_or_abs_path, line=line, column=column
            )

        # 3. Leer encabezados y muestreo de filas para inferencia de tipos
        schema_dict: Dict[str, str] = {}
        rows_inspected = 0

        try:
            with open(full_path, mode='r', encoding='utf-8-sig', errors='replace') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    raise CSVLoadError(
                        f"El archivo CSV '{rel_or_abs_path}' está vacío o no contiene encabezados legibles.",
                        path=rel_or_abs_path, line=line, column=column
                    )

                clean_headers = [h.strip() for h in headers if h.strip() != ""]
                if not clean_headers:
                    raise CSVLoadError(
                        f"El archivo CSV '{rel_or_abs_path}' no contiene nombres de columnas válidos.",
                        path=rel_or_abs_path, line=line, column=column
                    )

                # Muestrear hasta 500 filas representativas
                sample_rows: List[List[str]] = []
                for row in reader:
                    sample_rows.append(row)
                    rows_inspected += 1
                    if rows_inspected >= 500:
                        break

                for idx, col_name in enumerate(clean_headers):
                    values: List[str] = []
                    for row in sample_rows:
                        if idx < len(row):
                            v = row[idx].strip()
                            if v != "":
                                values.append(v)
                    schema_dict[col_name] = self.infer_column_type(values)

        except CSVLoadError:
            raise
        except Exception as err:
            raise CSVLoadError(
                f"Fallo al abrir o procesar el archivo CSV '{rel_or_abs_path}': {err}",
                path=rel_or_abs_path, line=line, column=column
            )

        return CSVSchema(file_path=rel_or_abs_path, columns=schema_dict, row_count=rows_inspected)

    @classmethod
    def infer_column_type(cls, values: List[str]) -> str:
        """
        Deduce el tipo de dato de una lista de valores textuales:
        - Si todos son verdaderos/falsos (o true/false) -> 'booleano'
        - Si todos son enteros -> 'entero'
        - Si todos son numéricos de punto flotante -> 'decimal'
        - En cualquier otro caso o mixto -> 'texto'
        """
        if not values:
            return "texto"

        is_bool = True
        is_int = True
        is_dec = True

        for val in values:
            lower = val.lower()

            # Mapeo explícito de 'verdadero' / 'falso'
            if lower not in ("verdadero", "falso", "true", "false", "v", "f"):
                is_bool = False

            # Comprobación de entero
            if is_int:
                try:
                    int(val)
                except ValueError:
                    is_int = False

            # Comprobación de decimal
            if is_dec:
                try:
                    float(val)
                except ValueError:
                    is_dec = False

        if is_bool:
            return "booleano"
        if is_int:
            return "entero"
        if is_dec:
            return "decimal"
        return "texto"
