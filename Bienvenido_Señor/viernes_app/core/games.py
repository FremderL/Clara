from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GameResult:
    message: str
    mutated: bool = False
    game: str = ""
    status: str = "ok"


class GameEngine:
    """Juegos locales con estado persistente en runtime.state."""

    def handle(self, text: str, games_state: dict[str, Any], now: datetime) -> GameResult | None:
        low = _normalize(text)
        if not low:
            return None
        if low in {"juegos", "que juegos tienes", "lista juegos", "juegos disponibles"}:
            return GameResult(
                "Puedo jugar: gato/tictactoe, batalla naval y adivina quien. "
                "Diga 'jugar gato', 'jugar batalla naval' o 'jugar adivina quien'."
            )
        if low in {"estado juego", "estado del juego", "tablero", "ver tablero", "ayuda juego", "ayuda del juego"}:
            return self._status_or_help(low, games_state)
        if self._is_start_tictactoe(low):
            return self._start_tictactoe(games_state)
        if self._is_start_battleship(low):
            return self._start_battleship(games_state)
        if self._is_start_guess_who(low):
            return self._start_guess_who(games_state, now)
        active = games_state.get("active")
        if active == "tictactoe":
            return self._play_tictactoe(low, games_state)
        if active == "battleship":
            return self._play_battleship(low, games_state)
        if active == "guess_who":
            return self._play_guess_who(low, games_state)
        return None

    def active_summary(self, games_state: dict[str, Any]) -> dict[str, Any]:
        active = str(games_state.get("active") or "")
        if not active:
            return {"active": False}
        data = games_state.get(active, {})
        return {
            "active": True,
            "game": active,
            "status": data.get("status", "active") if isinstance(data, dict) else "active",
            "turn": data.get("turn", "") if isinstance(data, dict) else "",
        }

    def _is_start_tictactoe(self, low: str) -> bool:
        return bool(re.search(r"\b(jugar|juega|inicia|nuevo|empezar)\b.*\b(gato|tictactoe|tic tac toe|tres en raya)\b", low))

    def _is_start_battleship(self, low: str) -> bool:
        return bool(re.search(r"\b(jugar|juega|inicia|nuevo|empezar)\b.*\b(batalla naval|barquitos|hundir barcos)\b", low))

    def _is_start_guess_who(self, low: str) -> bool:
        return bool(re.search(r"\b(jugar|juega|inicia|nuevo|empezar)\b.*\b(adivina quien|quien es quien)\b", low))

    def _status_or_help(self, low: str, games_state: dict[str, Any]) -> GameResult:
        active = str(games_state.get("active") or "")
        if low in {"ayuda juego", "ayuda del juego"}:
            if active == "tictactoe":
                return GameResult("En gato, diga una casilla del 1 al 9. Para salir: terminar juego.")
            if active == "battleship":
                return GameResult("En batalla naval, dispare con coordenadas como A1, C4 o dispara B2. Para salir: terminar juego.")
            if active == "guess_who":
                return GameResult("En adivina quien, pregunte: tiene lentes, tiene barba, es mujer, es hombre, usa sombrero; o adivine: es Ana.")
            return GameResult("Puede iniciar: jugar gato, jugar batalla naval o jugar adivina quien.")
        if active == "tictactoe":
            state = games_state.get("tictactoe", {})
            board = state.get("board", [" "] * 9) if isinstance(state, dict) else [" "] * 9
            return GameResult("Partida activa: gato.\n" + _format_tictactoe_board(list(board)))
        if active == "battleship":
            state = games_state.get("battleship", {})
            return GameResult("Partida activa: batalla naval.\n" + _format_battleship_board(state if isinstance(state, dict) else {}))
        if active == "guess_who":
            state = games_state.get("guess_who", {})
            questions = len(state.get("questions", [])) if isinstance(state, dict) else 0
            return GameResult(f"Partida activa: adivina quien. Preguntas realizadas: {questions}.")
        return GameResult("No hay una partida activa. Diga 'jugar gato', 'jugar batalla naval' o 'jugar adivina quien'.")

    def _start_tictactoe(self, games_state: dict[str, Any]) -> GameResult:
        games_state["active"] = "tictactoe"
        games_state["tictactoe"] = {
            "board": [" "] * 9,
            "turn": "user",
            "status": "active",
            "user": "X",
            "assistant": "O",
            "moves": [],
        }
        return GameResult(
            "Listo, jugamos gato. Usted es X. Elija una casilla del 1 al 9.\n"
            + _format_tictactoe_board(games_state["tictactoe"]["board"]),
            mutated=True,
            game="tictactoe",
        )

    def _play_tictactoe(self, low: str, games_state: dict[str, Any]) -> GameResult | None:
        state = games_state.get("tictactoe", {})
        if not isinstance(state, dict) or state.get("status") != "active":
            return None
        if _is_exit_game(low):
            state["status"] = "finished"
            games_state["active"] = ""
            return GameResult("Partida de gato terminada.", mutated=True, game="tictactoe", status="finished")
        move = _extract_tictactoe_move(low)
        if move is None:
            return None
        board = list(state.get("board", [" "] * 9))
        if board[move] != " ":
            return GameResult("Esa casilla ya esta ocupada. Elija otra.", game="tictactoe", status="invalid")
        board[move] = "X"
        state.setdefault("moves", []).append({"player": "user", "cell": move + 1})
        winner = _tictactoe_winner(board)
        if winner or _board_full(board):
            state["board"] = board
            state["status"] = "finished"
            games_state["active"] = ""
            return GameResult(_tictactoe_final_message(board, winner), mutated=True, game="tictactoe", status="finished")
        ai_move = _choose_tictactoe_move(board)
        board[ai_move] = "O"
        state.setdefault("moves", []).append({"player": "assistant", "cell": ai_move + 1})
        winner = _tictactoe_winner(board)
        state["board"] = board
        if winner or _board_full(board):
            state["status"] = "finished"
            games_state["active"] = ""
            return GameResult(_tictactoe_final_message(board, winner), mutated=True, game="tictactoe", status="finished")
        return GameResult(
            f"Usted jugo {move + 1}. Yo juego {ai_move + 1}.\n" + _format_tictactoe_board(board),
            mutated=True,
            game="tictactoe",
        )

    def _start_battleship(self, games_state: dict[str, Any]) -> GameResult:
        ships = ["A1", "A2", "C4", "D4", "E5"]
        games_state["active"] = "battleship"
        games_state["battleship"] = {
            "size": 5,
            "ships": ships,
            "shots": [],
            "hits": [],
            "misses": [],
            "status": "active",
        }
        return GameResult("Batalla naval lista. Tablero 5x5 de A1 a E5. Dispare con: dispara B4.", mutated=True, game="battleship")

    def _play_battleship(self, low: str, games_state: dict[str, Any]) -> GameResult | None:
        state = games_state.get("battleship", {})
        if not isinstance(state, dict) or state.get("status") != "active":
            return None
        if _is_exit_game(low):
            state["status"] = "finished"
            games_state["active"] = ""
            return GameResult(f"Partida terminada. Barcos: {', '.join(state.get('ships', []))}.", mutated=True, game="battleship", status="finished")
        shot = _extract_battleship_shot(low)
        if not shot:
            return None
        if shot in state.get("shots", []):
            return GameResult(f"Ya disparo a {shot}. Pruebe otra coordenada.", game="battleship", status="invalid")
        state.setdefault("shots", []).append(shot)
        if shot in state.get("ships", []):
            state.setdefault("hits", []).append(shot)
            remaining = len(set(state.get("ships", [])) - set(state.get("hits", [])))
            if remaining == 0:
                state["status"] = "finished"
                games_state["active"] = ""
                return GameResult(f"Impacto en {shot}. Hundio toda la flota.", mutated=True, game="battleship", status="finished")
            return GameResult(f"Impacto en {shot}. Quedan {remaining} parte(s) de barco.", mutated=True, game="battleship")
        state.setdefault("misses", []).append(shot)
        return GameResult(f"Agua en {shot}. Disparos: {len(state.get('shots', []))}.", mutated=True, game="battleship")

    def _start_guess_who(self, games_state: dict[str, Any], now: datetime) -> GameResult:
        index = now.day % len(_GUESS_WHO_CHARACTERS)
        character = _GUESS_WHO_CHARACTERS[index]
        games_state["active"] = "guess_who"
        games_state["guess_who"] = {
            "secret": character["name"],
            "questions": [],
            "status": "active",
        }
        return GameResult(
            "Adivina quien listo. Ya elegi un personaje. Pregunte cosas como: tiene lentes, tiene barba, es mujer, usa sombrero; o diga: es Ana.",
            mutated=True,
            game="guess_who",
        )

    def _play_guess_who(self, low: str, games_state: dict[str, Any]) -> GameResult | None:
        state = games_state.get("guess_who", {})
        if not isinstance(state, dict) or state.get("status") != "active":
            return None
        secret = _character_by_name(str(state.get("secret", "")))
        if secret is None:
            state["status"] = "finished"
            games_state["active"] = ""
            return GameResult("La partida de adivina quien no tenia personaje valido. La reinicie.", mutated=True, game="guess_who", status="failed")
        if _is_exit_game(low):
            state["status"] = "finished"
            games_state["active"] = ""
            return GameResult(f"Partida terminada. El personaje era {secret['name']}.", mutated=True, game="guess_who", status="finished")
        attribute = _extract_guess_attribute(low)
        if attribute:
            answer = bool(secret.get(attribute, False))
            state.setdefault("questions", []).append({"attribute": attribute, "answer": answer})
            return GameResult("Si." if answer else "No.", mutated=True, game="guess_who")
        guess = _extract_guess(low)
        if not guess:
            return None
        state.setdefault("questions", []).append({"guess": guess})
        if _normalize(secret["name"]) == _normalize(guess):
            state["status"] = "finished"
            games_state["active"] = ""
            return GameResult(f"Correcto. Era {secret['name']}.", mutated=True, game="guess_who", status="finished")
        return GameResult(f"No, no es {guess}.", mutated=True, game="guess_who")


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.lower().strip())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_tictactoe_move(low: str) -> int | None:
    match = re.match(r"^(?:casilla|posicion|poner|pon|juego|muevo|mover)?\s*([1-9])$", low)
    if not match:
        return None
    return int(match.group(1)) - 1


