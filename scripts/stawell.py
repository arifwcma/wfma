r"""
Stawell Data Import Script

Copies depth rasters from wfm_stawell project to wfma.

Source: C:\Users\m.rahman\qgis\wfm_stawell\stawell\data\rasters\{folder}\data.tif
Dest:   C:\Users\m.rahman\qgis\wfma\data\depth\Stawell_2024\{folder}.tif

Usage:
    python stawell.py
"""

import shutil
import sys
from pathlib import Path

# Paths
SOURCE_DIR = Path(r"C:\Users\m.rahman\qgis\wfm_stawell\stawell\data\rasters")
DEST_DIR = Path(r"C:\Users\m.rahman\qgis\wfma\data\depth\Stawell_2024")


def main():
    print("=" * 60)
    print("Stawell Data Import")
    print("=" * 60)
    print(f"\nSource: {SOURCE_DIR}")
    print(f"Dest:   {DEST_DIR}")

    # Check source exists
    if not SOURCE_DIR.exists():
        print(f"\nERROR: Source directory not found!")
        return False

    # Create destination if needed
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nDestination folder ready.")

    # Find all subfolders with data.tif
    copied = 0
    skipped = 0
    failed = 0

    folders = sorted([d for d in SOURCE_DIR.iterdir() if d.is_dir()])
    print(f"Found {len(folders)} folders to process.\n")

    for folder in folders:
        folder_name = folder.name
        source_tif = folder / "data.tif"
        dest_tif = DEST_DIR / f"{folder_name}.tif"

        if not source_tif.exists():
            print(f"  {folder_name}: No data.tif found, skipping")
            skipped += 1
            continue

        if dest_tif.exists():
            print(f"  {folder_name}: Already exists, skipping")
            skipped += 1
            continue

        try:
            shutil.copy2(source_tif, dest_tif)
            print(f"  {folder_name}: Copied")
            copied += 1
        except Exception as e:
            print(f"  {folder_name}: FAILED - {e}")
            failed += 1

    print(f"\n" + "=" * 60)
    print("Summary:")
    print(f"  Copied: {copied}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
