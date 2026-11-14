"""
SEED Voice Intelligence Module
Advanced Speech-to-Text and Text-to-Speech integration for SEED
"""
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class VoiceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceProfile:
    provider: str = "browser"
    voice_name: str = "en-US-JennyNeural"
    language: str = "en-US"
    rate: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0


class AdvancedVoiceManager:
    """Manages full voice interaction loops for SEED Control Center"""
    
    def __init__(self, profile: Optional[VoiceProfile] = None):
        self.profile = profile or VoiceProfile()
        self.state = VoiceState.IDLE
        self.history: List[Dict[str, str]] = []

    def speak(self, text: str) -> str:
        """Generate JavaScript code to speak the given text"""
        return f"""
(function() {{
    const utterance = new SpeechSynthesisUtterance({json.dumps(text)});
    utterance.rate = {self.profile.rate};
    utterance.pitch = {self.profile.pitch};
    utterance.volume = {self.profile.volume};
    speechSynthesis.speak(utterance);
    return {{ status: 'speaking', text: {json.dumps(text[:50])} }};
}})()
"""

    def stop(self):
        """Stop any current speech"""
        self.state = VoiceState.IDLE
        return '{"status": "stopped"}'

    def generate_client_script(self) -> str:
        """Returns the complete JavaScript snippet to inject full voice capabilities into the UI"""
        return f"""
window.SeedVoice = (() => {{
    let recognition = null;
    let synthesis = window.speechSynthesis;
    let currentState = "{self.state.value}";
    
    function setState(newState) {{
        currentState = newState;
        window.seedEventBus?.publish('voice:state', {{ state: newState }});
        const indicator = document.getElementById('voice-status-badge');
        if (indicator) indicator.textContent = newState.toUpperCase();
    }}

    return {{
        init() {{
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRec) {{
                console.warn("Speech Recognition not supported in this browser.");
                return;
            }}
            recognition = new SpeechRec();
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.lang = "{self.profile.language}";

            recognition.onstart = () => setState("listening");
            recognition.onresult = (e) => {{
                const transcript = Array.from(e.results)
                    .map(r => r[0].transcript)
                    .join('');
                const inputEl = document.getElementById('request-input');
                if (inputEl) inputEl.value = transcript;
            }};
            recognition.onerror = (e) => {{
                console.error("Speech recognition error", e);
                setState("error");
            }};
            recognition.onend = () => setState("idle");
        }},

        listen() {{
            if (!recognition) this.init();
            if (recognition) {{
                try {{
                    recognition.start();
                }} catch (err) {{
                    console.error("Recognition start error:", err);
                }}
            }}
        }},

        stopListen() {{
            if (recognition) recognition.stop();
            setState("idle");
        }},

        speak(text) {{
            if (!text || !synthesis) return;
            synthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = {self.profile.rate};
            utterance.pitch = {self.profile.pitch};
            utterance.volume = {self.profile.volume};
            
            const voices = synthesis.getVoices();
            const voice = voices.find(v => v.name.includes("{self.profile.voice_name}")) || voices[0];
            if (voice) utterance.voice = voice;

            utterance.onstart = () => setState("speaking");
            utterance.onend = () => setState("idle");
            utterance.onerror = () => setState("error");

            synthesis.speak(utterance);
        }},

        stop() {{
            if (synthesis) synthesis.cancel();
            this.stopListen();
            setState("idle");
        }}
    }};
}})();

document.addEventListener('DOMContentLoaded', () => {{
    window.SeedVoice.init();
}});
"""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "profile": {
                "provider": self.profile.provider,
                "voice_name": self.profile.voice_name,
                "language": self.profile.language,
                "rate": self.profile.rate,
                "pitch": self.profile.pitch,
                "volume": self.profile.volume
            }
        }
