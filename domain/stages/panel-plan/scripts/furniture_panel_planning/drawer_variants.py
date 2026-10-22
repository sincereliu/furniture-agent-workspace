"""抽屉变体：角色表、件数表与组合规则。

这里只有**结构**：某个变体出哪几个角色、哪些组合根本不成立、哪些组合已经物化。
没有任何毫米，也没有默认净空——毫米由包络（`construction_geometry`）与正面排版给，
候选数值由 Skill 的候选起点给（见 references/drawer-variants-contract.md）。

为什么按「角色」而不是按「变体」建表：变体之间差的只是**出哪几个角色**与
**尺寸从包络的哪几个命名量取**。下游（封边、连接、BOM、特征树、CAD）只认角色，
所以加一个滑轨系统不该让它们各长一个分支。
"""

from __future__ import annotations

from typing import Any

RUNNER_SIDE_MOUNT = "side_mount"
RUNNER_UNDERMOUNT = "undermount"
RUNNER_METAL_BOX = "metal_box"
RUNNERS: tuple[str, ...] = (RUNNER_SIDE_MOUNT, RUNNER_UNDERMOUNT, RUNNER_METAL_BOX)

FACE_BOX_FACE = "box_face"
FACE_APPLIED = "applied"
FACES: tuple[str, ...] = (FACE_BOX_FACE, FACE_APPLIED)

#: 缺省 = 今天唯一的做法：三节轨 + 盒体前板兼前脸。序列化等于缺省就不落盘。
DEFAULT_RUNNER = RUNNER_SIDE_MOUNT
DEFAULT_FACE = FACE_BOX_FACE

ROLE_FACE = "face"
ROLE_BOX_FRONT = "box_front"
ROLE_BOX_SIDE_L = "box_side_l"
ROLE_BOX_SIDE_R = "box_side_r"
ROLE_BOX_BACK = "box_back"
ROLE_BOX_BOTTOM = "box_bottom"

#: 角色 → 板件类型（`panel_type` 词表，制造与特征树按它分流）。
#: `box_front` 沿用旧词表 `drawer_front`：老冻结文件里它表示「盒体前板兼前脸」，
#: 改名只会让下游多认一个类型、老工程多一条迁移。
ROLE_PANEL_TYPES: dict[str, str] = {
    ROLE_FACE: "drawer_face",
    ROLE_BOX_FRONT: "drawer_front",
    ROLE_BOX_SIDE_L: "drawer_side",
    ROLE_BOX_SIDE_R: "drawer_side",
    ROLE_BOX_BACK: "drawer_back",
    ROLE_BOX_BOTTOM: "drawer_bottom",
}

#: 角色 → 材质角色。只有抽面与门同色，其余吃柜体板。
ROLE_MATERIAL_ROLES: dict[str, str] = {ROLE_FACE: "door"}

#: 组合 → 木件角色（顺序固定：可见面在前，便于人读清单）。
#: `box_face` 变体里「前脸」就是 `box_front` 本身，所以不另列 `face`。
ROLES_BY_VARIANT: dict[tuple[str, str], tuple[str, ...]] = {
    (RUNNER_SIDE_MOUNT, FACE_BOX_FACE): (
        ROLE_BOX_FRONT, ROLE_BOX_SIDE_L, ROLE_BOX_SIDE_R, ROLE_BOX_BACK, ROLE_BOX_BOTTOM,
    ),
    (RUNNER_SIDE_MOUNT, FACE_APPLIED): (
        ROLE_FACE, ROLE_BOX_FRONT, ROLE_BOX_SIDE_L, ROLE_BOX_SIDE_R, ROLE_BOX_BACK,
        ROLE_BOX_BOTTOM,
    ),
    (RUNNER_UNDERMOUNT, FACE_BOX_FACE): (
        ROLE_BOX_FRONT, ROLE_BOX_SIDE_L, ROLE_BOX_SIDE_R, ROLE_BOX_BACK, ROLE_BOX_BOTTOM,
    ),
    (RUNNER_UNDERMOUNT, FACE_APPLIED): (
        ROLE_FACE, ROLE_BOX_FRONT, ROLE_BOX_SIDE_L, ROLE_BOX_SIDE_R, ROLE_BOX_BACK,
        ROLE_BOX_BOTTOM,
    ),
    # 骑马抽的左右侧板是五金（金属），木件只剩眼前脸、背板和底板。
    (RUNNER_METAL_BOX, FACE_APPLIED): (
        ROLE_FACE, ROLE_BOX_BACK, ROLE_BOX_BOTTOM,
    ),
}

#: 组合合法性：有角色表的组合才成立。骑马抽没有木前板，所以不存在
#: `(metal_box, box_face)`——这不是「还没做」，是物理上没有这块板。
ALLOWED_VARIANTS: frozenset[tuple[str, str]] = frozenset(ROLES_BY_VARIANT)

#: 已经物化的组合。加变体 = 往这里加一条，再补该变体的包络与校验；
#: 没进这一步的组合在准入就被拒，不会出一版「字段收了、几何没做」的产物。
MATERIALIZED_VARIANTS: frozenset[tuple[str, str]] = frozenset(
    {(RUNNER_SIDE_MOUNT, FACE_BOX_FACE)}
)


def admit_drawer_variant(runner: Any, face: Any) -> tuple[str, str]:
    """准入一组抽屉变体：规范枚举 + 组合合法性。不做同义词、不让别名通过。"""
    runner_text = str(runner if runner is not None else RUNNER_SIDE_MOUNT).strip()
    face_text = str(face if face is not None else FACE_BOX_FACE).strip()
    if runner_text not in RUNNERS:
        raise ValueError(
            "drawer_runner must be one of: " + ", ".join(RUNNERS)
        )
    if face_text not in FACES:
        raise ValueError("drawer_face must be one of: " + ", ".join(FACES))
    if runner_text == RUNNER_METAL_BOX and face_text == FACE_BOX_FACE:
        raise ValueError(
            "a metal-box drawer has no wooden front board; drawer_face must be applied"
        )
    if (runner_text, face_text) not in ALLOWED_VARIANTS:
        raise ValueError(
            "unsupported drawer variant: runner="
            f"{runner_text}, face={face_text}"
        )
    return runner_text, face_text


def drawer_part_roles(runner: str, face: str) -> tuple[str, ...]:
    """这个变体出哪几个木件角色。件数 = 长度，不再写死常数。"""
    try:
        return ROLES_BY_VARIANT[(str(runner), str(face))]
    except KeyError as exc:
        raise ValueError(
            f"unsupported drawer variant: runner={runner}, face={face}"
        ) from exc


def drawer_part_count(runner: str, face: str) -> int:
    return len(drawer_part_roles(runner, face))


def drawer_is_materialized(runner: str, face: str) -> bool:
    return (str(runner), str(face)) in MATERIALIZED_VARIANTS


def panel_type_of_role(role: str) -> str:
    try:
        return ROLE_PANEL_TYPES[role]
    except KeyError as exc:
        raise ValueError(f"unknown drawer role: {role}") from exc


def material_role_of_role(role: str) -> str:
    return ROLE_MATERIAL_ROLES.get(role, "carcass")
