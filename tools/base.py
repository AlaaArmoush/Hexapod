from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    ok: bool
    action: str
    spoken_text: str
    data: Dict[str, Any] = field(default_factory=dict)
    display_face: Optional[str] = None
    display_text: Optional[str] = None
    display_duration_ms: Optional[int] = 3500
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "spoken_text": self.spoken_text,
            "data": dict(self.data),
            "display_face": self.display_face,
            "display_text": self.display_text,
            "display_duration_ms": self.display_duration_ms,
            "error": self.error,
        }
