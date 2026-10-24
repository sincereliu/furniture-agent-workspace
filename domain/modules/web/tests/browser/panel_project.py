"""Explicit test proposal; create real confirmed panels in the isolated store."""
from furniture_layout.project_layout import ProjectLayout
from furniture_workflow.input_adapter import stage_inputs_from_spec


def create_panel_project(orchestrator):
    layout = ProjectLayout.from_source({"rooms": [{
        "id": "room", "name": "板件检查", "width_mm": 4000,
        "depth_mm": 3000, "height_mm": 2800,
        "items": [{"id": "cabinet_1", "label": "检查柜", "category": "cabinet",
            "furniture_category": "floor_cabinet", "width": 600,
            "depth": 600, "height": 1000,
            "placement": {"mode": "wall", "host_wall": "north"}}],
    }]})
    parameters = {
        "board_thickness": 18.0, "back_thickness": 9.0, "door_thickness": 18.0,
        "sheet_width_mm": 1220.0, "sheet_length_mm": 2440.0,
        "toe_kick_height": 50.0, "back_offset": 18.0,
        "front_face_margin": 1.5, "front_gap": 2.0,
        "groove_depth": 6.0, "groove_clearance": 1.0,
        "toe_kick_reveal_front": 1.0, "toe_kick_reveal_back": 30.0,
        "toe_kick_support_count": 1, "back_mount": "groove", "back_rail_height": 70.0,
        "drawer_count": 0, "drawer_side_clearance": 13.0, "drawer_layer_gap": 1.5,
        "drawer_bottom_thickness": 18.0, "drawer_back_thickness": 18.0,
        "drawer_back_clearance": 0.0, "n_doors": 1, "shelves": [], "top_gap_mm": 0.0,
    }
    project = orchestrator.create_project("板件浏览器检查", layout,
        stage_inputs=stage_inputs_from_spec(parameters))
    orchestrator.confirm_layout(project)
    orchestrator.run_next(project)
    orchestrator.confirm_stage(project, "panel_plan")
    return project
