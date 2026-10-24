"""Runs the scoring tests (tests/scoring.test.js) under Node.

Scoring runs in the browser, so its tests are JavaScript. They get the maps in
exactly the shape the page gets them from /api/maps/<id>.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ticket_to_ride.maps import all_maps

HERE = Path(__file__).parent


def test_scoring_js(tmp_path):
    node = shutil.which("node")
    if not node:
        if os.environ.get("CI"):
            pytest.fail("Node is needed to run the scoring tests")
        pytest.skip("Node isn't installed")
    for m in all_maps().values():
        (tmp_path / f"{m.id}.json").write_text(json.dumps(m.to_json()))
    proc = subprocess.run(
        [node, "--test", str(HERE / "scoring.test.js")],
        env={**os.environ, "TTR_MAPS": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
