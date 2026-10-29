import os
import tempfile
from pathlib import Path


TEST_ROOT = Path(tempfile.mkdtemp(prefix="visionguard-tests-"))
os.environ.setdefault("VISIONGUARD_RUNTIME_DIR", str(TEST_ROOT / "runtime"))
os.environ.setdefault("VISIONGUARD_MODEL_DIR", str(Path(__file__).resolve().parents[2] / "models"))
os.environ.setdefault("VISIONGUARD_DATABASE_URL", f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}")
os.environ.setdefault("VISIONGUARD_AUTH_SECRET", "test-only-secret-with-at-least-thirty-two-characters")

