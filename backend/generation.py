# SPDX-License-Identifier: Apache-2.0
# Derived from Continuum-AI-Corp/OrcaBonsai-27B-Uncensored run.py.
# Modified for streaming callbacks, cancellation, and uncapped generation.
# Upstream commit: 947a80cd1d3b4f9a97417025e6c2c62223571287
import sys
import time

import mlx.core as mx

def sample(logits, temp, top_p):
    """Greedy when temp is 0, otherwise temperature + nucleus sampling."""
    if temp <= 0:
        return mx.argmax(logits)
    logits = logits / temp
    if not 0 < top_p < 1:
        return mx.random.categorical(logits)
    # Sample in descending-probability space, then map the choice back through the
    # sort order: simpler and cheaper than scattering a mask into vocab order.
    probs = mx.softmax(logits)
    order = mx.argsort(-probs)
    ordered = probs[order]
    keep = (mx.cumsum(ordered) - ordered) < top_p
    choice = mx.random.categorical(mx.log(mx.where(keep, ordered, 0.0) + 1e-30))
    return order[choice]


def generate(language_model, tok, ids, stops, max_new, temp, top_p, stream=True,
             on_text=None, cancelled=None):
    """Generate tokens with optional progress and cancellation callbacks.
    Why: API clients need visible progress and Stop must release the model.
    If wrong: disconnected requests keep generating and block later chats.
    """
    cache = language_model.make_cache() if hasattr(language_model, "make_cache") else None
    produced, t0 = [], time.time()
    prompt = mx.array([ids], dtype=mx.int32)
    # None means generate until EOS or cancellation, without a token cap.
    while max_new is None or len(produced) < max_new:
        if cancelled is not None and cancelled():
            break
        out = language_model(prompt, cache=cache)
        token = int(sample(out.logits[0, -1].astype(mx.float32), temp, top_p).item())
        if token in stops:
            break
        produced.append(token)
        if on_text is not None:
            # Decode the prefix to preserve Unicode split across tokens.
            on_text(tok.decode(produced).rstrip("\ufffd"))
        if stream:
            sys.stdout.write(tok.decode([token]))
            sys.stdout.flush()
        prompt = mx.array([[token]], dtype=mx.int32)
    if stream:
        sys.stdout.write("\n")
    elapsed = time.time() - t0
    return tok.decode(produced), elapsed, len(produced)
