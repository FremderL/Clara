"""
ollama_integration.py
Wrapper seguro para integración local con Ollama (API HTTP).
No modifica módulos existentes. Cumple reglas de seguridad y compatibilidad.
"""
import logging
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    requests = None
    logging.warning("El paquete 'requests' no está instalado. OllamaClient solo funcionará si está disponible.")

logging.basicConfig(level=logging.INFO)

class OllamaClient:
    def __init__(self, host: str = "http://localhost:11434", timeout: int = 20):
        self.host = host.rstrip('/')
        self.timeout = timeout
        if requests is None:
            raise ImportError("El paquete 'requests' es necesario para OllamaClient.")

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception as e:
            logging.warning(f"Ollama no disponible: {e}")
            return False

    def generate(self, prompt: str, model: str = "llama2", options: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Envía un prompt a Ollama y retorna la respuesta generada.
        """
        url = f"{self.host}/api/generate"
        payload = {"model": model, "prompt": prompt}
        if options:
            payload["options"] = options
        try:
            r = requests.post(url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            return data.get("response")
        except Exception as e:
            logging.error(f"Error al consultar Ollama: {e}")
            return None

# Ejemplo seguro de uso
if __name__ == "__main__":
    try:
        client = OllamaClient()
        if client.is_available():
            respuesta = client.generate("¿Cuál es la capital de Francia?", model="llama2")
            print("Respuesta de Ollama:", respuesta)
        else:
            print("Ollama no está disponible en localhost:11434")
    except Exception as ex:
        print("No se pudo inicializar OllamaClient:", ex)
