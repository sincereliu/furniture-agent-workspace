from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server


class ApiEntrypointTests(unittest.TestCase):
    def test_request_exposes_back_groove_and_toe_kick_controls(self) -> None:
        request = server.CabinetRequest(
            type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            groove_depth=8,
            groove_clearance=0.5,
            toe_kick_reveal_front=2,
            toe_kick_reveal_back=25,
            toe_kick_support_count=2,
        )

        payload = request.model_dump(exclude_none=True)
        self.assertEqual(payload["groove_depth"], 8)
        self.assertEqual(payload["groove_clearance"], 0.5)
        self.assertEqual(payload["toe_kick_support_count"], 2)

    def test_plan_endpoint_runs_through_the_application_workflow(self) -> None:
        response = asyncio.run(
            server.plan_cabinet(
                server.CabinetRequest(
                    type="wall_cabinet",
                    width=800,
                    depth=350,
                    height=900,
                )
            )
        )

        self.assertEqual(response.furniture_name, "吊柜")
        self.assertGreater(response.panel_count, 0)


if __name__ == "__main__":
    unittest.main()
