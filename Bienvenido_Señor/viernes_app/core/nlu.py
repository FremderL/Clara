from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.lower().strip())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[¿?¡!.,;:\"'()]+", " ", value)
    value = re.sub(r"[^a-z0-9\s:/_\-+*%.=]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    reason: str
    slots: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class IntentRule:
    intent: str
    confidence: float
    reason: str
    patterns: tuple[str, ...]


class NaturalLanguageRouter:
    """Router local de intenciones claras antes de usar clasificadores difusos."""

    _rules: tuple[IntentRule, ...] = (
        IntentRule(
            "help",
            0.96,
            "peticion de capacidades",
            (
                r"\b(que|q)\s+(puedes|sabes)\s+hacer\b",
                r"\b(lista|ayuda|comandos|capacidades)\b",
                r"\b(muestrame|dime|ensename)\s+(tus\s+)?(comandos|capacidades)\b",
            ),
        ),
        IntentRule(
            "history",
            0.96,
            "consulta de memoria conversacional",
            (
                r"\b(historial|conversaciones anteriores)\b",
                r"\bque\s+(hemos|hemos estado)\s+hablado\b",
                r"\bultimo\s+historial\b",
            ),
        ),
        IntentRule(
            "today_status",
            0.93,
            "consulta general del dia",
            (
                r"\b(resumen|estado|informe)\s+(del\s+dia|de\s+hoy)\b",
                r"\bcomo\s+va\s+mi\s+dia\b",
                r"\bque\s+tengo\s+hoy\b",
                r"^hoy$",
            ),
        ),
        IntentRule(
            "next_commitment",
            0.94,
            "consulta del siguiente pendiente",
            (
                r"\bque\s+(sigue|viene|toca)(\s+hoy|\s+ahora)?\b",
                r"\b(siguiente|proximo)\s+(pendiente|evento|compromiso)\b",
                r"\bque\s+hay\s+despues\b",
            ),
        ),
        IntentRule(
            "morning_brief",
            0.94,
            "resumen matutino",
            (
                r"\b(briefing|informe matutino|resumen matutino)\b",
                r"\b(rutina|reporte)\s+de\s+la\s+manana\b",
                r"\barranca\s+mi\s+dia\b",
            ),
        ),
        IntentRule(
            "smart_daily_brief",
            0.95,
            "briefing diario inteligente",
            (
                r"\bbriefing\s+(inteligente|diario|operativo)\b",
                r"\binforme\s+(inteligente|operativo)\s+(del\s+dia|de\s+hoy|de\s+manana)?\b",
                r"\bresumen\s+(inteligente|operativo)\s+(del\s+dia|de\s+hoy|de\s+manana)?\b",
                r"\barranca\s+mi\s+dia\b",
            ),
        ),
        IntentRule(
            "agenda_full",
            0.93,
            "consulta de agenda completa",
            (
                r"\b(mi|toda\s+mi)\s+agenda\b",
                r"\bagenda\s+(completa|entera)\b",
                r"\b(muestra|ver|revisa)\s+(toda\s+)?(mi\s+)?agenda\b",
            ),
        ),
        IntentRule(
            "cleanup_past_events",
            0.94,
            "limpieza de eventos pasados",
            (
                r"\b(limpia|limpiar|borra|borrar|elimina|eliminar)\s+(la\s+)?agenda\b",
                r"\b(limpia|borra|elimina)\s+(eventos|pendientes)\s+(pasados|viejos)\b",
                r"\bquita\s+lo\s+viejo\s+de\s+la\s+agenda\b",
            ),
        ),
        IntentRule(
            "weather",
            0.94,
            "consulta del clima",
            (
                r"\b(clima|temperatura|pronostico)\b",
                r"\bva\s+a\s+llover\b",
                r"\bcomo\s+esta\s+el\s+tiempo\b",
            ),
        ),
        IntentRule(
            "news",
            0.93,
            "consulta de noticias",
            (
                r"\b(noticias|titulares|novedades)\b",
                r"\bque\s+esta\s+pasando\b",
                r"\bresumen\s+de\s+noticias\b",
            ),
        ),
        IntentRule(
            "budget_summary",
            0.93,
            "consulta de presupuesto",
            (
                r"\b(presupuesto|balance)\b",
                r"\bcuanto\s+(dinero\s+)?tengo\b",
                r"\bcomo\s+voy\s+de\s+(dinero|gastos)\b",
            ),
        ),
        IntentRule(
            "habits_stats",
            0.92,
            "consulta de estadisticas de uso",
            (
                r"\b(mis\s+)?estadisticas\b",
                r"\bque\s+tanto\s+me\s+usas\b",
                r"\bmis\s+habitos\b",
            ),
        ),
        IntentRule(
            "habits_recommendations",
            0.92,
            "recomendaciones de habitos",
            (
                r"\b(recomendaciones|recomendaciones\s+de\s+habitos)\b",
                r"\b(corrige|mejora|ayudame\s+con)\s+mis\s+habitos\b",
                r"\bque\s+habitos\s+debo\s+mejorar\b",
            ),
        ),
        IntentRule(
            "habits_update",
            0.94,
            "actualizacion de resumen de habitos local",
            (
                r"\b(actualiza|entrena|mejora)\s+(tu\s+)?(cerebro|red\s+neuronal)\b",
                r"\b(autoactualizate|aprende\s+de\s+mis\s+habitos|aprende\s+de\s+mi)\b",
            ),
        ),
        IntentRule(
            "alias_suggestions",
            0.94,
            "sugerencias de alias",
            (
                r"\b(alias|atajos)\s+sugeridos\b",
                r"\bsugerencias\s+de\s+(alias|atajos|comandos)\b",
                r"\b(comandos|frases)\s+frecuentes\b",
                r"\bque\s+(alias|atajos)\s+puedo\s+usar\b",
            ),
        ),
        IntentRule(
            "proactive_suggestions",
            0.94,
            "sugerencias proactivas",
            (
                r"\bque\s+me\s+(sugieres|recomiendas)(\s+(ahora|hoy))?\b",
                r"\b(sugerencias|recomendaciones)\s+(ahora|operativas|de\s+contexto)\b",
                r"\brevisa(r)?\s+(mi\s+)?contexto\b",
            ),
        ),
        IntentRule(
            "proactive_mode",
            0.95,
            "cambio de modo proactivo",
            (
                r"\bmodo\s+proactivo\s+(conservador|conservadora|normal|apagado|activo|activado)\b",
                r"\b(activa|activar|desactiva|desactivar|enciende)\s+(el\s+)?modo\s+proactivo\b",
            ),
        ),
        IntentRule(
            "memory_remember",
            0.97,
            "memoria explicita",
            (
                r"^recuerda\s+que\s+.+",
                r"^recuerdame\s+que\s+.+",
                r"^aprende\s+que\s+.+",
                r"^guarda\s+en\s+memoria\s+que\s+.+",
                r"^memoriza\s+que\s+.+",
                r"^recuerda\s+esto\s*:?\s+.+",
            ),
        ),
        IntentRule(
            "memory_search",
            0.96,
            "busqueda contextual de memoria",
            (
                r"^que\s+recuerdas\s+(sobre|de)\s+.+",
                r"^(busca|buscar)\s+en\s+memoria\s+.+",
                r"^memoria\s+sobre\s+.+",
            ),
        ),
        IntentRule(
            "memory_query",
            0.95,
            "consulta de memoria personal",
            (
                r"\bque\s+sabes\s+de\s+mi\b",
                r"\b(mi\s+perfil|perfil\s+personal|memoria\s+personal)\b",
            ),
        ),
        IntentRule(
            "memory_forget",
            0.95,
            "olvido de memoria personal",
            (
                r"^olvida\s+que\s+.+",
                r"^borra\s+de\s+memoria\s+.+",
                r"^olvida\s+de\s+mi\s+.+",
            ),
        ),
        IntentRule(
            "memory_update",
            0.93,
            "actualizacion de perfil personal",
            (
                r"\bactualiza\s+(mi\s+)?perfil\b",
                r"\bactualiza\s+(mi\s+)?memoria\s+personal\b",
            ),
        ),
        IntentRule(
            "memory_preferences_query",
            0.95,
            "consulta de preferencias personales",
            (
                r"\bmis\s+preferencias\b",
                r"\bque\s+preferencias\s+(tienes|sabes)\b",
                r"\bpreferencias\s+personales\b",
            ),
        ),
        IntentRule(
            "memory_preference_set",
            0.96,
            "actualizacion de preferencia personal",
            (
                r"\bactualiza\s+mi\s+preferencia\s+de\s+.+",
                r"\bguarda\s+mi\s+preferencia\s+de\s+.+",
                r"\bmi\s+preferencia\s+de\s+.+\s+es\s+.+",
                r"^prefiero\s+que\s+me\s+respondas\s+.+",
                r"^prefiero\s+respuestas?\s+.+",
            ),
        ),
        IntentRule(
            "memory_preference_forget",
            0.94,
            "olvido de preferencia personal",
            (
                r"\b(olvida|borra|elimina)\s+(mi\s+)?preferencia\s+.+",
            ),
        ),
        IntentRule(
            "personal_rule_create",
            0.96,
            "creacion de regla personal",
            (
                r"\b(cuando|cuando\s+sea|si\s+es|los|el)\b.*\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b.*\brecuerdame\b",
                r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b.*\brecuerdame\b",
            ),
        ),
        IntentRule(
            "personal_rule_list",
            0.94,
            "consulta de reglas personales",
            (
                r"\b(reglas\s+personales|mis\s+reglas|ver\s+reglas\s+personales)\b",
            ),
        ),
        IntentRule(
            "personal_rule_forget",
            0.94,
            "olvido de regla personal",
            (
                r"^(olvida|borra|elimina)\s+regla\s+.+",
            ),
        ),
        IntentRule(
            "activity_week",
            0.95,
            "calendario operativo semanal",
            (
                r"\b(plan|calendario)\s+semanal\b",
                r"\bmi\s+semana\b",
                r"\bsemana\s+operativa\b",
                r"\bplan\s+de\s+la\s+semana\b",
                r"\bproximos\s+(dias|7\s+dias)\b",
            ),
        ),
        IntentRule(
            "activity_calendar",
            0.94,
            "calendario operativo",
            (
                r"\b(plan|calendario|actividad)\s+de\s+hoy\b",
                r"\bmi\s+calendario\b",
                r"\bplan\s+de\s+manana\b",
                r"\bcalendario\s+de\s+manana\b",
            ),
        ),
        IntentRule(
            "activity_next",
            0.94,
            "siguiente bloque operativo",
            (
                r"\bque\s+toca\s+despues\b",
                r"\bque\s+sigue\s+despues\b",
                r"\b(siguiente|proxima)\s+(bloque|actividad)\b",
            ),
        ),
        IntentRule(
            "activity_reorganize",
            0.94,
            "reorganizacion del dia",
            (
                r"\b(reorganiza|organiza|acomoda)\s+mi\s+dia\b",
                r"\b(planifica|reordena)\s+mi\s+dia\b",
                r"\b(reorganiza|organiza|acomoda|planifica|reordena)\s+(hoy|manana)\b",
            ),
        ),
        IntentRule(
            "weekly_goals",
            0.94,
            "objetivos semanales",
            (
                r"\bobjetivos\s+de\s+la\s+semana\b",
                r"\bmetas\s+semanales\b",
                r"\bque\s+objetivos\s+tengo\b",
            ),
        ),
        IntentRule(
            "day_progress",
            0.94,
            "avance del dia",
            (
                r"\bavance\s+de\s+hoy\b",
                r"\bcomo\s+voy\s+hoy\b",
                r"\bprogreso\s+del\s+dia\b",
            ),
        ),
        IntentRule(
            "day_close",
            0.95,
            "cierre del dia",
            (
                r"\bcerrar\s+mi\s+dia\b",
                r"\bcierra\s+mi\s+dia\b",
                r"\bprepara\s+mi\s+cierre\b",
            ),
        ),
        IntentRule(
            "prepare_tomorrow",
            0.95,
            "preparacion de manana",
            (
                r"\bprepara\s+manana\b",
                r"\bpreparar\s+manana\b",
                r"\bprepara\s+mi\s+manana\b",
                r"\bprepara\s+el\s+dia\s+de\s+manana\b",
            ),
        ),
        IntentRule(
            "pending_tasks_list",
            0.96,
            "consulta de pendientes abiertos",
            (
                r"\bque\s+tengo\s+pendiente(s)?\b",
                r"\b(mis\s+)?pendientes\b",
                r"\b(tareas|compromisos)\s+pendientes\b",
                r"\b(lista|listar|muestra|mostrar|ver|consulta)\s+(mis\s+)?(pendientes|tareas|compromisos)\b",
            ),
        ),
        IntentRule(
            "pending_tasks_today",
            0.97,
            "consulta de pendientes del dia",
            (
                r"\b(pendientes|tareas|compromisos)\s+de\s+hoy\b",
                r"\b(pendientes|tareas|compromisos)\s+para\s+hoy\b",
                r"\b(pendientes|tareas|compromisos)\s+de\s+manana\b",
                r"\b(pendientes|tareas|compromisos)\s+para\s+manana\b",
            ),
        ),
        IntentRule(
            "clarify_action",
            0.86,
            "peticion util pero ambigua",
            (
                (
                    r"\b(tengo|hay|me\s+toca|se\s+viene)\b.*"
                    r"\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b.*"
                    r"\b(ingles|poo|clase|clases|entrega|examen|tarea|proyecto|trabajo|reunion|cita|importante)\b"
                ),
                (
                    r"\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b.*"
                    r"\b(tengo|hay|me\s+toca|se\s+viene|algo|lo\s+de)\b.*"
                    r"\b(ingles|poo|clase|clases|entrega|examen|tarea|proyecto|trabajo|reunion|cita|importante)\b"
                ),
            ),
        ),
        IntentRule(
            "action_undo",
            0.97,
            "reversion de ultima accion",
            (
                r"\b(deshaz|deshacer|revierte|revertir)\s+(eso|ultimo|lo\s+ultimo|ultima\s+accion|ultimo\s+plan)\b",
                r"^undo$",
            ),
        ),
        IntentRule(
            "action_history",
            0.96,
            "historial de acciones",
            (
                r"\bque\s+(cambiaste|cambios\s+hiciste)\b",
                r"\b(historial|registro)\s+de\s+acciones\b",
                r"\b(muestrame|mostrar|ver)\s+acciones\s+recientes\b",
                r"\bacciones\s+recientes\b",
            ),
        ),
        IntentRule(
            "wake_schedule_change",
            0.995,
            "cambio de horario de autoarranque y rutina matutina",
            (
                (
                    r"\b(cambia|cambiar|cambiale|modifica|modificar|ajusta|ajustar|mueve|mover|"
                    r"programa|programar|pon|poner|deja|dejar|actualiza|actualizar)\b.*"
                    r"\b(autoarranque|despertar|rutina\s+de\s+la\s+manana|rutina\s+matutina)\b.*"
                    r"\b(a\s+las\s+\d{1,2}(?:\s+\d{2})?(?:\s*(?:am|pm))?|\d{1,2}\s+\d{2})\b"
                ),
                (
                    r"\b(cambia|cambiar|cambiale|modifica|modificar|ajusta|ajustar|mueve|mover|"
                    r"programa|programar|pon|poner|deja|dejar|actualiza|actualizar)\b.*"
                    r"\b(hora|horario)\b.*"
                    r"\b(autoarranque|despertar|rutina\s+de\s+la\s+manana|rutina\s+matutina)\b"
                ),
                r"\b(programa|programar)\s+despertar\s+a\s+las\s+\d{1,2}(?:\s+\d{2})?\b",
            ),
        ),
        IntentRule(
            "wake_schedule_query",
            0.98,
            "consulta de horario de autoarranque y rutina matutina",
            (
                r"\ba\s+que\s+hora\b.*\b(autoarranque|despertar|rutina\s+de\s+la\s+manana|rutina\s+matutina)\b",
                r"\b(autoarranque|despertar|rutina\s+de\s+la\s+manana|rutina\s+matutina)\b.*\b(hora|horario|configurado|iniciara|inicia|ejecutara|programado)\b",
                r"\b(hora|horario)\b.*\b(autoarranque|despertar|rutina\s+de\s+la\s+manana|rutina\s+matutina)\b",
            ),
        ),
        IntentRule(
            "proactive_feedback",
            0.96,
            "feedback de proactividad",
            (
                r"\bbuena\s+sugerencia\b",
                r"\bmuy\s+buena\s+sugerencia\b",
                r"\besa\s+sugerencia\s+(sirve|no\s+sirve)\b",
                r"\bmala\s+sugerencia\b",
                r"\bno\s+me\s+recuerdes\s+eso\b",
                r"\bno\s+(me\s+)?sugieras\s+esto\b",
                r"\brecuerdame\s+esto\s+mas\s+seguido\b",
                r"\bsugiere\s+mas\s+de\s+esto\b",
            ),
        ),
        IntentRule(
            "proactive_status",
            0.94,
            "estado de proactividad",
            (
                r"\bestado\s+proactivo\b",
            ),
        ),
        IntentRule(
            "proactive_explain",
            0.94,
            "explicacion de sugerencia proactiva",
            (
                r"\bpor\s+que\s+sugeriste\s+eso\b",
                r"\bpor\s+que\s+me\s+sugeriste\s+eso\b",
                r"\bexplica\s+(la\s+)?sugerencia\b",
            ),
        ),
        IntentRule(
            "intelligent_status",
            0.94,
            "estado inteligente",
            (
                r"\bestado\s+inteligente\b",
                r"\bdashboard\s+inteligente\b",
                r"\bmodo\s+inteligente\b",
            ),
        ),
        IntentRule(
            "decision_explain",
            0.97,
            "explicacion de ultima decision",
            (
                r"\bexplica\s+por\s+que\s+entendiste\s+eso\b",
                r"\bpor\s+que\s+entendiste\s+eso\b",
                r"\bque\s+entendiste\s+del\s+comando\b",
            ),
        ),
        IntentRule(
            "command_dry_run",
            0.98,
            "simulacion de comando",
            (
                r"^probar\s+comando\s+.+",
                r"^simula\s+comando\s+.+",
                r"^prueba\s+sin\s+ejecutar\s+.+",
            ),
        ),
        IntentRule(
            "command_audit",
            0.99,
            "auditoria de comandos",
            (
                r"\baudita\s+comandos\b",
                r"\bauditoria\s+de\s+comandos\b",
                r"\brevisa\s+entendimiento\s+de\s+comandos\b",
            ),
        ),
        IntentRule(
            "action_plan",
            0.9,
            "plan para peticion no programada",
            (
                r"\b(ayudame|organiza|organizame|planea|prepara|preparame|reorganiza|acomoda|necesito|agenda|agendame|recuerdame)\b.*\b(clase|clases|agenda|rutina|salida|salir|manana|hoy|ingles|temprano|entrega|estudiar|estudio|recordatorio|maleta|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b",
                r"\b(clase|clases|agenda|rutina|salida|salir|manana|hoy|ingles|temprano|entrega|estudiar|estudio|recordatorio|maleta|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b.*\b(ayudame|organiza|organizame|planea|prepara|preparame|reorganiza|acomoda|necesito|agenda|agendame|recuerdame)\b",
                r"\b(ayudame|organiza|preparame)\b.*\b(abre|abrir|investiga|busca|consulta|aprende\s+sobre)\b",
                r"\b(ayudame|prepara|preparame|guarda|guardar|memoriza|recordar)\b.*\b(memoria|perfil|preferencia|prefiero)\b",
                r"\b(ayudame|prepara|preparame|avisame|avisar|notifica|notificarme|manda|mandame|envia|enviame)\b.*\b(telegram|notificacion|aviso|mensaje)\b",
                r"\b(tengo\s+que|hay\s+que|debo)\b.+",
                r"\b(crea|crear|agrega|agregar|anota|apunta)\b.*\b(pendiente|tarea|compromiso)\b",
                r"\b(ya\s+hice|ya\s+termine|complete|completa|marca)\b.*\b(pendiente|tarea|compromiso|esto|eso)\b",
                r"\b(pospon|posponer|posponme|mueve|pasa|aplaza)\b.*\b(pendiente|tarea|compromiso|esto|eso)\b",
                r"\b(cancela|cancelar|elimina|eliminar|borra|borrar)\b.*\b(pendiente|tarea|compromiso)\b",
            ),
        ),
        IntentRule(
            "classes_today",
            0.93,
            "consulta de clases del dia",
            (
                r"\b(clases|materias)\s+(de\s+)?hoy\b",
                r"\bque\s+(clases|materias)\s+(me\s+)?(tengo|tocan)\b",
                r"\bhorario\s+de\s+clases\b",
                r"\bhorario\s+de\s+hoy\b",
                r"\bmi\s+horario\s+de\s+hoy\b",
            ),
        ),
        IntentRule(
            "classes_overview",
            0.91,
            "consulta de clases semanales",
            (
                r"\b(mis|ver|mostrar)\s+clases\b",
                r"\bhorario\s+semanal\b",
                r"\bque\s+clases\s+tengo\b",
            ),
        ),
        IntentRule(
            "classes_cancelled_today",
            0.96,
            "cancelacion de clases del dia",
            (
                r"\b(me\s+)?cancelaron\s+(las\s+)?clases\s+hoy\b",
                r"\bhoy\s+(me\s+)?cancelaron\s+(las\s+)?clases\b",
                r"\bhoy\s+(no\s+hay|no\s+tengo|se\s+cancelaron)\s+clases\b",
                r"\b(cancela|marca)\s+(las\s+)?clases\s+(de\s+)?hoy\b",
            ),
        ),
        IntentRule(
            "classes_change",
            0.975,
            "cambio de horario o clases",
            (
                (
                    r"\b(cambia|cambiar|modifica|modificar|reemplaza|reemplazar|actualiza|actualizar|pon|poner)\b.*"
                    r"\b(horario\s+de\s+clases|clase|clases|materia|materias)\b"
                ),
                (
                    r"\b(horario\s+de\s+clases|clase|clases|materia|materias)\b.*"
                    r"\b(cambia|modifica|reemplaza|actualiza|pon)\b"
                ),
            ),
        ),
        IntentRule(
            "free_day_today",
            0.95,
            "dia libre",
            (
                r"\b(dia\s+libre|libre)\s+hoy\b",
                r"\bhoy\s+(tengo\s+)?dia\s+libre\b",
                r"\bmarca\s+hoy\s+como\s+(libre|dia\s+libre)\b",
                r"\bno\s+voy\s+a\s+(la\s+)?(uni|universidad|escuela)\s+hoy\b",
            ),
        ),
        IntentRule(
            "mark_arrival",
            0.95,
            "confirmacion de llegada",
            (
                r"\b(ya\s+)?llegue\b",
                r"\bestoy\s+en\s+casa\b",
                r"\bmarca(r)?\s+(mi\s+)?llegada\b",
                r"\bacabo\s+de\s+llegar\b",
            ),
        ),
        IntentRule(
            "mark_left_home",
            0.95,
            "confirmacion de salida",
            (
                r"\b(ya\s+)?sali\b",
                r"\bvoy\s+saliendo\b",
                r"\bya\s+me\s+fui\b",
                r"\bmarca(r)?\s+(mi\s+)?salida\b",
            ),
        ),
        IntentRule(
            "mark_bath_done",
            0.95,
            "confirmacion de bano",
            (
                r"\b(ya\s+)?me\s+bane\b",
                r"\b(ya\s+)?me\s+banie\b",
                r"\bbano\s+(hecho|listo)\b",
                r"\bmarca(r)?\s+(el\s+)?bano\b",
            ),
        ),
        IntentRule(
            "routine_slot_change",
            0.965,
            "cambio de hora de rutina",
            (
                (
                    r"\b(cambia|cambiar|modifica|modificar|ajusta|ajustar|mueve|mover|pon|poner|actualiza|actualizar)\b.*"
                    r"\b(rutina|recordatorio\s+rutina)\b.*"
                    r"\b(desayuno|desayunar|preparacion|prepararse|salida|salir|bano|banarse|maleta|deberes|pendientes|tareas)\b.*"
                    r"\ba\s+las\s+\d{1,2}(?:\s+\d{2})?\b"
                ),
            ),
        ),
        IntentRule(
            "routine_slot_query",
            0.93,
            "consulta de hora de rutina",
            (
                (
                    r"\b(a\s+que\s+hora|hora|horario)\b.*"
                    r"\b(rutina|recordatorio\s+rutina)\b.*"
                    r"\b(desayuno|desayunar|preparacion|prepararse|salida|salir|bano|banarse|maleta|deberes|pendientes|tareas)\b"
                ),
            ),
        ),
        IntentRule(
            "routine_timeline",
            0.92,
            "consulta de rutina",
            (
                r"\b(ver|muestra|mostrar|revisa)\s+(mi\s+)?rutina\b",
                r"\b(rutina\s+semanal|linea\s+de\s+rutina|mis\s+rutinas)\b",
            ),
        ),
        IntentRule(
            "leave_time_query",
            0.96,
            "consulta de salida",
            (
                r"\b(horario|hora)\s+de\s+salida\b",
                r"\b(a\s+que\s+hora|cuando)\s+(salgo|salir|salimos)\b",
                r"\bcuando\s+es\s+mi\s+salida\b",
                r"\bcual\s+es\s+(mi\s+)?salida\b",
            ),
        ),
        IntentRule(
            "leave_time_change",
            0.97,
            "cambio de salida",
            (
                (
                    r"\b(cambia|cambiar|modifica|modificar|ajusta|ajustar|mueve|mover|pon|deja)\b.*"
                    r"\b((horario|hora)\s+de\s+salida|salida|salir)\b"
                ),
                (
                    r"\b((horario|hora)\s+de\s+salida|salida)\b.*"
                    r"\b(cambia|modifica|ajusta|mueve|pon|deja)\b"
                ),
            ),
        ),
        IntentRule(
            "voice_status",
            0.91,
            "estado de voz",
            (
                r"\b(estado|estatus)\s+de\s+(voz|microfono)\b",
                r"\bvoz\s+(estado|estatus)\b",
                r"\besta\s+activo\s+el\s+microfono\b",
            ),
        ),
        IntentRule(
            "telegram_activate",
            0.94,
            "activacion de telegram",
            (
                r"\bactivar\s+telegram\b",
                r"\bactiva\s+telegram\b",
                r"\bconfigurar\s+telegram\b",
            ),
        ),
        IntentRule(
            "telegram_test",
            0.94,
            "prueba de telegram",
            (
                r"\bprobar\s+telegram\b",
                r"\bprueba\s+telegram\b",
            ),
        ),
        IntentRule(
            "telegram_notify",
            0.93,
            "notificacion por telegram",
            (
                r"\bnotificarme\s+por\s+telegram\b",
                r"\bavisame\s+por\s+telegram\b",
            ),
        ),
        IntentRule(
            "wake_energy_diagnostic",
            0.95,
            "diagnostico de energia y bloqueo",
            (
                r"\bdiagnostico\s+(de\s+)?energia\b",
                r"\benergia\s+y\s+bloqueo\b",
                r"\bestado\s+energia\b",
            ),
        ),
        IntentRule(
            "wake_test_schedule",
            0.96,
            "prueba programada de despertar",
            (
                r"\bprobar\s+despertar\s+en\s+2\s+minutos\b",
                r"\bprueba\s+despertar\s+en\s+2\s+minutos\b",
                r"\bprobar\s+despertar\s+dos\s+minutos\b",
            ),
        ),
        IntentRule(
            "wake_repair",
            0.95,
            "reparacion de despertar",
            (
                r"\breparar\s+despertar\b",
                r"\breparar\s+autoarranque\b",
                r"\breparar\s+despertar\s+seguro\b",
            ),
        ),
        IntentRule(
            "wake_status",
            0.91,
            "diagnostico de despertar",
            (
                r"\b(verificar|diagnostico|revisar)\s+despertar\b",
                r"\bmodo\s+residente\b",
                r"\btarea\s+programada\b",
            ),
        ),
    )

    def classify(self, text: str) -> IntentResult | None:
        low = normalize(text)
        if not low:
            return None
        if low.startswith("/cmd "):
            return self._result("registered_command", 1.0, "comando explicito", low)
        game = self._game_result(low)
        if game is not None:
            return game
        if self._looks_like_math(low):
            return self._result("math", 0.94, "expresion matematica", low)
        if self._looks_like_open_app(low):
            return self._result("open_app", 0.93, "apertura de aplicacion", low)
        analysis = self._analysis_result(low)
        if analysis is not None:
            return analysis
        if self._looks_like_research(low):
            return self._result("research", 0.92, "consulta de investigacion", low)

        candidates = [
            self._result(rule.intent, rule.confidence, rule.reason, low, pattern)
            for rule in self._rules
            for pattern in rule.patterns
            if re.search(pattern, low)
        ]
        candidates = self._filter_conflicts(low, candidates)
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.confidence)

    def _filter_conflicts(self, low: str, candidates: list[IntentResult]) -> list[IntentResult]:
        if "salida" in low or re.search(r"\b(salir|salgo|salimos)\b", low):
            candidates = [item for item in candidates if item.intent not in {"classes_today", "classes_overview"}]
        if re.search(r"\b(clases|materias)\b", low):
            candidates = [
                item for item in candidates if item.intent not in {"leave_time_query", "leave_time_change"}
            ]
        if re.search(r"\b(cambia|modifica|ajusta|mueve|pon|deja)\b", low):
            candidates = [item for item in candidates if item.intent not in {"leave_time_query"}]
        if re.search(r"\b(cambia|cambiar|modifica|modificar|reemplaza|reemplazar|actualiza|actualizar|pon|poner)\b", low) and re.search(
            r"\b(horario\s+de\s+clases|clase|clases|materia|materias)\b",
            low,
        ):
            candidates = [item for item in candidates if item.intent not in {"classes_today", "classes_overview"}]
        if re.search(r"\b(cambia|cambiar|modifica|modificar|ajusta|ajustar|mueve|mover|programa|programar|pon|poner|deja|dejar|actualiza|actualizar)\b", low) and re.search(
            r"\b(autoarranque|despertar|rutina\s+de\s+la\s+manana|rutina\s+matutina)\b",
            low,
        ):
            candidates = [item for item in candidates if item.intent not in {"wake_schedule_query"}]
        return candidates

    def _result(
        self,
        intent: str,
        confidence: float,
        reason: str,
        low: str,
        pattern: str = "",
    ) -> IntentResult:
        slots = self._extract_slots(intent, low)
        if pattern:
            slots["pattern"] = pattern
        return IntentResult(intent, confidence, reason, slots)

    def _extract_slots(self, intent: str, low: str) -> dict[str, str]:
        slots: dict[str, str] = {}
        time_value = self._extract_time(low)
        if time_value:
            slots["time"] = time_value
        date_ref = self._extract_date_ref(low)
        if date_ref:
            slots["date_ref"] = date_ref
        weekday = self._extract_weekday(low)
        if weekday:
            slots["weekday"] = weekday
        if intent == "open_app":
            app = self._strip_open_app_prefix(low)
            if app:
                slots["app"] = app
        elif intent == "research":
            query = self._strip_research_prefix(low)
            if query:
                slots["query"] = query
        elif intent in {"simulation_request", "research_table", "chart_request", "analysis_report"}:
            query = self._strip_analysis_prefix(low, intent)
            if query:
                slots["query"] = query
        elif intent == "game_command":
            slots["game_text"] = low
        elif intent == "math":
            expression = self._strip_math_prefix(low)
            if expression:
                slots["expression"] = expression
        elif intent == "proactive_mode":
            mode = self._extract_proactive_mode(low)
            if mode:
                slots["mode"] = mode
        elif intent == "memory_remember":
            text = re.sub(r"^(recuerda|recuerdame|aprende|guarda\s+en\s+memoria|memoriza)\s+que\s+", "", low).strip()
            text = re.sub(r"^recuerda\s+esto\s*:?\s*", "", text).strip()
            slots["memory_text"] = text
        elif intent == "memory_search":
            slots["memory_query"] = re.sub(r"^(que\s+recuerdas\s+(sobre|de)|busca\s+en\s+memoria|buscar\s+en\s+memoria|memoria\s+sobre)\s+", "", low).strip()
        elif intent == "memory_forget":
            slots["memory_query"] = re.sub(r"^(olvida que|borra de memoria|olvida de mi)\s+", "", low).strip()
        elif intent == "memory_preference_set":
            key, value = self._extract_preference(low)
            if key:
                slots["preference_key"] = key
            if value:
                slots["preference_value"] = value
        elif intent == "memory_preference_forget":
            slots["preference_query"] = re.sub(r"^.*?\bpreferencia\b", "", low).strip()
        elif intent == "proactive_feedback":
            slots["feedback"] = self._extract_proactive_feedback(low)
        return slots

    def _extract_preference(self, low: str) -> tuple[str, str]:
        match = re.search(r"\bpreferencia\s+de\s+(.+?)\s+(?:es|a|como)\s+(.+)$", low)
        if match:
            return match.group(1).strip(" ,-"), match.group(2).strip(" ,-")
        match = re.search(r"\bactualiza\s+mi\s+preferencia\s+de\s+(.+?)\s+a\s+(.+)$", low)
        if match:
            return match.group(1).strip(" ,-"), match.group(2).strip(" ,-")
        match = re.search(r"\bguarda\s+mi\s+preferencia\s+de\s+(.+?)\s+(?:como|a)\s+(.+)$", low)
        if match:
            return match.group(1).strip(" ,-"), match.group(2).strip(" ,-")
        match = re.search(r"^prefiero\s+que\s+me\s+respondas\s+(.+)$", low)
        if match:
            return "respuesta", match.group(1).strip(" ,-")
        match = re.search(r"^prefiero\s+respuestas?\s+(.+)$", low)
        if match:
            return "respuesta", match.group(1).strip(" ,-")
        return "", ""

    def _extract_proactive_mode(self, low: str) -> str:
        if "apagado" in low or "desactiva" in low or "desactivar" in low:
            return "off"
        if "normal" in low:
            return "normal"
        if "conservador" in low or "conservadora" in low:
            return "conservative"
        if "activo" in low or "activado" in low or "activa" in low or "activar" in low or "enciende" in low:
            return "on"
        return ""

    def _extract_proactive_feedback(self, low: str) -> str:
        if "no me recuerdes" in low:
            return "pause"
        if "no sugieras" in low or "no me sugieras" in low:
            return "pause"
        if "mas seguido" in low:
            return "more"
        if "sugiere mas" in low:
            return "more"
        if "no sirve" in low or "mala sugerencia" in low:
            return "negative"
        if "buena sugerencia" in low or "sirve" in low:
            return "positive"
        return ""

    def _extract_time(self, low: str) -> str:
        match = re.search(r"\b(\d{1,2}):(\d{2})\b", low)
        if match:
            hh, mm = int(match.group(1)), int(match.group(2))
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return f"{hh:02d}:{mm:02d}"
        match = re.search(r"\ba\s+las\s+(\d{1,2})(?:\s+(\d{2}))?\b", low)
        if not match:
            return ""
        hh = int(match.group(1))
        raw_mm = match.group(2)
        mm = int(raw_mm) if raw_mm else 0
        if not 0 <= mm <= 59:
            return ""
        if ("pm" in low or "tarde" in low or "noche" in low) and hh < 12:
            hh += 12
        if 0 <= hh <= 23:
            return f"{hh:02d}:{mm:02d}"
        return ""

    def _extract_date_ref(self, low: str) -> str:
        date_low = re.sub(r"\b(de|por|en)\s+la\s+manana\b", " ", low)
        if "hoy" in date_low:
            return "hoy"
        if "manana" in date_low:
            return "manana"
        match = re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", date_low)
        if match:
            return match.group(0)
        match = re.search(r"\b\d{1,2}\s+de\s+[a-z]+(?:\s+de\s+\d{4})?\b", date_low)
        if match:
            return match.group(0)
        return ""

    def _extract_weekday(self, low: str) -> str:
        match = re.search(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", low)
        return match.group(1) if match else ""

    def _strip_open_app_prefix(self, low: str) -> str:
        app = re.sub(
            r"^(abre|abrir|inicia|ejecuta|lanza|quiero abrir|necesito abrir|abre la app|abre la aplicacion|abre el programa)\s+",
            "",
            low,
            count=1,
        )
        return app.strip(" ,-")

    def _strip_research_prefix(self, low: str) -> str:
        query = re.sub(
            r"^(investiga|investigar|busca|buscar|busca en la web|buscar en la web|busca en internet|buscar en internet|investiga en la web|consulta|consulta en internet|aprende sobre)\s+",
            "",
            low,
            count=1,
        )
        query = re.sub(r"^(en\s+)?(internet|la\s+web|web)\s+", "", query)
        return query.strip(" ,-")

    def _strip_analysis_prefix(self, low: str, intent: str) -> str:
        if intent == "simulation_request":
            query = re.sub(r"^(simula|simular|analiza\s+escenario|escenario|que\s+pasaria\s+si)\s+", "", low, count=1)
            return query.strip(" ,-")
        if intent == "research_table":
            query = self._strip_research_prefix(low)
            query = re.sub(r"\b(y\s+)?(haz|hacer|crea|crear|genera|generar)\s+(una\s+)?tabla\b", " ", query)
            query = re.sub(r"\b(en\s+)?tabla\b", " ", query)
            return re.sub(r"\s+", " ", query).strip(" ,-")
        if intent == "chart_request":
            query = re.sub(r"^(haz|hacer|crea|crear|genera|generar|muestra|mostrar)\s+(una\s+)?(grafica|grafico|chart)\s+(de|sobre)?\s*", "", low, count=1)
            query = re.sub(r"^(grafica|grafico|chart)\s+(de|sobre)?\s*", "", query, count=1)
            return query.strip(" ,-")
        if intent == "analysis_report":
            query = re.sub(r"^(reporte|informe|analisis)\s+(de|del|sobre)?\s*", "", low, count=1)
            return query.strip(" ,-")
        return low

    def _strip_math_prefix(self, low: str) -> str:
        expression = re.sub(
            r"^(calcula|calcular|cuanto es|cuanto da|resuelve|resolver|operacion|haz la cuenta)\s+",
            "",
            low,
            count=1,
        )
        return expression.strip(" ,-")

    def _looks_like_open_app(self, low: str) -> bool:
        return bool(
            re.match(
                r"^(abre|abrir|inicia|ejecuta|lanza|quiero abrir|necesito abrir|abre la app|abre la aplicacion|abre el programa)\s+\S+",
                low,
            )
        )

    def _looks_like_research(self, low: str) -> bool:
        local_domains = (
            "agenda",
            "clase",
            "clases",
            "horario",
            "presupuesto",
            "balance",
            "clima",
            "rutina",
            "voz",
            "microfono",
            "pendiente",
            "pendientes",
            "tarea",
            "tareas",
            "compromiso",
            "compromisos",
        )
        explicit_web = low.startswith(("busca en internet ", "buscar en internet ", "consulta en internet "))
        if not explicit_web and any(domain in low for domain in local_domains):
            return False
        return bool(
            re.match(
                r"^(investiga|investigar|busca|buscar|busca en la web|busca en internet|consulta|consulta en internet|aprende sobre)\s+\S+",
                low,
            )
        )

    def _analysis_result(self, low: str) -> IntentResult | None:
        if re.match(r"^(simula|simular|analiza\s+escenario|escenario)\s+\S+", low) or re.match(r"^que\s+pasaria\s+si\s+\S+", low):
            return self._result("simulation_request", 0.97, "simulacion", low)
        if re.match(r"^(dame|dime|genera|propone|propon|sugiere)\s+(tus\s+propias\s+)?ideas?\b", low):
            return self._result("simulation_request", 0.95, "generacion de ideas", low)
        if re.search(r"\b(grafica|grafico|chart)\b", low):
            return self._result("chart_request", 0.97, "solicitud de grafica", low)
        if re.search(r"\btabla\b", low) and (
            re.search(r"\b(investiga|investigar|busca|buscar|consulta|haz|hacer|crea|crear|genera|generar|compara|comparar)\b", low)
            or re.match(r"^tabla\s+(de|sobre)\s+\S+", low)
        ):
            return self._result("research_table", 0.97, "investigacion estructurada en tabla", low)
        if re.match(r"^(reporte|informe|analisis)\s+(de|del|sobre)\s+\S+", low):
            return self._result("analysis_report", 0.95, "reporte de analisis", low)
        if re.match(r"^(estado|estatus)\s+control\s+remoto$", low):
            return self._result("remote_control_status", 0.96, "estado de control remoto", low)
        if re.match(r"^(probar|prueba)\s+control\s+remoto$", low):
            return self._result("remote_control_test", 0.96, "prueba de control remoto", low)
        if re.match(r"^(activar|activa)\s+control\s+remoto(?:\s+telegram)?$", low):
            return self._result("remote_control_activate", 0.96, "activacion de control remoto", low)
        return None

    def _game_result(self, low: str) -> IntentResult | None:
        if low in {
            "juegos",
            "que juegos tienes",
            "lista juegos",
            "juegos disponibles",
            "estado juego",
            "estado del juego",
            "tablero",
            "ver tablero",
            "ayuda juego",
            "ayuda del juego",
        }:
            return self._result("game_command", 0.96, "consulta de juegos", low)
        if re.search(r"\b(jugar|juega|inicia|nuevo|empezar)\b.*\b(gato|tictactoe|tic tac toe|tres en raya|batalla naval|barquitos|hundir barcos|adivina quien|quien es quien)\b", low):
            return self._result("game_command", 0.97, "inicio de juego", low)
        if re.match(r"^dispara\s+[a-e]\s*[1-5]$", low):
            return self._result("game_command", 0.93, "turno de batalla naval", low)
        if re.match(r"^(tiene|usa|es|sera|creo que es)\s+\S+", low) and re.search(r"\b(lentes|barba|sombrero|gorra|mujer|hombre|estudiante|ana|luis|marta|carlos)\b", low):
            return self._result("game_command", 0.88, "turno de adivina quien", low)
        return None

    def _looks_like_math(self, low: str) -> bool:
        if re.match(r"^(calcula|calcular|cuanto es|cuanto da|resuelve|resolver|operacion|haz la cuenta)\s+\S+", low):
            return True
        has_number = bool(re.search(r"\d", low))
        has_operator = bool(re.search(r"(\*\*|[+\-*/%()])", low))
        return has_number and has_operator
