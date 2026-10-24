"""Run every Web Node behavior check; fail if any check fails or cannot run."""
from __future__ import annotations

import shutil
import subprocess

from browser_support import NODE_TESTS


def main() -> int:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required")
    checks = sorted(NODE_TESTS.glob("*_check.mjs"))
    if not checks:
        raise RuntimeError("No Web Node checks found")
    failed = []
    for path in checks:
        try:
            result = subprocess.run([node, str(path)], capture_output=True, text=True,
                                    encoding="utf-8", timeout=30)
            passed = result.returncode == 0
            if not passed:
                print(result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            passed = False
            print(f"Timed out: {path.name}")
        print(f"{'PASS' if passed else 'FAIL'} {path.name}", flush=True)
        if not passed:
            failed.append(path.name)
    print(f"Node: {len(checks) - len(failed)}/{len(checks)} passed")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
