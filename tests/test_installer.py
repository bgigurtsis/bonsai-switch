import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import installer
import launcher


class InstallationTests(unittest.TestCase):
    def test_missing_files_fail_with_actionable_message(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(launcher, 'DATA', Path(folder)):
            with self.assertRaisesRegex(RuntimeError, 'Run Install.command'):
                launcher.commands()

    def test_paths_with_spaces_are_separate_arguments(self):
        with tempfile.TemporaryDirectory(prefix='adapter test ') as folder:
            data = Path(folder)
            for name in ['gguf/Ternary-Bonsai-2-27B-PQ2_0.gguf', 'bonsai/bin/mac/llama-server',
                         'python/bin/python', 'mlx/config.json', 'mlx/runtime/vision_artifact.py',
                         'orca/directions/refusal_dir.safetensors']:
                path = data / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            with patch.object(launcher, 'DATA', data):
                specs = launcher.commands()
            self.assertEqual(specs[0][2][0], str(data / 'bonsai/bin/mac/llama-server'))
            self.assertNotIn('--alias orcabonsai', ' '.join(specs[0][2]))

    def test_wrong_source_revision_is_not_reset(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(installer, 'DATA', Path(folder)):
            (Path(folder) / 'upstream').mkdir()
            with patch.object(installer.subprocess, 'check_output', return_value='different\n'), patch.object(installer, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'different revision'):
                    installer.checkout('upstream', 'https://example.invalid/repo.git', 'expected')
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
