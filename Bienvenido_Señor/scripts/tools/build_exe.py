"""
Compila J.A.R.V.I.S. OS v5 con PyInstaller (--onefile --noconsole).
Coloque config.json junto al .exe en dist/ para configurar sin recompilar.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if ROOT.name == "tools":
    ROOT = ROOT.parent.parent
MAIN = ROOT / "jarvis_os_v5" / "main.py"
DIST = ROOT / "dist"


def main() -> int:
    if not MAIN.is_file():
        print("No se encuentra jarvis_os_v5/main.py", file=sys.stderr)
        return 1
    DIST.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconsole",
        "--clean",
        "--name",
        "JARVIS",
        "--distpath",
        str(DIST),
        "--workpath",
        str(ROOT / "build" / "pyi_work"),
        "--specpath",
        str(ROOT / "build"),
        "--paths",
        str(ROOT),
        "--collect-submodules=jarvis_os_v5",
        str(MAIN),
    ]
    print("Ejecutando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    example = ROOT / "jarvis_os_v5" / "config.example.json"
    if example.is_file():
        dest = DIST / "config.json"
        if not dest.is_file():
            shutil.copy2(example, dest)
            print(f"Copiado ejemplo de config a {dest}")
    print("Salida en:", DIST / "JARVIS.exe" if sys.platform == "win32" else DIST / "JARVIS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
