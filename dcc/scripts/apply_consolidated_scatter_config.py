#!/usr/bin/env python3
#region Imports
import json
import os
import sys
#endregion

#region Types
# Updates config/scatter.json to reference the 11 consolidated GLB containers
# while preserving all existing count, transform, and spatial parameters.
#endregion

#region Scaffolding
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "scatter.json")

MAPPING = {
    "maple_tree_line": {
        "asset": "tree_maple.glb",
        "lods": [
            {"lod_level": 0, "node_name": "Maple_tree1_LOD1", "min_screen_coverage_percent": 0.08},
            {"lod_level": 1, "node_name": "Maple_tree1_LOD2", "min_screen_coverage_percent": 0.02},
            {"lod_level": 2, "node_name": "Maple_tree1_LOD3", "min_screen_coverage_percent": 0.001}
        ]
    },
    "aspen_tree_line": {
        "asset": "tree_aspen.glb",
        "lods": [
            {"lod_level": 0, "node_name": "aspen2_LOD1", "min_screen_coverage_percent": 0.08},
            {"lod_level": 1, "node_name": "aspen2_LOD2", "min_screen_coverage_percent": 0.02},
            {"lod_level": 2, "node_name": "aspen2_LOD3", "min_screen_coverage_percent": 0.001}
        ]
    },
    "tree_01_scatter": {
        "asset": "tree_01.glb",
        "lods": [
            {"lod_level": 0, "node_name": "Tree_01_LOD1", "min_screen_coverage_percent": 0.08},
            {"lod_level": 1, "node_name": "Tree_01_LOD2", "min_screen_coverage_percent": 0.02},
            {"lod_level": 2, "node_name": "Tree_01_LOD3", "min_screen_coverage_percent": 0.001}
        ]
    },
    "tree_02_scatter": {
        "asset": "tree_02.glb",
        "lods": [
            {"lod_level": 0, "node_name": "Tree_02_LOD1", "min_screen_coverage_percent": 0.08},
            {"lod_level": 1, "node_name": "Tree_02_LOD2", "min_screen_coverage_percent": 0.02},
            {"lod_level": 2, "node_name": "Tree_02_LOD3", "min_screen_coverage_percent": 0.001}
        ]
    },
    "forest_fern_01": {
        "asset": "fern_01.glb",
        "lods": [
            {"lod_level": 0, "node_name": "AE_15TH_FERN_01_LOD1", "min_screen_coverage_percent": 0.04},
            {"lod_level": 1, "node_name": "AE_15TH_FERN_01_LOD2", "min_screen_coverage_percent": 0.01},
            {"lod_level": 2, "node_name": "AE_15TH_FERN_01_LOD3", "min_screen_coverage_percent": 0.0005}
        ]
    },
    "forest_fern_02": {
        "asset": "fern_02.glb",
        "lods": [
            {"lod_level": 0, "node_name": "AE_15TH_FERN_02_LOD1", "min_screen_coverage_percent": 0.04},
            {"lod_level": 1, "node_name": "AE_15TH_FERN_02_LOD2", "min_screen_coverage_percent": 0.01},
            {"lod_level": 2, "node_name": "AE_15TH_FERN_02_LOD3", "min_screen_coverage_percent": 0.0005}
        ]
    },
    "forest_bush_01": {
        "asset": "bush_01.glb",
        "lods": [
            {"lod_level": 0, "node_name": "AE_15TH_FOREST_BUSH_01_LOD1", "min_screen_coverage_percent": 0.06},
            {"lod_level": 1, "node_name": "AE_15TH_FOREST_BUSH_01_LOD2", "min_screen_coverage_percent": 0.015},
            {"lod_level": 2, "node_name": "AE_15TH_FOREST_BUSH_01_LOD3", "min_screen_coverage_percent": 0.0008}
        ]
    },
    "forest_ground_leaves": {
        "asset": "leaves.glb",
        "lods": [
            {"lod_level": 0, "node_name": "AE_15TH_DRY_LEAVES_02", "min_screen_coverage_percent": 0.002},
            {"lod_level": 1, "node_name": "AE_15TH_DRY_LEAVES_03", "min_screen_coverage_percent": 0.0002}
        ]
    },
    "forest_rock_01": {
        "asset": "rock_01.glb",
        "lods": [
            {"lod_level": 0, "node_name": "Rock_01_LOD2", "min_screen_coverage_percent": 0.01},
            {"lod_level": 1, "node_name": "Rock_01_LOD3", "min_screen_coverage_percent": 0.0005}
        ]
    },
    "forest_rock_02": {
        "asset": "rock_02.glb",
        "lods": [
            {"lod_level": 0, "node_name": "Rock_02_LOD2", "min_screen_coverage_percent": 0.01},
            {"lod_level": 1, "node_name": "Rock_02_LOD3", "min_screen_coverage_percent": 0.0005}
        ]
    },
    "forest_rock_03": {
        "asset": "rock_03.glb",
        "lods": [
            {"lod_level": 0, "node_name": "Rock_03_LOD2", "min_screen_coverage_percent": 0.01},
            {"lod_level": 1, "node_name": "Rock_03_LOD3", "min_screen_coverage_percent": 0.0005}
        ]
    }
}
#endregion

#region Domain
def apply_consolidation(rules):
    for rule in rules:
        name = rule.get("name")
        if name in MAPPING:
            m = MAPPING[name]
            rule["asset"] = m["asset"]
            rule.pop("prototype_asset", None)
            
            orig_cov = {}
            for lod in rule.get("lods", []):
                orig_cov[lod.get("lod_level")] = lod.get("min_screen_coverage_percent")
            
            updated_lods = []
            for lod_spec in m["lods"]:
                lvl = lod_spec["lod_level"]
                cov = orig_cov.get(lvl, lod_spec["min_screen_coverage_percent"])
                updated_lods.append({
                    "lod_level": lvl,
                    "prototype_asset": m["asset"],
                    "node_name": lod_spec["node_name"],
                    "min_screen_coverage_percent": cov
                })
            rule["lods"] = updated_lods
    return rules
#endregion

#region Core
def update_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        rules = json.load(f)
    
    updated = apply_consolidation(rules)
    
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2)
    print(f"Updated {CONFIG_PATH} with {len(updated)} rules referencing consolidated assets.")
#endregion

#region Main
if __name__ == "__main__":
    update_config()
#endregion
