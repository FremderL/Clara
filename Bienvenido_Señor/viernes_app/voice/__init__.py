"""Voz, reconocimiento y conversación continua."""

from viernes_app.voice.continuous import ContinuousConversationController
from viernes_app.voice.interruption import InterruptionDetector
from viernes_app.voice.profiles import VoiceProfile, VoiceProfileManager
from viernes_app.voice.voice import ViernesVoice
from viernes_app.voice.wake_word import WakeWordDetector

__all__ = [
    "ContinuousConversationController",
    "InterruptionDetector",
    "VoiceProfile",
    "VoiceProfileManager",
    "ViernesVoice",
    "WakeWordDetector",
]
