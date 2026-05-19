from bridge.response_parser import parse_line


def test_parse_ok_true():
    parsed = parse_line(b'{"ok":true,"cmd":"stand"}\n')
    assert parsed["ok"] is True
    assert parsed["cmd"] == "stand"


def test_parse_ok_false_with_error():
    parsed = parse_line(b'{"ok":false,"error":"ambiguous_gait_bound"}\n')
    assert parsed["ok"] is False
    assert parsed["error"] == "ambiguous_gait_bound"


def test_parse_event_ready():
    parsed = parse_line(b'{"event":"ready","firmware":"hexapod"}\n')
    assert parsed["event"] == "ready"
    assert parsed["json"]["firmware"] == "hexapod"


def test_parse_status_response():
    raw = b'{"ok":true,"cmd":"status","mode":"standing","active_cmd":"","gesture":"","face":"idle"}'
    parsed = parse_line(raw)
    assert parsed["cmd"] == "status"
    assert parsed["json"]["mode"] == "standing"
    assert parsed["json"]["face"] == "idle"


def test_parse_non_json_debug_text():
    parsed = parse_line(b"[DEBUG] menu active\n")
    assert parsed["json"] is None
    assert parsed["ok"] is None
    assert parsed["raw"] == "[DEBUG] menu active"


def test_parse_malformed_json():
    parsed = parse_line(b"{bad json\n")
    assert parsed["json"] is None
    assert parsed["raw"] == "{bad json"


def test_parse_empty_line():
    assert parse_line(b"") is None


def test_parse_whitespace_only():
    assert parse_line(b"   \r\n") is None


def test_parse_gait_ack():
    parsed = parse_line(b'{"ok":true,"cmd":"gait","state":"walking","bound":"steps","steps":3}')
    assert parsed["ok"] is True
    assert parsed["cmd"] == "gait"
    assert parsed["json"]["steps"] == 3


def test_parse_rotate_ack():
    parsed = parse_line(b'{"ok":true,"cmd":"rotate","state":"rotating","dir":"left","bound":"cycles","cycles":3}')
    assert parsed["ok"] is True
    assert parsed["cmd"] == "rotate"
    assert parsed["json"]["dir"] == "left"
    assert parsed["json"]["cycles"] == 3
