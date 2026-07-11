from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

import server


class ApiEntrypointTests(unittest.TestCase):
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
