"""Check the real frozen-panel page, edits, HTTP save and read-only sharing.

Run outside the Windows sandbox with workspace .venv Python and Chromium.
Uses an isolated temporary store and the actual planning/freezing pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from unittest import mock

from project_browser_support import WORKSPACE, isolated_project_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests/browser"))
from panel_project import create_panel_project


def browser_checks(output: Path, report: dict) -> None:
    import server
    from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
    from furniture_workflow.workflow_store import JsonProjectStore
    from playwright.sync_api import sync_playwright

    def verify(condition: bool, name: str) -> None:
        if not condition:
            raise AssertionError(name)
        report["checks"].append(name)

    with isolated_project_server() as base, \
            mock.patch.dict(os.environ, {server.LAYOUT_EDIT_ENV: "1"}), \
            sync_playwright() as playwright:
        store = JsonProjectStore(server.STORE_ROOT)
        orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE, project_store=store)
        project = create_panel_project(orchestrator)
        before_sha = store.load(project.id).latest.confirmed_panel_sha256
        before_revisions = len(store.load(project.id).revisions)
        url = base + f"/api/project/{project.id}/cabinets/cabinet_1/panels"
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1320, "height": 950})
            page.set_default_timeout(15000)
            page.on("pageerror", lambda error: report["errors"].append(str(error)))
            page.on("console", lambda message: report["errors"].append(message.text)
                    if message.type == "error" else None)
            page.on("requestfailed", lambda request: report["errors"].append(
                f"{request.method} {request.url}: {request.failure}")
                if "/layout-view/" in request.url or "/vendor/" in request.url else None)
            page.goto(url)
            page.wait_for_function("() => window.page !== undefined")
            verify(page.evaluate("page.__test.meshes.length > 0"),
                   "real frozen panels and all viewer modules load")

            page.locator("[data-view=front]").click()
            verify(page.evaluate("page.__test.camera.position.z < 0"),
                   "front camera faces the doors")
            page.locator("[data-view=back]").click()
            verify(page.evaluate("page.__test.camera.position.z > 0"),
                   "back camera faces the back panel")
            page.locator("[data-view=front]").click()

            wood = page.evaluate("""page.__test.meshes.find(record =>
                record.panel.panel_type === 'side').panel.id""")
            page.evaluate("id => page.select(id)", wood)
            original = page.evaluate("""id => {
                const record = page.__test.meshes.find(record => record.panel.id === id);
                return {axis: record.panel.grain.axis, rotation: record.woodMap.rotation};
            }""", wood)
            verify(page.locator("#grain-editor").is_hidden(),
                   "selecting a panel does not change its properties")
            before_label = page.locator("#detail .grainrow").text_content()
            page.locator("#detail .grainrow").click()
            grain_axis = page.evaluate("""id => {
                const record = page.__test.meshes.find(record => record.panel.id === id);
                return record.panel.grainView.axis;
            }""", wood)
            verify(page.locator("#detail .grainrow").text_content() != before_label
                   and page.evaluate("""({id, rotation}) =>
                       page.__test.meshes.find(record => record.panel.id === id)
                           .woodMap.rotation !== rotation""", {"id": wood, "rotation": original["rotation"]}),
                   "grain editing changes both the displayed direction and real texture")
            page.locator("#detail .grainrow").click()
            verify(page.locator("#detail .grainrow").text_content() == before_label
                   and page.evaluate("""({id, rotation}) =>
                       page.__test.meshes.find(record => record.panel.id === id)
                           .woodMap.rotation === rotation""", {"id": wood, "rotation": original["rotation"]}),
                   "repeated grain toggles restore the original texture")
            page.locator("#detail .grainrow").click()

            door = page.evaluate("""page.__test.meshes.find(record =>
                record.panel.panel_type === 'door' && !record.panel.hinge_locked).panel.id""")
            page.evaluate("id => page.select(id)", door)
            page.locator("#detail .hingerow button").first.click()
            page.locator("#open").evaluate("element => element.value = '80'")
            page.locator("#open").dispatch_event("input")
            left_angle = page.evaluate("id => page.__test.meshes.find(r => r.panel.id === id).mesh.rotation.z", door)
            page.locator("#detail .hingerow button").last.click()
            right_angle = page.evaluate("id => page.__test.meshes.find(r => r.panel.id === id).mesh.rotation.z", door)
            verify(left_angle < 0 < right_angle,
                   "editable hinge sides change the actual door opening direction")
            page.locator("#toggle-doors").click()
            verify(page.evaluate("""page.__test.meshes.filter(record =>
                record.panel.panel_type === 'door').every(record => !record.mesh.visible)"""),
                   "door visibility controls reach the renderer")
            page.locator("#toggle-doors").click()
            page.screenshot(path=str(output / "edited.png"))
            report["screenshots"].append("edited.png")

            with page.expect_response(lambda response: response.request.method == "POST"
                                      and response.url == url) as saved:
                with page.expect_navigation(wait_until="domcontentloaded"):
                    page.locator("#grain-save").click()
            verify(saved.value.ok, "panel edits are accepted by the real HTTP endpoint")
            operation = saved.value.request.post_data_json
            verify(operation["axes"] == {wood: grain_axis} and operation["hinges"] == {door: "right"},
                   "the request contains the selected grain axis and hinge side")
            page.wait_for_function("() => window.page !== undefined")
            reloaded = page.evaluate("""({wood, door}) => {
                const records = page.__test.meshes;
                return {axis: records.find(record => record.panel.id === wood).panel.grain.axis,
                    hinge: records.find(record => record.panel.id === door).panel.hinge_side};
            }""", {"wood": wood, "door": door})
            current = store.load(project.id)
            verify(current.latest.confirmed_panel_sha256 != before_sha
                   and len(current.revisions) == before_revisions + 1
                   and reloaded == {"axis": grain_axis, "hinge": "right"}
                   and page.locator("#grain-editor").is_hidden(),
                   "save creates a new frozen revision and reloads its actual grain and hinge")
            page.screenshot(path=str(output / "saved.png"))
            report["screenshots"].append("saved.png")

            page.goto(url + "?mode=view")
            page.wait_for_function("() => window.page !== undefined")
            page.evaluate("id => page.select(id)", wood)
            verify(page.locator("#detail .grainrow").count() == 0
                   and page.locator("#grain-save").is_hidden()
                   and page.locator("#detail").is_visible(),
                   "shared panels remain selectable without property editing controls")
            page.evaluate("id => page.select(id)", door)
            verify(page.locator("#detail .hingerow button").count() == 0,
                   "shared panels do not expose hinge editing controls")
            page.screenshot(path=str(output / "shared.png"))
            report["screenshots"].append("shared.png")
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WORKSPACE / "temp/panel-checks")
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"checks": [], "errors": [], "screenshots": []}
    try:
        browser_checks(output, report)
    except Exception as error:
        report["fatal"] = f"{type(error).__name__}: {error}"
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report.get("fatal") or report["errors"] or not report["checks"]))


if __name__ == "__main__":
    raise SystemExit(main())
