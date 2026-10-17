import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from xo_inventory.config import parse_config  # noqa: E402


@pytest.fixture
def inventory_dir(tmp_path):
    """
    Returns a helper that writes files under a fresh inventory folder:

        root = inventory_dir({"hosts/web1.yaml": "app: web", ...})
    """

    def make(files: dict[str, str]) -> Path:
        root = tmp_path / "inventory"
        root.mkdir(exist_ok=True)
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content))
        return root

    return make


@pytest.fixture
def make_config(tmp_path):
    """Build a Config pointing at `root`, with optional section overrides."""

    def make(root: Path, **sections):
        data = {"main": {"STORAGE_LOCATION": str(root)}}
        for section, values in sections.items():
            data.setdefault(section.replace("_", "-"), {}).update(values)
        return parse_config(data, tmp_path / "xo_inventory.yaml")

    return make
