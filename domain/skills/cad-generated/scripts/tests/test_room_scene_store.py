from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.scene_store import (
    list_scene_ids,
    load_scene_source,
    save_scene_source,
    scene_exists,
)


ROOM = {
    "id": "room",
    "name": "卧室",
    "width_mm": 3000,
    "depth_mm": 4000,
    "height_mm": 2400,
}
ITEMS = [
    {
        "id": "wardrobe",
        "label": "衣柜",
        "category": "wardrobe",
        "width": 1800,
        "depth": 600,
        "height": 2200,
        "placement": {"mode": "wall", "host_wall": "north", "offset_mm": 200},
    }
]


class RoomSceneStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-room-scene-store"
        if self.root.exists():
            shutil.rmtree(self.root)

    def tearDown(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_round_trip_preserves_source(self) -> None:
        save_scene_source("demo", ROOM, ITEMS, root=self.root)
        loaded = load_scene_source("demo", root=self.root)
        self.assertEqual(loaded["scene_id"], "demo")
        self.assertEqual(loaded["room"]["width_mm"], 3000)
        self.assertEqual(len(loaded["items"]), 1)
        self.assertEqual(loaded["items"][0]["id"], "wardrobe")

    def test_missing_scene_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_scene_source("absent", root=self.root)

    def test_invalid_scene_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            save_scene_source("../escape", ROOM, ITEMS, root=self.root)

    def test_empty_items_rejected(self) -> None:
        with self.assertRaises(ValueError):
            save_scene_source("demo", ROOM, [], root=self.root)

    def test_exists_and_list(self) -> None:
        self.assertFalse(scene_exists("demo", root=self.root))
        save_scene_source("b", ROOM, ITEMS, root=self.root)
        save_scene_source("a", ROOM, ITEMS, root=self.root)
        self.assertTrue(scene_exists("a", root=self.root))
        self.assertEqual(list_scene_ids(root=self.root), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
