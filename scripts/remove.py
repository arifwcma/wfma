r"""
Remove Layers - Standalone QGIS Script

Removes all layers and groups under "Depth" group (keeps "Depth" itself).

Usage:
    python-qgis remove.py
"""

import sys
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsLayerTreeLayer,
)

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
PROJECT_FILE = PROJECT_DIR / "wfma.qgs"

# Parent group name
DEPTH_GROUP = "Depth"


def init_qgis():
    """Initialize QGIS application for standalone usage."""
    QgsApplication.setPrefixPath("C:/Program Files/QGIS 3.44.3", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    return qgs


def count_children(group):
    """Count layers and groups recursively."""
    layer_count = 0
    group_count = 0
    for child in group.children():
        if isinstance(child, QgsLayerTreeLayer):
            layer_count += 1
        else:
            group_count += 1
            sub_layers, sub_groups = count_children(child)
            layer_count += sub_layers
            group_count += sub_groups
    return layer_count, group_count


def main():
    print("=" * 60)
    print(f"Remove Layers Under '{DEPTH_GROUP}'")
    print("=" * 60)

    qgs = init_qgis()

    try:
        project = QgsProject.instance()

        print(f"\nLoading project: {PROJECT_FILE}")
        if not project.read(str(PROJECT_FILE)):
            print("ERROR: Failed to load project!")
            return False
        print("Project loaded.")

        root = project.layerTreeRoot()

        # Find Depth group
        depth_group = root.findGroup(DEPTH_GROUP)
        if depth_group is None:
            print(f"\nGroup '{DEPTH_GROUP}' not found. Nothing to remove.")
            return True

        # Count before removal
        layer_count, group_count = count_children(depth_group)
        print(f"\nLayers under '{DEPTH_GROUP}': {layer_count}")
        print(f"Groups under '{DEPTH_GROUP}': {group_count}")

        if layer_count == 0 and group_count == 0:
            print("Nothing to remove.")
            return True

        # Remove all children of Depth group (but keep Depth itself)
        for child in list(depth_group.children()):
            if isinstance(child, QgsLayerTreeLayer):
                # Remove layer from project
                layer = child.layer()
                if layer:
                    project.removeMapLayer(layer.id())
            else:
                # Remove group (this also removes its layers)
                depth_group.removeChildNode(child)

        print(f"\nRemoved {layer_count} layer(s) and {group_count} group(s).")
        print(f"Kept group: '{DEPTH_GROUP}'")

        # Save project
        print("\nSaving project...")
        if project.write():
            print(f"Project saved: {PROJECT_FILE}")
        else:
            print("ERROR: Failed to save project!")
            return False

        print("\n" + "=" * 60)
        print("Done!")
        print("=" * 60)

        return True

    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