def _format_tictactoe_board(board: list[str]) -> str:
    cells = [value if value != " " else str(index + 1) for index, value in enumerate(board)]
    return f"{cells[0]} | {cells[1]} | {cells[2]}\n--+---+--\n{cells[3]} | {cells[4]} | {cells[5]}\n--+---+--\n{cells[6]} | {cells[7]} | {cells[8]}"


def _tictactoe_winner(board: list[str]) -> str:
    lines = (
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
        (0, 3, 6),
        (1, 4, 7),
        (2, 5, 8),
        (0, 4, 8),
        (2, 4, 6),
    )
    for a, b, c in lines:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return ""


def _board_full(board: list[str]) -> bool:
    return all(cell != " " for cell in board)


def _choose_tictactoe_move(board: list[str]) -> int:
    for mark in ("O", "X"):
        for index, value in enumerate(board):
            if value != " ":
                continue
            candidate = list(board)
            candidate[index] = mark
            if _tictactoe_winner(candidate) == mark:
                return index
    for index in (4, 0, 2, 6, 8, 1, 3, 5, 7):
        if board[index] == " ":
            return index
    return 0


def _tictactoe_final_message(board: list[str], winner: str) -> str:
    board_text = _format_tictactoe_board(board)
    if winner == "X":
        return "Gano usted.\n" + board_text
    if winner == "O":
        return "Gane yo.\n" + board_text
    return "Empate.\n" + board_text


