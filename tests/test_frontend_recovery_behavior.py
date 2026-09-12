"""Execute frontend contracts rather than only checking source strings."""
import shutil
import subprocess

import pytest


def test_frontend_recovery_javascript_contracts():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for JavaScript behavior checks')
    result = subprocess.run([node, '--test', 'tests/frontend-recovery.test.cjs'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
