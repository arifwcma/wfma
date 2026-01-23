r"""
Setup Depths - Standalone QGIS Script

For each subfolder in data\depth:
  - Create a layer tree group named after the subfolder
  - Add each GeoTIFF in that subfolder into the group
  - Force CRS to EPSG:7854
  - Apply depth.qml style

Usage:
    python-qgis setup.py
"""

import sys
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRasterLayer,
)

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
PROJECT_FILE = PROJECT_DIR / "wfma.qgs"
DEPTH_DIR = PROJECT_DIR / "data" / "depth"
DEPTH_STYLE = r"C:\Users\m.rahman\qgis\wfma\scripts\qmls\depth.qml"


def init_qgis():
    """Initialize QGIS application for standalone usage."""
    QgsApplication.setPrefixPath("C:/Program Files/QGIS 3.44.3", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    return qgs


def layer_exists_in_group(group, layer_name):
    """Check if a layer with the given name already exists in the group."""
    for child in group.children():
        if hasattr(child, 'name') and child.name() == layer_name:
            return True
    return False


def setup_depths():
    """Main function to import and style depth rasters."""
    print("=" * 60)
    print("Setup Depths")
    print("=" * 60)

    # Initialize QGIS
    print("\nInitializing QGIS...")
    qgs = init_qgis()

    # CRS must be created AFTER QGIS is initialized
    target_crs = QgsCoordinateReferenceSystem("EPSG:7854")

    try:
        project = QgsProject.instance()

        # Load project
        print(f"\nLoading project: {PROJECT_FILE}")
        if not project.read(str(PROJECT_FILE)):
            print("ERROR: Failed to load project!")
            return False
        print("Project loaded.")

        # Check depth directory
        print(f"\nDepth directory: {DEPTH_DIR}")
        if not DEPTH_DIR.exists():
            print("ERROR: Depth directory not found!")
            return False

        # Check style file
        print(f"Style file: {DEPTH_STYLE}")
        if not Path(DEPTH_STYLE).exists():
            print("WARNING: Style file not found, layers will use default style.")

        # Get layer tree root
        root = project.layerTreeRoot()

        # Find or create "Depth" parent group
        depth_group = root.findGroup("Depth")
        if depth_group is None:
            depth_group = root.addGroup("Depth")
            print("Created parent group: Depth")
        else:
            print("Using existing parent group: Depth")

        # Find subfolders
        subfolders = sorted(
            [d for d in DEPTH_DIR.iterdir() if d.is_dir()],
            key=lambda x: x.name.lower()
        )
        print(f"Found {len(subfolders)} subfolders")

        if not subfolders:
            print("No subfolders to process.")
            return True

        # Counters
        total_added = 0
        total_skipped = 0
        total_failed = 0

        # Process each subfolder
        for folder in subfolders:
            folder_name = folder.name
            print(f"\n  Processing: {folder_name}")

            # Find or create group under Depth
            group = depth_group.findGroup(folder_name)
            if group is None:
                group = depth_group.addGroup(folder_name)
                print(f"    Created group: {folder_name}")
            else:
                print(f"    Using existing group: {folder_name}")

            # Find TIFFs
            tif_files = sorted(
                [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in (".tif", ".tiff")],
                key=lambda x: x.name.lower()
            )
            print(f"    Found {len(tif_files)} TIFFs")

            # Process each TIFF
            for tif_path in tif_files:
                tif_name = tif_path.stem

                # Skip if already exists
                if layer_exists_in_group(group, tif_name):
                    print(f"      Skipped (exists): {tif_name}")
                    total_skipped += 1
                    continue

                # Load raster
                layer = QgsRasterLayer(str(tif_path), tif_name)

                if not layer.isValid():
                    print(f"      FAILED: {tif_name}")
                    total_failed += 1
                    continue

                # Set CRS
                layer.setCrs(target_crs)

                # Apply style
                layer.loadNamedStyle(DEPTH_STYLE)

                # Add to project and group
                project.addMapLayer(layer, False)
                group.addLayer(layer)

                print(f"      Added: {tif_name}")
                total_added += 1

        # Save project
        print("\n" + "=" * 60)
        print("Saving project...")
        if project.write():
            print(f"Project saved: {PROJECT_FILE}")
        else:
            print("ERROR: Failed to save project!")
            return False

        # Summary
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  Added: {total_added}")
        print(f"  Skipped: {total_skipped}")
        print(f"  Failed: {total_failed}")
        print("=" * 60)
        print("Done!")

        return True

    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    success = setup_depths()
    sys.exit(0 if success else 1)