def _extract_battleship_shot(low: str) -> str:
    match = re.search(r"\b([a-e])\s*([1-5])\b", low)
    if not match:
        return ""
    return f"{match.group(1).upper()}{match.group(2)}"


def _format_battleship_board(state: dict[str, Any]) -> str:
    hits = set(str(item).upper() for item in state.get("hits", []) if item)
    misses = set(str(item).upper() for item in state.get("misses", []) if item)
    rows = ["   1 2 3 4 5"]
    for row in "ABCDE":
        cells = []
        for col in "12345":
            coord = row + col
            if coord in hits:
                cells.append("X")
            elif coord in misses:
                cells.append("o")
            else:
                cells.append(".")
        rows.append(f"{row}  " + " ".join(cells))
    return "\n".join(rows)


_GUESS_WHO_CHARACTERS = [
    {"name": "Ana", "mujer": True, "hombre": False, "lentes": True, "barba": False, "sombrero": False, "estudiante": True},
    {"name": "Luis", "mujer": False, "hombre": True, "lentes": False, "barba": True, "sombrero": False, "estudiante": False},
    {"name": "Marta", "mujer": True, "hombre": False, "lentes": False, "barba": False, "sombrero": True, "estudiante": False},
    {"name": "Carlos", "mujer": False, "hombre": True, "lentes": True, "barba": False, "sombrero": True, "estudiante": True},
]


def _character_by_name(name: str) -> dict[str, Any] | None:
    normalized = _normalize(name)
    return next((item for item in _GUESS_WHO_CHARACTERS if _normalize(str(item["name"])) == normalized), None)


def _extract_guess(low: str) -> str:
    match = re.search(r"\b(?:es|sera|creo que es)\s+([a-z]+)\b", low)
    if not match:
        return ""
    guess = match.group(1).strip()
    return guess.title() if _character_by_name(guess) is not None else ""


def _extract_guess_attribute(low: str) -> str:
    if re.search(r"\b(lentes|anteojos)\b", low):
        return "lentes"
    if "barba" in low:
        return "barba"
    if "sombrero" in low or "gorra" in low:
        return "sombrero"
    if "mujer" in low or "femenino" in low:
        return "mujer"
    if "hombre" in low or "masculino" in low:
        return "hombre"
    if "estudiante" in low:
        return "estudiante"
    return ""


def _is_exit_game(low: str) -> bool:
    return low in {"salir juego", "terminar juego", "cancelar juego", "rendirse", "me rindo"}
