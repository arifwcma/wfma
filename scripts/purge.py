r"""
Purge Unused Depth Data - Standalone QGIS Script

Removes files and folders from data\depth that are NOT used by layers
in the "Depth" group. Keeps only the TIF files that are actually imported.

Usage:
    python-qgis purge.py           Show what would be deleted (dry run)
    python-qgis purge.py -confirm  Actually delete unused files
"""

import argparse
import shutil
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
DEPTH_DIR = PROJECT_DIR / "data" / "depth"

# Parent group name
DEPTH_GROUP = "Depth"


def init_qgis():
    """Initialize QGIS application for standalone usage."""
    QgsApplication.setPrefixPath("C:/Program Files/QGIS 3.44.3", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    return qgs


def get_layer_sources(node):
    """Recursively get all layer source paths under a node."""
    sources = []
    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            layer = child.layer()
            if layer:
                src = layer.source()
                # Strip any |layerid=0 suffix
                src = src.split("|")[0]
                sources.append(Path(src))
        else:
            sources.extend(get_layer_sources(child))
    return sources


def main():
    parser = argparse.ArgumentParser(
        description="Purge unused depth data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-confirm",
        action="store_true",
        help="Actually delete files (without this flag, only shows what would be deleted)"
    )
    args = parser.parse_args()

    dry_run = not args.confirm

    print("=" * 60)
    print("Purge Unused Depth Data")
    if dry_run:
        print("(DRY RUN - no files will be deleted)")
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
            print(f"\nERROR: Group '{DEPTH_GROUP}' not found.")
            return False

        # Get all layer source paths
        layer_sources = get_layer_sources(depth_group)
        print(f"\nLayers in '{DEPTH_GROUP}': {len(layer_sources)}")

        if not layer_sources:
            print("No layers found. Nothing to keep.")
            return True

        # Normalize paths and get required TIF files
        required_tifs = set()
        required_folders = set()

        for src in layer_sources:
            try:
                src_resolved = src.resolve()
                required_tifs.add(src_resolved)
                # Also keep the parent folder (area folder)
                required_folders.add(src_resolved.parent)
            except Exception as e:
                print(f"  Warning: Could not resolve path {src}: {e}")

        print(f"Required TIF files: {len(required_tifs)}")
        print(f"Required folders: {len(required_folders)}")

        # Check depth directory
        if not DEPTH_DIR.exists():
            print(f"\nDepth directory not found: {DEPTH_DIR}")
            return True

        # Find all files and folders to delete
        files_to_delete = []
        folders_to_delete = []

        for area_folder in DEPTH_DIR.iterdir():
            if not area_folder.is_dir():
                # File at root level of depth dir
                files_to_delete.append(area_folder)
                continue

            area_resolved = area_folder.resolve()

            if area_resolved not in required_folders:
                # Entire folder not needed
                folders_to_delete.append(area_folder)
            else:
                # Check files within the folder
                for f in area_folder.iterdir():
                    f_resolved = f.resolve()
                    if f.is_file() and f_resolved not in required_tifs:
                        files_to_delete.append(f)

        # Report
        print(f"\n" + "-" * 60)
        print("Files to delete:")
        if files_to_delete:
            for f in sorted(files_to_delete):
                print(f"  {f}")
        else:
            print("  (none)")

        print(f"\nFolders to delete (entirely):")
        if folders_to_delete:
            for f in sorted(folders_to_delete):
                print(f"  {f}")
        else:
            print("  (none)")

        total_files = len(files_to_delete)
        total_folders = len(folders_to_delete)

        if total_files == 0 and total_folders == 0:
            print("\nNothing to purge. All files are in use.")
            return True

        print(f"\nSummary: {total_files} file(s), {total_folders} folder(s) to delete")

        if dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN complete. To actually delete, run:")
            print("  python-qgis purge.py -confirm")
            print("=" * 60)
            return True

        # Actually delete
        print("\nDeleting...")

        deleted_files = 0
        deleted_folders = 0

        for f in files_to_delete:
            try:
                f.unlink()
                deleted_files += 1
                print(f"  Deleted file: {f.name}")
            except Exception as e:
                print(f"  ERROR deleting {f}: {e}")

        for folder in folders_to_delete:
            try:
                shutil.rmtree(folder)
                deleted_folders += 1
                print(f"  Deleted folder: {folder.name}")
            except Exception as e:
                print(f"  ERROR deleting {folder}: {e}")

        print(f"\n" + "=" * 60)
        print(f"Deleted {deleted_files} file(s) and {deleted_folders} folder(s).")
        print("=" * 60)

        return True

    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
