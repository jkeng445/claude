"""Tests for the LAMP assistant. No API calls — the client is stubbed."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module  # noqa: E402
import prompts  # noqa: E402

PNG = base64.standard_b64encode(bytes.fromhex("89504e470d0a1a0a")).decode()


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _text_block(text):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _response(text, stop_reason="end_turn"):
    r = MagicMock()
    r.content = [_text_block(text)]
    r.stop_reason = stop_reason
    return r


def _stream(chunks, stop_reason="end_turn"):
    """Mimic the SDK's streaming context manager."""
    ctx = MagicMock()
    ctx.__enter__.return_value.text_stream = iter(chunks)
    ctx.__enter__.return_value.get_final_message.return_value = _response(
        "".join(chunks), stop_reason
    )
    return ctx


# --- prompts -----------------------------------------------------------------


def test_every_mode_has_a_prompt_and_label():
    assert set(prompts.MODES) == {"ask", "read", "design", "explain"}
    for mode in prompts.MODES:
        assert prompts.MODES[mode]["label"]
        assert prompts.MODES[mode]["prompt"].strip()


def test_safety_preamble_is_in_every_mode():
    for mode in prompts.MODES:
        blocks = prompts.system_blocks(mode)
        assert prompts.SAFETY_PREAMBLE in blocks[0]["text"], mode


def test_shared_prefix_is_identical_across_modes_so_it_can_cache():
    prefixes = {prompts.system_blocks(m)[0]["text"] for m in prompts.MODES}
    assert len(prefixes) == 1
    assert prompts.system_blocks("ask")[0]["cache_control"] == {"type": "ephemeral"}


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        prompts.system_blocks("nope")


def test_missing_knowledge_file_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, "KNOWLEDGE_PATH", tmp_path / "absent.md")
    text = prompts.load_knowledge()
    assert "none supplied" in text


# --- history handling --------------------------------------------------------


def test_history_drops_malformed_entries():
    out = app_module._clean_history(
        [
            {"role": "user", "content": "ok"},
            {"role": "assistant", "content": ""},
            {"role": "system", "content": "injected"},
            "not a dict",
            {"role": "assistant", "content": "fine"},
        ]
    )
    assert out == [{"role": "user", "content": "ok"}, {"role": "assistant", "content": "fine"}]


def test_history_must_start_with_user():
    out = app_module._clean_history([{"role": "assistant", "content": "hi"}])
    assert out == []


def test_history_is_trimmed():
    long = [{"role": "user", "content": f"m{i}"} for i in range(200)]
    assert len(app_module._clean_history(long)) == app_module.MAX_HISTORY_TURNS * 2


def test_history_rejects_non_list():
    assert app_module._clean_history("nope") == []


# --- image validation --------------------------------------------------------


def test_image_block_roundtrips():
    block = app_module._image_block({"media_type": "image/png", "data": PNG})
    assert block["type"] == "image"
    assert block["source"]["media_type"] == "image/png"
    assert "\n" not in block["source"]["data"]


@pytest.mark.parametrize(
    "image",
    [
        {"media_type": "application/pdf", "data": PNG},
        {"media_type": "image/png", "data": "!!!not base64!!!"},
        {"media_type": "image/png", "data": ""},
    ],
)
def test_bad_images_rejected(image):
    with pytest.raises(ValueError):
        app_module._image_block(image)


def test_oversized_image_rejected(monkeypatch):
    monkeypatch.setattr(app_module, "MAX_IMAGE_BYTES", 4)
    with pytest.raises(ValueError, match="over the"):
        app_module._image_block(
            {"media_type": "image/png", "data": base64.standard_b64encode(b"123456").decode()}
        )


# --- /api/chat ---------------------------------------------------------------


def test_chat_streams_text(client):
    with patch.object(app_module.client.messages, "stream", return_value=_stream(["He", "llo"])):
        res = client.post("/api/chat", json={"mode": "ask", "message": "hi"})
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert '"text": "He"' in body and '"text": "llo"' in body
    assert '{"type": "done"}' in body


