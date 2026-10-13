"""布局页进入一台柜子的板件页：不要求整份布局已确认，也不写出板件。"""

from __future__ import annotations

import asyncio
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.room_page import render_draft_page
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


def cabinet_home() -> ProjectLayout:
    return ProjectLayout.from_source(
        {
            "rooms": [
                {
                    "id": "bedroom",
                    "name": "卧室",
                    "width_mm": 4000,
                    "depth_mm": 3600,
                    "height_mm": 2800,
                    "items": [
                        {
                            "id": "wardrobe",
                            "label": "衣柜",
                            "category": "wardrobe",
                            "furniture_category": "floor_cabinet",
                            "width": 1800,
                            "depth": 600,
                            "height": 2200,
                            "placement": {"mode": "wall", "host_wall": "north"},
                        },
                        {
                            "id": "bookcase",
                            "label": "书柜",
                            "category": "shelf",
                            "furniture_category": "floor_cabinet",
                            "manufacture": False,
                            "width": 900,
                            "depth": 350,
                            "height": 1800,
                            "placement": {"mode": "wall", "host_wall": "south"},
                        },
                    ],
                }
            ]
        }
    )


class CabinetPanelPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-cabinet-panel-page"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self._patch = mock.patch.object(server, "STORE_ROOT", self.root)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_unconfirmed_layout_opens_one_cabinet_and_refuses_the_other(self) -> None:
        project = self.orchestrator.create_project("家", cabinet_home())
        self.assertFalse(project.latest.layout.confirmed)
        revisions = len(project.revisions)

        page = asyncio.run(
            server.project_cabinet_panels(project.id, "wardrobe")
        ).body.decode("utf-8")
        self.assertIn("衣柜 · 板件", page)
        self.assertIn("1800 mm", page)
        self.assertIn("600 mm", page)
        self.assertIn("2200 mm", page)
        self.assertIn("回布局", page)
        self.assertIn("绿面是柜门这一面", page)
        self.assertIn("/vendor/three/0.186.0/three.module.js", page)
        self.assertIn('fetch("/api/preview/presence"', page)
        self.assertIn(f"room=bedroom", page)
        self.assertIn("item=wardrobe", page)
        self.assertNotIn("审查清单", page)
        self.assertEqual(len(self.store.load(project.id).revisions), revisions)
        self.assertFalse(self.store.load(project.id).latest.layout.confirmed)

        preview = asyncio.run(server.project_preview(project.id, _local())).body.decode("utf-8")
        self.assertIn(f'/api/project/{project.id}/cabinets', preview)
        self.assertIn("板件规划", preview)
        self.assertIn("这件只占位置", preview)
        self.assertIn("先保存外形", preview)

        draft = render_draft_page("draft", project.latest.layout.rooms[0])["html"]
        self.assertIn('const PANEL_URL_BASE="";', draft)

        with self.assertRaises(HTTPException) as kept:
            asyncio.run(server.project_cabinet_panels(project.id, "bookcase"))
        self.assertEqual(kept.exception.status_code, 422)
        self.assertEqual(kept.exception.detail, "这件只占位置")

        with self.assertRaises(HTTPException) as missing:
            asyncio.run(server.project_cabinet_panels(project.id, "missing"))
        self.assertEqual(missing.exception.status_code, 404)

        shared = asyncio.run(
            server.project_cabinet_panels(project.id, "wardrobe", mode="view")
        ).body.decode("utf-8")
        self.assertNotIn('id="shutdown-preview"', shared)
        self.assertIn("mode=view", shared)


def _local():
    from fake_request_support import local_request

    return local_request()


if __name__ == "__main__":
    unittest.main()
