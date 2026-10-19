---
trigger: always_on
description: Strictly enforce Blender MCP execution over headless CLI to prevent memory-disk desynchronization
---

# Force Blender MCP Execution Directive

1. **Mandatory Blender MCP Over Headless CLI**:
   - ALL Blender scene queries, inspections, geometry edits, material adjustments, vertex weight painting, and glTF exports MUST be executed via Blender MCP (`execute_blender_code`, `get_scene_info`, `look`, etc.).
   - Running headless background processes (`blender.exe -b ...`) to alter `Model/asset.blend` is STRICTLY FORBIDDEN when an interactive Blender GUI session is open.
   - Rationale: Headless CLI processes execute in isolated memory spaces and update only the `.blend` file on disk. The interactive Blender GUI does not automatically reload disk files, causing the user's viewport to become desynchronized from disk and engine state.

2. **Lockstep Disk Persistence**:
   - Every script executed via `execute_blender_code` that mutates scene state MUST conclude with `bpy.ops.wm.save_mainfile()`.
   - This ensures the active GUI viewport and the on-disk `Model/asset.blend` remain 100% synchronized in real time.

3. **In-Session glTF Export**:
   - glTF 2.0 export (`bpy.ops.export_scene.gltf`) MUST be invoked directly within the interactive session via `execute_blender_code`, ensuring that exported assets reflect the exact current memory state of the scene.

4. **Connection Failure Protocol**:
   - If Blender MCP is unreachable (e.g., socket connection refused or server not running), do NOT silently fall back to headless CLI.
   - Instead, inform the user to start the Blender MCP server in their open Blender GUI instance (`Interface: Blender MCP -> Start Server`) or verify port 9876.
