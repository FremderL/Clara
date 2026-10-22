from __future__ import annotations

import argparse
import logging
import time

# Solo mostrar warnings y errores reales en consola, no INFO de cada modulo
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

from viernes_app.core.assistant import ViernesAssistant


def main() -> None:
    parser = argparse.ArgumentParser(description="Viernes - Asistente Personal")
    parser.add_argument("--mode", choices=("gui", "scheduler", "morning", "remote"), default="gui")
    parser.add_argument("--loop-seconds", type=int, default=0)
    args = parser.parse_args()

    if args.mode == "gui":
        from viernes_app.ui.gui import ViernesGUI
        try:
            ViernesGUI().run()
        except KeyboardInterrupt:
            print("Viernes se cerro desde la consola.")
        return

    assistant = ViernesAssistant()

    if args.mode == "morning":
        assistant.morning_brief()
        assistant.scheduler_tick()
        return

    if args.mode == "remote":
        sleep_seconds = max(5, args.loop_seconds or int(assistant.config.get("remote_control", {}).get("poll_interval_seconds", 5) or 5))
        while True:
            assistant.remote_control_tick()
            time.sleep(sleep_seconds)

    if args.loop_seconds > 0:
        while True:
            assistant.scheduler_tick()
            time.sleep(max(5, args.loop_seconds))
    else:
        assistant.scheduler_tick()


if __name__ == "__main__":
    main()
