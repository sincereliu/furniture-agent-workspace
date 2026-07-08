"""订单管理器 — 订单创建、流水号、index 维护

职责:
  ✅ 订单目录初始化
  ✅ 流水号生成（扫描 store/orders/ 目录）
  ✅ index.json 维护
  ❌ 不涉及 BOM/开料/打孔计算（那是 order_builder 的职责）
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from furniture_schema.order import Order, OrderIndex, OrderItem


# ── 配置 ─────────────────────────────────────────────────────
STORE_ROOT = Path(__file__).resolve().parents[2] / "store"
ORDERS_DIR = STORE_ROOT / "orders"
INDEX_PATH = STORE_ROOT / "index.json"


def init_store() -> Path:
    """初始化 store 目录结构"""
    STORE_ROOT.mkdir(parents=True, exist_ok=True)
    ORDERS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        _save_index(OrderIndex(orders=[]))
    return STORE_ROOT


def _load_index() -> OrderIndex:
    """加载订单索引"""
    if not INDEX_PATH.exists():
        return OrderIndex(orders=[])
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    orders = []
    for o in data.get("orders", []):
        items = []
        for it in o.get("items", []):
            from furniture_schema.spec import FurnitureSpec
            items.append(OrderItem(
                item_id=it["item_id"],
                room=it["room"],
                furniture_type=it["furniture_type"],
                spec=FurnitureSpec.from_dict(it["spec"]),
                quantity=it.get("quantity", 1),
            ))
        orders.append(Order(
            order_id=o["order_id"],
            display_name=o["display_name"],
            customer_name=o["customer_name"],
            address=o["address"],
            sign_date=o["sign_date"],
            delivery_date=o["delivery_date"],
            notes=o.get("notes", ""),
            items=items,
            status=o.get("status", "待生产"),
        ))
    return OrderIndex(orders=orders)


def _save_index(index: OrderIndex) -> None:
    """保存订单索引"""
    data = {
        "orders": [
            {
                "order_id": o.order_id,
                "display_name": o.display_name,
                "customer_name": o.customer_name,
                "address": o.address,
                "sign_date": o.sign_date,
                "delivery_date": o.delivery_date,
                "notes": o.notes,
                "status": o.status,
                "items": [
                    {
                        "item_id": it.item_id,
                        "room": it.room,
                        "furniture_type": it.furniture_type,
                        "spec": {
                            "type": it.spec.furniture_type,
                            "width": it.spec.width,
                            "depth": it.spec.depth,
                            "height": it.spec.height,
                            "shelf_count": it.spec.shelf_count,
                            "n_doors": it.spec.n_doors,
                        },
                        "quantity": it.quantity,
                    }
                    for it in o.items
                ],
            }
            for o in index.orders
        ]
    }
    INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_next_serial(date_str: Optional[str] = None) -> int:
    """获取下一个流水号（扫目录取最大值+1）。

    Args:
        date_str: 日期字符串如 "260709"，None = 今天
    """
    if date_str is None:
        date_str = datetime.now().strftime("%y%m%d")

    ORDERS_DIR.mkdir(parents=True, exist_ok=True)
    max_serial = 0
    for entry in os.listdir(str(ORDERS_DIR)):
        if entry.startswith(date_str) and "-" in entry:
            try:
                serial = int(entry.split("-")[1])
                max_serial = max(max_serial, serial)
            except (ValueError, IndexError):
                continue
    return max_serial + 1


def create_order(
    customer_name: str,
    address: str,
    delivery_date: str,
    items: List[OrderItem],
    notes: str = "",
    sign_date: Optional[str] = None,
) -> Order:
    """创建新订单。

    Args:
        customer_name: 客户姓名
        address: 安装地址
        delivery_date: 交付日期
        items: 订单明细
        notes: 备注
        sign_date: 签单日期，None = 今天

    Returns:
        创建好的 Order 对象
    """
    init_store()

    if sign_date is None:
        sign_date = datetime.now().strftime("%Y-%m-%d")

    date_prefix = datetime.strptime(sign_date, "%Y-%m-%d").strftime("%y%m%d") if len(sign_date) == 10 else datetime.now().strftime("%y%m%d")
    serial = get_next_serial(date_prefix)
    order_id = f"{date_prefix}-{serial:04d}"
    display_name = f"{order_id} {address}"

    order = Order(
        order_id=order_id,
        display_name=display_name,
        customer_name=customer_name,
        address=address,
        sign_date=sign_date,
        delivery_date=delivery_date,
        notes=notes,
        items=items,
        status="待生产",
    )

    # 创建订单目录
    order_dir = ORDERS_DIR / display_name
    order_dir.mkdir(parents=True, exist_ok=True)

    # 保存 order.json
    order_data = {
        "order_id": order.order_id,
        "display_name": order.display_name,
        "customer_name": order.customer_name,
        "address": order.address,
        "sign_date": order.sign_date,
        "delivery_date": order.delivery_date,
        "notes": order.notes,
        "status": order.status,
        "items": [
            {
                "item_id": it.item_id,
                "room": it.room,
                "furniture_type": it.furniture_type,
                "spec": {
                    "type": it.spec.furniture_type,
                    "width": it.spec.width,
                    "depth": it.spec.depth,
                    "height": it.spec.height,
                    "shelf_count": it.spec.shelf_count,
                    "n_doors": it.spec.n_doors,
                },
                "quantity": it.quantity,
            }
            for it in items
        ],
    }
    (order_dir / "order.json").write_text(
        json.dumps(order_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 创建子目录
    for sub in ["采购", "生产/cut_plans", "归档/cad", "rooms"]:
        (order_dir / sub).mkdir(parents=True, exist_ok=True)

    # 更新 index
    index = _load_index()
    index.orders.append(order)
    _save_index(index)

    return order


def get_order_dir(order: Order) -> Path:
    """获取订单文件夹路径"""
    return ORDERS_DIR / order.display_name