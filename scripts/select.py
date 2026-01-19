"""
QGIS Layer Selection Script

A command-line tool for flexible layer selection with filtering.

Usage:
    & "C:\\Program Files\\QGIS 3.44.3\\bin\\python-qgis.bat" select.py [options]

Options:
    --area, -a NAME    Filter by area name (case insensitive substring)
    --group, -g NAME   Filter by parent group name (case insensitive substring)
    --year, -y N       Filter by year (numeric match, e.g. 10 won't match 100)

Examples:
    select.py                                   Select all layers and groups
    select.py --area concongella               Select layers containing 'concongella'
    select.py --area concongella --group height Select layers under 'height' groups
    select.py -a concongella -g height -y 5    Combine all filters (AND logic)
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
PROJECT_FILE = PROJECT_DIR / "pozi_mirror.qgs"


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
    """
    Recursively deselect (uncheck) all layers and groups.
    
    Args:
        node: The root node to start from
    
    Returns:
        tuple: (layer_count, group_count) of items deselected
    """
    layer_count = 0
    group_count = 0
    
    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            child.setItemVisibilityChecked(False)
            layer_count += 1
        else:
            # It's a group
            child.setItemVisibilityChecked(False)
            group_count += 1
            # Recurse into group
            sub_layers, sub_groups = deselect_all(child)
            layer_count += sub_layers
            group_count += sub_groups
    
    return layer_count, group_count


def select_all(node):
    """
    Recursively select (check) all layers and groups.
    
    Args:
        node: The root node to start from
    
    Returns:
        tuple: (layer_count, group_count) of items selected
    """
    layer_count = 0
    group_count = 0
    
    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            child.setItemVisibilityChecked(True)
            layer_count += 1
        else:
            # It's a group
            child.setItemVisibilityChecked(True)
            group_count += 1
            # Recurse into group
            sub_layers, sub_groups = select_all(child)
            layer_count += sub_layers
            group_count += sub_groups
    
    return layer_count, group_count


def get_ancestor_groups(node):
    """
    Get all ancestor groups from a node up to (but not including) the root.
    
    Args:
        node: The layer tree node
    
    Returns:
        list: List of ancestor group nodes, from immediate parent to root
    """
    ancestors = []
    parent = node.parent()
    while parent is not None:
        # Check if it's a group (not the root which is QgsLayerTree)
        if isinstance(parent, QgsLayerTreeGroup) and parent.parent() is not None:
            ancestors.append(parent)
        parent = parent.parent()
    return ancestors


def get_parent_group_names(node):
    """
    Get names of all ancestor groups for a node.
    
    Args:
        node: The layer tree node
    
    Returns:
        list: List of ancestor group names
    """
    return [g.name() for g in get_ancestor_groups(node)]


def matches_year(layer_name, year):
    """
    Check if layer name contains the year number (not as part of a larger number).
    
    For example, year=10 matches '_10y_' but not '_100y_'.
    
    Args:
        layer_name: The layer name to check
        year: The year number to match
    
    Returns:
        bool: True if year matches
    """
    pattern = rf'(?<!\d){year}(?!\d)'
    return bool(re.search(pattern, layer_name))


def matches_filters(layer_node, args):
    """
    Check if a layer matches all specified filters.
    
    Args:
        layer_node: The QgsLayerTreeLayer node
        args: Parsed arguments with area, group, year filters
    
    Returns:
        bool: True if layer matches all filters
    """
    layer = layer_node.layer()
    if not layer:
        return False
    
    layer_name = layer.name()
    parent_group_names = get_parent_group_names(layer_node)
    
    # Check area filter (case insensitive substring in layer name)
    if args.area:
        if args.area.lower() not in layer_name.lower():
            return False
    
    # Check group filter (case insensitive substring in any parent group name)
    if args.group:
        group_match = any(
            args.group.lower() in group_name.lower()
            for group_name in parent_group_names
        )
        if not group_match:
            return False
    
    # Check year filter (numeric match in layer name)
    if args.year is not None:
        if not matches_year(layer_name, args.year):
            return False
    
    return True


def find_matching_layers(node, args):
    """
    Recursively find all layers matching the filters.
    
    Args:
        node: The root node to search from
        args: Parsed arguments with filters
    
    Returns:
        list: List of (layer_node, ancestor_groups) tuples for matching layers
    """
    matches = []
    
    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            if matches_filters(child, args):
                ancestors = get_ancestor_groups(child)
                matches.append((child, ancestors))
        else:
            # It's a group - recurse into it
            matches.extend(find_matching_layers(child, args))
    
    return matches


def main():
    parser = argparse.ArgumentParser(
        description="QGIS Layer Selection Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  select.py                                   Select all layers and groups
  select.py --area concongella               Select layers containing 'concongella'
  select.py --area concongella --group height Select layers under 'height' groups
  select.py -a concongella -g height -y 5    Combine all filters (AND logic)
        """
    )
    
    parser.add_argument(
        "--area", "-a",
        help="Filter by area name (case insensitive substring match in layer name)"
    )
    parser.add_argument(
        "--group", "-g",
        help="Filter by parent group name (case insensitive substring match)"
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        help="Filter by year (numeric match, e.g. 10 won't match 100)"
    )
    
    args = parser.parse_args()
    
    # Check if any filters are specified
    has_filters = args.area or args.group or args.year is not None
    
    if has_filters:
        filters = []
        if args.area:
            filters.append(f"area='{args.area}'")
        if args.group:
            filters.append(f"group='{args.group}'")
        if args.year is not None:
            filters.append(f"year={args.year}")
        print(f"Selecting layers with filters: {', '.join(filters)}")
    else:
        print("Selecting all layers and groups...")
    
    qgs = init_qgis()
    try:
        project = load_project()
        if not project:
            return False
        
        root = project.layerTreeRoot()
        
        # Step 1: Deselect everything
        deselect_all(root)
        
        if not has_filters:
            # No filters - select everything
            layer_count, group_count = select_all(root)
            print(f"Selected {layer_count} layer(s) and {group_count} group(s).")
        else:
            # Find matching layers
            matches = find_matching_layers(root, args)
            
            if not matches:
                print("No layers matched the filters.")
            else:
                # Collect all groups that need to be selected (ancestors of matching layers)
                groups_to_select = set()
                layers_selected = 0
                
                for layer_node, ancestors in matches:
                    # Select the layer
                    layer_node.setItemVisibilityChecked(True)
                    layers_selected += 1
                    
                    # Collect ancestor groups
                    for group in ancestors:
                        groups_to_select.add(group)
                
                # Select all ancestor groups
                for group in groups_to_select:
                    group.setItemVisibilityChecked(True)
                
                print(f"Selected {layers_selected} layer(s) and {len(groups_to_select)} ancestor group(s).")
                
                # Print matched layers
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
