"""
concurrency_utils.py
Utilidades thread-safe para concurrencia segura en Python.
Incluye locks, decoradores y helpers. Sin dependencias externas.
"""
import threading
import functools
import logging

logging.basicConfig(level=logging.INFO)

def synchronized(lock_name="_lock"):
    """
    Decorador para métodos thread-safe usando un lock por instancia.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            lock = getattr(self, lock_name, None)
            if lock is None:
                raise AttributeError(f"No se encontró lock '{lock_name}' en instancia {self}")
            with lock:
                return func(self, *args, **kwargs)
        return wrapper
    return decorator

class ThreadSafeMixin:
    """
    Mixin para añadir un lock a cualquier clase.
    """
    def __init__(self, *args, **kwargs):
        self._lock = threading.RLock()
        super().__init__(*args, **kwargs)

# Ejemplo seguro de uso
if __name__ == "__main__":
    class Contador(ThreadSafeMixin):
        def __init__(self):
            super().__init__()
            self.valor = 0
        @synchronized()
        def inc(self):
            self.valor += 1
    c = Contador()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=10) as ex:
        for _ in range(100):
            ex.submit(c.inc)
    print("Valor final:", c.valor)
