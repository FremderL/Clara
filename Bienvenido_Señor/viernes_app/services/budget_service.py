from __future__ import annotations

import re
from typing import Optional

from viernes_app.services.budget_data import (
    add_expense,
    add_income,
    delete_transaction,
    get_expenses_by_category,
    get_recent_transactions,
    parse_amount,
    reset_budget,
    set_budget_limit,
    summarize_budget,
    update_transaction,
)


def handle_budget_command(low: str, original: str) -> Optional[str]:
    if low in {"reiniciar presupuesto", "reset presupuesto", "limpiar presupuesto", "borrar presupuesto"}:
        reset_budget()
        return "Presupuesto reiniciado. Balance, ingresos, gastos y limite quedaron en cero."

    amount = parse_amount(original)
    actionish = any(word in low for word in ("agrega", "agregar", "anade", "añade", "registrar", "registra", "pon", "mete", "suma"))
    if amount is not None and "ingreso" in low and actionish:
        desc = re.sub(
            r"\b(agrega|agregar|anade|añade|registrar|registra|pon|mete|suma|el|la|al|a|presupuesto|como|ingreso|de|por|con)\b",
            " ",
            low,
        )
        desc = re.sub(r"\$?\d+(?:\.\d+)?", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip(" ,-") or "Ingreso"
        result = add_income(amount, desc)
        return f"Ingreso registrado. Balance actual: ${result['balance']:.2f}."

    if amount is not None and "gasto" in low and actionish:
        desc = re.sub(
            r"\b(agrega|agregar|anade|añade|registrar|registra|pon|mete|resta|el|la|al|a|presupuesto|como|gasto|de|por|con)\b",
            " ",
            low,
        )
        desc = re.sub(r"\$?\d+(?:\.\d+)?", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip(" ,-") or "Gasto"
        result = add_expense(amount, desc)
        return f"Gasto registrado en {result['category']}. Balance actual: ${result['balance']:.2f}."

    if low in {"balance", "presupuesto", "resumen de presupuesto", "mi presupuesto"}:
        return summarize_budget()

    if low.startswith("agregar ingreso ") or low.startswith("ingreso "):
        amount = parse_amount(original)
        if amount is None:
            return "No pude entender el monto del ingreso."
        desc = re.sub(r"^(agregar ingreso|ingreso)\s+", "", original, flags=re.IGNORECASE).strip()
        desc = re.sub(r"\$?\d+(?:\.\d+)?", "", desc).strip(" ,-") or "Ingreso"
        result = add_income(amount, desc)
        return f"Ingreso registrado. Balance actual: ${result['balance']:.2f}."

    if low.startswith("agregar gasto ") or low.startswith("gasto "):
        amount = parse_amount(original)
        if amount is None:
            return "No pude entender el monto del gasto."
        desc = re.sub(r"^(agregar gasto|gasto)\s+", "", original, flags=re.IGNORECASE).strip()
        desc = re.sub(r"\$?\d+(?:\.\d+)?", "", desc).strip(" ,-") or "Gasto"
        result = add_expense(amount, desc)
        return f"Gasto registrado en {result['category']}. Balance actual: ${result['balance']:.2f}."

    if low.startswith("establecer presupuesto ") or low.startswith("limite de presupuesto "):
        amount = parse_amount(original)
        if amount is None:
            return "No pude entender el limite del presupuesto."
        result = set_budget_limit(amount)
        return f"Listo. El limite de presupuesto ahora es ${result['budget_limit']:.2f}."

    if low.startswith(("eliminar ultimo gasto", "borrar ultimo gasto")):
        result = delete_transaction("ultimo", tx_type="expense")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese gasto."))
        tx = result["transaction"]
        return f"Elimine el gasto '{tx.get('description', 'Gasto')}'. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("eliminar ultimo ingreso", "borrar ultimo ingreso")):
        result = delete_transaction("ultimo", tx_type="income")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese ingreso."))
        tx = result["transaction"]
        return f"Elimine el ingreso '{tx.get('description', 'Ingreso')}'. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("eliminar gasto ", "borrar gasto ", "elimina gasto ", "borra gasto ")):
        query = re.sub(r"^(eliminar gasto|borrar gasto|elimina gasto|borra gasto)\s+", "", low).strip()
        result = delete_transaction(query, tx_type="expense")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese gasto."))
        tx = result["transaction"]
        return f"Elimine el gasto '{tx.get('description', 'Gasto')}'. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("eliminar ingreso ", "borrar ingreso ", "elimina ingreso ", "borra ingreso ")):
        query = re.sub(r"^(eliminar ingreso|borrar ingreso|elimina ingreso|borra ingreso)\s+", "", low).strip()
        result = delete_transaction(query, tx_type="income")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese ingreso."))
        tx = result["transaction"]
        return f"Elimine el ingreso '{tx.get('description', 'Ingreso')}'. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("eliminar movimiento ", "borrar movimiento ", "elimina movimiento ", "borra movimiento ")):
        query = re.sub(r"^(eliminar movimiento|borrar movimiento|elimina movimiento|borra movimiento)\s+", "", low).strip()
        result = delete_transaction(query)
        if not result.get("success"):
            return str(result.get("message", "No encontre ese movimiento."))
        tx = result["transaction"]
        return f"Elimine el movimiento '{tx.get('description', 'Movimiento')}'. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("corrige ultimo gasto", "modifica ultimo gasto", "cambia ultimo gasto")):
        amount = parse_amount(original)
        if amount is None:
            return "No pude entender el nuevo monto del gasto."
        result = update_transaction("ultimo", amount=amount, tx_type="expense")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese gasto."))
        return f"Gasto corregido. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("corrige ultimo ingreso", "modifica ultimo ingreso", "cambia ultimo ingreso")):
        amount = parse_amount(original)
        if amount is None:
            return "No pude entender el nuevo monto del ingreso."
        result = update_transaction("ultimo", amount=amount, tx_type="income")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese ingreso."))
        return f"Ingreso corregido. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("modificar gasto ", "modifica gasto ", "corrige gasto ", "cambia gasto ")):
        body = re.sub(r"^(modificar gasto|modifica gasto|corrige gasto|cambia gasto)\s+", "", low).strip()
        parts = re.split(r"\s+a\s+", body, maxsplit=1)
        query = parts[0].strip() or "ultimo"
        amount = parse_amount(parts[1] if len(parts) > 1 else original)
        if amount is None:
            return "No pude entender el nuevo monto del gasto."
        result = update_transaction(query, amount=amount, tx_type="expense")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese gasto."))
        return f"Gasto modificado. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("modificar ingreso ", "modifica ingreso ", "corrige ingreso ", "cambia ingreso ")):
        body = re.sub(r"^(modificar ingreso|modifica ingreso|corrige ingreso|cambia ingreso)\s+", "", low).strip()
        parts = re.split(r"\s+a\s+", body, maxsplit=1)
        query = parts[0].strip() or "ultimo"
        amount = parse_amount(parts[1] if len(parts) > 1 else original)
        if amount is None:
            return "No pude entender el nuevo monto del ingreso."
        result = update_transaction(query, amount=amount, tx_type="income")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese ingreso."))
        return f"Ingreso modificado. Balance actual: ${result['balance']:.2f}."

    if low.startswith(("renombrar gasto ", "renombra gasto ", "descripcion gasto ")):
        body = re.sub(r"^(renombrar gasto|renombra gasto|descripcion gasto)\s+", "", low).strip()
        parts = re.split(r"\s+a\s+|\s+como\s+", body, maxsplit=1)
        if len(parts) < 2:
            return "Diga por ejemplo: renombra gasto cafe a cafeteria."
        result = update_transaction(parts[0], description=parts[1], tx_type="expense")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese gasto."))
        return "Descripcion del gasto actualizada."

    if low.startswith(("renombrar ingreso ", "renombra ingreso ", "descripcion ingreso ")):
        body = re.sub(r"^(renombrar ingreso|renombra ingreso|descripcion ingreso)\s+", "", low).strip()
        parts = re.split(r"\s+a\s+|\s+como\s+", body, maxsplit=1)
        if len(parts) < 2:
            return "Diga por ejemplo: renombra ingreso beca a beca mensual."
        result = update_transaction(parts[0], description=parts[1], tx_type="income")
        if not result.get("success"):
            return str(result.get("message", "No encontre ese ingreso."))
        return "Descripcion del ingreso actualizada."

    if low in {"gastos por categoria", "categorias de gastos"}:
        by_cat = get_expenses_by_category()
        if not by_cat:
            return "Todavia no hay gastos registrados."
        return "Gastos por categoria: " + ", ".join(
            f"{cat}: ${amt:.2f}" for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1])
        )

    if low in {"movimientos", "transacciones", "ultimos movimientos"}:
        recent = get_recent_transactions()
        if not recent:
            return "Todavia no hay movimientos en el presupuesto."
        detail = []
        for item in recent[:8]:
            tx = item["transaction"]
            sign = "+" if item["type"] == "income" else "-"
            detail.append(f"{sign}${tx.get('amount', 0):.2f} {tx.get('description', '')}")
        return "Movimientos recientes: " + " | ".join(detail)

    return None
