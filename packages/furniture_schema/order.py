"""订单层数据模型 — OrderIndex / Order / OrderItem

职责:
  ✅ 定义订单层的数据结构
  ❌ 不涉及文件 I/O（那是 order_manager 的职责）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from furniture_schema.spec import FurnitureSpec


@dataclass
class OrderItem:
    """订单中的单个家具单元"""
    item_id: str                # "地柜A"
    room: str                   # "厨房"
    furniture_type: str         # "floor_cabinet"
    spec: FurnitureSpec         # 规格
    quantity: int = 1           # 同款数量


@dataclass
class Order:
    """单个订单的完整数据"""
    order_id: str               # "260709-0001"
    display_name: str           # "260709-0001 XX小区XX栋"
    customer_name: str          # "张先生"
    address: str                # 安装地址
    sign_date: str              # "2026-07-09"
    delivery_date: str          # "2026-08-01"
    notes: str = ""             # 特殊要求
    items: List[OrderItem] = field(default_factory=list)
    status: str = "待生产"      # 待生产 / 生产中 / 已完成


@dataclass
class OrderIndex:
    """所有订单的汇总索引（generated/store/index.json 的内容）"""
    orders: List[Order] = field(default_factory=list)
