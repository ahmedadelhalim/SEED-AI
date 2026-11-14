"""
SEED Voice Module - Text-to-Speech and Speech-to-Text
Uses Web Speech API for browser-based voice interaction
"""
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class VoiceProvider(Enum):
    """Available voice providers"""
    BROWSER_WEB Speech = "browser"
    AZURE_SPEECH = "azure"
    OLLAMA_LOCAL = "ollama"


@dataclass
class VoiceConfig:
    """Voice configuration"""
    provider: VoiceProvider = VoiceProvider.BROWSER_WEB Speech
    voice_id: str = "en-US-JennyNeural"
    rate: float = 1.0  # Speech rate (0.5-2.0)
    pitch: float = 1.0
    volume: float = 1.0
    azure_key: Optional[str] = None
    azure_region: str = "eastus"


@dataclass
class SpeechResult:
    """Speech recognition result"""
    transcript: str
    confidence: float
    is_final: bool
    language: str = "en-US"


class SeedVoiceEngine:
    """SEED Voice Engine for TTS and STT"""
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self._is_speaking = False
        self._is_listening = False
        
    def speak(self, text: str, voice_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert text to speech using browser Web Speech API
        Returns JavaScript code to execute in browser
        """
        voice = voice_id or self.config.voice_id
        
        # Generate JavaScript for browser TTS
        js_code = f"""
(function() {{
    const utterance = new SpeechSynthesisUtterance({json.dumps(text)});
    utterance.voice = speechSynthesis.getVoices().find(v => v.name.includes({json.dumps(voice)})) || null;
    utterance.rate = {self.config.rate};
    utterance.pitch = {self.config.pitch};
    utterance.volume = {self.config.volume};
    
    utterance.onstart = () => {{
        window.seedEventBus?.publish('voice:speaking', {{ state: true }});
    }};
    utterance.onend = () => {{
        window.seedEventBus?.publish('voice:speaking', {{ state: false }});
    }};
    utterance.onerror = (e) => {{
        window.seedEventBus?.publish('voice:error', {{ error: e.error }});
    }};
    
    speechSynthesis.speak(utterance);
    return {{ status: 'speaking', text: {json.dumps(text[:50])} }};
}})()
"""
        return {
            "status": "queued",
            "text": text,
            "voice": voice,
            "javascript": js_code
        }
    
    def stop_speaking(self) -> str:
        """Stop current speech"""
        return """
(function() {
    speechSynthesis.cancel();
    window.seedEventBus?.publish('voice:speaking', { state: false });
    return { status: 'stopped' };
})()
"""
    
    def get_listening_js(self) -> str:
        """Get JavaScript for speech recognition"""
        return """
(function() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        return { error: 'Speech recognition not supported' };
    }
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    
    recognition.onstart = () => {
        window.seedEventBus?.publish('voice:listening', { state: true });
    };
    
    recognition.onresult = (event) => {
        const results = event.results;
        const last = results.length - 1;
        const transcript = results[last][0].transcript;
        const confidence = results[last][0].confidence;
        const isFinal = results[last].isFinal;
        
        window.seedEventBus?.publish('voice:result', { 
            transcript, 
            confidence, 
            isFinal 
        });
    };
    
    recognition.onerror = (event) => {
        window.seedEventBus?.publish('voice:error', { error: event.error });
    };
    
    recognition.onend = () => {
        window.seedEventBus?.publish('voice:listening', { state: false });
    };
    
    window.__seedRecognition = recognition;
    recognition.start();
    
    return { status: 'listening' };
})()
"""
    
    def get_stop_listening_js(self) -> str:
        """Stop speech recognition"""
        return """
(function() {
    if (window.__seedRecognition) {
        window.__seedRecognition.stop();
        window.__seedRecognition = null;
    }
    window.seedEventBus?.publish('voice:listening', { state: false });
    return { status: 'stopped' };
})()
"""
    
    def get_available_voices_js(self) -> str:
        """Get available voices in browser"""
        return """
(function() {
    const waitForVoices = () => {
        const voices = speechSynthesis.getVoices();
        if (voices.length > 0) {
            return voices.map(v => ({ name: v.name, lang: v.lang, default: v.default }));
        }
        return null;
    };
    
    let voices = waitForVoices();
    if (!voices) {
        speechSynthesis.onvoiceschanged = () => {
            voices = waitForVoices();
        };
    }
    
    return voices || [{ name: 'Loading...', lang: 'en-US' }];
})()
"""
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration"""
        return {
            "provider": self.config.provider.value,
            "voice_id": self.config.voice_id,
            "rate": self.config.rate,
            "pitch": self.config.pitch,
            "volume": self.config.volume,
            "is_speaking": self._is_speaking,
            "is_listening": self._is_listening
        }


# Default voice engine instance
_default_engine: Optional[SeedVoiceEngine] = None

def get_voice_engine(config: Optional[VoiceConfig] = None) -> SeedVoiceEngine:
    """Get or create default voice engine"""
    global _default_engine
    if _default_engine is None:
        _default_engine = SeedVoiceEngine(config)
    return _default_engine


def speak(text: str) -> Dict[str, Any]:
    """Quick speak function"""
    engine = get_voice_engine()
    return engine.speak(text)


def stop() -> str:
    """Quick stop function"""
    engine = get_voice_engine()
    return engine.stop_speaking()