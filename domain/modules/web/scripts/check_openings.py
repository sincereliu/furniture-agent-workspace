"""Check actual layout door/window rendering and save screenshots without opening projects.

Run outside the sandbox with the workspace .venv Python, like check_outline.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from browser_support import NODE_TESTS, WORKSPACE, static_server


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WORKSPACE / "temp" / "opening-checks")
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"checks": [], "screenshots": [], "errors": []}
    try:
        for name in ("opening_models_check.mjs", "opening_markers_check.mjs", "wall_solid_check.mjs"):
            subprocess.run([shutil.which("node") or "node", str(NODE_TESTS / name)], check=True, timeout=30)
            report["checks"].append(name)
        with static_server() as base, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 850})
                page.set_default_timeout(15000)
                page.on("pageerror", lambda error: report["errors"].append(str(error)))
                page.on("console", lambda msg: report["errors"].append(msg.text) if msg.type == "error" else None)
                page.goto(base + "/web-checks/opening_models_browser_check.html")
                page.wait_for_function("window.openingDemo !== undefined")
                page.evaluate("__diag.scene.getObjectByName('milky-way-sky').userData.ready")
                for mode in ("normal", "reverse", "detail", "far"):
                    page.evaluate("mode => openingDemo.show(mode)", mode)
                    page.wait_for_function("""() => {
                      const walls=__diag.stageGroup.children.filter(n=>n.userData.wallId);
                      return walls.some(w=>!w.visible)&&walls.every(w=>
                        w.userData.material.opacity<0.002||w.userData.material.opacity>0.998);
                    }""")
                    state = page.evaluate("""() => {
                      const walls=__diag.stageGroup.children.filter(n=>n.userData.wallId);
                      return walls.map(w=>({id:w.userData.wallId,visible:w.visible,opacity:w.userData.material.opacity,
                        openings:w.userData.openings.map(o=>({
                          marker:o.userData.marker.visible,
                          surfaces:o.userData.surfaces.every(s=>Math.abs(s.material.opacity-s.opacity*w.userData.material.opacity)<1e-6),
                          count:o.children.length,
                        }))}));
                    }""")
                    assert sum(len(w["openings"]) for w in state) == 5, (mode, state)
                    assert any(w["visible"] for w in state) and any(not w["visible"] for w in state), (mode, state)
                    for wall in state:
                        for opening in wall["openings"]:
                            assert opening["surfaces"] and opening["count"] > 20, state
                            assert opening["marker"] == (wall["opacity"] < 0.998), state
                    filename = f"{mode}.png"
                    page.screenshot(path=str(output / filename))
                    report["screenshots"].append(filename)
                    report["checks"].append(f"{mode}: all walls share entity/marker fade")
                # Exercise actual scene caching/rebuilding with changed dimensions and sill height.
                result = page.evaluate("""() => {
                  const data=structuredClone(openingDemo.data);
                  const original=__diag.stageGroup.children.find(w=>w.userData.wallId==='north').userData.openings[0];
                  let disposed=0;original.traverse(n=>n.geometry?.addEventListener('dispose',()=>disposed++));
                  data.openings[1].sill_height_mm=1000;data.openings[1].width_mm=1400;
                  openingDemo.view.sync(data,{dims:false,readOnly:true});
                  const next=__diag.stageGroup.children.find(w=>w.userData.wallId==='north').userData.openings[1];
                  return {disposed,sill:next.position.y,marker:next.userData.marker.userData.text,
                    picked:openingDemo.view.pick(600,350)};
                }""")
                assert result["disposed"] > 20 and result["sill"] == 1001 and "1400" in result["marker"]
                assert result["picked"] is None
                report["checks"].append("real layout rebuild disposes old geometry, applies dimensions and keeps furniture picking separate")
                assert not report["errors"], report["errors"]
            finally:
                browser.close()
    except Exception as error:
        report["fatal"] = f"{type(error).__name__}: {error}"
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int("fatal" in report or bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
