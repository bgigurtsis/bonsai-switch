# SPDX-License-Identifier: Apache-2.0
# Local HTTP integration; upstream model implementation is installed separately.
#!/usr/bin/env python3
"""Serve Bonsai 2 and OrcaBonsai through an OpenAI-compatible local API."""

from __future__ import annotations

import asyncio
import json
import queue
import os
import sys
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterator

import jinja2
import mlx.core as mx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

# Upstream code stays in its own pinned checkout with its original notices.
UPSTREAM = Path(os.environ["ORCABONSAI_UPSTREAM"]).resolve()
sys.path.insert(0, str(UPSTREAM))

from bonsai_abliterate.ablation import Ablated, install, load_direction
from bonsai_abliterate.pack import eos_ids, load_pack, load_tokenizer
from generation import generate


PACK = Path(os.environ["ORCABONSAI_PACK"]).resolve()
DIRECTION = UPSTREAM / "directions" / "refusal_dir.safetensors"
HOST = "127.0.0.1"
PORT = int(os.environ.get("ORCABONSAI_PORT", "18123"))

MODEL_MODES: dict[str, float] = {
    "bonsai-original": 0.0,
    "orcabonsai": 1.0,
}

EFFORT_MAP = {
    "minimal": "low",
    "low": "low",
    "medium": "medium",
    "high": "xhigh",
    "xhigh": "xhigh",
    "max": "xhigh",
}

app = FastAPI(title="OrcaBonsai LM Studio Adapter")
_lock = threading.Lock()
_admission = threading.Lock()
_state: dict[str, Any] = {}
# MLX arrays and streams must stay on one persistent inference thread.
_inference = ThreadPoolExecutor(max_workers=1, thread_name_prefix="orca-inference")


def _load_once() -> dict[str, Any]:
    """Load one shared model and wrap it so alpha can change per request.

    Why: original Bonsai and OrcaBonsai use identical weights; only runtime alpha differs.
    If wrong: switching model IDs could duplicate memory or apply the wrong behavior.
    """
    if _state:
        return _state
    model, config = load_pack(PACK)
    tokenizer = load_tokenizer(PACK)
    stops = eos_ids(PACK, config, tokenizer)
    direction, _ = load_direction(DIRECTION)
    paths = install(model, config, direction, alpha=0.0)
    language_model = model.language_model
    wrappers: list[Ablated] = []
    for path in paths:
        current = language_model
        for part in path.split("."):
            current = current[int(part)] if part.isdigit() else getattr(current, part)
        if not isinstance(current, Ablated):
            raise RuntimeError(f"Expected ablation wrapper at {path}")
        wrappers.append(current)
    _state.update(
        model=model,
        language_model=language_model,
        config=config,
        tokenizer=tokenizer,
        stops=stops,
        wrappers=wrappers,
    )
    return _state


