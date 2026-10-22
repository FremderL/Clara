"""
command_registry.py
Registro dinámico y seguro de comandos para Viernes.
Permite registrar, listar y ejecutar comandos de forma extensible.
"""
import logging
from typing import Callable, Dict, List, Optional

logging.basicConfig(level=logging.INFO)

class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        if name in self._commands:
            logging.warning(f"Comando '{name}' ya registrado. Sobrescribiendo.")
        self._commands[name] = func
        logging.info(f"Comando registrado: {name}")

    def unregister(self, name: str):
        if name in self._commands:
            del self._commands[name]
            logging.info(f"Comando eliminado: {name}")

    def execute(self, name: str, *args, **kwargs):
        if name not in self._commands:
            raise ValueError(f"Comando '{name}' no encontrado.")
        return self._commands[name](*args, **kwargs)

    def list_commands(self) -> List[str]:
        return list(self._commands.keys())

    def get(self, name: str) -> Optional[Callable]:
        return self._commands.get(name)

# Ejemplo seguro de uso
if __name__ == "__main__":
    registry = CommandRegistry()
    def hola():
        print("Hola mundo!")
    registry.register("saludo", hola)
    registry.execute("saludo")
    print("Comandos disponibles:", registry.list_commands())
