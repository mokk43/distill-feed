from __future__ import annotations

from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