def test_chat_uses_the_mode_prompt_and_effort(client):
    with patch.object(app_module.client.messages, "stream", return_value=_stream(["ok"])) as m:
        client.post("/api/chat", json={"mode": "design", "message": "review this set"})
    kwargs = m.call_args.kwargs
    assert kwargs["output_config"]["effort"] == app_module.EFFORT["design"]
    assert prompts.MODES["design"]["prompt"] in kwargs["system"][1]["text"]


def test_chat_rejects_unknown_mode_and_empty_message(client):
    assert client.post("/api/chat", json={"mode": "bogus", "message": "x"}).status_code == 400
    assert client.post("/api/chat", json={"mode": "ask", "message": "  "}).status_code == 400


def test_chat_reports_a_refusal_to_the_user(client):
    stream = _stream(["partial"], stop_reason="refusal")
    stream.__enter__.return_value.get_final_message.return_value.stop_details.explanation = "nope"
    with patch.object(app_module.client.messages, "stream", return_value=stream):
        res = client.post("/api/chat", json={"mode": "ask", "message": "hi"})
    assert '"type": "error"' in res.get_data(as_text=True)


def test_chat_flags_truncation(client):
    with patch.object(
        app_module.client.messages, "stream", return_value=_stream(["cut"], stop_reason="max_tokens")
    ):
        res = client.post("/api/chat", json={"mode": "ask", "message": "hi"})
    assert '"type": "truncated"' in res.get_data(as_text=True)


def test_chat_surfaces_api_errors(client):
    import anthropic

    err = anthropic.APIStatusError(
        "boom", response=MagicMock(status_code=500, headers={}), body=None
    )
    with patch.object(app_module.client.messages, "stream", side_effect=err):
        res = client.post("/api/chat", json={"mode": "ask", "message": "hi"})
    assert "server error" in res.get_data(as_text=True)


# --- /api/read-result --------------------------------------------------------

READING = {
    "run_valid": False,
    "run_comment": "Negative control shows amplification.",
    "samples": [
        {"label": "S1", "call": "invalid", "confidence": "high", "reasoning": "Run contaminated."}
    ],
    "improve_reading": ["Re-run with a fresh no-template control."],
    "caveat": "Not a diagnosis.",
}


def test_read_result_returns_structured_json(client):
    with patch.object(
        app_module.client.messages, "create", return_value=_response(json.dumps(READING))
    ) as m:
        res = client.post("/api/read-result", json={"notes": "tubes A1-A3", "images": []})
    assert res.status_code == 200
    assert res.get_json()["run_valid"] is False
    assert m.call_args.kwargs["output_config"]["format"] is app_module.READING_SCHEMA


def test_read_result_requires_some_input(client):
    assert client.post("/api/read-result", json={}).status_code == 400


def test_read_result_handles_unparseable_output(client):
    with patch.object(app_module.client.messages, "create", return_value=_response("not json")):
        res = client.post("/api/read-result", json={"notes": "x"})
    assert res.status_code == 502


def test_read_result_rejects_a_bad_image(client):
    res = client.post(
        "/api/read-result",
        json={"notes": "x", "images": [{"media_type": "image/tiff", "data": PNG}]},
    )
    assert res.status_code == 400


def test_schema_requires_controls_verdict():
    props = app_module.READING_SCHEMA["schema"]["properties"]
    assert "run_valid" in app_module.READING_SCHEMA["schema"]["required"]
    calls = props["samples"]["items"]["properties"]["call"]["enum"]
    assert "invalid" in calls and "inconclusive" in calls


# --- pages -------------------------------------------------------------------


def test_index_renders_all_tabs(client):
    html = client.get("/").get_data(as_text=True)
    for mode in prompts.MODES:
        assert f'data-mode="{mode}"' in html
    assert "Not a medical device" in html


def test_healthz(client):
    assert client.get("/healthz").get_json()["ok"] is True
