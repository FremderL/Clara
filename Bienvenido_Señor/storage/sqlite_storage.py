"""
sqlite_storage.py
Almacenamiento robusto y thread-safe usando SQLite en modo WAL.
No modifica módulos existentes. Cumple reglas de seguridad y compatibilidad.
"""
import sqlite3
import threading
import logging
from typing import Any, Optional, Tuple

logging.basicConfig(level=logging.INFO)

class SQLiteStorage:
    def __init__(self, db_path: str = "viernes_data.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        with self._lock, sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.commit()
        logging.info("SQLite inicializado en modo WAL: %s", self.db_path)

    def execute(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> Any:
        with self._lock, sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cur = conn.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            if query.strip().lower().startswith("select"):
                result = cur.fetchall()
            else:
                conn.commit()
                result = cur.rowcount
            cur.close()
            return result

    def safe_insert(self, table: str, data: dict) -> int:
        keys = ','.join(data.keys())
        placeholders = ','.join(['?']*len(data))
        query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
        return self.execute(query, tuple(data.values()))

# Ejemplo seguro de uso
if __name__ == "__main__":
    db = SQLiteStorage(":memory:")
    db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, valor TEXT)")
    db.safe_insert("test", {"valor": "hola"})
    print(db.execute("SELECT * FROM test"))
