"""制造层连接点（ConnectionPoint）——配对孔的组合。

一个三合一 = 轮孔 + 杆孔 + 螺母孔 = 一个连接点，本质是「一件事：把两块板连起来」。
现状 `connection_id` 是 `HoleSpec`/`HoleFeature` 上的字符串（`<承面>→<端面>#<排次>`）；
本模块把它升级为实体：结构字段 + 组成孔，支持整体增删与按点校验。

完整口径见 references/feature-contract.md「连接点（ConnectionPoint）」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from furniture_manufacturing.features import HoleFeature


@dataclass
class ConnectionPoint:
    """一个三合一连接点：承面/端面在某排的连接。

    `connection_id` 是稳定 id（承面→端面#排次，由 `make_connection_id` 生成）；
    `bearing_id`/`end_id`/`row_index` 是它确定性解析出的结构字段；
    `holes` 是这个点的组成孔（1 轮 + 1 杆 + 1 螺母）。
    """

    connection_id: str = ""
    bearing_id: str = ""
    end_id: str = ""
    row_index: int = 0
    owner: str = ""  # 哪个连接件产的这个点（如 "TrinityConnector" / "BackMountConnector"）
    holes: list[HoleFeature] = field(default_factory=list)

    def holes_of_type(self, hole_type: str) -> list[HoleFeature]:
        """这个点里指定孔型的孔（如 `three_in_one_cam`）。"""
        return [hole for hole in self.holes if hole.hole_type == hole_type]

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ConnectionPoint":
        """把序列化字典还原成连接点（`asdict` 的逆向）。

        `holes` 里的每项经 `feature_from_dict` 按 `kind` 还原为 HoleFeature；
        延迟导入以避开 connection_points ↔ features ↔ connectors 的循环依赖。
        """
        from furniture_manufacturing.features import feature_from_dict

        return cls(
            connection_id=str(data.get("connection_id", "")),
            bearing_id=str(data.get("bearing_id", "")),
            end_id=str(data.get("end_id", "")),
            row_index=int(data.get("row_index", 0)),
            owner=str(data.get("owner", "")),
            holes=[feature_from_dict(h) for h in data.get("holes", [])],
        )


def parse_connection_id(connection_id: str) -> tuple[str, str, int]:
    """把 connection_id（`<承面>→<端面>#<排次>`）确定性解析回结构字段。

    这是 `make_connection_id` 的结构化逆向，非自然语言解析：分隔符 `→` 与 `#`
    是固定契约，面板 id 不含这两个字符。
    """
    pairs, _, row = connection_id.rpartition("#")
    bearing_id, _, end_id = pairs.partition("→")
    return bearing_id, end_id, int(row)


def collect_connection_points(
    holes: list[HoleFeature],
    *,
    owner: str = "",
) -> list[ConnectionPoint]:
    """按 connection_id 把孔分组为连接点实体（整体增删/按点校验的单元）。

    无 connection_id 的孔（如活动层板销孔）不构成连接点，被跳过。
    owner 标记这批孔来自哪个连接件（如 "TrinityConnector"）；结果按
    connection_id 排序，可复现。
    """
    by_id: dict[str, list[HoleFeature]] = {}
    for hole in holes:
        if hole.connection_id:
            by_id.setdefault(hole.connection_id, []).append(hole)
    points: list[ConnectionPoint] = []
    for conn_id, conn_holes in sorted(by_id.items()):
        bearing_id, end_id, row_index = parse_connection_id(conn_id)
        points.append(
            ConnectionPoint(
                connection_id=conn_id,
                bearing_id=bearing_id,
                end_id=end_id,
                row_index=row_index,
                owner=owner,
                holes=conn_holes,
            )
        )
    return points
