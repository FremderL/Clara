"""
Rutas compartidas del proyecto.

La entrada publica sigue siendo viernes.py en la raiz. El codigo vive dentro de
viernes_app/ y los datos historicos se conservan en la raiz por compatibilidad.
Los archivos generados nuevos deben ir en runtime/.
"""
from __future__ import annotations

from pathlib import Path

# viernes_app/paths.py -> padre = viernes_app, abuelo = raiz del repo.
REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "runtime"

CONFIG_PATH = REPO_ROOT / "viernes_config.json"
STATE_PATH = REPO_ROOT / "viernes_state.json"
AGENDA_PATH = REPO_ROOT / "viernes_agenda.json"
BUDGET_PATH = REPO_ROOT / "viernes_budget.json"
SQLITE_DB_PATH = REPO_ROOT / "viernes_data.db"
NEWS_CACHE_PATH = RUNTIME_DIR / "news_cache.json"
PERSONAL_MEMORY_PATH = RUNTIME_DIR / "personal_memory.json"
PENDING_TASKS_PATH = RUNTIME_DIR / "pending_tasks.json"
ACTION_HISTORY_PATH = RUNTIME_DIR / "action_history.json"
