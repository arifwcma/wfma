import os
import sys
from pathlib import Path

# Initialize QGIS application for standalone scripts
from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsLayerTreeGroup,
)

# Get the script directory and project paths
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
PROJECT_FILE = PROJECT_DIR / "pozi_mirror.qgs"
DATA_FLOOD_DIR = PROJECT_DIR / "data" / "flood"

# Layer types to process (matching folder names)
LAYER_TYPES = ["Height", "Depths", "Velocity"]


def init_qgis():
    """Initialize QGIS application for standalone usage."""
    # Supply path to qgis install location
    QgsApplication.setPrefixPath("C:/Program Files/QGIS 3.44.3", True)
    
    # Create a reference to the QgsApplication
    qgs = QgsApplication([], False)
    qgs.initQgis()
    
    return qgs


def get_or_create_group(parent_group: QgsLayerTreeGroup, group_name: str) -> QgsLayerTreeGroup:
    """Get an existing group or create a new one if it doesn't exist."""
    existing_group = parent_group.findGroup(group_name)
    if existing_group is not None:
        print(f"  Found existing group: {group_name}")
        return existing_group
    
    print(f"  Creating new group: {group_name}")
    return parent_group.addGroup(group_name)


def layer_exists_in_group(group: QgsLayerTreeGroup, layer_name: str) -> bool:
    """Check if a layer with the given name already exists in the group."""
    for child in group.children():
        if hasattr(child, 'name') and child.name() == layer_name:
            return True
    return False


def add_vector_layer(project: QgsProject, file_path: Path, group: QgsLayerTreeGroup):
    """Add a vector layer (shapefile) to the project and group."""
    layer_name = file_path.stem
    
    # Check if layer already exists in group
    if layer_exists_in_group(group, layer_name):
        print(f"    Layer already exists, skipping: {layer_name}")
        return
    
    layer = QgsVectorLayer(str(file_path), layer_name, "ogr")
    
    if not layer.isValid():
        print(f"    ERROR: Failed to load vector layer: {file_path}")
        return
    
    # Add layer to project
    project.addMapLayer(layer, False)
    
    # Add layer to the group
    group.addLayer(layer)
    print(f"    Added vector layer: {layer_name}")


def add_raster_layer(project: QgsProject, file_path: Path, group: QgsLayerTreeGroup):
    """Add a raster layer (TIF) to the project and group."""
    layer_name = file_path.stem
    
    # Check if layer already exists in group
    if layer_exists_in_group(group, layer_name):
        print(f"    Layer already exists, skipping: {layer_name}")
        return
    
    layer = QgsRasterLayer(str(file_path), layer_name)
    
    if not layer.isValid():
        print(f"    ERROR: Failed to load raster layer: {file_path}")
        return
    
    # Add layer to project
    project.addMapLayer(layer, False)
    
    # Add layer to the group
    group.addLayer(layer)
    print(f"    Added raster layer: {layer_name}")


def setup_flood_layers():
    """Main function to setup flood map layers."""
    print("=" * 60)
    print("QGIS Flood Layers Setup Script")
    print("=" * 60)
    
    # Initialize QGIS
    print("\nInitializing QGIS...")
    qgs = init_qgis()
    
    try:
        # Get project instance
        project = QgsProject.instance()
        
        # Load the project file
        print(f"\nLoading project: {PROJECT_FILE}")
        if not project.read(str(PROJECT_FILE)):
            print("ERROR: Failed to load project file!")
            return False
        print("Project loaded successfully.")
        
        # Get the layer tree root
        root = project.layerTreeRoot()
        
        # Step 1: Create/get "Flood maps" group
        print("\nStep 1: Setting up 'Flood maps' group...")
        flood_maps_group = get_or_create_group(root, "Flood maps")
        
        # Step 2: Create/get layer type groups (Height, Depths, Velocity)
        print("\nStep 2: Setting up layer type groups...")
        layer_type_groups = {}
        for layer_type in LAYER_TYPES:
            layer_type_groups[layer_type] = get_or_create_group(flood_maps_group, layer_type)
        
        # Step 3: Process each study folder
        print("\nStep 3: Processing study folders and adding layers...")
        
        if not DATA_FLOOD_DIR.exists():
            print(f"ERROR: Data directory not found: {DATA_FLOOD_DIR}")
            return False
        
        # Get all study folders
        study_folders = [d for d in DATA_FLOOD_DIR.iterdir() if d.is_dir()]
        
        for study_folder in sorted(study_folders):
            study_name = study_folder.name
            print(f"\n  Processing study: {study_name}")
            
            for layer_type in LAYER_TYPES:
                layer_type_folder = study_folder / layer_type
                
                if not layer_type_folder.exists():
                    print(f"    Skipping {layer_type} (folder not found)")
                    continue
                
                print(f"\n    Processing {layer_type}...")
                
                # Get or create study group under layer type
                layer_type_group = layer_type_groups[layer_type]
                study_group = get_or_create_group(layer_type_group, study_name)
                
                # Find all .shp and .tif files in the layer type folder
                shp_files = list(layer_type_folder.glob("*.shp"))
                tif_files = list(layer_type_folder.glob("*.tif"))
                
                # Add shapefiles
                for shp_file in sorted(shp_files):
                    add_vector_layer(project, shp_file, study_group)
                
                # Add TIF files
                for tif_file in sorted(tif_files):
                    add_raster_layer(project, tif_file, study_group)
                
                if not shp_files and not tif_files:
                    print(f"      No .shp or .tif files found in {layer_type_folder}")
        
        # Step 4: Save the project
        print("\n" + "=" * 60)
        print("Step 4: Saving project...")
        if project.write():
            print(f"Project saved successfully: {PROJECT_FILE}")
        else:
            print("ERROR: Failed to save project!")
            return False
        
        print("\n" + "=" * 60)
        print("Flood layers setup completed successfully!")
        print("=" * 60)
        
        return True
        
    finally:
        # Clean up QGIS
        qgs.exitQgis()


if __name__ == "__main__":
    success = setup_flood_layers()
    sys.exit(0 if success else 1)

