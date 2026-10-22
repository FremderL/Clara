from __future__ import annotations

import json
import urllib.request
from typing import Optional


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = "llama3.2"
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                self._available = resp.status == 200
        except Exception:
            self._available = False
        return self._available

    def set_model(self, model: str) -> None:
        clean = (model or "").strip()
        if clean:
            self.model = clean

    def chat(self, system_prompt: str, user_message: str, temperature: float = 0.55) -> Optional[str]:
        if not self.is_available():
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": 280,
            },
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("message", {}).get("content", "").strip()
        except Exception:
            return None

    def list_models(self) -> list[str]:
        if not self.is_available():
            return []
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []


SYSTEM_PROMPT = """Eres Viernes, asistente personal de Kaiser, un estudiante universitario en Colima, Mexico.
Respondes en espanol natural, breve y util. Tu prioridad es entender intencion, recordar contexto del dia y ayudar a ejecutar la siguiente accion concreta.

Capacidades reales disponibles en la app:
- agenda, recordatorios, clases, rutinas y estado del dia
- presupuesto, ingresos, gastos y balance
- clima, noticias, busqueda web y apertura de aplicaciones
- diagnostico de autoinicio, modo residente y rutina matutina

Reglas:
- No inventes que ya hiciste acciones si no se ejecutaron antes en el codigo.
- Si falta informacion, pide solo el dato minimo.
- Usa el contexto adicional como memoria operativa.
- Maximo 3 oraciones salvo que el usuario pida detalle.
- Si detectas riesgo, dilo claro y ofrece un siguiente paso concreto.
"""


def generate_ai_response(
    client: OllamaClient,
    user_message: str,
    context_info: str = "",
) -> Optional[str]:
    full_prompt = f"{SYSTEM_PROMPT}\n\nContexto operativo actual:\n{context_info}"
    return client.chat(system_prompt=full_prompt, user_message=user_message, temperature=0.55)
