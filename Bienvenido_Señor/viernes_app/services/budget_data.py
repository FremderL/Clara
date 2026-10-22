from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from viernes_app.paths import BUDGET_PATH


CATEGORIES = {
    "comida": ["comida", "desayuno", "almuerzo", "cena", "restaurante", "lonche", "cafeteria"],
    "transporte": ["transporte", "taxi", "uber", "gasolina", "combustible", "camion", "metro"],
    "entretenimiento": ["entretenimiento", "netflix", "spotify", "pelicula", "juego", "steam"],
    "utilidades": ["luz", "agua", "internet", "telefono", "servicio", "cargo"],
    "escuela": ["escuela", "libros", "material", "impresiones", "transporte escolar"],
    "ropa": ["ropa", "zapatos", "accesorios"],
    "salud": ["salud", "medicina", "doctor", "gimnasio"],
    "otros": [],
}


def load_budget() -> dict[str, Any]:
    try:
        if BUDGET_PATH.exists():
            with open(BUDGET_PATH, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "balance": 0.0,
        "income": [],
        "expenses": [],
        "budget_limit": 0.0,
    }


def save_budget(data: dict[str, Any]) -> None:
    with open(BUDGET_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _recalculate_balance(data: dict[str, Any]) -> None:
    data["balance"] = sum(float(e.get("amount", 0)) for e in data.get("income", [])) - sum(
        float(e.get("amount", 0)) for e in data.get("expenses", [])
    )


def _all_transactions(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    items: list[tuple[str, dict[str, Any]]] = []
    items.extend(("income", item) for item in data.get("income", []))
    items.extend(("expense", item) for item in data.get("expenses", []))
    items.sort(key=lambda item: str(item[1].get("timestamp", "")), reverse=True)
    return items


def _find_transaction(data: dict[str, Any], query: str, tx_type: str = "") -> tuple[str, dict[str, Any]] | None:
    q = (query or "").lower().strip()
    q = q.replace("ultimo movimiento", "ultimo").replace("ultimo gasto", "ultimo").replace("ultimo ingreso", "ultimo")
    if q in {"", "ultimo", "ultima"}:
        for kind, tx in _all_transactions(data):
            if not tx_type or kind == tx_type:
                return kind, tx
        return None
    for noise in ("gasto", "ingreso", "movimiento", "transaccion", "de", "del"):
        q = q.replace(f" {noise} ", " ")
    q = " ".join(q.split())
    for kind, tx in _all_transactions(data):
        if tx_type and kind != tx_type:
            continue
        tx_id = str(tx.get("id", "")).lower()
        desc = str(tx.get("description", "")).lower()
        category = str(tx.get("category", "")).lower()
        if q and (q in tx_id or q in desc or desc in q or q in category):
            return kind, tx
    return None


def detect_category(description: str) -> str:
    desc = description.lower()
    for cat, keywords in CATEGORIES.items():
        if any(kw in desc for kw in keywords):
            return cat
    return "otros"


def add_income(amount: float, description: str, date: Optional[str] = None) -> dict[str, Any]:
    data = load_budget()
    entry = {
        "id": str(datetime.now().timestamp()),
        "amount": amount,
        "description": description.strip(),
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
    }
    data["income"].append(entry)
    data["balance"] += amount
    save_budget(data)
    return {"success": True, "balance": data["balance"], "entry": entry}


def add_expense(amount: float, description: str, category: Optional[str] = None, date: Optional[str] = None) -> dict[str, Any]:
    data = load_budget()
    cat = category or detect_category(description)
    entry = {
        "id": str(datetime.now().timestamp()),
        "amount": amount,
        "description": description.strip(),
        "category": cat,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
    }
    data["expenses"].append(entry)
    data["balance"] -= amount
    
    if data.get("budget_limit", 0) > 0:
        total_expenses = sum(e["amount"] for e in data["expenses"])
        if total_expenses > data["budget_limit"]:
            entry["over_budget"] = True
    
    save_budget(data)
    return {"success": True, "balance": data["balance"], "entry": entry, "category": cat}


def get_balance() -> dict[str, Any]:
    data = load_budget()
    return {
        "balance": data["balance"],
        "total_income": sum(e["amount"] for e in data["income"]),
        "total_expenses": sum(e["amount"] for e in data["expenses"]),
        "budget_limit": data.get("budget_limit", 0),
        "remaining_budget": data.get("budget_limit", 0) - sum(e["amount"] for e in data["expenses"]),
    }


def get_expenses_by_category() -> dict[str, float]:
    data = load_budget()
    result: dict[str, float] = {}
    for exp in data["expenses"]:
        cat = exp.get("category", "otros")
        result[cat] = result.get(cat, 0) + exp["amount"]
    return result


def get_recent_transactions(limit: int = 10) -> list[dict[str, Any]]:
    data = load_budget()
    all_tx = [(t, "income") for t in data["income"]] + [(t, "expense") for t in data["expenses"]]
    all_tx.sort(key=lambda x: x[0].get("timestamp", ""), reverse=True)
    return [{"transaction": t[0], "type": t[1]} for t in all_tx[:limit]]


def set_budget_limit(limit: float) -> dict[str, Any]:
    data = load_budget()
    data["budget_limit"] = limit
    save_budget(data)
    return {"success": True, "budget_limit": limit}


def delete_transaction(query: str, tx_type: str = "") -> dict[str, Any]:
    data = load_budget()
    found = _find_transaction(data, query, tx_type=tx_type)
    if found is None:
        return {"success": False, "message": "No encontre ese movimiento."}
    kind, tx = found
    section = "income" if kind == "income" else "expenses"
    data[section] = [item for item in data.get(section, []) if str(item.get("id")) != str(tx.get("id"))]
    _recalculate_balance(data)
    save_budget(data)
    return {"success": True, "type": kind, "transaction": tx, "balance": data["balance"]}


def update_transaction(
    query: str,
    *,
    amount: Optional[float] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    tx_type: str = "",
) -> dict[str, Any]:
    data = load_budget()
    found = _find_transaction(data, query, tx_type=tx_type)
    if found is None:
        return {"success": False, "message": "No encontre ese movimiento."}
    kind, tx = found
    if amount is not None:
        tx["amount"] = float(amount)
    if description is not None and description.strip():
        tx["description"] = description.strip()
        if kind == "expense":
            tx["category"] = category or detect_category(description)
    elif category is not None and kind == "expense":
        tx["category"] = category
    tx["updated_at"] = datetime.now().isoformat()
    _recalculate_balance(data)
    save_budget(data)
    return {"success": True, "type": kind, "transaction": tx, "balance": data["balance"]}


def reset_budget() -> dict[str, Any]:
    save_budget({"balance": 0.0, "income": [], "expenses": [], "budget_limit": 0.0})
    return {"success": True}


def parse_amount(text: str) -> Optional[float]:
    import re
    text = text.lower().replace(",", "")
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:pesos?|mxn)?",
        r"\$\s*(\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return float(m.group(1))
    return None


def summarize_budget() -> str:
    data = load_budget()
    total_in = sum(e["amount"] for e in data["income"])
    total_exp = sum(e["amount"] for e in data["expenses"])
    balance = data["balance"]
    limit = data.get("budget_limit", 0)
    
    parts = [f"Balance actual: ${balance:.2f}"]
    parts.append(f"Ingresos: ${total_in:.2f}")
    parts.append(f"Gastos: ${total_exp:.2f}")
    
    if limit > 0:
        remaining = limit - total_exp
        pct = (total_exp / limit) * 100
        parts.append(f"Presupuesto: ${limit:.2f} (${remaining:.2f} restantes, {pct:.1f}% usado)")
    
    by_cat = get_expenses_by_category()
    if by_cat:
        cats = ", ".join(f"{k}: ${v:.0f}" for k, v in sorted(by_cat.items(), key=lambda x: -x[1]))
        parts.append(f"Por categoría: {cats}")
    
    return " | ".join(parts)
