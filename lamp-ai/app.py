"""LAMP assistant — a small Flask app over the Claude API.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python app.py
    # open http://localhost:5000
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os

import anthropic
from flask import Flask, Response, jsonify, render_template, request

from prompts import MODES, system_blocks

MODEL = os.environ.get("LAMP_AI_MODEL", "claude-opus-5-5")
MAX_TOKENS = 8000
MAX_HISTORY_TURNS = 20
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

# Effort per mode: reading a result and reviewing a design are the judgement
# calls, so they get more. Public explanations are easy and benefit from speed.
EFFORT = {"ask": "high", "read": "high", "design": "xhigh", "explain": "medium"}

log = logging.getLogger("lamp_ai")

app = Flask(__name__)
client = anthropic.Anthropic()

# Structured output for result reading, so the UI can colour-code calls instead
# of regex-ing prose.
READING_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "run_valid": {
                "type": "boolean",
                "description": "False if controls failed or are absent/unreadable.",
            },
            "run_comment": {
                "type": "string",
                "description": "Why the run is valid or invalid, citing the controls.",
            },
            "samples": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "call": {
                            "type": "string",
                            "enum": [
                                "target detected",
                                "target not detected",
                                "inconclusive",
                                "invalid",
                            ],
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "moderate", "low"],
                        },
                        "reasoning": {"type": "string"},
                    },
                    "required": ["label", "call", "confidence", "reasoning"],
                    "additionalProperties": False,
                },
            },
            "improve_reading": {
                "type": "array",
                "items": {"type": "string"},
                "description": "What would make this reading more reliable.",
            },
            "caveat": {
                "type": "string",
                "description": "The standing caveat shown with every reading.",
            },
        },
        "required": [
            "run_valid",
            "run_comment",
            "samples",
            "improve_reading",
            "caveat",
        ],
        "additionalProperties": False,
    },
}


def _trim(history: list[dict]) -> list[dict]:
    """Keep the conversation bounded. Oldest turns go first."""
    return history[-(MAX_HISTORY_TURNS * 2) :]


def _clean_history(raw: object) -> list[dict]:
    """Accept only well-formed user/assistant text turns from the client."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content})
    # The API requires the first message to be from the user.
    while out and out[0]["role"] != "user":
        out.pop(0)
    return _trim(out)


def _image_block(image: dict) -> dict:
    """Validate a client-supplied base64 image and build a content block."""
    media_type = image.get("media_type")
    data = image.get("data") or ""
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"unsupported image type: {media_type!r}")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("image data is not valid base64") from exc
    if not raw:
        raise ValueError("image data is empty")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"image is {len(raw) // 1024}KB, over the {MAX_IMAGE_BYTES // 1024 // 1024}MB limit"
        )
    # Re-encode so no stray newlines reach the API.
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(raw).decode("ascii"),
        },
    }


def _user_content(text: str, images: list[dict]) -> str | list[dict]:
    if not images:
        return text
    # Images before text reads better for the model.
    return [_image_block(img) for img in images] + [{"type": "text", "text": text}]


@app.get("/")
def index():
    return render_template("index.html", modes=MODES)


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "model": MODEL})


@app.post("/api/chat")
def chat():
    """Streaming chat for the ask / design / explain modes."""
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "ask")
    message = (body.get("message") or "").strip()
    images = body.get("images") or []

    if mode not in MODES:
        return jsonify({"error": f"unknown mode: {mode}"}), 400
    if not message and not images:
        return jsonify({"error": "message is empty"}), 400

    try:
        content = _user_content(message, images)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    messages = _clean_history(body.get("history")) + [{"role": "user", "content": content}]

    def events():
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_blocks(mode),
                output_config={"effort": EFFORT.get(mode, "high")},
                messages=messages,
            ) as stream:
                for chunk in stream.text_stream:
                    yield _sse({"type": "delta", "text": chunk})
                final = stream.get_final_message()
            if final.stop_reason == "refusal":
                detail = getattr(final.stop_details, "explanation", None)
                yield _sse(
                    {
                        "type": "error",
                        "error": detail
                        or "That request was declined. Rephrase it, or ask about "
                        "detection and diagnostics.",
                    }
                )
            elif final.stop_reason == "max_tokens":
                yield _sse({"type": "truncated"})
            yield _sse({"type": "done"})
        except anthropic.APIStatusError as exc:
            log.exception("API error during stream")
            yield _sse({"type": "error", "error": _friendly(exc)})
        except anthropic.APIConnectionError:
            log.exception("connection error during stream")
            yield _sse({"type": "error", "error": "Could not reach the API. Check the network."})

    return Response(
        events(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/read-result")
def read_result():
    """Non-streaming, structured result reading."""
    body = request.get_json(silent=True) or {}
    notes = (body.get("notes") or "").strip()
    images = body.get("images") or []
    readings = (body.get("readings") or "").strip()

    if not images and not notes and not readings:
        return jsonify({"error": "provide a photo, readings, or a description"}), 400

    parts = []
    if notes:
        parts.append(f"Operator notes:\n{notes}")
    if readings:
        parts.append(f"Readings / curve data:\n{readings}")
    if not parts:
        parts.append("No notes supplied. Read the image on its own.")
    parts.append(
        "Interpret this run. Check the controls first and set run_valid "
        "accordingly. Use the sample labels given, or describe each tube's "
        "position if none were given."
    )

    try:
        content = _user_content("\n\n".join(parts), images)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_blocks("read"),
            output_config={"effort": EFFORT["read"], "format": READING_SCHEMA},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APIStatusError as exc:
        log.exception("API error reading result")
        return jsonify({"error": _friendly(exc)}), 502
    except anthropic.APIConnectionError:
        log.exception("connection error reading result")
        return jsonify({"error": "Could not reach the API. Check the network."}), 502

    if response.stop_reason == "refusal":
        return jsonify({"error": "That request was declined."}), 400

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.error("structured output was not valid JSON: %r", text[:500])
        return jsonify({"error": "The model's reply could not be parsed. Try again."}), 502
    return jsonify(data)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _friendly(exc: anthropic.APIStatusError) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "ANTHROPIC_API_KEY is missing or invalid on the server."
    if isinstance(exc, anthropic.RateLimitError):
        return "Rate limited. Wait a moment and try again."
    if exc.status_code >= 500:
        return "The API had a server error. Try again shortly."
    return f"API error: {exc.message}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
