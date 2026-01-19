"""
Raw Import Script: Import flood investigation data

This script imports flood study folders from I:\FloodInvestigations
into data/flood, maintaining the expected folder structure.

Source structure:
    I:\FloodInvestigations\{StudyName}\Data\Depth\  (or Depths\)
    I:\FloodInvestigations\{StudyName}\Data\Height\
    I:\FloodInvestigations\{StudyName}\Data\Velocity\

Destination structure:
    data/flood/{StudyName}/Depths/   (note: Depth -> Depths rename)
    data/flood/{StudyName}/Height/
    data/flood/{StudyName}/Velocity/

Usage:
    python raw_import.py
"""

import shutil
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
DEST_FLOOD_DIR = PROJECT_DIR / "data" / "flood"
SOURCE_DIR = Path(r"I:\FloodInvestigations")

# Layer type mappings (source folder names -> destination folder name)
# Each entry is: (list of possible source names, destination name)
LAYER_TYPE_MAPPING = [
    (["Depth", "Depths"], "Depths"),  # Try Depth first, then Depths
    (["Height"], "Height"),
    (["Velocity"], "Velocity"),
]


def copy_folder_merge(src: Path, dst: Path):
    """
    Copy folder contents, merging with existing destination.
    New files are copied, existing files are kept.
    """
    if not src.exists():
        return 0
    
    # Create destination if it doesn't exist
    dst.mkdir(parents=True, exist_ok=True)
    
    files_copied = 0
    
    for item in src.iterdir():
        dest_item = dst / item.name
        
        if item.is_dir():
            # Recursively copy subdirectories
            files_copied += copy_folder_merge(item, dest_item)
        else:
            # Copy file only if it doesn't exist at destination
            if not dest_item.exists():
                shutil.copy2(item, dest_item)
                files_copied += 1
                print(f"      Copied: {item.name}")
            else:
                print(f"      Skipped (exists): {item.name}")
    
    return files_copied


def raw_import():
    """Main function to import flood investigation data."""
    print("=" * 60)
    print("Raw Import: Flood Investigations Data")
    print("=" * 60)
    print(f"\nSource: {SOURCE_DIR}")
    print(f"Destination: {DEST_FLOOD_DIR}")
    
    # Check source directory exists
    if not SOURCE_DIR.exists():
        print(f"\nERROR: Source directory not found: {SOURCE_DIR}")
        return False
    
    # Ensure destination directory exists
    DEST_FLOOD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Track skipped items
    skipped = []
    
    # Track statistics
    studies_processed = 0
    total_files_copied = 0
    
    print("\n" + "-" * 60)
    print("Processing folders...")
    print("-" * 60)
    
    # Iterate through all children in source directory
    for child in sorted(SOURCE_DIR.iterdir()):
        child_name = child.name
        
        # Skip if not a directory
        if not child.is_dir():
            skipped.append((child_name, "Not a folder"))
            continue
        
        # Check for Data subfolder
        data_folder = child / "Data"
        if not data_folder.exists() or not data_folder.is_dir():
            skipped.append((child_name, "No 'Data' subfolder found"))
            continue
        
        print(f"\n  Processing: {child_name}")
        
        # Destination study folder
        dest_study_folder = DEST_FLOOD_DIR / child_name
        
        # Track if any layer types were found
        layer_types_found = False
        
        # Process each layer type
        for src_layer_names, dest_layer_name in LAYER_TYPE_MAPPING:
            # Try each possible source folder name in order
            src_layer_folder = None
            used_src_name = None
            
            for src_name in src_layer_names:
                candidate = data_folder / src_name
                if candidate.exists() and candidate.is_dir():
                    src_layer_folder = candidate
                    used_src_name = src_name
                    break
            
            if src_layer_folder is not None:
                layer_types_found = True
                dest_layer_folder = dest_study_folder / dest_layer_name
                
                print(f"\n    Copying {used_src_name} -> {dest_layer_name}...")
                files_copied = copy_folder_merge(src_layer_folder, dest_layer_folder)
                total_files_copied += files_copied
                print(f"    Files copied: {files_copied}")
        
        if layer_types_found:
            studies_processed += 1
        else:
            skipped.append((child_name, "No Depth/Height/Velocity folders in Data"))
    
    # Print summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"\nStudies processed: {studies_processed}")
    print(f"Total files copied: {total_files_copied}")
    
    # Print skipped items
    if skipped:
        print(f"\nSkipped items ({len(skipped)}):")
        print("-" * 40)
        for name, reason in skipped:
            print(f"  {name}")
            print(f"    Reason: {reason}")
    else:
        print("\nNo items were skipped.")
    
    print("\n" + "=" * 60)
    print("Import completed!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    raw_import()