def _set_alpha(wrappers: list[Ablated], alpha: float) -> None:
    """Set the reversible runtime projection strength for one request.

    Why: alpha zero is original Bonsai while alpha one is OrcaBonsai.
    If wrong: a request labeled original could silently run the ablated model.
    """
    for wrapper in wrappers:
        wrapper._alpha = alpha  # noqa: SLF001 - upstream exposes alpha only on its wrapper.


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI tool-call arguments into the mapping expected by the template.

    Why: OpenAI transports store arguments as JSON strings; the model template iterates keys.
    If wrong: tool-call history fails to render after the first agent action.
    """
    normalized = json.loads(json.dumps(messages))
    for message in normalized:
        for call in message.get("tool_calls") or []:
            function = call.get("function", call)
            arguments = function.get("arguments")
            if isinstance(arguments, str):
                try:
                    function["arguments"] = json.loads(arguments)
                except json.JSONDecodeError:
                    function["arguments"] = {"input": arguments}
    return normalized


def _render(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    effort: str | None,
) -> str:
    """Render chat, tools, and the selected reasoning effort with the model's template.

    Why: the bundled renderer does not expose tools or reasoning effort.
    If wrong: Oh My Pi cannot call tools or low/xhigh labels behave identically.
    """
    template = (PACK / "chat_template.jinja").read_text()
    env = jinja2.Environment(trim_blocks=False, lstrip_blocks=False)
    env.globals["raise_exception"] = lambda message: (_ for _ in ()).throw(
        ValueError(message)
    )
    return env.from_string(template).render(
        messages=_normalize_messages(messages),
        tools=tools,
        add_generation_prompt=True,
        enable_thinking=effort is not None,
        reasoning_effort=effort or "low",
    )


def _decode_parameter(value: str) -> Any:
    stripped = value.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


def _parse_reply(text: str) -> tuple[str, str, list[dict[str, Any]]]:
    """Separate visible answer, reasoning, and XML tool calls.

    Why: Bonsai emits its native XML tool syntax while OpenAI clients expect JSON tool calls.
    If wrong: Oh My Pi displays tool XML instead of executing the requested tool.
    """
    if "</think>" in text:
        reasoning, remainder = text.split("</think>", 1)
    else:
        reasoning, remainder = "", text
    calls: list[dict[str, Any]] = []
    pattern = re.compile(
        r"<tool_call>\s*<function=([^>\s]+)>\s*(.*?)</function>\s*</tool_call>",
        re.DOTALL,
    )
    matches = list(pattern.finditer(remainder))
    for match in matches:
        arguments: dict[str, Any] = {}
        for parameter in re.finditer(
            r"<parameter=([^>\s]+)>\s*(.*?)</parameter>", match.group(2), re.DOTALL
        ):
            arguments[parameter.group(1)] = _decode_parameter(parameter.group(2))
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:24]}",
                "type": "function",
                "function": {
                    "name": match.group(1),
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
        )
    content = remainder[: matches[0].start()] if matches else remainder
    return content.strip(), reasoning.strip(), calls


def _completion(payload: dict[str, Any], on_text=None, cancelled=None) -> dict[str, Any]:
    """Run one request under a lock because alpha and MLX state are shared.

    Why: simultaneous requests with different model IDs must not change alpha mid-generation.
    If wrong: replies can mix original and ablated behavior nondeterministically.
    """
    model_id = payload.get("model", "orcabonsai")
    if model_id not in MODEL_MODES:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="messages must be a non-empty list")
    alpha = MODEL_MODES[model_id]
    tools = payload.get("tools") or []
    requested_effort = payload.get("reasoning_effort")
    thinking_enabled = payload.get("enable_thinking")
    if thinking_enabled is False:
        effort = None
    elif thinking_enabled is True:
        effort = EFFORT_MAP.get(str(requested_effort).lower(), "low")
    else:
        effort = EFFORT_MAP.get(str(requested_effort).lower())
    # No server-imposed output cap; only honor an explicit caller budget.
    requested_tokens = payload.get("max_completion_tokens", payload.get("max_tokens"))
    max_tokens = int(requested_tokens) if requested_tokens is not None else None
    if max_tokens is not None and max_tokens <= 0:
        raise HTTPException(status_code=400, detail="An explicit token budget must be positive")
    temperature = float(payload.get("temperature", 0.0) or 0.0)
    top_p = float(payload.get("top_p", 0.95) or 0.95)

    with _lock:
        state = _load_once()
        _set_alpha(state["wrappers"], alpha)
        prompt_text = _render(messages, tools, effort)
        prompt_ids = state["tokenizer"].encode(
            prompt_text, add_special_tokens=False
        ).ids
        reply, elapsed, generated = generate(
            state["language_model"],
            state["tokenizer"],
            prompt_ids,
            state["stops"],
            max_tokens,
            temperature,
            top_p,
            stream=False,
            on_text=on_text if not tools and effort is None else None,
            cancelled=cancelled,
        )
    content, reasoning, tool_calls = _parse_reply(reply)
    message: dict[str, Any] = {"role": "assistant", "content": content or None}
    if reasoning:
        message["reasoning_content"] = reasoning
    if tool_calls:
        message["tool_calls"] = tool_calls
    finish_reason = "tool_calls" if tool_calls else (
        "length" if max_tokens is not None and generated >= max_tokens else "stop"
    )
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": len(prompt_ids),
            "completion_tokens": generated,
            "total_tokens": len(prompt_ids) + generated,
        },
        "timing": {"generation_seconds": elapsed},
        "reasoning_effort": effort or "off",
    }


def _run_completion(payload, on_text=None, cancelled=None):
    """Keep both HTTP response modes on the inference thread's GPU stream."""
    try:
        with mx.stream(mx.gpu):
            return _completion(payload, on_text, cancelled)
    finally:
        _admission.release()


async def _as_sse(payload: dict[str, Any]):
    """Stream plain replies while generation runs and cancel on disconnect.
    Why: buffering the full answer makes short greetings appear hung.
    If wrong: partial Unicode is lost or a stopped chat blocks the next one.
    """
    events = queue.Queue()
    stopped = threading.Event()
    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    sent = ""

    def produce():
        try:
            result = _run_completion(payload, lambda text: events.put(("text", text)), stopped.is_set)
            events.put(("done", result))
        except Exception as exc:  # Relay worker failures to the streaming client.
            events.put(("error", str(exc)))

    def chunk(delta, finish=None, usage=None):
        event = {
            "id": response_id, "object": "chat.completion.chunk",
            "created": created, "model": payload.get("model", "orcabonsai"),
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        if usage is not None:
            event["usage"] = usage
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    worker = _inference.submit(produce)
    try:
        yield chunk({"role": "assistant"})
        while True:
            try:
                kind, value = events.get_nowait()
            except queue.Empty:
                # Async waiting lets Starlette cancel us on client disconnect.
                await asyncio.sleep(0.02)
                continue
            if kind == "error":
                yield f"data: {json.dumps({'error': {'message': value}})}\n\n"
                break
            if kind == "text":
                if value.startswith(sent):
                    delta = value[len(sent):]
                    if delta:
                        yield chunk({"content": delta})
                    sent = value
                continue
            choice = value["choices"][0]
            message = dict(choice["message"])
            message.pop("role", None)
            if sent:
                # Plain content was already delivered; do not repeat it.
                message.pop("content", None)
            calls = message.get("tool_calls", [])
            for index, call in enumerate(calls):
                call["index"] = index
            if message:
                yield chunk(message)
            yield chunk({}, choice["finish_reason"], value["usage"])
            break
        yield "data: [DONE]\n\n"
    finally:
        stopped.set()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "orcabonsai-lmstudio-adapter", "loaded": bool(_state), "busy": _admission.locked()}


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "owned_by": "local"}
            for model_id in MODEL_MODES
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(payload: dict[str, Any]):
    if payload.get("model", "orcabonsai") not in MODEL_MODES:
        raise HTTPException(status_code=404, detail="Unknown model")
    if not isinstance(payload.get("messages"), list) or not payload["messages"]:
        raise HTTPException(status_code=400, detail="messages must be a non-empty list")
    if not _admission.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Orca is busy in another chat. Stop that response or wait for it to finish.")
    if payload.get("stream"):
        return StreamingResponse(_as_sse(payload), media_type="text/event-stream")
    return JSONResponse(_inference.submit(_run_completion, payload).result())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
