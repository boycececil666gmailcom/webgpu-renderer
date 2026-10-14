---
trigger: always_on
description: Auto-execute all Blender MCP tools and commands proactively
---

# Blender Automated Execution Directive

- **Proactive Execution**: Always execute Blender MCP tools (`execute_blender_code`, `get_scene_info`, `look`, `get_addon_status`, `search_assets`, `import_asset`, etc.) and CLI commands directly without asking the user for prior approval.
- **Execution Workflow**: Inspect the scene, run python code via `execute_blender_code`, and verify results via `look` autonomously.

