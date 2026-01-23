r"""
QGIS Layer Selection Script

Selects/deselects layers under the "Depth" group.

Usage:
    python-qgis select.py           Select all layers under Depth
    python-qgis select.py -none     Deselect all layers under Depth
    python-qgis select.py [filters] Select layers matching filters

Filters:
    -none              Deselect all layers
    --area, -a NAME    Filter by area name (case insensitive substring)
    --group, -g NAME   Filter by parent group name (case insensitive substring)
    --year, -y N       Filter by year (numeric match, e.g. 10 won't match 100)

Examples:
    select.py                                   Select all layers under Depth
    select.py -none                             Deselect all layers under Depth
    select.py --area concongella                Select layers containing 'concongella'
    select.py -a concongella -g height -y 5     Combine filters (AND logic)
"""

import argparse
import re
import sys
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsLayerTreeLayer,
    QgsLayerTreeGroup,
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


def deselect_all(node):
    """Recursively deselect (uncheck) all layers and groups."""
    layer_count = 0
    group_count = 0

    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            child.setItemVisibilityChecked(False)
            layer_count += 1
        else:
            child.setItemVisibilityChecked(False)
            group_count += 1
            sub_layers, sub_groups = deselect_all(child)
            layer_count += sub_layers
            group_count += sub_groups

    return layer_count, group_count


def select_all(node):
    """Recursively select (check) all layers and groups."""
    layer_count = 0
    group_count = 0

    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            child.setItemVisibilityChecked(True)
            layer_count += 1
        else:
            child.setItemVisibilityChecked(True)
            group_count += 1
            sub_layers, sub_groups = select_all(child)
            layer_count += sub_layers
            group_count += sub_groups

    return layer_count, group_count


def get_ancestor_groups(node):
    """Get all ancestor groups from a node up to (but not including) the root."""
    ancestors = []
    parent = node.parent()
    while parent is not None:
        if isinstance(parent, QgsLayerTreeGroup) and parent.parent() is not None:
            ancestors.append(parent)
        parent = parent.parent()
    return ancestors


def get_parent_group_names(node):
    """Get names of all ancestor groups for a node."""
    return [g.name() for g in get_ancestor_groups(node)]


def matches_year(layer_name, year):
    """Check if layer name contains the year number (not as part of a larger number)."""
    pattern = rf'(?<!\d){year}(?!\d)'
    return bool(re.search(pattern, layer_name))


def matches_filters(layer_node, args):
    """Check if a layer matches all specified filters."""
    layer = layer_node.layer()
    if not layer:
        return False

    layer_name = layer.name()
    parent_group_names = get_parent_group_names(layer_node)

    if args.area:
        if args.area.lower() not in layer_name.lower():
            return False

    if args.group:
        group_match = any(
            args.group.lower() in group_name.lower()
            for group_name in parent_group_names
        )
        if not group_match:
            return False

    if args.year is not None:
        if not matches_year(layer_name, args.year):
            return False

    return True


def find_matching_layers(node, args):
    """Recursively find all layers matching the filters."""
    matches = []

    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            if matches_filters(child, args):
                ancestors = get_ancestor_groups(child)
                matches.append((child, ancestors))
        else:
            matches.extend(find_matching_layers(child, args))

    return matches


def main():
    parser = argparse.ArgumentParser(
        description="QGIS Layer Selection Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-none",
        action="store_true",
        dest="none",
        help="Deselect all layers"
    )
    parser.add_argument(
        "--area", "-a",
        help="Filter by area name (case insensitive substring)"
    )
    parser.add_argument(
        "--group", "-g",
        help="Filter by parent group name (case insensitive substring)"
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        help="Filter by year (numeric match)"
    )

    args = parser.parse_args()

    # Check for -none flag
    if args.none:
        print(f"Deselecting all layers under '{DEPTH_GROUP}'...")
        mode = "none"
    elif args.area or args.group or args.year is not None:
        filters = []
        if args.area:
            filters.append(f"area='{args.area}'")
        if args.group:
            filters.append(f"group='{args.group}'")
        if args.year is not None:
            filters.append(f"year={args.year}")
        print(f"Selecting layers: {', '.join(filters)}")
        mode = "filter"
    else:
        print(f"Selecting all layers under '{DEPTH_GROUP}'...")
        mode = "all"

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

        if mode == "none":
            # Deselect Depth group and all its children
            depth_group.setItemVisibilityChecked(False)
            layer_count, group_count = deselect_all(depth_group)
            print(f"Deselected {layer_count} layer(s) and {group_count} group(s).")

        elif mode == "all":
            # Select Depth group and all its children
            depth_group.setItemVisibilityChecked(True)
            layer_count, group_count = select_all(depth_group)
            print(f"Selected {layer_count} layer(s) and {group_count} group(s).")

        else:
            # Filter mode - first deselect all under Depth
            depth_group.setItemVisibilityChecked(False)
            deselect_all(depth_group)

            matches = find_matching_layers(depth_group, args)

            if not matches:
                print("No layers matched the filters.")
            else:
                groups_to_select = set()
                layers_selected = 0

                for layer_node, ancestors in matches:
                    layer_node.setItemVisibilityChecked(True)
                    layers_selected += 1
                    for group in ancestors:
                        groups_to_select.add(group)

                for group in groups_to_select:
                    group.setItemVisibilityChecked(True)

                print(f"Selected {layers_selected} layer(s) and {len(groups_to_select)} group(s).")

                print("\nMatched layers:")
                for layer_node, _ in matches:
                    layer = layer_node.layer()
                    if layer:
                        print(f"  - {layer.name()}")

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
