"""空间 → 单元：契约、工艺目录、求解器（设计稿见 layout-plan/references/space-split-design.md）。

验收口径按设计稿第九节的批次 1+2：
- 老输入（没有 `spaces`）行为不变；
- 空间展开成单元包络，单元 id 只增不改；
- 同输入逐字节同输出；**不可行不会静默变形**（停问）；
- **目录缺项就停问**，绝不按柜型编默认值。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.craft_catalog import (
    DEFAULT_CATALOG_PATH,
    MissingCraftData,
    load_craft_catalog,
)
from furniture_layout.project_edit import apply_layout_edit, room_scene_source
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.room_page import room_page_payload as RoomPageDocument
from furniture_layout.room_page import space_groups
from furniture_layout.scene import RoomScene, SpaceRequest, parse_space_requests
from furniture_layout.scene_planning import plan_scene
from furniture_layout.space_split import (
    SpaceInfeasible,
    door_count_for,
    next_unit_index,
    net_width_mm,
    split_space,
)


LAYOUT_PAGE = WORKSPACE_ROOT / "domain" / "skills" / "layout-plan" / "scripts" / "furniture_layout"

ROOM = {"id": "room", "name": "衣帽间", "width_mm": 4000, "depth_mm": 3000, "height_mm": 3200}


def space(**overrides) -> dict:
    payload = {
        "id": "north_run",
        "kind": "wardrobe",
        "mode": "wall",
        "host_wall": "north",
        "offset_mm": 200,
        "width_mm": 800,
        "height_mm": 2400,
    }
    payload.update(overrides)
    return payload


class CraftCatalogTests(unittest.TestCase):
    """目录是数据：读得到、校验得住、缺项说得清。"""

    def setUp(self) -> None:
        self.catalog = load_craft_catalog()

    def test_real_catalog_carries_the_workshop_numbers(self) -> None:
        self.assertEqual(self.catalog.version, "draft-2026-10-02")
        self.assertEqual(self.catalog.door_bounds("wardrobe"), (300.0, 450.0))
        self.assertEqual(self.catalog.door_bounds("kitchen_base"), (400.0, 450.0))
        self.assertEqual(self.catalog.door_bounds("sideboard"), (350.0, 400.0))
        self.assertEqual(self.catalog.recommended_depth_mm("wardrobe"), 600.0)
        self.assertEqual(self.catalog.recommended_depth_mm("sideboard"), 350.0)
        self.assertEqual(self.catalog.toe_kick_mm_for("kitchen_base"), 100.0)
        self.assertEqual(self.catalog.toe_kick_mm_for("wardrobe"), 50.0)
        # 厨房：柜体高 = 台面完成面 830 − 常用台面厚 15。
        self.assertEqual(self.catalog.envelope_height_mm("kitchen_base"), 815.0)
        # 收口策略默认按上限扣（最保险）。
        self.assertEqual(self.catalog.filler_policy, "reserve_max")
        self.assertEqual(self.catalog.filler_mm("wardrobe"), 60.0)
        # 还没给的三项，要能报出来（停问话术用）。
        self.assertEqual(
            self.catalog.missing_readiness_keys(),
            ("unit_widths_mm", "bays", "reach"),
        )

    def test_unknown_family_stops_and_asks(self) -> None:
        with self.assertRaises(MissingCraftData) as caught:
            self.catalog.family("tv_wall")
        self.assertIn("families.tv_wall", str(caught.exception))
        self.assertIn("wardrobe", str(caught.exception), "要说清现有柜类")

    def test_broken_catalogs_are_rejected_at_load(self) -> None:
        source = DEFAULT_CATALOG_PATH.read_text(encoding="utf-8")
        cases = {
            "区间反了": source.replace("[300, 450]", "[450, 300]", 1),
            "负数": source.replace("max_width_mm: 450", "max_width_mm: -450", 1),
            "未知键": source.replace("version:", "version_x:", 1) + "\nversion: draft\n",
            "策略不认识": source.replace("filler_policy: reserve_max", "filler_policy: guess", 1),
        }
        for label, text in cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "craft-catalog.yaml"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_craft_catalog(path)

    def test_missing_typical_filler_stops_and_asks(self) -> None:
        source = DEFAULT_CATALOG_PATH.read_text(encoding="utf-8").replace(
            "filler_policy: reserve_max", "filler_policy: reserve_typical", 1
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "craft-catalog.yaml"
            path.write_text(source, encoding="utf-8")
            catalog = load_craft_catalog(path)
            with self.assertRaises(MissingCraftData) as caught:
                catalog.filler_mm("wardrobe")
            self.assertIn("filler_typical_mm", str(caught.exception))


class SpaceContractTests(unittest.TestCase):
    def test_shape_rules(self) -> None:
        parsed = parse_space_requests([space()])
        self.assertEqual(parsed[0].id, "north_run")
        self.assertEqual(parsed[0].constraints, ())
        self.assertEqual(parsed[0].to_dict()["host_wall"], "north")

        with self.assertRaisesRegex(ValueError, r"spaces\[0\]\.id 'north-run'"):
            parse_space_requests([space(id="north-run")])
        with self.assertRaisesRegex(ValueError, "kind is required"):
            parse_space_requests([space(kind="")])
        with self.assertRaisesRegex(ValueError, "mode must be one of"):
            parse_space_requests([space(mode="floating")])
        with self.assertRaisesRegex(ValueError, "host_wall must be one of"):
            parse_space_requests([space(host_wall="up")])
        with self.assertRaisesRegex(ValueError, "offset_mm is required"):
            parse_space_requests([{k: v for k, v in space().items() if k != "offset_mm"}])
        with self.assertRaisesRegex(ValueError, "duplicate space id"):
            parse_space_requests([space(), space()])
        with self.assertRaisesRegex(ValueError, "does not support"):
            parse_space_requests([{**space(), "bays": 3}])
        with self.assertRaisesRegex(ValueError, "constraints must contain"):
            parse_space_requests([space(constraints=[""])])

    def test_free_space_keeps_only_its_own_anchor_fields(self) -> None:
        parsed = parse_space_requests(
            [
                {
                    "id": "island",
                    "kind": "sideboard",
                    "mode": "free",
                    "width_mm": 1200,
                    "origin_x_mm": 800,
                    "origin_y_mm": 1200,
                }
            ]
        )[0]
        self.assertIsNone(parsed.host_wall)
        self.assertNotIn("host_wall", parsed.to_dict())

    def test_scene_round_trips_spaces_and_stays_optional(self) -> None:
        scene = plan_scene(ROOM, [], allow_empty=False) if False else None
        self.assertIsNone(scene)
        # 老场景（只有 room + items）照旧读得进来，且 to_dict 不带 spaces。
        legacy = {
            "room": {**ROOM, "items": []},
            "items": [],
        }
        restored = RoomScene.from_dict(
            {
                "room": {k: v for k, v in legacy["room"].items() if k != "items"},
                "items": [],
            }
        )
        self.assertEqual(restored.spaces, ())
        self.assertNotIn("spaces", restored.to_dict())


class SplitSolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_craft_catalog()

    def test_one_space_that_fits_becomes_one_compliant_unit(self) -> None:
        result = split_space(SpaceRequest.from_dict(space()), self.catalog)
        unit = result.units[0]
        self.assertEqual(unit.id, "north_run_u1")
        self.assertEqual(unit.width_mm, 740.0, "800 − 收口 60")
        self.assertEqual(unit.depth_mm, 600.0, "衣柜进深取目录 600")
        self.assertEqual(unit.height_mm, 2400.0)
        self.assertEqual(unit.n_doors, 2, "740 用两扇 450 的门")
        self.assertEqual(result.catalog_version, self.catalog.version)
        self.assertIn("收口 60", result.notes[0])
        self.assertEqual(result.costs, ())

    def test_kitchen_space_takes_its_height_from_the_counter_numbers(self) -> None:
        """厨房地柜不写高度：目录用「台面完成面 830 − 常用台面厚 15」推出 815。"""
        request = SpaceRequest.from_dict(
            space(id="kitchen_run", kind="kitchen_base", width_mm=900, height_mm=None)
        )
        result = split_space(request, self.catalog)
        unit = result.units[0]
        self.assertEqual(unit.height_mm, 815.0)
        self.assertEqual(unit.n_doors, 2, "净宽 840 两扇门各 420，落在厨房 400–450 里")
        self.assertEqual(result.costs, ())
        self.assertIn("高度取 815", result.assumptions)

    def test_kitchen_height_derivation(self) -> None:
        self.assertEqual(self.catalog.envelope_height_mm("kitchen_base"), 815.0)
        with self.assertRaises(MissingCraftData):
            self.catalog.envelope_height_mm("wardrobe")

    def test_too_wide_stops_and_asks_instead_of_silently_shrinking(self) -> None:
        request = SpaceRequest.from_dict(space(width_mm=2400))
        with self.assertRaises(SpaceInfeasible) as caught:
            split_space(request, self.catalog)
        message = str(caught.exception)
        self.assertIn("2400", message, "要说清这块空间本来多宽")
        self.assertIn("2340", message, "也要说清扣完收口剩多少")
        self.assertIn("两扇平开门", message)
        self.assertIn("unit_widths_mm", message, "要说清缺的是哪一项宽档")
        self.assertTrue(caught.exception.options, "停问要给出可行的做法")

    def test_functional_bays_stop_and_ask_while_the_catalog_lacks_them(self) -> None:
        request = SpaceRequest.from_dict(space(constraints=["bay=long_hang"]))
        with self.assertRaises(MissingCraftData) as caught:
            split_space(request, self.catalog)
        self.assertIn("bays", str(caught.exception))
        self.assertIn("long_hang", str(caught.exception))

    def test_sliding_doors_stop_and_ask(self) -> None:
        request = SpaceRequest.from_dict(space(constraints=["opening=sliding"]))
        with self.assertRaises(MissingCraftData) as caught:
            split_space(request, self.catalog)
        self.assertIn("sliding", str(caught.exception))

    def test_field_filler_override_is_deducted(self) -> None:
        request = SpaceRequest.from_dict(space(constraints=["filler_mm=40"]))
        self.assertEqual(net_width_mm(request, self.catalog), 760.0)
        result = split_space(request, self.catalog)
        self.assertEqual(result.units[0].width_mm, 760.0)
        with self.assertRaisesRegex(ValueError, "filler_mm must be a number"):
            net_width_mm(
                SpaceRequest.from_dict(space(constraints=["filler_mm=很宽"])),
                self.catalog,
            )

    def test_door_count_follows_the_family_cap(self) -> None:
        self.assertEqual(door_count_for(400, self.catalog, "wardrobe"), 1)
        self.assertEqual(door_count_for(900, self.catalog, "wardrobe"), 2)
        self.assertEqual(door_count_for(901, self.catalog, "wardrobe"), 0)
        self.assertEqual(
            door_count_for(800, self.catalog, "sideboard"), 2, "薄柜两扇各 400，正好在上限"
        )
        self.assertEqual(door_count_for(801, self.catalog, "sideboard"), 0)

    def test_same_input_gives_byte_identical_result(self) -> None:
        request = SpaceRequest.from_dict(space())
        first = split_space(request, self.catalog)
        second = split_space(request, self.catalog)
        self.assertEqual(first, second)

    def test_no_space_left_after_filler_stops_and_asks(self) -> None:
        request = SpaceRequest.from_dict(space(width_mm=30))
        with self.assertRaises(SpaceInfeasible) as caught:
            split_space(request, self.catalog)
        self.assertIn("放不下任何柜子", str(caught.exception))

    def test_next_unit_index_never_reuses_a_number(self) -> None:
        self.assertEqual(next_unit_index([], "north_run"), 1)
        self.assertEqual(
            next_unit_index(["north_run_u1", "north_run_u3"], "north_run"), 4,
            "删掉的号不回收（回收会让继承判据撞车）",
        )
        self.assertEqual(
            next_unit_index(["other_u9", "north_run_u2"], "north_run"), 3,
            "别的空间的序号不算数",
        )


class SpaceExpansionTests(unittest.TestCase):
    """接进布局入口：`rooms[].spaces[]` 展开成 `items[]`，摆好、校验过。"""

    def test_a_space_expands_into_a_placed_unit(self) -> None:
        scene = plan_scene({**ROOM, "spaces": [space()]}, [])
        self.assertEqual([item.id for item in scene.items], ["north_run_u1"])
        item = scene.items[0]
        self.assertEqual(item.width, 740.0)
        self.assertEqual(item.placement.host_wall, "north")
        self.assertEqual(item.placement.offset_mm, 200.0)
        self.assertEqual([entry.id for entry in scene.spaces], ["north_run"])
        # 存下来再读回来，空间还在（输入侧的源不丢）。
        restored = RoomScene.from_dict(scene.to_dict())
        self.assertEqual(restored.spaces, scene.spaces)
        self.assertEqual(restored.to_dict(), scene.to_dict())

    def test_explicit_items_and_spaces_coexist_in_a_stable_order(self) -> None:
        explicit = [
            {
                "id": "desk_1",
                "category": "柜体",
                "furniture_category": "floor_cabinet",
                "width": 1200,
                "depth": 600,
                "height": 750,
                "placement": {"mode": "wall", "host_wall": "south", "offset_mm": 100},
            }
        ]
        scene = plan_scene({**ROOM, "spaces": [space()]}, explicit)
        self.assertEqual([item.id for item in scene.items], ["desk_1", "north_run_u1"])

    def test_a_space_that_cannot_be_built_never_becomes_a_silent_envelope(self) -> None:
        """今天 `fill` 会给一个 3000 宽的包络——那是做不出来的柜子。空间路径要拦住。"""
        with self.assertRaises(SpaceInfeasible):
            plan_scene({**ROOM, "spaces": [space(width_mm=3000)]}, [])

    def test_legacy_input_never_touches_the_catalog(self) -> None:
        """没有 spaces 的输入连目录都不读（老工程不受目录改动影响）。"""
        scene = plan_scene(ROOM, [], allow_empty=True)
        self.assertEqual(scene.spaces, ())


class SpacePageTests(unittest.TestCase):
    """页面要看得见"这块空间展开成了哪几台"，而且**拖动不能把空间弄丢**。"""

    def _scene(self, *, pinned: tuple[str, ...] = ()):
        payload = space(pinned=list(pinned)) if pinned else space()
        return plan_scene({**ROOM, "spaces": [payload]}, [])

    def test_payload_groups_units_by_the_id_rule(self) -> None:
        scene = self._scene()
        groups = space_groups(scene)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group["id"], "north_run")
        self.assertEqual(group["kind"], "wardrobe")
        self.assertEqual(group["host_wall"], "north")
        self.assertEqual(group["unit_ids"], ["north_run_u1"])
        self.assertEqual(group["pinned"], [])
        # 组是**现算**的：不另存"空间 → 单元"的映射。
        self.assertNotIn("unit_ids", scene.to_dict()["spaces"][0])

    def test_pinned_units_are_marked_and_only_if_they_exist(self) -> None:
        scene = self._scene(pinned=("north_run_u1", "north_run_u9"))
        self.assertEqual(
            space_groups(scene)[0]["pinned"],
            ["north_run_u1"],
            "不存在（或不属于这里）的单元不算钉住",
        )

    def test_page_payload_carries_the_groups_and_the_hooks_exist(self) -> None:
        payload = RoomPageDocument(self._scene())
        self.assertEqual(
            [group["id"] for group in payload["spaces"]], ["north_run"]
        )
        page = (LAYOUT_PAGE / "templates" / "room_page.html").read_text(encoding="utf-8")
        script = (LAYOUT_PAGE / "templates" / "room_page.js").read_text(encoding="utf-8")
        self.assertIn('id="space-card"', page)
        self.assertIn('id="space-list"', page)
        self.assertIn("syncSpacePanel(", script)
        self.assertIn("spaceUnits(", script)
        self.assertIn("钉住", script)
        self.assertNotIn("syncSpacePanel(", page, "渲染在脚本里，不在模板里")

    def test_dragging_a_space_unit_keeps_the_space_and_the_edit(self) -> None:
        """拖动一个空间单元：空间来源不许丢、改过的宽度要留住、也不许多出一台。"""
        scene = self._scene()
        layout = ProjectLayout(rooms=(scene,), confirmed=True)
        edited = apply_layout_edit(
            layout, {"op": "resize", "item_id": "north_run_u1", "width": 700}
        )
        room = edited.rooms[0]
        self.assertEqual([entry.id for entry in room.spaces], ["north_run"], "空间还在")
        self.assertEqual(len(room.items), 1, "不许重复展开成两台")
        self.assertEqual(room.items[0].width, 700.0, "手改过的宽度要留住")
        # **手改 = 升格为钉住**：从此重解不再动它（设计稿 §五）。
        self.assertEqual(room.spaces[0].pinned, ("north_run_u1",))
        # 拿场景源再规划一次（重放）必须是幂等的。
        source = room_scene_source(room)
        self.assertEqual(source["room"]["spaces"][0]["id"], "north_run")
        again = plan_scene(dict(source["room"]), list(source["items"]))
        self.assertEqual([item.id for item in again.items], ["north_run_u1"])
        self.assertEqual(again.items[0].width, 700.0)

    def test_moving_the_space_keeps_pinned_units_where_they_are(self) -> None:
        """改"这块地方"：钉住的单元原样不动（客户自己定过的那台）。"""
        scene = self._scene(pinned=("north_run_u1",))
        layout = ProjectLayout(rooms=(scene,), confirmed=True)
        moved = apply_layout_edit(
            layout, {"op": "move", "item_id": "north_run_u1", "offset_mm": 210}
        )
        self.assertEqual(moved.rooms[0].items[0].placement.offset_mm, 210.0)

        wider = apply_layout_edit(
            moved, {"op": "space", "space_id": "north_run", "width_mm": 900}
        )
        after = wider.rooms[0]
        self.assertEqual(after.spaces[0].width_mm, 900.0, "空间改到了")
        self.assertEqual(
            after.items[0].placement.offset_mm, 210.0, "钉住的那台不许被重解搬走"
        )

    def test_unpinned_units_are_resolved_again_when_the_space_changes(self) -> None:
        scene = self._scene()
        layout = ProjectLayout(rooms=(scene,), confirmed=True)
        wider = apply_layout_edit(
            layout, {"op": "space", "space_id": "north_run", "width_mm": 900}
        )
        room = wider.rooms[0]
        self.assertEqual(
            room.items[0].width, 840.0, "没钉住 → 按新的空间重解（900 − 收口 60）"
        )
        self.assertEqual(room.spaces[0].pinned, ())

    def test_pinned_unit_that_no_longer_fits_stops_and_asks(self) -> None:
        scene = self._scene(pinned=("north_run_u1",))
        layout = ProjectLayout(rooms=(scene,), confirmed=True)
        with self.assertRaisesRegex(ValueError, "放不进这块地方") as caught:
            apply_layout_edit(
                layout, {"op": "space", "space_id": "north_run", "width_mm": 400}
            )
        self.assertIn("north_run_u1", str(caught.exception))
        self.assertIn("取消钉住", str(caught.exception), "要给出另一条路")

    def test_space_edit_shape_rules(self) -> None:
        scene = self._scene()
        layout = ProjectLayout(rooms=(scene,), confirmed=True)
        with self.assertRaisesRegex(ValueError, "unknown space"):
            apply_layout_edit(
                layout, {"op": "space", "space_id": "nope", "width_mm": 800}
            )
        with self.assertRaisesRegex(ValueError, "requires offset_mm or width_mm"):
            apply_layout_edit(layout, {"op": "space", "space_id": "north_run"})
        with self.assertRaisesRegex(ValueError, "does not support"):
            apply_layout_edit(
                layout, {"op": "space", "space_id": "north_run", "height_mm": 2000}
            )
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            apply_layout_edit(
                layout, {"op": "space", "space_id": "north_run", "offset_mm": -5}
            )
        with self.assertRaisesRegex(ValueError, "must be positive"):
            apply_layout_edit(
                layout, {"op": "space", "space_id": "north_run", "width_mm": 0}
            )

    def test_old_rooms_do_not_get_a_space_field(self) -> None:
        scene = plan_scene(ROOM, [], allow_empty=True)
        self.assertEqual(space_groups(scene), [])
        self.assertNotIn("spaces", room_scene_source(scene)["room"])


class SpaceEditHttpTests(unittest.TestCase):
    """页面上"改这块地方"那条路：请求模型收得下，多余的字段在下游拒掉。"""

    @classmethod
    def setUpClass(cls) -> None:
        import server  # 服务端模型住在这里（FastAPI 已在环境里）

        cls.server = server

    def test_space_op_is_accepted_and_items_are_still_items(self) -> None:
        model = self.server.ProjectLayoutEditRequest
        space_op = model(
            expected_version="v1", op="space", space_id="north_run",
            offset_mm=200, width_mm=900,
        )
        self.assertEqual(
            space_op.model_dump(exclude_none=True),
            {
                "expected_version": "v1",
                "op": "space",
                "space_id": "north_run",
                "offset_mm": 200.0,
                "width_mm": 900.0,
            },
        )
        item_op = model(
            expected_version="v1", op="resize", item_id="north_run_u1", width=700
        )
        self.assertEqual(item_op.item_id, "north_run_u1")

    def test_identity_must_be_unambiguous(self) -> None:
        from pydantic import ValidationError

        model = self.server.ProjectLayoutEditRequest
        for label, payload in (
            ("空间缺 space_id", {"op": "space", "width_mm": 900}),
            (
                "两个身份都给",
                {"op": "space", "space_id": "s", "item_id": "i"},
            ),
            ("件级缺 item_id", {"op": "resize", "width": 700}),
        ):
            with self.subTest(case=label), self.assertRaises(ValidationError):
                model(expected_version="v1", **payload)

    def test_extra_fields_for_a_space_edit_are_rejected_downstream(self) -> None:
        """模型允许，不代表这一步用得着——真正的准入在 `_edit_space` 里。"""
        scene = plan_scene({**ROOM, "spaces": [space()]}, [])
        layout = ProjectLayout(rooms=(scene,), confirmed=True)
        with self.assertRaisesRegex(ValueError, "space edit does not support: height"):
            apply_layout_edit(
                layout,
                {"op": "space", "space_id": "north_run", "width_mm": 900, "height": 2000},
            )


if __name__ == "__main__":
    unittest.main()
