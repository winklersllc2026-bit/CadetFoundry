"""USB mode: the start file keeps all data on the drive, a model copies with exactly its own files, and the portable
AI only starts when the drive carries one and no Ollama is running."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())

import make_usb  # noqa: E402
import run  # noqa: E402


class UsbTests(unittest.TestCase):
    def test_start_file_keeps_data_on_the_drive(self):
        bat = make_usb.START_BAT
        self.assertIn('set "VANGUARD_DATA=%~dp0VanguardData"', bat)
        self.assertIn(r'"%~dp0Vanguard\python\python.exe" run.py', bat)
        self.assertIn("%*", bat)
        self.assertIn("VANGUARD_OLLAMA", bat)

    def test_a_file_briefly_locked_by_antivirus_is_retried(self):
        calls = []
        def flaky(x):
            calls.append(x)
            if len(calls) < 3:
                raise PermissionError("in use")
            return "copied"
        self.assertEqual(make_usb._retry(flaky, "f", wait=0), "copied")
        self.assertEqual(len(calls), 3)
        with self.assertRaises(PermissionError):
            make_usb._retry(lambda x: (_ for _ in ()).throw(PermissionError()), "f", tries=2, wait=0)

    def test_copy_model_copies_only_its_blobs(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src = Path(src)
            man = src / "manifests" / "registry.ollama.ai" / "library" / "tiny" / "1b"
            man.parent.mkdir(parents=True)
            man.write_text(json.dumps({"config": {"digest": "sha256:aa"}, "layers": [{"digest": "sha256:bb"}]}))
            (src / "blobs").mkdir()
            for name in ("sha256-aa", "sha256-bb", "sha256-other"):
                (src / "blobs" / name).write_bytes(b"x" * 10)
            with mock.patch.dict(os.environ, {"OLLAMA_MODELS": str(src)}):
                size = make_usb.copy_model("tiny:1b", Path(dst))
            self.assertEqual(size, 20)
            self.assertEqual(sorted(p.name for p in (Path(dst) / "blobs").iterdir()), ["sha256-aa", "sha256-bb"])
            self.assertTrue((Path(dst) / "manifests" / "registry.ollama.ai" / "library" / "tiny" / "1b").exists())
            with mock.patch.dict(os.environ, {"OLLAMA_MODELS": str(src)}), self.assertRaises(FileNotFoundError):
                make_usb.copy_model("missing:7b", Path(dst))

    def test_portable_ai_starts_only_when_needed(self):
        with mock.patch("subprocess.Popen") as popen:
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("VANGUARD_OLLAMA", None)
                run._start_portable_ai()                          # not a USB drive with AI
            with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
                exe = f.name
            try:
                with mock.patch.dict(os.environ, {"VANGUARD_OLLAMA": exe}), \
                        mock.patch("vanguard.engine.local_models", return_value=["qwen2.5:3b"]):
                    run._start_portable_ai()                      # an Ollama is already running: use it
                self.assertFalse(popen.called)
                with mock.patch.dict(os.environ, {"VANGUARD_OLLAMA": exe}), \
                        mock.patch("vanguard.engine.local_models", return_value=None), mock.patch("atexit.register"):
                    run._start_portable_ai()                      # none running: start the drive's copy
                args, kwargs = popen.call_args
                self.assertEqual(args[0], [exe, "serve"])
                self.assertEqual(kwargs["env"]["OLLAMA_MODELS"], os.path.join(os.path.dirname(exe), "models"))
            finally:
                os.unlink(exe)


if __name__ == "__main__":
    unittest.main()
