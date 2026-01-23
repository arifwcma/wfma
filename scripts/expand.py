r"""
QGIS Group Expand/Collapse Script

Expands/collapses groups under the "Depth" group.

Usage:
    python-qgis expand.py           Expand all groups under Depth
    python-qgis expand.py -none     Collapse all groups under Depth
"""

import argparse
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


def load_project():
    """Load the QGIS project."""
    project = QgsProject.instance()
    if not project.read(str(PROJECT_FILE)):
        print(f"ERROR: Failed to load project: {PROJECT_FILE}")
        return None
    return project


def set_expanded_recursive(node, expanded):
    """Recursively set expanded state for all groups."""
    group_count = 0

    for child in node.children():
        if not isinstance(child, QgsLayerTreeLayer):
            # It's a group
            child.setExpanded(expanded)
            group_count += 1
            group_count += set_expanded_recursive(child, expanded)

    return group_count


def main():
    parser = argparse.ArgumentParser(
        description="QGIS Group Expand/Collapse Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-none",
        action="store_true",
        dest="none",
        help="Collapse all groups"
    )

    args = parser.parse_args()

    if args.none:
        print(f"Collapsing all groups under '{DEPTH_GROUP}'...")
        expand = False
    else:
        print(f"Expanding all groups under '{DEPTH_GROUP}'...")
        expand = True

    qgs = init_qgis()
    try:
        project = load_project()
        if not project:
            return False

        root = project.layerTreeRoot()

        # Find Depth group
        depth_group = root.findGroup(DEPTH_GROUP)
        if depth_group is None:
            print(f"ERROR: Group '{DEPTH_GROUP}' not found.")
            return False

        # Set Depth group expanded state
        depth_group.setExpanded(expand)

        # Set all child groups expanded state
        group_count = set_expanded_recursive(depth_group, expand)

        action = "Expanded" if expand else "Collapsed"
        print(f"{action} {group_count} group(s).")

        if project.write():
            print("\nProject saved.")
            return True
        else:
            print("ERROR: Failed to save project.")
            return False
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
