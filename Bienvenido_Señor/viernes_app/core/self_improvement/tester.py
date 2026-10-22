from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from viernes_app.paths import REPO_ROOT


@dataclass(frozen=True)
class TestRunResult:
    passed: bool
    command: list[str]
    output: str
    returncode: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "command": list(self.command),
            "output": self.output,
            "returncode": self.returncode,
        }


class ImprovementTester:
    def __init__(self, root: Path = REPO_ROOT) -> None:
        self.root = Path(root)

    def run_unit_tests(self, pattern: str = "test*.py", *, timeout: int = 120) -> TestRunResult:
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern]
        try:
            result = subprocess.run(command, cwd=str(self.root), capture_output=True, text=True, timeout=timeout)
            output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            return TestRunResult(result.returncode == 0, command, output[-5000:], result.returncode)
        except Exception as exc:
            return TestRunResult(False, command, str(exc), 1)
