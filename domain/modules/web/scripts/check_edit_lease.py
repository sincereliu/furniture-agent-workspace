"""Check the real layout page's lease recovery against an isolated HTTP service.

Run with workspace .venv Python outside the Windows sandbox. The shared browser
fixture creates a temporary store; no user project or preview process is touched.
"""
from __future__ import annotations

import json
import os
from unittest import mock

from check_drag import WORKSPACE, isolated_server


HOOK = """
window.__leaseCheck={
  snapshot:()=>({phase:leaseStore.phase,hasToken:Boolean(leaseStore.token),
    id:leaseStore.id,holder:leaseStore.shown&&leaseStore.shown.holder,
    editable:ownsLease(),pending:Boolean(leaseStore.pending)}),
  canEdit:()=>canEditLayout(),
  save:()=>persist(scene.items[0],'resize',{width:scene.items[0].width+1}),
  idle:()=>{leaseStore.lastInteraction=0;yieldIdleLease()},
};
"""


def check():
    import server
    from furniture_layout.project_layout import ProjectLayout
    from furniture_workflow.workflow_lease import read_lease, release, transfer
    from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
    from furniture_workflow.workflow_store import JsonProjectStore
    from playwright.sync_api import sync_playwright

    checks, errors = [], []
    source = {"rooms": [{"id": "room", "name": "检查房间", "width_mm": 4000,
        "depth_mm": 3600, "height_mm": 2800, "items": [{"id": "cab",
        "label": "书柜", "category": "bookcase", "furniture_category": "floor_cabinet",
        "width": 900, "depth": 400, "height": 1000,
        "placement": {"mode": "free", "origin_x_mm": 900,
                      "origin_y_mm": 200, "rotation_z_deg": 0}}]}]}

    with isolated_server() as base, \
            mock.patch.dict(os.environ, {server.LAYOUT_EDIT_ENV: "1"}), \
            sync_playwright() as playwright:
        project = FurnitureOrchestrator(workspace_root=WORKSPACE,
            project_store=JsonProjectStore(server.STORE_ROOT)).create_project("租约检查", ProjectLayout.from_source(source))
        url = base + f"/api/project/{project.id}/preview"
        lease_url = base + f"/api/project/{project.id}/edit-lease"
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1320, "height": 950})
        context.set_default_timeout(15000)

        def instrument(route):
            response = route.fetch()
            body, suffix = response.text().rsplit("</script>", 1)
            route.fulfill(response=response, body=body + HOOK + "</script>" + suffix)

        context.route("**/preview", instrument)

        def open_page():
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            page.wait_for_function("() => window.__leaseCheck !== undefined")
            return page

        def phase(page, value):
            page.wait_for_function("value => window.__leaseCheck.snapshot().phase === value "
                                   "&& !window.__leaseCheck.snapshot().pending", arg=value)

        def held_by(page):
            snapshot = page.evaluate("window.__leaseCheck.snapshot()")
            lease = read_lease(server.STORE_ROOT, project.id)
            assert snapshot["editable"] and snapshot["hasToken"] and lease.id == snapshot["id"]
            assert page.locator("#lease-badge").evaluate("element => element.classList.contains('mine')")

        try:
            first = open_page()
            phase(first, "ready")
            held_by(first)
            first.reload()
            phase(first, "ready")
            first.wait_for_function("async url => {const response=await fetch(url);"
                "const doc=await response.json();return doc.lease&&doc.lease.expires_in>60}",
                arg=base + f"/api/project/{project.id}/layout")
            held_by(first)
            checks.append("reload acquires before subscribing and keeps a connection-held lease")
            second = open_page()
            phase(second, "blocked")
            assert second.locator("#take-lease").is_visible()
            assert not second.evaluate("window.__leaseCheck.canEdit()")
            second.locator("#take-lease").click()
            phase(second, "ready")
            phase(first, "blocked")
            held_by(second)
            assert not first.evaluate("window.__leaseCheck.snapshot().hasToken")
            assert not first.evaluate("window.__leaseCheck.canEdit()")
            assert second.evaluate("window.__leaseCheck.save()")
            document = context.request.get(base + f"/api/project/{project.id}/layout").json()
            assert document["rooms"][0]["scene"]["items"][0]["width"] == 901
            checks.append("second window can explicitly take over and save; first window loses its credentials")

            second.close()
            phase(first, "ready")
            held_by(first)
            checks.append("remaining window reacquires automatically after owner closes")

            agent = transfer(server.STORE_ROOT, project.id, to="agent", label="检查助手")
            phase(first, "blocked")
            release(server.STORE_ROOT, project.id, token=agent.token)
            phase(first, "ready")
            held_by(first)
            agent = transfer(server.STORE_ROOT, project.id, to="agent", label="检查助手")
            phase(first, "blocked")
            first.locator("#take-lease").click()
            phase(first, "ready")
            held_by(first)
            checks.append("agent release returns editing automatically; explicit takeover also works")

            first.evaluate("window.__leaseCheck.idle()")
            phase(first, "idle")
            assert not first.evaluate("window.__leaseCheck.canEdit()")
            first.mouse.move(20, 20)
            phase(first, "ready")
            held_by(first)
            checks.append("idle page yields and can reacquire without reload")
            first.close()

            # A failed initial POST must expose a retry instead of claiming another writer exists.
            failed = context.new_page()
            failed.on("pageerror", lambda error: errors.append(str(error)))
            failed.route(lease_url, lambda route: route.abort("failed"))
            failed.goto(url)
            phase(failed, "error")
            assert not failed.evaluate("window.__leaseCheck.canEdit()")
            assert failed.locator("#take-lease").is_visible()
            failed.unroute(lease_url)
            failed.locator("#take-lease").click()
            phase(failed, "ready")
            held_by(failed)
            assert failed.evaluate("window.__leaseCheck.save()")
            checks.append("network failure offers retry and the recovered page really saves")
            failed.close()

            broken = context.new_page()
            broken.route(lease_url, lambda route: route.fulfill(status=500, json={"detail": "test failure"}))
            broken.goto(url)
            phase(broken, "error")
            assert not broken.evaluate("window.__leaseCheck.canEdit()")
            assert broken.locator("#take-lease").is_visible()
            broken.unroute(lease_url)
            broken.locator("#take-lease").click()
            phase(broken, "ready")
            held_by(broken)
            checks.append("HTTP failure also offers a working retry")
            broken.close()

            denied = context.new_page()
            denied.route(lease_url, lambda route: route.fulfill(status=403, json={"detail": "local only"}))
            denied.goto(url)
            phase(denied, "denied")
            assert not denied.evaluate("window.__leaseCheck.canEdit()")
            assert denied.locator("#take-lease").is_hidden()
            checks.append("403 stays read only without a misleading takeover button")
            denied.close()

            # With a delayed acquisition, pointer events must not fan out concurrent POSTs.
            delayed = context.new_page()
            delayed.add_init_script("""
              const originalFetch=window.fetch;
              window.__leasePosts=0;
              window.fetch=async function(input, options){
                if(String(input).endsWith('/edit-lease')&&options&&options.method==='POST'){
                  window.__leasePosts++;
                  await new Promise(resolve=>setTimeout(resolve,300));
                }
                return originalFetch(input,options);
              };
            """)
            delayed.goto(url)
            delayed.wait_for_function("() => window.__leaseCheck !== undefined")
            delayed.evaluate("for(let i=0;i<20;i++)window.dispatchEvent(new Event('pointerdown'))")
            phase(delayed, "ready")
            held_by(delayed)
            assert delayed.evaluate("window.__leasePosts") == 1
            checks.append("concurrent interactions share one lease request")
            delayed.close()

            assert not errors, errors
            print(json.dumps({"checks": checks, "page_errors": errors}, ensure_ascii=False, indent=2))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    check()
