"""检查 GLB 文件内容 — 调试预览问题"""
import struct, json, sys
from pathlib import Path

glb_path = Path("generated/.floor_cabinet_preview.step.glb")
data = glb_path.read_bytes()
header_len = struct.unpack('<I', data[12:16])[0]
print(f"Total size: {len(data)} bytes")

gltf = json.loads(data[20:20+header_len].decode())
meshes = gltf.get("meshes", [])
nodes = gltf.get("nodes", [])
scenes = gltf.get("scenes", [])
buffers = gltf.get("buffers", [])
views = gltf.get("bufferViews", [])
accessors = gltf.get("accessors", [])

print(f"Meshes: {len(meshes)}")
print(f"Nodes: {len(nodes)}")
print(f"Scenes: {len(scenes)}")
print(f"Buffers: {len(buffers)}")
print(f"BufferViews: {len(views)}")
print(f"Accessors: {len(accessors)}")

if scenes:
    s = scenes[0]
    print(f"Default scene nodes: {s.get('nodes', [])}")
    root_nodes = s.get('nodes', [])
    for ni in root_nodes:
        if ni < len(nodes):
            n = nodes[ni]
            print(f"  Root node[{ni}]: {n}")

if meshes:
    m = meshes[0]
    primitives = m.get("primitives", [])
    if primitives:
        p = primitives[0]
        print(f"First mesh primitive: indices={p.get('indices')}, attributes={list(p.get('attributes', {}).keys())}")

# Check buffer sizes
for i, b in enumerate(buffers):
    uri = b.get("uri", "")
    byte_length = b.get("byteLength", 0)
    print(f"Buffer[{i}]: byteLength={byte_length}, uri={uri[:50] if uri else '(binary chunk)'}")

# Check if any node has mesh
mesh_nodes = [n for n in nodes if "mesh" in n]
print(f"Nodes with mesh: {len(mesh_nodes)}")
if mesh_nodes:
    print(f"Example: {mesh_nodes[0]}")
else:
    print("WARNING: No nodes reference any meshes! Model might be empty.")