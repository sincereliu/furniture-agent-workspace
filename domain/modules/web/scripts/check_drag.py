"""Exercise real canvas gestures and HTTP saves with an isolated temporary store.

Run outside the Windows sandbox with workspace .venv Python. Chromium must be installed.
No user project is opened or modified. --output writes the inspected canvas screenshot.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from urllib.request import urlopen
from unittest import mock

WORKSPACE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(WORKSPACE / "domain/stages/cad-generated/scripts"))
from runtime_paths import bootstrap_runtime_paths
bootstrap_runtime_paths(WORKSPACE)


@contextmanager
def isolated_server():
    import server
    import uvicorn
    from furniture_layout.scene_planning import plan_scene
    from furniture_layout.scene_edit import apply_scene_edit
    from furniture_layout.scene_store import save_scene

    room = {"id": "room", "width_mm": 3600, "depth_mm": 3000, "height_mm": 2800}
    item = {"id": "cab", "label": "书柜", "category": "bookcase", "furniture_category": "floor_cabinet",
            "width": 900, "depth": 400, "height": 1000,
            "placement": {"mode": "free", "origin_x_mm": 900, "origin_y_mm": 120, "rotation_z_deg": 0}}
    scene = apply_scene_edit(plan_scene(room, [item]), {"op": "set_pose", "item_id": "cab", "mode": "wall",
        "host_wall": "north", "origin_x_mm": 900, "origin_y_mm": 0, "origin_z_mm": 0, "rotation_z_deg": 0})
    with tempfile.TemporaryDirectory(prefix="furniture-drag-browser-") as directory, \
            mock.patch.object(server, "OUTPUT_ROOT", Path(directory)), \
            mock.patch.object(server, "STORE_ROOT", Path(directory)), \
            mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "0"}):
        save_scene("drag-check", scene, root=directory)
        anchor = {**item, "placement": {"mode": "wall", "host_wall": "north"}}
        dependent = {"id": "shelf", "category": "shelf", "width": 400, "depth": 300, "height": 1000,
                     "placement": {"mode": "wall", "host_wall": "north",
                                   "against": {"west": {"kind": "item", "id": "cab"}}}}
        fill = {"id": "fill", "category": "shelf", "depth": 300, "height": 1000,
                "placement": {"mode": "wall", "host_wall": "north", "fill": True}}
        save_scene("drag-against", plan_scene(room, [anchor, dependent]), root=directory)
        save_scene("drag-fill", plan_scene(room, [anchor, fill]), root=directory)
        save_scene("drag-disjoint", plan_scene(room, [anchor,
            {**fill, "height": 600, "placement": {**fill["placement"], "origin_z_mm": 1500}}]), root=directory)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        service = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port,
                                              log_level="error", lifespan="off"))
        thread = threading.Thread(target=lambda: service.run(sockets=[sock]), daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    with urlopen(base + "/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(.05)
            else:
                raise RuntimeError("temporary preview service did not become healthy")
            yield base
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            sock.close()
            if thread.is_alive():
                raise RuntimeError("temporary preview service did not stop")


HOOK = """
const checkDragModule=await import('/layout-view/layout_drag.js');
window.__dragCheck={
  scene:()=>structuredClone(displayScene()),
  committed:()=>structuredClone(scene),
  active:()=>Boolean(drag),
  pointer:()=>drag&&drag.pointerId,
  point:()=>{
    const item=scene.items[0],p=item.placement,angle=p.rotation_z_deg*Math.PI/180;
    const rect=canvas.getBoundingClientRect();
    for(const fx of [.3,.6,.8])for(const fy of [.3,.6,.8])for(const fz of [.3,.6,.8]){
      const x=p.origin_x_mm+fx*item.width*Math.cos(angle)-fy*item.depth*Math.sin(angle);
      const y=p.origin_y_mm+fx*item.width*Math.sin(angle)+fy*item.depth*Math.cos(angle);
      const pt=view.project(x,y,p.origin_z_mm+item.height*fz);
      const hit=view.pick(rect.left+pt.x,rect.top+pt.y);
      if(hit&&hit.kind==='item'&&hit.itemId===item.id)return {x:rect.left+pt.x,y:rect.top+pt.y};
    }
    throw Error('no exposed furniture surface for pointer test');
  },
  delta:([x,y])=>{
    const item=scene.items[0],basis=camera();
    const scale=verticalPlaneScale(canvas,basis,[...footprintCenter(item),item.z_start]);
    const a=checkDragModule.groundDragDelta({dx:1,dy:0,scale,right:basis.right,forward:basis.forward});
    const b=checkDragModule.groundDragDelta({dx:0,dy:1,scale,right:basis.right,forward:basis.forward});
    const det=a[0]*b[1]-a[1]*b[0];
    return [(x*b[1]-y*b[0])/det,(a[0]*y-a[1]*x)/det];
  }
};
"""


def check(output: Path | None = None):
    from playwright.sync_api import sync_playwright

    errors, writes, checks = [], [], []
    with isolated_server() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1320, "height": 950})
            page.set_default_timeout(15000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: writes.append(request.post_data_json)
                    if request.method == "POST" and request.url.endswith("/edit") else None)

            def instrument(route):
                response = route.fetch()
                body, suffix = response.text().rsplit("</script>", 1)
                route.fulfill(response=response, body=body + HOOK + "</script>" + suffix)

            page.route("**/editor", instrument)
            url = base + "/api/room-scene/drag-check/editor"

            def open_page():
                page.goto(url)
                page.wait_for_function("() => window.__dragCheck !== undefined")

            def snapshot(which="scene"):
                return page.evaluate(f"window.__dragCheck.{which}().items[0]")

            def start():
                point = page.evaluate("window.__dragCheck.point()")
                page.mouse.move(point["x"], point["y"])
                page.mouse.down()
                page.wait_for_function("() => window.__dragCheck.active()")
                return point

            def move(point, x, y, steps=8):
                delta = page.evaluate("delta=>window.__dragCheck.delta(delta)", [x, y])
                page.mouse.move(point["x"] + delta[0], point["y"] + delta[1], steps=steps)
                assert page.evaluate("window.__dragCheck.active()"), {
                    "error": "gesture cancelled during pointer move", "page_errors": errors,
                    "status": page.locator("#status").text_content(), "target": [x, y]}

            def release():
                preview = snapshot()
                with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/edit")) as saved:
                    page.mouse.up()
                response = saved.value
                assert response.ok, response.text()
                payload = response.json()["items"][0]
                for key in ("mode", "host_wall", "origin_x_mm", "origin_y_mm", "origin_z_mm", "rotation_z_deg"):
                    assert payload["placement"][key] == preview["placement"][key], (key, preview, payload)
                for a, b in zip(preview["footprint"], payload["footprint"]):
                    assert abs(a[0] - b["x_mm"]) < 1e-6 and abs(a[1] - b["y_mm"]) < 1e-6
                for key, value in payload["clearances_mm"].items():
                    assert abs(preview["clearances_mm"][key] - value) < 1e-6
                page.wait_for_function("() => !window.__dragCheck.active() && document.querySelector('#status').textContent.includes('已保存')")
                return payload

            open_page()
            original = snapshot("committed")
            point = start()
            move(point, 0, 800)
            move(point, 200, 800)
            move(point, 200, 0)
            assert snapshot()["placement"]["mode"] == "wall"
            move(point, 200, 800)
            candidate = snapshot()
            assert candidate["placement"]["origin_x_mm"] == 1100, candidate
            assert candidate["placement"]["origin_y_mm"] == 800, candidate
            assert snapshot("committed") == original
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                page.locator("#scene").screenshot(path=str(output))
            payload = release()
            checks.append("continuous detach / move / attach / detach preserves along-wall position")
            open_page()
            assert snapshot()["placement"] == payload["placement"]
            checks.append("preview, HTTP save and reopened standalone room have the same pose")

            # Attach on the next gesture; the backend must retain x=1100, not repack to x=0.
            point = start();move(point, 0, -800)
            assert snapshot()["placement"]["mode"] == "wall"
            payload = release()
            assert payload["placement"]["origin_x_mm"] == 1100
            checks.append("attachment after release saves the exact wall position")

            before, count = snapshot("committed"), len(writes)
            start();page.mouse.up()
            assert snapshot() == before and len(writes) == count
            checks.append("a click without dragging preserves wall placement and sends no edit")
            point = start();move(point, 100, 800)
            page.keyboard.press("Escape")
            page.mouse.up()
            assert snapshot() == before and len(writes) == count
            checks.append("Escape discards the private candidate and sends no edit")
            point = start();move(point, 100, 800)
            pointer = page.evaluate("window.__dragCheck.pointer()")
            page.dispatch_event("#scene", "pointercancel", {"pointerId": pointer})
            page.mouse.up()
            assert snapshot() == before and len(writes) == count
            checks.append("pointer cancellation restores geometry and controls")

            def reject(route):
                route.abort("connectionfailed")

            page.route("**/edit", reject)
            point = start();move(point, 0, 800);page.mouse.up()
            page.wait_for_function("() => document.querySelector('#status').textContent.includes('保存失败')")
            assert snapshot() == before
            page.unroute("**/edit", reject)
            checks.append("failed save recovers the confirmed pose")

            # Hold an actual HTTP response, then deliver it in the next gesture.
            held = {}
            def hold(route):
                held["response"] = route.fetch()
                held["route"] = route
                page.evaluate("window.__dragHeld=true")
            page.route("**/edit", hold, times=1)
            point = start();move(point, 0, 800);page.mouse.up()
            page.wait_for_function("() => window.__dragHeld === true")
            assert held, "edit response was not intercepted"
            point = start();move(point, 100, 0)
            active = snapshot()
            held["route"].fulfill(response=held["response"])
            page.wait_for_function("() => document.querySelector('#status').textContent.includes('已保存')")
            assert snapshot() == active
            release()
            checks.append("a late save response cannot overwrite the next gesture")

            for selector, value, field in (("[data-height-input]", "150", "origin_z_mm"),
                                            ("[data-rotation]", "15", "rotation_z_deg")):
                with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/edit")) as saved:
                    control = page.locator(selector)
                    control.fill(value)
                    control.press("Enter")
                response = saved.value
                assert response.ok, response.text()
                page.wait_for_function("() => document.querySelector('#status').textContent.includes('已保存')")
                assert snapshot()["placement"][field] == float(value)
                assert page.locator(selector).input_value() == value
            checks.append("height and rotation inputs use the same exact-pose save path")

            # A resized shape must be acknowledged before solving a new gesture on it.
            page.evaluate("window.__dragHeld=false")
            page.route("**/edit", hold, times=1)
            control = page.locator('[data-size="width"]')
            control.fill("800");control.press("Enter")
            page.wait_for_function("() => window.__dragHeld === true")
            count = len(writes)
            point = page.evaluate("window.__dragCheck.point()")
            page.mouse.move(point["x"], point["y"]);page.mouse.down();page.mouse.up()
            assert not page.evaluate("window.__dragCheck.active()") and len(writes) == count
            held["route"].fulfill(response=held["response"])
            page.wait_for_function("() => window.__dragCheck.committed().items[0].width === 800")
            checks.append("pending resize cannot start a gesture with stale dimensions")
            for constraint in ("against", "fill"):
                url = base + f"/api/room-scene/drag-{constraint}/editor"
                open_page()
                before, count = snapshot(), len(writes)
                point = start();move(point, 0, 800)
                assert snapshot() == before, (constraint, before, snapshot())
                page.mouse.up()
                assert not page.evaluate("window.__dragCheck.active()") and len(writes) == count
                checks.append(f"{constraint} dependency stops an invalid detach before release, without an edit")
                # Numeric edits must use the same checks as pointer gestures.
                control = page.locator('[data-rotation]')
                control.fill("90");control.press("Enter")
                assert snapshot() == before and len(writes) == count
                checks.append(f"{constraint} dependency blocks an invalid numeric rotation without saving")
                with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/edit")) as saved:
                    control = page.locator('[data-height-input]')
                    control.fill("1200");control.press("Enter")
                response = saved.value
                assert response.ok, response.text()
                page.wait_for_function("() => window.__dragCheck.committed().items[0].placement.origin_z_mm === 999")
                assert response.json()["items"][0]["placement"]["origin_z_mm"] == 999
                open_page()
                assert snapshot()["placement"]["origin_z_mm"] == 999
                checks.append(f"{constraint} dependency clamps height to a saveable pose and preserves it on reopen")
            url = base + "/api/room-scene/drag-disjoint/editor"
            open_page()
            point = start();move(point, 0, 800)
            assert snapshot()["placement"]["origin_y_mm"] == 800
            release()
            checks.append("a fill in a disjoint height band leaves valid dragging enabled")
            assert not errors, errors
            return {"checks": checks, "writes": len(writes), "page_errors": errors,
                    "screenshot": str(output) if output else None}
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.output), ensure_ascii=False, indent=2))
