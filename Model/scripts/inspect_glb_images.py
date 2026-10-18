import json
import struct

for path in ['gltf/base_scene.glb', 'gltf/base_scene_optimized.glb']:
    with open(path, 'rb') as f:
        f.read(12)
        chunk_len, _ = struct.unpack('<II', f.read(8))
        d = json.loads(f.read(chunk_len).decode('utf-8'))
        print(f"=== {path} ===")
        print("Total images:", len(d.get('images', [])))
        for i, img in enumerate(d.get('images', [])):
            print(f"  [{i}] name: {img.get('name')}, mime: {img.get('mimeType')}")
        
        # Check buffer size
        total_buf_len = sum(b.get('byteLength', 0) for b in d.get('buffers', []))
        print(f"Total buffer bytes: {total_buf_len:,} ({total_buf_len / 1024 / 1024:.2f} MB)")

