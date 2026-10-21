"""首页门户页面与端点测试。"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import unittest

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_web.home_page import render_home_page
import server


class TestHomePage(unittest.TestCase):
    def test_render_home_page_empty(self) -> None:
        html = render_home_page("0.8.0", [])
        self.assertIn("Furniture Agent", html)
        self.assertIn("Studio Console", html)
        self.assertIn("v0.8.0", html)
        self.assertIn("工坊就绪", html)
        self.assertIn("六阶段端到端协同流水线", html)
        self.assertIn("布局规划", html)
        self.assertIn("板件规划", html)
        self.assertIn("制造方案", html)
        self.assertIn("特征树规划", html)
        self.assertIn("CAD 几何生成", html)
        self.assertIn("交付验证", html)
        self.assertIn("工程档案目录库", html)
        self.assertIn("三维空间与交互画布", html)
        self.assertIn("CAD 与生产制造中心", html)
        self.assertIn("/projects", html)
        self.assertIn("/docs", html)

    def test_render_home_page_with_projects(self) -> None:
        mock_projects = [
            {
                "id": "proj_living_room",
                "name": "客餐厅全屋定制",
                "availability": "ready",
                "created_at": "2026-10-20T10:00:00Z",
                "layout_confirmed": True,
                "revision_number": 3,
                "room_count": 2,
                "item_count": 5,
            },
            {
                "id": "proj_study",
                "name": "书房书柜方案",
                "availability": "ready",
                "created_at": "2026-10-21T09:00:00Z",
                "layout_confirmed": False,
                "revision_number": 1,
                "room_count": 1,
                "item_count": 2,
            },
        ]
        html = render_home_page("0.8.0", mock_projects)
        self.assertIn("客餐厅全屋定制", html)
        self.assertIn("proj_living_room", html)
        self.assertIn("布局已确认", html)
        self.assertIn("r3", html)
        self.assertIn("QUICK RESUME", html)
        self.assertIn("2", html)  # ready count

    def test_server_root_endpoint(self) -> None:
        response = asyncio.run(server.root())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        body = response.body.decode("utf-8")
        self.assertIn("Furniture Agent", body)
        self.assertIn("Studio Console", body)
        self.assertIn("/projects", body)
        self.assertIn("/docs", body)


if __name__ == "__main__":
    unittest.main()
