from __future__ import annotations

import html
import json
import random
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

from viernes_app.paths import NEWS_CACHE_PATH


def get_weather(city: str = "Colima, Colima, Mexico") -> str:
    try:
        city_enc = city.replace(" ", "+")
        url = f"https://wttr.in/{city_enc}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        current = data.get("current_condition", [{}])[0]
        temp = current.get("temp_C", "?")
        condition = current.get("weatherDesc", [{}])[0].get("value", "Desconocido")
        humidity = current.get("humidity", "?")
        return f"Clima en {city}: {temp} C, {condition}. Humedad: {humidity}%"
    except Exception:
        return "No pude obtener el clima. Verifique la ciudad."


def _clean_search_text(value: str) -> str:
    value = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -\t\r\n")


def _trim_search_text(value: str, limit: int = 420) -> str:
    text = _clean_search_text(value)
    if len(text) <= limit:
        return text
    shortened = text[:limit].rstrip()
    best_cut = max(shortened.rfind(". "), shortened.rfind("; "), shortened.rfind(": "))
    if best_cut >= 180:
        return shortened[: best_cut + 1].strip()
    return shortened.rsplit(" ", 1)[0].rstrip(" ,;:") + "..."


def _duckduckgo_instant_answer(query: str) -> Optional[str]:
    query_enc = urllib.parse.quote_plus(query)
    url = f"https://api.duckduckgo.com/?q={query_enc}&format=json&no_redirect=1&no_html=1&kl=mx-es"
    req = urllib.request.Request(url, headers={"User-Agent": "Viernes/1.0 (+local-assistant)"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    abstract = str(data.get("AbstractText", "") or "").strip()
    heading = str(data.get("Heading", "") or "").strip()
    if abstract:
        return _trim_search_text(f"{heading + ': ' if heading else ''}{abstract}", 520)
    related = data.get("RelatedTopics", [])
    if isinstance(related, list):
        snippets = []
        for item in related:
            if isinstance(item, dict) and item.get("Text"):
                snippets.append(str(item["Text"]).strip())
            if len(snippets) >= 2:
                break
        if snippets:
            return _trim_search_text(" ".join(snippets), 520)
    return None


def _duckduckgo_html_results(query: str, max_results: int = 3) -> list[str]:
    query_enc = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={query_enc}"
    req = urllib.request.Request(url, headers={"User-Agent": "Viernes/1.0 (+local-assistant)"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw_html = resp.read().decode("utf-8", errors="replace")

    pattern = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>'
        r'.{0,2500}?'
        r'(?:<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>|'
        r'<div[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>)',
        flags=re.IGNORECASE | re.DOTALL,
    )
    results: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(raw_html):
        title = _clean_search_text(match.group(1))
        snippet = _clean_search_text(match.group(2) or match.group(3) or "")
        if not snippet:
            continue
        text = _trim_search_text(f"{title}: {snippet}" if title else snippet)
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(text)
        if len(results) >= max_results:
            break

    if results:
        return results

    title_pattern = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in title_pattern.finditer(raw_html):
        title = _clean_search_text(match.group(1))
        if title and title.lower() not in seen:
            seen.add(title.lower())
            results.append(f"Resultado encontrado: {title}")
        if len(results) >= max_results:
            break
    return results


def search_web(query: str) -> Optional[str]:
    try:
        clean_query = re.sub(r"\s+", " ", query or "").strip()
        if not clean_query:
            return None

        instant = _duckduckgo_instant_answer(clean_query)
        results = _duckduckgo_html_results(clean_query)
        sections: list[str] = []
        if instant:
            sections.append(_clean_search_text(instant))
        sections.extend(results)

        if sections:
            summary = " ".join(f"{idx}. {_trim_search_text(item)}" for idx, item in enumerate(sections[:3], start=1))
            return _trim_search_text(summary, 1200)
        return "No encontre resultados claros."
    except Exception:
        return None


def translate_text(text: str, target_lang: str = "es") -> str:
    try:
        target_low = target_lang.lower()
        if "ingles" in target_low or "english" in target_low:
            target = "en"
        elif "frances" in target_low or "french" in target_low:
            target = "fr"
        elif "aleman" in target_low or "german" in target_low:
            target = "de"
        elif "portugues" in target_low or "portuguese" in target_low:
            target = "pt"
        else:
            target = "en"

        text_enc = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={text_enc}&langpair=es|{target}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        translated = data.get("responseData", {}).get("translatedText", "")
        if translated:
            return f"Traduccion: {translated}"
        return "No pude traducir el texto."
    except Exception:
        return "Error al traducir."


def calculate(expression: str) -> str:
    """Evaluación segura (AST + whitelist); no usa eval()."""
    try:
        from jarvis_os_v5.core.safe_math import safe_eval_math

        raw = (expression or "").strip()
        if not raw:
            return "Indique una expresión, por ejemplo: sqrt(144)+sin(radians(90))."
        result = safe_eval_math(raw)
        return f"Resultado: {result}"
    except Exception as e:
        return f"No pude calcular de forma segura: {e}"


def set_timer(minutes: int, name: str = "Temporizador") -> str:
    import threading
    import time

    def timer_done() -> None:
        time.sleep(minutes * 60)
        print(f"{name}: tiempo completado.")

    threading.Thread(target=timer_done, daemon=True).start()
    return f"Temporizador de {minutes} minutos activado. Le avisare cuando termine."


NEWS_FEEDS: dict[str, list[str]] = {
    "world": [
        "https://news.google.com/rss/headlines/section/topic/WORLD?hl=es-419&gl=MX&ceid=MX:es-419",
        "https://news.google.com/rss?hl=es-419&gl=MX&ceid=MX:es-419",
        "https://feeds.bbci.co.uk/mundo/rss.xml",
    ],
    "general": [
        "https://news.google.com/rss?hl=es-419&gl=MX&ceid=MX:es-419",
        "https://feeds.bbci.co.uk/mundo/rss.xml",
    ],
    "technology": [
        "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=es-419&gl=MX&ceid=MX:es-419",
        "https://news.google.com/rss/search?q=tecnologia&hl=es-419&gl=MX&ceid=MX:es-419",
    ],
    "science": [
        "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=es-419&gl=MX&ceid=MX:es-419",
        "https://news.google.com/rss/search?q=ciencia&hl=es-419&gl=MX&ceid=MX:es-419",
    ],
    "mexico": [
        "https://news.google.com/rss/headlines/section/topic/NATION?hl=es-419&gl=MX&ceid=MX:es-419",
        "https://news.google.com/rss/search?q=Mexico&hl=es-419&gl=MX&ceid=MX:es-419",
    ],
}


def _clean_news_title(raw: str) -> str:
    title = html.unescape(re.sub(r"\s+", " ", raw or "")).strip()
    title = re.sub(r"<[^>]+>", "", title).strip()
    return title[:180]


def _load_news_cache() -> dict:
    try:
        if NEWS_CACHE_PATH.exists():
            with open(NEWS_CACHE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _save_news_cache(cache: dict) -> None:
    try:
        NEWS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(NEWS_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _cached_news(topic: str, max_items: int) -> list[str]:
    cache = _load_news_cache()
    entry = cache.get(topic) if isinstance(cache, dict) else None
    if not isinstance(entry, dict):
        candidates = [value for value in cache.values() if isinstance(value, dict)]
        candidates.sort(key=lambda item: str(item.get("fetched_at", "")), reverse=True)
        entry = candidates[0] if candidates else None
    if not isinstance(entry, dict):
        return []
    try:
        fetched_at = datetime.fromisoformat(str(entry.get("fetched_at", "")))
        if datetime.now() - fetched_at > timedelta(hours=18):
            return []
    except ValueError:
        return []
    headlines = entry.get("headlines", [])
    if not isinstance(headlines, list):
        return []
    return [str(item) for item in headlines if str(item).strip()][:max_items]


def _fetch_news_titles(url: str, max_items: int) -> list[str]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            "User-Agent": "Viernes/1.0 (+local-assistant)",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        payload = resp.read()
    root = ET.fromstring(payload)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    titles: list[str] = []
    seen: set[str] = set()
    for item in items:
        title_node = item.find("title")
        if title_node is None:
            title_node = item.find("{http://www.w3.org/2005/Atom}title")
        title = _clean_news_title(title_node.text if title_node is not None else "")
        key = title.lower()
        if title and key not in seen:
            titles.append(title)
            seen.add(key)
        if len(titles) >= max_items:
            break
    return titles


def get_news(topic: str = "world", max_items: int = 5) -> str:
    topic_key = (topic or "world").strip().lower()
    if topic_key not in NEWS_FEEDS:
        topic_key = "world"
    max_items = max(1, min(int(max_items or 5), 8))

    errors: list[str] = []
    for url in NEWS_FEEDS[topic_key]:
        try:
            headlines = _fetch_news_titles(url, max_items)
            if headlines:
                cache = _load_news_cache()
                cache[topic_key] = {
                    "fetched_at": datetime.now().isoformat(timespec="seconds"),
                    "source": url,
                    "headlines": headlines,
                }
                _save_news_cache(cache)
                return "Noticias:\n" + "\n".join(f"- {title}" for title in headlines)
        except Exception as exc:
            errors.append(str(exc))

    cached = _cached_news(topic_key, max_items)
    if cached:
        return "Noticias guardadas:\n" + "\n".join(f"- {title}" for title in cached)
    detail = errors[-1] if errors else "sin titulares disponibles"
    return f"No pude obtener noticias. Detalle: {detail}"


def tell_joke() -> str:
    jokes = [
        "Que le dice un jaguar a otro? Jaguar you?",
        "Por que el libro de matematicas estaba triste? Porque tenia muchos problemas.",
        "Que hace una abeja en el gimnasio? Zum-ba.",
        "Cual es el cafe mas malo? El cafe sin servicio.",
        "Como se dice panuelo en japones? Saka-moko.",
        "Que hace una gallina en un banco? Pollo-fondo.",
    ]
    return random.choice(jokes)


def control_system(action: str) -> str:
    import subprocess

    action = action.lower()
    if "apaga" in action or "apagar" in action:
        subprocess.run(["shutdown", "/s", "/t", "60", "/c", "Viernes: Apagando en 60 segundos"], capture_output=True)
        return "PC apagandose en 60 segundos. Diga cancelar apagado para detenerlo."
    if "cancela" in action and "apagado" in action:
        subprocess.run(["shutdown", "/a"], capture_output=True)
        return "Apagado cancelado."
    if "reinicia" in action or "reiniciar" in action:
        subprocess.run(["shutdown", "/r", "/t", "60", "/c", "Viernes: Reiniciando en 60 segundos"], capture_output=True)
        return "PC reiniciandose en 60 segundos."
    if "bloquea" in action or "bloquear" in action:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True)
        return "PC bloqueada."
    if "suspende" in action or "suspender" in action:
        subprocess.run(
            [
                "powershell",
                "-Command",
                "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)",
            ],
            capture_output=True,
        )
        return "PC suspendida."
    return "Accion no reconocida. Puedo apagar, reiniciar, bloquear o suspender."


def add_note(text: str, title: str = "") -> str:
    from viernes_app.paths import REPO_ROOT

    notes_file = REPO_ROOT / "viernes_notes.json"
    try:
        if notes_file.exists():
            with open(notes_file, encoding="utf-8") as f:
                notes = json.load(f)
        else:
            notes = []

        note = {
            "id": str(datetime.now().timestamp()),
            "title": title or f"Nota {len(notes)+1}",
            "text": text,
            "created": datetime.now().isoformat(),
        }
        notes.append(note)

        with open(notes_file, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)

        return f"Nota guardada: {note['title']}"
    except Exception:
        return "Error al guardar nota."


def get_notes() -> str:
    from viernes_app.paths import REPO_ROOT

    notes_file = REPO_ROOT / "viernes_notes.json"
    try:
        if not notes_file.exists():
            return "No hay notas guardadas."
        with open(notes_file, encoding="utf-8") as f:
            notes = json.load(f)
        if not notes:
            return "No hay notas guardadas."
        result = "Notas:\n"
        for note in notes[-10:]:
            result += f"- {note['title']}: {note['text'][:50]}...\n"
        return result
    except Exception:
        return "Error al obtener notas."
