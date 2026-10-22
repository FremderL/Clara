from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class UserLevel(IntEnum):
    CONVERSATION = 0
    BASIC_TOOLS = 1
    MUTATION = 2
    ADMIN = 3


@dataclass(frozen=True)
class UserLevelInfo:
    level: UserLevel
    label: str
    description: str


USER_LEVELS: dict[int, UserLevelInfo] = {
    0: UserLevelInfo(UserLevel.CONVERSATION, "Nivel 0", "Solo conversacion."),
    1: UserLevelInfo(UserLevel.BASIC_TOOLS, "Nivel 1", "Abrir programas y leer recursos autorizados."),
    2: UserLevelInfo(UserLevel.MUTATION, "Nivel 2", "Modificar archivos y ejecutar scripts autorizados."),
    3: UserLevelInfo(UserLevel.ADMIN, "Nivel 3", "Control administrativo completo."),
}


def coerce_user_level(value: int | str | UserLevel | None, default: UserLevel = UserLevel.BASIC_TOOLS) -> UserLevel:
    if isinstance(value, UserLevel):
        return value
    try:
        level = int(value) if value is not None and value != "" else int(default)
    except (TypeError, ValueError):
        level = int(default)
    return UserLevel(max(0, min(3, level)))
