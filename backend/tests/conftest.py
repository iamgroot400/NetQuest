import sys
from pathlib import Path

# Tests import `app.*` directly, so the backend root must be importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
