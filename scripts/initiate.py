"""
Initiate flood data by copying depth folders from source mirror.

Source: C:/Users/m.rahman/qgis/pozi_mirror/data/flood/
For each area (subfolder), copies Depths subfolders to data/depth/{area}
"""

import shutil
from pathlib import Path

SRC = Path(r"C:\Users\m.rahman\qgis\pozi_mirror\data\flood")
DST = Path(__file__).parent.parent / "data" / "depth"


def copy_depths():
    """Copy depth data from source mirror for all areas."""
    if not SRC.exists():
        print(f"Source not found: {SRC}")
        return

    for area_folder in SRC.iterdir():
        if not area_folder.is_dir():
            continue

        area = area_folder.name
        depths_folder = area_folder / "Depths"

        if not depths_folder.exists() or not depths_folder.is_dir():
            print(f"[{area}] No Depths folder, skipping")
            continue

        # Check if Depths folder has any children
        children = list(depths_folder.iterdir())
        if not children:
            print(f"[{area}] Depths folder empty, skipping")
            continue

        # Create destination area folder
        area_dst = DST / area
        area_dst.mkdir(parents=True, exist_ok=True)

        # Copy each child (file or folder) from Depths to destination
        for child in children:
            dst_child = area_dst / child.name
            if dst_child.exists():
                print(f"[{area}] {child.name} already exists, skipping")
                continue

            print(f"[{area}] Copying {child.name}...")
            if child.is_dir():
                shutil.copytree(child, dst_child)
            else:
                shutil.copy2(child, dst_child)

        print(f"[{area}] Done - {len(children)} item(s)")


if __name__ == "__main__":
    copy_depths()
