"""Build complete current-protocol poses from explicit test state."""


def pose(scene_or_layout, item_id, **values):
    scenes = getattr(scene_or_layout, "rooms", (scene_or_layout,))
    item = next(item for scene in scenes for item in scene.items if item.id == item_id)
    placement = item.placement.to_dict()
    placement.update(values)
    if placement["mode"] == "free":
        placement.pop("host_wall", None)
        placement.pop("against", None)
    elif any(key in values for key in ("host_wall", "origin_x_mm", "origin_y_mm", "rotation_z_deg")) and "against" not in values:
        placement.pop("against", None)
    op = {"op": "set_pose", "item_id": item_id,
          **{key: placement[key] for key in ("mode", "origin_x_mm", "origin_y_mm",
                                           "origin_z_mm", "rotation_z_deg")},
          "against": placement.get("against", {})}
    if placement["mode"] == "wall":
        op["host_wall"] = placement["host_wall"]
    return op


def planning_source(scene):
    return {"room": scene.room.to_dict(), "items": [item.to_source() for item in scene.items]}
