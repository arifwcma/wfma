r"""
Purge Unused Depth Data

Two-phase approach to avoid GDAL file handle issues:

Phase 1 (requires python-qgis):
    python-qgis purge.py -list
    Analyzes project and writes paths to delete into purge.txt

Phase 2 (plain Python, no QGIS):
    python purge.py -confirm
    Reads purge.txt and deletes the files/folders
"""

import sys
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
PROJECT_FILE = PROJECT_DIR / "wfma.qgs"
DEPTH_DIR = PROJECT_DIR / "data" / "depth"
PURGE_FILE = SCRIPT_DIR / "purge.txt"

# Parent group name
DEPTH_GROUP = "Depth"


def do_list():
    """Phase 1: Analyze project and write paths to purge.txt"""
    # Import QGIS only for this phase
    from qgis.core import (
        QgsApplication,
        QgsProject,
        QgsLayerTreeLayer,
    )

    def get_layer_sources(node):
        sources = []
        for child in node.children():
            if isinstance(child, QgsLayerTreeLayer):
                layer = child.layer()
                if layer:
                    src = layer.source().split("|")[0]
                    sources.append(Path(src))
            else:
                sources.extend(get_layer_sources(child))
        return sources

    print("=" * 60)
    print("Purge - Phase 1: Analyze")
    print("=" * 60)

    # Initialize QGIS
    QgsApplication.setPrefixPath("C:/Program Files/QGIS 3.44.3", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()

    try:
        project = QgsProject.instance()

        print(f"\nLoading project: {PROJECT_FILE}")
        if not project.read(str(PROJECT_FILE)):
            print("ERROR: Failed to load project!")
            return False
        print("Project loaded.")

        root = project.layerTreeRoot()

        depth_group = root.findGroup(DEPTH_GROUP)
        if depth_group is None:
            print(f"\nERROR: Group '{DEPTH_GROUP}' not found.")
            return False

        layer_sources = get_layer_sources(depth_group)
        print(f"\nLayers in '{DEPTH_GROUP}': {len(layer_sources)}")

        if not layer_sources:
            print("No layers found. Nothing to keep.")
            return True

        # Normalize paths
        required_tifs = set()
        required_folders = set()

        for src in layer_sources:
            try:
                src_resolved = src.resolve()
                required_tifs.add(str(src_resolved))
                required_folders.add(str(src_resolved.parent))
            except Exception as e:
                print(f"  Warning: Could not resolve path {src}: {e}")

        print(f"Required TIF files: {len(required_tifs)}")
        print(f"Required folders: {len(required_folders)}")

        if not DEPTH_DIR.exists():
            print(f"\nDepth directory not found: {DEPTH_DIR}")
            return True

        # Find paths to delete
        files_to_delete = []
        folders_to_delete = []

        for area_folder in DEPTH_DIR.iterdir():
            if not area_folder.is_dir():
                files_to_delete.append(str(area_folder.resolve()))
                continue

            area_resolved = str(area_folder.resolve())

            if area_resolved not in required_folders:
                folders_to_delete.append(area_resolved)
            else:
                for f in area_folder.iterdir():
                    f_resolved = str(f.resolve())
                    if f.is_file() and f_resolved not in required_tifs:
                        files_to_delete.append(f_resolved)

        # Report
        print(f"\n" + "-" * 60)
        print("Files to delete:")
        for f in sorted(files_to_delete):
            print(f"  {f}")
        if not files_to_delete:
            print("  (none)")

        print(f"\nFolders to delete:")
        for f in sorted(folders_to_delete):
            print(f"  {f}")
        if not folders_to_delete:
            print("  (none)")

        total = len(files_to_delete) + len(folders_to_delete)

        if total == 0:
            print("\nNothing to purge.")
            # Write empty file
            PURGE_FILE.write_text("")
            return True

        # Write to purge.txt
        with open(PURGE_FILE, 'w', encoding='utf-8') as f:
            for path in files_to_delete:
                f.write(f"FILE:{path}\n")
            for path in folders_to_delete:
                f.write(f"FOLDER:{path}\n")

        print(f"\n" + "=" * 60)
        print(f"Written {total} path(s) to: {PURGE_FILE}")
        print("\nNext step: Close QGIS, then run:")
        print("  python purge.py -confirm")
        print("=" * 60)

        return True

    finally:
        project.removeAllMapLayers()
        project.clear()
        qgs.exitQgis()


def do_confirm():
    """Phase 2: Read purge.txt and delete (NO QGIS)"""
    import shutil

    print("=" * 60)
    print("Purge - Phase 2: Delete")
    print("=" * 60)

    if not PURGE_FILE.exists():
        print(f"\nERROR: {PURGE_FILE} not found.")
        print("Run 'python-qgis purge.py -list' first.")
        return False

    content = PURGE_FILE.read_text(encoding='utf-8').strip()
    if not content:
        print("\nNothing to delete (purge.txt is empty).")
        return True

    lines = content.split('\n')
    print(f"\nFound {len(lines)} path(s) to delete.\n")

    deleted_files = 0
    deleted_folders = 0
    errors = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("FILE:"):
            path = Path(line[5:])
            try:
                path.unlink()
                print(f"  Deleted file: {path.name}")
                deleted_files += 1
            except Exception as e:
                print(f"  ERROR deleting file {path}: {e}")
                errors += 1

        elif line.startswith("FOLDER:"):
            path = Path(line[7:])
            try:
                shutil.rmtree(path)
                print(f"  Deleted folder: {path.name}")
                deleted_folders += 1
            except Exception as e:
                print(f"  ERROR deleting folder {path}: {e}")
                errors += 1

    # Clear purge.txt after successful deletion
    if errors == 0:
        PURGE_FILE.write_text("")

    print(f"\n" + "=" * 60)
    print(f"Deleted: {deleted_files} file(s), {deleted_folders} folder(s)")
    if errors:
        print(f"Errors: {errors}")
    print("=" * 60)

    return errors == 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python-qgis purge.py -list      Analyze and write purge.txt")
        print("  python purge.py -confirm        Delete paths in purge.txt")
        return False

    arg = sys.argv[1].lower()

    if arg == "-list":
        return do_list()
    elif arg == "-confirm":
        return do_confirm()
    else:
        print(f"Unknown argument: {arg}")
        print("Use -list or -confirm")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
