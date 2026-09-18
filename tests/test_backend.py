"""Regression tests use fake inference; model weights are never loaded."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('ORCABONSAI_UPSTREAM', str(ROOT / '.runtime/orca'))
os.environ.setdefault('ORCABONSAI_PACK', str(ROOT / '.runtime/mlx'))
sys.path.insert(0, str(ROOT / 'backend'))
import server


def completed(text):
    return {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}], 'usage': {}}


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_precedes_completion(self):
        release = threading.Event()
        finished = threading.Event()
        def fake(payload, on_text, cancelled):
            on_text('Hello')
            on_text('Hello 🌳')
            release.wait(2)
            finished.set()
            return completed('Hello 🌳')
        with patch.object(server, '_completion', fake):
            server._admission.acquire()
            stream = server._as_sse({'model': 'orcabonsai'})
            await anext(stream)
            first = await anext(stream)
            self.assertFalse(finished.is_set())
            release.set()
            chunks = [first] + [chunk async for chunk in stream]
        content = ''
        for chunk in chunks:
            if '[DONE]' not in chunk:
                content += json.loads(chunk[6:])['choices'][0]['delta'].get('content', '')
        self.assertEqual(content, 'Hello 🌳')
        self.assertFalse(server._admission.locked())

    async def test_disconnect_releases_worker(self):
        observed = threading.Event()
        def fake(payload, on_text, cancelled):
            import time
            while not cancelled():
                time.sleep(0.01)
            observed.set()
            return completed('')
        with patch.object(server, '_completion', fake):
            server._admission.acquire()
            stream = server._as_sse({'model': 'orcabonsai'})
            await anext(stream)
            await stream.aclose()
            self.assertTrue(await asyncio.to_thread(observed.wait, 2))
            await asyncio.sleep(0.05)
            self.assertFalse(server._admission.locked())

    async def test_busy_is_an_immediate_error(self):
        server._admission.acquire()
        try:
            with self.assertRaises(server.HTTPException) as error:
                server.chat_completions({'model': 'orcabonsai', 'messages': [{'role': 'user', 'content': 'hi'}], 'stream': True})
            self.assertEqual(error.exception.status_code, 409)
        finally:
            server._admission.release()


class OutputBudgetTests(unittest.TestCase):
    def test_no_default_or_tool_ceiling(self):
        from types import SimpleNamespace
        seen = []
        def fake_generate(*args, **kwargs):
            seen.append(args[4])
            return 'Finished.', 0, 5000
        state = {'wrappers': [], 'tokenizer': SimpleNamespace(encode=lambda *args, **kwargs: SimpleNamespace(ids=[1])),
                 'language_model': None, 'stops': {0}}
        with patch.object(server, '_load_once', return_value=state), patch.object(server, '_set_alpha'), \
             patch.object(server, '_render', return_value='hello'), patch.object(server, 'generate', fake_generate):
            for tools in ([], [{'type': 'function'}]):
                result = server._completion({'model': 'orcabonsai', 'messages': [{'role': 'user', 'content': 'hello'}], 'tools': tools})
                self.assertIsNone(seen[-1])
                self.assertEqual(result['choices'][0]['finish_reason'], 'stop')


if __name__ == '__main__':
    unittest.main()
