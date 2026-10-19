---
trigger: always_on
description: Auto-execute all Blender MCP tools proactively and mandate MCP over headless CLI
---

# Blender Automated Execution Directive

- **Mandatory MCP Protocol**: Always use Blender MCP tools (`execute_blender_code`, `get_scene_info`, `look`, `get_addon_status`, `search_assets`, `import_asset`, etc.) for all Blender scene operations. Do not run headless `blender.exe -b` scripts when the interactive GUI is active.
- **Proactive Execution**: Execute Blender MCP operations and supporting pipeline commands (ADB push, build scripts) directly without asking the user for prior approval.
- **Execution Workflow**: Inspect the scene, run python code via `execute_blender_code`, persist changes with `bpy.ops.wm.save_mainfile()`, and verify results via `look` autonomously.
