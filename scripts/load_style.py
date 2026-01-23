r"""
Load Style - Standalone QGIS Script

Applies depth.qml style to all layers under the "Depth" group.

Usage:
    python-qgis load_style.py
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
DEPTH_STYLE = r"C:\Users\m.rahman\qgis\wfma\scripts\qmls\depth.qml"

# Parent group name
DEPTH_GROUP = "Depth"


def init_qgis():
    """Initialize QGIS application for standalone usage."""
    QgsApplication.setPrefixPath("C:/Program Files/QGIS 3.44.3", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    return qgs


def apply_style_recursive(node, style_path):
    """Recursively apply style to all layers under a node."""
    count = 0
    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            layer = child.layer()
            if layer:
                layer.loadNamedStyle(style_path)
                layer.triggerRepaint()
                print(f"  Styled: {layer.name()}")
                count += 1
        else:
            # It's a group - recurse
            count += apply_style_recursive(child, style_path)
    return count


def main():
    print("=" * 60)
    print("Load Style")
    print("=" * 60)

    # Check style file
    if not Path(DEPTH_STYLE).exists():
        print(f"ERROR: Style file not found: {DEPTH_STYLE}")
        return False

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
            print(f"\nERROR: Group '{DEPTH_GROUP}' not found.")
            return False

        print(f"\nApplying style to layers under '{DEPTH_GROUP}'...")
        count = apply_style_recursive(depth_group, DEPTH_STYLE)

        print(f"\nStyled {count} layer(s).")

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
