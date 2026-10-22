from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from viernes_app.paths import RUNTIME_DIR


VOICE_PROFILES_PATH = RUNTIME_DIR / "voice_profiles.json"


@dataclass(frozen=True)
class VoiceProfile:
    name: str
    tts_type: str = "windows"
    rate: int = 165
    wake_word: str = "viernes"
    continuous: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tts_type": self.tts_type,
            "rate": self.rate,
            "wake_word": self.wake_word,
            "continuous": self.continuous,
        }


class VoiceProfileManager:
    def __init__(self, path: Path = VOICE_PROFILES_PATH) -> None:
        self.path = Path(path)

    def load_profiles(self) -> dict[str, VoiceProfile]:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {
                        name: VoiceProfile(
                            name=name,
                            tts_type=str(value.get("tts_type", "windows")),
                            rate=int(value.get("rate", 165) or 165),
                            wake_word=str(value.get("wake_word", "viernes")),
                            continuous=bool(value.get("continuous", False)),
                        )
                        for name, value in data.items()
                        if isinstance(value, dict)
                    }
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return {"default": VoiceProfile("default")}

    def save_profile(self, profile: VoiceProfile) -> None:
        profiles = self.load_profiles()
        profiles[profile.name] = profile
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps({name: item.to_dict() for name, item in profiles.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def get(self, name: str = "default") -> VoiceProfile:
        profiles = self.load_profiles()
        return profiles.get(name) or profiles.get("default") or VoiceProfile("default")

    def names(self) -> list[str]:
        return sorted(self.load_profiles().keys())
