"""
semantic_router.py
Router semántico modular para enrutar comandos/intenciones a funciones.
Solo depende de NumPy y re. Cumple reglas de seguridad y compatibilidad.
"""
import numpy as np
import re
import logging
from typing import Callable, List, Tuple, Optional

logging.basicConfig(level=logging.INFO)

class SemanticRouter:
    def __init__(self):
        self.routes: List[Tuple[str, Callable, Optional[np.ndarray]]] = []

    def register(self, pattern: str, func: Callable, embedding: Optional[np.ndarray] = None):
        """
        Registra un patrón (regex o frase clave), función destino y opcionalmente embedding.
        """
        self.routes.append((pattern, func, embedding))
        logging.info(f"Registrado patrón: {pattern} -> {func.__name__}")

    def _text_to_vec(self, text: str) -> np.ndarray:
        # Simple vectorización: cuenta de caracteres (puede mejorarse con embeddings reales)
        vec = np.zeros(128)
        for c in text.lower():
            if ord(c) < 128:
                vec[ord(c)] += 1
        return vec

    def _cosine_sim(self, v1: np.ndarray, v2: np.ndarray) -> float:
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    def route(self, text: str):
        """
        Busca el patrón más similar o coincidente y ejecuta la función asociada.
        """
        # 1. Regex exacto
        for pattern, func, _ in self.routes:
            if re.search(pattern, text, re.IGNORECASE):
                logging.info(f"Coincidencia regex: {pattern}")
                return func(text)
        # 2. Similaridad semántica básica
        text_vec = self._text_to_vec(text)
        best_score = 0.0
        best_func = None
        for pattern, func, embedding in self.routes:
            if embedding is not None:
                score = self._cosine_sim(text_vec, embedding)
                if score > best_score:
                    best_score = score
                    best_func = func
        if best_func and best_score > 0.7:
            logging.info(f"Coincidencia semántica con score {best_score:.2f}")
            return best_func(text)
        logging.debug("No se encontró ruta para: %s", text)
        return None

# Ejemplo seguro de uso
if __name__ == "__main__":
    router = SemanticRouter()
    def saludo(text):
        print("Hola! Has dicho:", text)
    def despedida(text):
        print("Adiós! Has dicho:", text)
    # Registro por regex
    router.register(r"hola|buenos días", saludo)
    router.register(r"adiós|hasta luego", despedida)
    # Registro por embedding (similitud)
    emb_saludo = router._text_to_vec("saludo")
    router.register("saludo", saludo, emb_saludo)
    # Pruebas
    router.route("Hola, sistema")
    router.route("Me despido, hasta luego")
    router.route("Esto es un saludo cordial")
