from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Tuple


class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    EXECUTING = "executing"
    AWAITING_APPROVAL = "awaiting_approval"
    ERROR = "error"


SUPPORTED_SPEECH_LANGUAGES = ("ar", "en")


@dataclass(frozen=True)
class SpeechTranscript:
    text: str
    language: str
    confidence: Optional[float] = None

    def __post_init__(self):
        if self.language not in SUPPORTED_SPEECH_LANGUAGES:
            raise ValueError("Speech language must be Arabic or English")
        if not self.text.strip():
            raise ValueError("Transcript text cannot be empty")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("Transcript confidence must be between zero and one")


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    language: str
    session_id: str

    def __post_init__(self):
        if self.language not in SUPPORTED_SPEECH_LANGUAGES:
            raise ValueError("Speech language must be Arabic or English")
        if not self.session_id:
            raise ValueError("A SEED session ID is required")


@dataclass(frozen=True)
class SpeechAudio:
    content: bytes
    media_type: str
    duration_seconds: Optional[float] = None


@dataclass(frozen=True)
class WakeWordPolicy:
    enabled: bool = False
    phrase: str = "Hey SEED"
    privacy_acknowledged: bool = False

    def __post_init__(self):
        if self.enabled and not self.privacy_acknowledged:
            raise PermissionError(
                "Wake-word activation requires explicit privacy acknowledgement"
            )


@dataclass(frozen=True)
class VisualStateUpdate:
    state: AssistantState
    session_id: str
    task_id: Optional[int] = None
    event_id: Optional[int] = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.session_id:
            raise ValueError("A SEED session ID is required")


@dataclass(frozen=True)
class VisemeFrame:
    timestamp_seconds: float
    viseme: str
    weight: float = 1.0


class SpeechInputAdapter(ABC):
    """Replaceable STT boundary; implementations must not retain audio by default."""

    @abstractmethod
    async def transcribe(self, audio: bytes,
                         preferred_language: Optional[str] = None) -> SpeechTranscript:
        raise NotImplementedError


class SpeechOutputAdapter(ABC):
    """Replaceable TTS boundary; output remains subordinate to a SEED session."""

    @abstractmethod
    async def synthesize(self, request: SpeechRequest) -> SpeechAudio:
        raise NotImplementedError

    @abstractmethod
    async def interrupt(self, session_id: str) -> None:
        raise NotImplementedError


class VisualStateClient(ABC):
    """Presentation clients render state emitted by SEED; they do not choose it."""

    @abstractmethod
    async def publish_state(self, update: VisualStateUpdate) -> None:
        raise NotImplementedError


class AvatarPresentationAdapter(ABC):
    """Optional rendering-only adapter for facial reactions and audio visemes."""

    @abstractmethod
    async def publish_state(self, update: VisualStateUpdate) -> None:
        raise NotImplementedError

    @abstractmethod
    async def publish_lip_sync(self, session_id: str,
                               frames: Tuple[VisemeFrame, ...]) -> None:
        raise NotImplementedError