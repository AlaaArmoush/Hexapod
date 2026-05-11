from typing import Callable, Dict, List, Optional

from .base import ToolResult
from .memory_tools import forget_memory, recall_memory, remember_fact
from .system_tools import battery_status, network_status, system_status
from .time_tools import get_date, get_time
from .timer_tools import set_reminder, set_timer
from .tool_types import ToolMeta
from .web_tools import search_web


NOT_IMPLEMENTED_TEXT = "This capability is not yet available."


def _not_implemented_result(action: str, display_face: str) -> ToolResult:
    return ToolResult(
        ok=False,
        action=action,
        spoken_text=NOT_IMPLEMENTED_TEXT,
        display_face=display_face,
        error="not_implemented",
    )


def _stub(action: str, display_face: str) -> Callable[..., ToolResult]:
    def call_stub(*args, **kwargs) -> ToolResult:
        return _not_implemented_result(action, display_face)

    return call_stub


def _meta(
    name: str,
    description: str,
    required_args: List[str],
    optional_args: List[str],
    display_face: str,
    *,
    implemented: bool = False,
    fn: Optional[Callable[..., ToolResult]] = None,
    needs_internet: bool = False,
    needs_camera: bool = False,
    needs_microphone: bool = False,
    affects_motion: bool = False,
) -> ToolMeta:
    return ToolMeta(
        name=name,
        description=description,
        required_args=required_args,
        optional_args=optional_args,
        implemented=implemented,
        needs_internet=needs_internet,
        needs_camera=needs_camera,
        needs_microphone=needs_microphone,
        affects_motion=affects_motion,
        recommended_display_face=display_face,
        fn=fn if fn is not None else _stub(name, display_face),
    )


TOOL_REGISTRY: List[ToolMeta] = [
    _meta("get_time", "Return the current local time.", [], [], "clock", implemented=True, fn=get_time),
    _meta("get_date", "Return the current local date.", [], [], "calendar", implemented=True, fn=get_date),
    _meta("search_web", "Search the web for a short answer or top results.", ["query"], [], "search", implemented=True, fn=search_web, needs_internet=True),
    _meta("remember_fact", "Store a key/value memory fact.", ["key", "value"], [], "memory", implemented=True, fn=remember_fact),
    _meta("recall_memory", "Recall a stored memory fact by key.", ["key"], [], "memory", implemented=True, fn=recall_memory),
    _meta("forget_memory", "Delete a stored memory fact by key.", ["key"], [], "memory", implemented=True, fn=forget_memory),
    _meta("system_status", "Report host CPU, memory, disk, uptime, and platform status.", [], [], "system", implemented=True, fn=system_status),
    _meta("network_status", "Report whether the host appears to have network connectivity.", [], [], "wifi", implemented=True, fn=network_status),
    _meta("battery_status", "Report battery status when a battery source is available.", [], [], "battery", implemented=True, fn=battery_status),
    _meta("set_timer", "Store timer metadata for a future scheduler.", ["label", "duration_seconds"], [], "timer", implemented=True, fn=set_timer),
    _meta("set_reminder", "Store reminder metadata for a future scheduler.", ["label", "datetime_str"], [], "reminder", implemented=True, fn=set_reminder),
    _meta("capture_image", "Capture an image from the camera.", [], [], "camera", needs_camera=True),
    _meta("describe_scene", "Describe what the camera currently sees.", [], [], "camera", needs_camera=True),
    _meta("detect_person", "Detect whether a person is visible.", [], [], "camera", needs_camera=True),
    _meta("detect_object", "Detect whether a requested object is visible.", ["object_name"], [], "camera", needs_camera=True),
    _meta("mic_status", "Report microphone availability and status.", [], [], "microphone", needs_microphone=True),
    _meta("voice_direction_estimate", "Estimate the direction of a speaker.", [], [], "microphone", needs_microphone=True),
    _meta("camera_status", "Report camera availability and status.", [], [], "camera", needs_camera=True),
    _meta("tell_joke", "Tell a short local joke.", [], [], "speaking"),
    _meta("local_file_lookup", "Look up a local file or note by query.", ["query"], [], "memory"),
    _meta("read_project_note", "Read a local project note by name.", ["name"], [], "memory"),
    _meta("explain_capability", "Explain one known robot capability.", ["capability"], [], "system"),
]

_TOOLS_BY_NAME: Dict[str, ToolMeta] = {tool.name: tool for tool in TOOL_REGISTRY}


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def get_tool(name: str) -> Optional[ToolMeta]:
    return _TOOLS_BY_NAME.get(_normalize_name(name))


def list_implemented() -> List[ToolMeta]:
    return [tool for tool in TOOL_REGISTRY if tool.implemented]


def list_all() -> List[ToolMeta]:
    return list(TOOL_REGISTRY)


def call_tool(name: str, **kwargs) -> ToolResult:
    action = _normalize_name(name)
    tool = get_tool(action)
    if tool is None:
        return ToolResult(
            ok=False,
            action=action,
            spoken_text="I do not know that tool yet.",
            data={"available_tools": [item.name for item in TOOL_REGISTRY]},
            display_face="error",
            error="unknown_tool",
        )

    if tool.fn is None:
        return _not_implemented_result(tool.name, tool.recommended_display_face)

    return tool.fn(**kwargs)
