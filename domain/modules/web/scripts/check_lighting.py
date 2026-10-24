"""Verify real indoor illumination, cutaway occlusion and shadow resources in Chromium."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from browser_support import WORKSPACE, static_server


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WORKSPACE / "temp" / "lighting-checks")
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"checks": [], "screenshots": [], "errors": []}
    try:
        with static_server() as base, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 850})
                page.set_default_timeout(15000)
                page.on("pageerror", lambda error: report["errors"].append(str(error)))
                page.on("console", lambda msg: report["errors"].append(msg.text) if msg.type == "error" else None)
                page.goto(base + "/web-checks/room_lighting_browser_check.html")
                page.wait_for_function("window.lightingDemo !== undefined")
                page.evaluate("__diag.scene.getObjectByName('milky-way-sky').userData.ready")
                report["checks"] = page.evaluate("lightingDemo.checks()")
                for mode in ("both", "ceiling", "window", "reverse", "horizon"):
                    page.evaluate("mode => lightingDemo.show(mode)", mode)
                    page.wait_for_timeout(400)
                    filename = f"{mode}.png"
                    page.screenshot(path=str(output / filename))
                    report["screenshots"].append(filename)
            finally:
                browser.close()
    except Exception as error:
        report["fatal"] = f"{type(error).__name__}: {error}"
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool("fatal" in report or report["errors"] or not report["checks"]
                    or any(not check["pass"] for check in report["checks"])))


if __name__ == "__main__":
    raise SystemExit(main())
