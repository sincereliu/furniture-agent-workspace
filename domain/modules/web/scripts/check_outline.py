"""Run outline checks and save real WebGL screenshots for visual review.

Run with the workspace .venv Python. Node and Playwright Chromium must be installed.
This starts a temporary loopback static server; it never opens or writes projects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
from browser_support import NODE_TESTS, WORKSPACE, static_server
NODE_CHECKS = (
    "sofa_solid_check.mjs",
    "sofa_upholstery_check.mjs",
    "outline_style_check.mjs",
    "cartoon_outline_check.mjs",
    "shaped_item_ink_check.mjs",
    "ink_depth_check.mjs",
    "wall_contact_check.mjs",
    "wall_surface_check.mjs",
)


def browser_checks(output: Path) -> dict:
    from playwright.sync_api import sync_playwright

    errors: list[str] = []
    report: dict = {"checks": [], "screenshots": []}
    with static_server() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1000, "height": 800}, device_scale_factor=1)
            page.set_default_timeout(15000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(base + "/web-checks/cartoon_outline_browser_check.html?sofa", wait_until="commit")
            page.wait_for_function("document.body.dataset.result !== undefined", timeout=60000)
            report["checks"] = json.loads(page.locator("#details").text_content())
            page.locator("canvas").first.screenshot(path=str(output / "sofa.png"))
            report["screenshots"].append("sofa.png")
            page.goto(base + "/web-checks/cartoon_outline_browser_check.html?room")
            for viewport, prefix in ((1000, "room"), (560, "small-room")):
                page.set_viewport_size({"width": viewport, "height": 800})
                page.reload()
                page.evaluate("__diag.scene.getObjectByName('milky-way-sky').userData.ready")
                for label, name in (("常规", "normal"), ("缩远", "far"), ("另一视角", "reverse"),
                                    ("选中书柜", "selected"), ("碰撞书柜", "blocked")):
                    page.get_by_role("button", name=label, exact=True).click()
                    # Let the existing wall fade settle before capturing a comparison frame.
                    page.wait_for_timeout(450)
                    filename = f"{prefix}-{name}.png"
                    page.locator("#room-demo").screenshot(path=str(output / filename))
                    report["screenshots"].append(filename)
            report["errors"] = errors
        finally:
            browser.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WORKSPACE / "temp" / "outline-checks")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report: dict = {"node": []}
    try:
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js is required; node was not found on PATH")
        for filename in NODE_CHECKS:
            result = subprocess.run([node, str(NODE_TESTS / filename)], capture_output=True, text=True,
                                    encoding="utf-8", timeout=30)
            report["node"].append({"name": filename, "passed": result.returncode == 0,
                                   "output": result.stdout + result.stderr})
            print(f"{'PASS' if result.returncode == 0 else 'FAIL'} {filename}", flush=True)
        report.update(browser_checks(output))
    except Exception as error:
        report["fatal"] = str(error)
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    checks = report.get("checks", [])
    passed = sum(bool(check["pass"]) for check in checks)
    print(f"WebGL: {passed}/{len(checks)} passed; artifacts: {output}", flush=True)
    for check in checks:
        if not check["pass"]:
            print(f"FAIL {check['name']}")
    if report.get("fatal"):
        print(report["fatal"])
    for error in report.get("errors", []):
        print(f"BROWSER ERROR {error}")
    return int(bool(report.get("fatal") or report.get("errors") or not checks
                    or passed != len(checks) or any(not item["passed"] for item in report["node"])))


if __name__ == "__main__":
    raise SystemExit(main())
