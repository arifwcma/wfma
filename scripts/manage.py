"""
QGIS Project Management Script

A command-line tool for various QGIS project tasks.

Usage:
    & "C:\\Program Files\\QGIS 3.44.3\\bin\\python-qgis.bat" manage.py <command>

Commands:
    select      - Select (check) all layers, or a specific group recursively
                  Usage: select [group_name]
    deselect    - Deselect (uncheck) all layers
    crs         - Set CRS of all layers under 'Flood maps' to EPSG:7854
    style_dump  - Export styles from source layers to QML files (qmls/ folder)
    style_load  - Load styles from QML files and apply to layer groups
    vd          - Create Velocity x Depth rasters for each area and year
    hazard      - Create Hazard classification rasters (H1-H6) using ARR method
                  Uses Depth, Velocity, and VelocityXDepth layers from vd_log.csv
                  Classification per ARR Table 6.7.4 (Smith et al., 2014)
"""

import argparse
import re
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
PROJECT_FILE = PROJECT_DIR / "pozi_mirror.qgs"
QML_DIR = SCRIPT_DIR / "qmls"


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


def set_all_layers_visibility(project, visible: bool, include_groups: bool = False):
    """Set visibility (checked state) for all layers (and optionally groups) in the project."""
    root = project.layerTreeRoot()
    
    def process_node(node):
        """Recursively process all nodes in the layer tree."""
        layer_count = 0
        group_count = 0
        for child in node.children():
            if isinstance(child, QgsLayerTreeLayer):
                child.setItemVisibilityChecked(visible)
                layer_count += 1
            else:
                # It's a group
                if include_groups:
                    child.setItemVisibilityChecked(visible)
                    group_count += 1
                # Recurse into group
                sub_layers, sub_groups = process_node(child)
                layer_count += sub_layers
                group_count += sub_groups
        return layer_count, group_count
    
    return process_node(root)


def select_group_recursive(node, visible: bool = True):
    """
    Recursively select/deselect a group and all its children (groups and layers).
    
    Args:
        node: The layer tree node (group) to process
        visible: True to select, False to deselect
    
    Returns:
        tuple: (layer_count, group_count)
    """
    layer_count = 0
    group_count = 0
    
    # Select the group itself
    node.setItemVisibilityChecked(visible)
    group_count += 1
    
    for child in node.children():
        if isinstance(child, QgsLayerTreeLayer):
            child.setItemVisibilityChecked(visible)
            layer_count += 1
        else:
            # It's a group - recurse
            sub_layers, sub_groups = select_group_recursive(child, visible)
            layer_count += sub_layers
            group_count += sub_groups
    
    return layer_count, group_count


def find_group_recursive(node, group_name):
    """
    Recursively search for a group by name in the layer tree.
    
    Args:
        node: The starting node to search from
        group_name: The name of the group to find
    
    Returns:
        The group node if found, None otherwise
    """
    for child in node.children():
        if not isinstance(child, QgsLayerTreeLayer):
            # It's a group
            if child.name() == group_name:
                return child
            # Recurse into subgroups
            found = find_group_recursive(child, group_name)
            if found:
                return found
    return None


def cmd_select(args):
    """Select (check) all layers, or a specific group recursively."""
    group_name = getattr(args, 'group', None)
    
    if group_name:
        print(f"Selecting group '{group_name}' and all children...")
    else:
        print("Selecting all layers...")
    
    qgs = init_qgis()
    try:
        project = load_project()
        if not project:
            return False
        
        root = project.layerTreeRoot()
        
        if group_name:
            # Find the specified group
            target_group = find_group_recursive(root, group_name)
            if not target_group:
                print(f"ERROR: Group '{group_name}' not found.")
                return False
            
            layer_count, group_count = select_group_recursive(target_group, True)
            print(f"Selected {layer_count} layer(s) and {group_count} group(s).")
        else:
            # Select all layers
            layer_count, _ = set_all_layers_visibility(project, True)
            print(f"Selected {layer_count} layer(s).")
        
        if project.write():
            print("Project saved.")
            return True
        else:
            print("ERROR: Failed to save project.")
            return False
    finally:
        qgs.exitQgis()


def cmd_deselect(args):
    """Deselect (uncheck) all layers and groups."""
    print("Deselecting all layers and groups...")
    
    qgs = init_qgis()
    try:
        project = load_project()
        if not project:
            return False
        
        layer_count, group_count = set_all_layers_visibility(project, False, include_groups=True)
        print(f"Deselected {layer_count} layer(s) and {group_count} group(s).")
        
        if project.write():
            print("Project saved.")
            return True
        else:
            print("ERROR: Failed to save project.")
            return False
    finally:
        qgs.exitQgis()


def cmd_crs(args):
    """Set CRS of all layers under 'Flood maps' to EPSG:7854."""
    print("Setting CRS to EPSG:7854 for all 'Flood maps' layers...")
    
    qgs = init_qgis()
    try:
        from qgis.core import QgsCoordinateReferenceSystem
        
        project = load_project()
        if not project:
            return False
        
        root = project.layerTreeRoot()
        
        # Create the target CRS
        target_crs = QgsCoordinateReferenceSystem("EPSG:7854")
        if not target_crs.isValid():
            print("ERROR: EPSG:7854 is not a valid CRS.")
            return False
        
        print(f"Target CRS: {target_crs.authid()} - {target_crs.description()}")
        
        # Find the 'Flood maps' group
        flood_maps_group = root.findGroup("Flood maps")
        if not flood_maps_group:
            print("ERROR: 'Flood maps' group not found.")
            return False
        
        # Apply CRS to all layers under 'Flood maps'
        def apply_crs_to_group(node):
            """Recursively apply CRS to all layers in the group."""
            count = 0
            for child in node.children():
                if isinstance(child, QgsLayerTreeLayer):
                    layer = child.layer()
                    if layer:
                        layer.setCrs(target_crs)
                        print(f"  Set CRS for: {layer.name()}")
                        count += 1
                else:
                    # It's a group, recurse into it
                    count += apply_crs_to_group(child)
            return count
        
        count = apply_crs_to_group(flood_maps_group)
        print(f"\nUpdated CRS for {count} layer(s).")
        
        if project.write():
            print("Project saved.")
            return True
        else:
            print("ERROR: Failed to save project.")
            return False
    finally:
        qgs.exitQgis()


# Style mappings: (source layer name, target group name, qml filename)
STYLE_MAPPINGS = [
    ("Concongella_5y_h_Max", "Height", "height.qml"),
    ("Concongella_5y_d_Max", "Depths", "depth.qml"),
    ("Concongella_5y_V_Max", "Velocity", "velocity.qml"),
    ("Concongella_2015_5y_VD", "VelocityXDepth", "vd.qml"),
    ("Concongella_2015_5y_Hazard", "Hazard", "hazard.qml"),
]


def cmd_style_dump(args):
    """Export styles from source layers to QML files."""
    print("Dumping styles to QML files...")
    
    qgs = init_qgis()
    try:
        project = load_project()
        if not project:
            return False
        
        # Create qmls directory if it doesn't exist
        QML_DIR.mkdir(parents=True, exist_ok=True)
        
        dumped_count = 0
        
        for source_name, target_group_name, qml_filename in STYLE_MAPPINGS:
            qml_path = QML_DIR / qml_filename
            
            # Find the source layer
            source_layers = project.mapLayersByName(source_name)
            if not source_layers:
                print(f"  Source layer '{source_name}' not found. Skipping.")
                continue
            
            source_layer = source_layers[0]
            
            # Save style to QML file
            msg, ok = source_layer.saveNamedStyle(str(qml_path))
            if ok:
                print(f"  {source_name} -> {qml_filename}")
                dumped_count += 1
            else:
                print(f"  ERROR saving {source_name}: {msg}")
        
        print(f"\nDumped {dumped_count} style(s) to {QML_DIR}")
        return True
    finally:
        qgs.exitQgis()


def cmd_style_load(args):
    """Load styles from QML files and apply to target layer groups."""
    print("Loading styles from QML files...")
    
    qgs = init_qgis()
    try:
        project = load_project()
        if not project:
            return False
        
        root = project.layerTreeRoot()
        
        # Find the 'Flood maps' group
        flood_maps_group = root.findGroup("Flood maps")
        if not flood_maps_group:
            print("ERROR: 'Flood maps' group not found.")
            return False
        
        total_updated = 0
        
        for source_name, target_group_name, qml_filename in STYLE_MAPPINGS:
            print(f"\n--- {target_group_name} ---")
            
            qml_path = QML_DIR / qml_filename
            if not qml_path.exists():
                print(f"  QML file '{qml_filename}' not found. Run 'style_dump' first.")
                continue
            
            print(f"  Source: {qml_filename}")
            
            # Find the target group under 'Flood maps'
            target_group = flood_maps_group.findGroup(target_group_name)
            if not target_group:
                print(f"  Target group '{target_group_name}' not found. Skipping.")
                continue
            
            # Apply style to all layers in target group
            def apply_style_to_group(node):
                """Recursively apply style to all layers in the group."""
                count = 0
                for child in node.children():
                    if isinstance(child, QgsLayerTreeLayer):
                        layer = child.layer()
                        if layer:
                            msg, ok = layer.loadNamedStyle(str(qml_path))
                            if ok:
                                layer.triggerRepaint()
                                print(f"    Applied to: {layer.name()}")
                                count += 1
                            else:
                                print(f"    ERROR on {layer.name()}: {msg}")
                    else:
                        # It's a group, recurse into it
                        count += apply_style_to_group(child)
                return count
            
            count = apply_style_to_group(target_group)
            total_updated += count
            print(f"  Updated {count} layer(s) in {target_group_name}")
        
        print(f"\n{'=' * 40}")
        print(f"Total layers updated: {total_updated}")
        
        if project.write():
            print("Project saved.")
            return True
        else:
            print("ERROR: Failed to save project.")
            return False
    finally:
        qgs.exitQgis()


# Years to process for VD calculation
VD_YEARS = [5, 10, 20, 50, 100, 200]


def find_layer_for_year(group, year, raster_only=True):
    """
    Find a layer in the group that matches the given year.
    Matches the NUMBER, not just the string (e.g., year=10 matches _10y but not _100y).
    """
    from qgis.core import QgsRasterLayer, QgsMapLayer
    
    pattern = rf'(?<!\d){year}(?!\d)'  # Negative lookbehind/ahead for digits
    
    for child in group.children():
        if isinstance(child, QgsLayerTreeLayer):
            layer = child.layer()
            if layer and re.search(pattern, layer.name()):
                # Filter for raster layers only if requested
                if raster_only and layer.type() != QgsMapLayer.RasterLayer:
                    continue
                return layer
    return None


def get_or_create_group(parent_group, group_name):
    """Get an existing group or create a new one."""
    existing = parent_group.findGroup(group_name)
    if existing:
        return existing
    return parent_group.addGroup(group_name)


def multiply_rasters_gdal(vel_path: str, depth_path: str, output_path: str, force: bool = False) -> tuple:
    """
    Multiply two rasters using GDAL/numpy (stable, future-proof approach).
    
    Args:
        vel_path: Path to velocity raster
        depth_path: Path to depth raster
        output_path: Path for output raster
        force: If True, overwrite existing files; if False, skip existing
    
    Returns:
        tuple: (success: bool, error_message: str or None, skipped: bool)
    """
    import os
    from osgeo import gdal
    import numpy as np
    
    # Check if output already exists
    if not force and os.path.exists(output_path):
        return True, None, True  # Success, no error, was skipped
    
    # Delete existing file if force mode
    if force and os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception as e:
            return False, f"Could not delete existing file: {e}", False
    
    # Suppress GDAL error messages (we handle errors ourselves)
    gdal.PushErrorHandler('CPLQuietErrorHandler')
    
    try:
        # Open input rasters
        vel_ds = gdal.Open(vel_path, gdal.GA_ReadOnly)
        depth_ds = gdal.Open(depth_path, gdal.GA_ReadOnly)
        
        if vel_ds is None:
            return False, f"Could not open velocity raster: {vel_path}", False
        if depth_ds is None:
            return False, f"Could not open depth raster: {depth_path}", False
        
        # Get raster properties from velocity layer (use as reference)
        cols = vel_ds.RasterXSize
        rows = vel_ds.RasterYSize
        geotransform = vel_ds.GetGeoTransform()
        projection = vel_ds.GetProjection()
        
        # Read bands as numpy arrays (use float64 to avoid overflow)
        vel_band = vel_ds.GetRasterBand(1)
        depth_band = depth_ds.GetRasterBand(1)
        
        vel_nodata = vel_band.GetNoDataValue()
        depth_nodata = depth_band.GetNoDataValue()
        
        vel_data = vel_band.ReadAsArray().astype(np.float64)
        depth_data = depth_band.ReadAsArray().astype(np.float64)
        
        # Handle potential size mismatch by resampling depth to match velocity
        if depth_data.shape != vel_data.shape:
            from osgeo import gdalconst
            
            mem_driver = gdal.GetDriverByName('MEM')
            temp_ds = mem_driver.Create('', cols, rows, 1, gdal.GDT_Float64)
            temp_ds.SetGeoTransform(geotransform)
            temp_ds.SetProjection(projection)
            
            gdal.ReprojectImage(depth_ds, temp_ds, None, None, gdalconst.GRA_Bilinear)
            depth_data = temp_ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
            temp_ds = None
        
        # Create output array with multiplication
        result_data = vel_data * depth_data
        
        # Handle nodata: if either input is nodata, output should be nodata
        output_nodata = -9999.0
        if vel_nodata is not None:
            result_data = np.where(vel_data == vel_nodata, output_nodata, result_data)
        if depth_nodata is not None:
            result_data = np.where(depth_data == depth_nodata, output_nodata, result_data)
        
        # Convert back to float32 for output (clamp extreme values)
        result_data = np.clip(result_data, -3.4e38, 3.4e38).astype(np.float32)
        
        # Create output GeoTIFF
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            output_path,
            cols,
            rows,
            1,
            gdal.GDT_Float32,
            options=['COMPRESS=LZW', 'TILED=YES']
        )
        
        if out_ds is None:
            return False, f"Could not create output raster: {output_path}", False
        
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)
        
        out_band = out_ds.GetRasterBand(1)
        out_band.SetNoDataValue(output_nodata)
        out_band.WriteArray(result_data)
        out_band.FlushCache()
        
        # Cleanup
        vel_ds = None
        depth_ds = None
        out_ds = None
        
        return True, None, False  # Success, no error, not skipped
        
    except Exception as e:
        return False, str(e), False
    
    finally:
        gdal.PopErrorHandler()


# ARR Hazard Classification Thresholds (Table 6.7.4, Smith et al., 2014)
# Format: (class_value, vd_threshold, depth_threshold, velocity_threshold)
# Classification assigns highest class where ANY threshold is exceeded
HAZARD_THRESHOLDS = [
    # (class, max_vd, max_depth, max_velocity) - checked from highest to lowest
    (6, float('inf'), float('inf'), float('inf')),  # H6: VD > 4.0
    (5, 4.0, 4.0, 4.0),                              # H5: VD <= 4.0, D <= 4.0, V <= 4.0
    (4, 1.0, 2.0, 2.0),                              # H4: VD <= 1.0, D <= 2.0, V <= 2.0
    (3, 0.6, 1.2, 2.0),                              # H3: VD <= 0.6, D <= 1.2, V <= 2.0
    (2, 0.6, 0.5, 2.0),                              # H2: VD <= 0.6, D <= 0.5, V <= 2.0
    (1, 0.3, 0.3, 2.0),                              # H1: VD <= 0.3, D <= 0.3, V <= 2.0
]


def classify_hazard_gdal(depth_path: str, vel_path: str, vd_path: str, output_path: str, force: bool = False) -> tuple:
    """
    Classify hazard using Depth, Velocity, and VelocityXDepth rasters (ARR method).
    
    For each cell, assigns the HIGHEST hazard class (H1-H6) where ANY threshold is exceeded.
    
    Args:
        depth_path: Path to depth raster
        vel_path: Path to velocity raster
        vd_path: Path to VelocityXDepth raster
        output_path: Path for output hazard raster
        force: If True, overwrite existing files; if False, skip existing
    
    Returns:
        tuple: (success: bool, error_message: str or None, skipped: bool)
    """
    import os
    from osgeo import gdal
    import numpy as np
    
    # Check if output already exists
    if not force and os.path.exists(output_path):
        return True, None, True  # Success, no error, was skipped
    
    # Delete existing file if force mode
    if force and os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception as e:
            return False, f"Could not delete existing file: {e}", False
    
    # Suppress GDAL error messages
    gdal.PushErrorHandler('CPLQuietErrorHandler')
    
    try:
        # Open input rasters
        depth_ds = gdal.Open(depth_path, gdal.GA_ReadOnly)
        vel_ds = gdal.Open(vel_path, gdal.GA_ReadOnly)
        vd_ds = gdal.Open(vd_path, gdal.GA_ReadOnly)
        
        if depth_ds is None:
            return False, f"Could not open depth raster: {depth_path}", False
        if vel_ds is None:
            return False, f"Could not open velocity raster: {vel_path}", False
        if vd_ds is None:
            return False, f"Could not open VD raster: {vd_path}", False
        
        # Use VD raster as reference for output dimensions
        cols = vd_ds.RasterXSize
        rows = vd_ds.RasterYSize
        geotransform = vd_ds.GetGeoTransform()
        projection = vd_ds.GetProjection()
        
        # Read VD band
        vd_band = vd_ds.GetRasterBand(1)
        vd_nodata = vd_band.GetNoDataValue()
        vd_data = vd_band.ReadAsArray().astype(np.float64)
        
        # Read and resample depth if needed
        depth_band = depth_ds.GetRasterBand(1)
        depth_nodata = depth_band.GetNoDataValue()
        depth_data = depth_band.ReadAsArray().astype(np.float64)
        
        if depth_data.shape != vd_data.shape:
            from osgeo import gdalconst
            mem_driver = gdal.GetDriverByName('MEM')
            temp_ds = mem_driver.Create('', cols, rows, 1, gdal.GDT_Float64)
            temp_ds.SetGeoTransform(geotransform)
            temp_ds.SetProjection(projection)
            gdal.ReprojectImage(depth_ds, temp_ds, None, None, gdalconst.GRA_Bilinear)
            depth_data = temp_ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
            temp_ds = None
        
        # Read and resample velocity if needed
        vel_band = vel_ds.GetRasterBand(1)
        vel_nodata = vel_band.GetNoDataValue()
        vel_data = vel_band.ReadAsArray().astype(np.float64)
        
        if vel_data.shape != vd_data.shape:
            from osgeo import gdalconst
            mem_driver = gdal.GetDriverByName('MEM')
            temp_ds = mem_driver.Create('', cols, rows, 1, gdal.GDT_Float64)
            temp_ds.SetGeoTransform(geotransform)
            temp_ds.SetProjection(projection)
            gdal.ReprojectImage(vel_ds, temp_ds, None, None, gdalconst.GRA_Bilinear)
            vel_data = temp_ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
            temp_ds = None
        
        # Create nodata mask (any input is nodata = output is nodata)
        nodata_mask = np.zeros(vd_data.shape, dtype=bool)
        if vd_nodata is not None:
            nodata_mask |= (vd_data == vd_nodata)
        if depth_nodata is not None:
            nodata_mask |= (depth_data == depth_nodata)
        if vel_nodata is not None:
            nodata_mask |= (vel_data == vel_nodata)
        
        # Initialize result with zeros (no hazard / below H1)
        result_data = np.zeros(vd_data.shape, dtype=np.uint8)
        
        # Classify hazard: assign highest class where ANY threshold is exceeded
        # Work from H1 (lowest) to H6 (highest) so higher classes overwrite
        
        # H1: VD > 0, D > 0.3, or V > 2.0 (any flooding above safe limits)
        h1_mask = (vd_data > 0) | (depth_data > 0.3) | (vel_data > 2.0)
        result_data = np.where(h1_mask & ~nodata_mask, 1, result_data)
        
        # H2: VD > 0.3, or D > 0.5
        h2_mask = (vd_data > 0.3) | (depth_data > 0.5)
        result_data = np.where(h2_mask & ~nodata_mask, 2, result_data)
        
        # H3: VD > 0.6, or D > 1.2
        h3_mask = (vd_data > 0.6) | (depth_data > 1.2)
        result_data = np.where(h3_mask & ~nodata_mask, 3, result_data)
        
        # H4: VD > 1.0, or D > 2.0
        h4_mask = (vd_data > 1.0) | (depth_data > 2.0)
        result_data = np.where(h4_mask & ~nodata_mask, 4, result_data)
        
        # H5: VD > 4.0, or D > 4.0, or V > 4.0
        h5_mask = (vd_data > 4.0) | (depth_data > 4.0) | (vel_data > 4.0)
        result_data = np.where(h5_mask & ~nodata_mask, 5, result_data)
        
        # H6: VD > 4.0 (already captured above, but explicit for clarity)
        # Note: Per ARR, H6 is "D*V > 4.0" with no other limits
        # H5 and H6 share VD > 4.0, but H6 has no depth/velocity limits
        # In practice, if VD > 4.0, it's at least H5; checking D/V determines if it stays H5 or goes H6
        # Since H6 has no limits on D and V individually, any cell with VD > 4.0 is H6
        h6_mask = (vd_data > 4.0)
        result_data = np.where(h6_mask & ~nodata_mask, 6, result_data)
        
        # Set nodata areas to 0 (will be marked as nodata in output)
        output_nodata = 0
        result_data = np.where(nodata_mask, output_nodata, result_data)
        
        # Create output GeoTIFF
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            output_path,
            cols,
            rows,
            1,
            gdal.GDT_Byte,
            options=['COMPRESS=LZW', 'TILED=YES']
        )
        
        if out_ds is None:
            return False, f"Could not create output raster: {output_path}", False
        
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)
        
        out_band = out_ds.GetRasterBand(1)
        out_band.SetNoDataValue(output_nodata)
        out_band.WriteArray(result_data)
        out_band.FlushCache()
        
        # Cleanup
        depth_ds = None
        vel_ds = None
        vd_ds = None
        out_ds = None
        
        return True, None, False  # Success, no error, not skipped
        
    except Exception as e:
        return False, str(e), False
    
    finally:
        gdal.PopErrorHandler()


def cmd_vd(args):
    """Create Velocity x Depth rasters for each area and year using GDAL."""
    # Suppress GDAL error messages BEFORE QGIS initialization
    # (QGIS loads project with potentially malformed layers on startup)
    import os
    from osgeo import gdal
    gdal.SetConfigOption('CPL_LOG', 'NUL' if os.name == 'nt' else '/dev/null')
    gdal.PushErrorHandler('CPLQuietErrorHandler')
    
    # Hard-coded overrides for specific (area, year, layer_type) combinations
    # Format: (area, year, "velocity" or "depth"): "exact_layer_name"
    VD_LAYER_OVERRIDES = {
        ("Concongella_2015", 100, "depth"): "Concongella_100y_d_Max",
        # Add more overrides here as needed
    }
    
    def get_override_layer(project, area, year, layer_type):
        """Get layer by exact name from override rules."""
        key = (area, year, layer_type)
        if key in VD_LAYER_OVERRIDES:
            layer_name = VD_LAYER_OVERRIDES[key]
            layers = project.mapLayersByName(layer_name)
            if layers:
                return layers[0]
        return None
    
    print("Creating Velocity x Depth rasters...")
    
    qgs = init_qgis()
    try:
        from qgis.core import QgsRasterLayer
        
        project = load_project()
        if not project:
            return False
        
        root = project.layerTreeRoot()
        
        # Find the 'Flood maps' group
        flood_maps_group = root.findGroup("Flood maps")
        if not flood_maps_group:
            print("ERROR: 'Flood maps' group not found.")
            return False
        
        # Find Velocity and Depths groups
        velocity_group = flood_maps_group.findGroup("Velocity")
        depths_group = flood_maps_group.findGroup("Depths")
        
        if not velocity_group:
            print("ERROR: 'Velocity' group not found under 'Flood maps'.")
            return False
        if not depths_group:
            print("ERROR: 'Depths' group not found under 'Flood maps'.")
            return False
        
        # Create VelocityXDepth group
        vd_group = get_or_create_group(flood_maps_group, "VelocityXDepth")
        
        # Collect area names from Velocity group (subgroups)
        areas = []
        for child in velocity_group.children():
            if not isinstance(child, QgsLayerTreeLayer):
                areas.append(child.name())
        
        not_found = []
        created_count = 0
        skipped_count = 0
        log_entries = []  # For CSV log: (vd_path, velocity_path, depth_path)
        
        for area in sorted(areas):
            # Find area subgroups in Velocity and Depths
            vel_area_group = velocity_group.findGroup(area)
            depth_area_group = depths_group.findGroup(area)
            
            if not vel_area_group:
                for year in VD_YEARS:
                    not_found.append((area, year, "Velocity area group not found"))
                continue
            
            if not depth_area_group:
                for year in VD_YEARS:
                    not_found.append((area, year, "Depths area group not found"))
                continue
            
            # Create area group under VelocityXDepth
            vd_area_group = get_or_create_group(vd_group, area)
            
            # Create output directory
            output_dir = PROJECT_DIR / "data" / "flood" / area / "VelocityXDepth"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for year in VD_YEARS:
                # Find velocity layer for this year (check overrides first)
                vel_layer = get_override_layer(project, area, year, "velocity")
                if not vel_layer:
                    vel_layer = find_layer_for_year(vel_area_group, year)
                if not vel_layer:
                    not_found.append((area, year, "Velocity layer not found"))
                    continue
                
                # Find depth layer for this year (check overrides first)
                depth_layer = get_override_layer(project, area, year, "depth")
                if not depth_layer:
                    depth_layer = find_layer_for_year(depth_area_group, year)
                if not depth_layer:
                    not_found.append((area, year, "Depths layer not found"))
                    continue
                
                # Output file name and path
                output_name = f"{area}_{year}y_VD"
                output_path = output_dir / f"{output_name}.tif"
                
                # Get source file paths from layers
                vel_source = vel_layer.source()
                depth_source = depth_layer.source()
                
                # If force mode, remove existing layer first to release file lock
                if args.force:
                    existing_layers = project.mapLayersByName(output_name)
                    for existing in existing_layers:
                        project.removeMapLayer(existing.id())
                
                # Multiply rasters using GDAL (stable, future-proof)
                success, error, skipped = multiply_rasters_gdal(vel_source, depth_source, str(output_path), force=args.force)
                
                if not success:
                    not_found.append((area, year, f"Raster calculation failed: {error}"))
                    continue
                
                if skipped:
                    skipped_count += 1
                    # Still need to ensure layer is in project
                
                # Remove existing layer with same name if exists (for non-force mode)
                if not args.force:
                    existing_layers = project.mapLayersByName(output_name)
                    for existing in existing_layers:
                        project.removeMapLayer(existing.id())
                
                # Add the new layer to the project
                new_layer = QgsRasterLayer(str(output_path), output_name)
                if new_layer.isValid():
                    project.addMapLayer(new_layer, False)
                    vd_area_group.addLayer(new_layer)
                    
                    # Build full paths for log
                    vd_path = f"Flood maps/VelocityXDepth/{area}/{output_name}"
                    vel_path = f"Flood maps/Velocity/{area}/{vel_layer.name()}"
                    depth_path = f"Flood maps/Depths/{area}/{depth_layer.name()}"
                    log_entries.append((vd_path, vel_path, depth_path))
                    
                    if not skipped:
                        created_count += 1
                        print(f"  {output_name} = {vel_layer.name()} * {depth_layer.name()}")
                else:
                    not_found.append((area, year, "Failed to load created raster"))
        
        # Write CSV log
        import csv
        log_file = PROJECT_DIR / "scripts" / "vd_log.csv"
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["vd", "velocity", "depth"])
            for entry in log_entries:
                writer.writerow(entry)
        print(f"\nLog written to: {log_file}")
        
        # Print not found cases
        if not_found:
            print("\n" + "=" * 50)
            print("NOT FOUND / ERRORS:")
            print("=" * 50)
            for area, year, reason in not_found:
                print(f"  {area} - {year}y: {reason}")
        
        print("\n" + "=" * 50)
        print(f"Total not found/errors: {len(not_found)}")
        print(f"Total VD layers created: {created_count}")
        print(f"Total VD layers skipped (already exist): {skipped_count}")
        print(f"Total logged entries: {len(log_entries)}")
        print("=" * 50)
        
        if project.write():
            print("Project saved.")
            return True
        else:
            print("ERROR: Failed to save project.")
            return False
    finally:
        qgs.exitQgis()
        gdal.PopErrorHandler()


def cmd_hazard(args):
    """Create Hazard classification rasters (H1-H6) using Depth, Velocity, and VD layers."""
    import os
    import csv
    from osgeo import gdal
    gdal.SetConfigOption('CPL_LOG', 'NUL' if os.name == 'nt' else '/dev/null')
    gdal.PushErrorHandler('CPLQuietErrorHandler')
    
    print("Creating Hazard classification rasters (H1-H6)...")
    print("Using ARR Combined Hazard Curves methodology (Smith et al., 2014)")
    
    qgs = init_qgis()
    try:
        from qgis.core import QgsRasterLayer
        
        project = load_project()
        if not project:
            return False
        
        root = project.layerTreeRoot()
        
        # Find the 'Flood maps' group
        flood_maps_group = root.findGroup("Flood maps")
        if not flood_maps_group:
            print("ERROR: 'Flood maps' group not found.")
            return False
        
        # Read vd_log.csv to get layer mappings
        vd_log_file = PROJECT_DIR / "scripts" / "vd_log.csv"
        if not vd_log_file.exists():
            print(f"ERROR: vd_log.csv not found at {vd_log_file}")
            print("Please run 'manage.py vd' first to create VelocityXDepth layers.")
            return False
        
        vd_mappings = []
        with open(vd_log_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                vd_mappings.append(row)
        
        print(f"Found {len(vd_mappings)} VD layer mappings in vd_log.csv")
        
        # Create Hazard group under Flood maps
        hazard_group = get_or_create_group(flood_maps_group, "Hazard")
        
        not_found = []
        created_count = 0
        skipped_count = 0
        log_entries = []  # For CSV log: (hazard_path, vd_path, depth_path, velocity_path)
        
        for mapping in vd_mappings:
            vd_layer_path = mapping['vd']
            vel_layer_path = mapping['velocity']
            depth_layer_path = mapping['depth']
            
            # Parse area and layer name from VD path
            # Format: "Flood maps/VelocityXDepth/{area}/{area}_{year}y_VD"
            parts = vd_layer_path.split('/')
            if len(parts) < 4:
                not_found.append((vd_layer_path, "Invalid VD path format"))
                continue
            
            area = parts[2]
            vd_layer_name = parts[3]
            
            # Extract year from VD layer name (e.g., "Concongella_2015_5y_VD" -> "5")
            year_match = re.search(r'_(\d+)y_VD$', vd_layer_name)
            if not year_match:
                not_found.append((vd_layer_path, "Could not extract year from VD layer name"))
                continue
            year = year_match.group(1)
            
            # Find the actual layers by name
            vd_layer_name_only = parts[3]
            vel_layer_name = vel_layer_path.split('/')[-1]
            depth_layer_name = depth_layer_path.split('/')[-1]
            
            vd_layers = project.mapLayersByName(vd_layer_name_only)
            vel_layers = project.mapLayersByName(vel_layer_name)
            depth_layers = project.mapLayersByName(depth_layer_name)
            
            if not vd_layers:
                not_found.append((vd_layer_path, "VD layer not found in project"))
                continue
            if not vel_layers:
                not_found.append((vd_layer_path, f"Velocity layer '{vel_layer_name}' not found"))
                continue
            if not depth_layers:
                not_found.append((vd_layer_path, f"Depth layer '{depth_layer_name}' not found"))
                continue
            
            vd_layer = vd_layers[0]
            vel_layer = vel_layers[0]
            depth_layer = depth_layers[0]
            
            # Get source file paths
            vd_source = vd_layer.source()
            vel_source = vel_layer.source()
            depth_source = depth_layer.source()
            
            # Create area group under Hazard
            hazard_area_group = get_or_create_group(hazard_group, area)
            
            # Create output directory
            output_dir = PROJECT_DIR / "data" / "flood" / area / "Hazard"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Output file name and path
            output_name = f"{area}_{year}y_Hazard"
            output_path = output_dir / f"{output_name}.tif"
            
            # If force mode, remove existing layer first to release file lock
            if args.force:
                existing_layers = project.mapLayersByName(output_name)
                for existing in existing_layers:
                    project.removeMapLayer(existing.id())
            
            # Classify hazard using GDAL
            success, error, skipped = classify_hazard_gdal(
                depth_source, vel_source, vd_source, str(output_path), force=args.force
            )
            
            if not success:
                not_found.append((vd_layer_path, f"Hazard classification failed: {error}"))
                continue
            
            if skipped:
                skipped_count += 1
            
            # Remove existing layer with same name if exists (for non-force mode)
            if not args.force:
                existing_layers = project.mapLayersByName(output_name)
                for existing in existing_layers:
                    project.removeMapLayer(existing.id())
            
            # Add the new layer to the project
            new_layer = QgsRasterLayer(str(output_path), output_name)
            if new_layer.isValid():
                project.addMapLayer(new_layer, False)
                hazard_area_group.addLayer(new_layer)
                
                # Build full paths for log
                hazard_path = f"Flood maps/Hazard/{area}/{output_name}"
                log_entries.append((hazard_path, vd_layer_path, depth_layer_path, vel_layer_path))
                
                if not skipped:
                    created_count += 1
                    print(f"  {output_name} <- D:{depth_layer_name}, V:{vel_layer_name}, VD:{vd_layer_name_only}")
            else:
                not_found.append((vd_layer_path, "Failed to load created hazard raster"))
        
        # Write CSV log
        log_file = PROJECT_DIR / "scripts" / "hazard_log.csv"
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["hazard", "vd", "depth", "velocity"])
            for entry in log_entries:
                writer.writerow(entry)
        print(f"\nLog written to: {log_file}")
        
        # Print not found cases
        if not_found:
            print("\n" + "=" * 50)
            print("NOT FOUND / ERRORS:")
            print("=" * 50)
            for item, reason in not_found:
                print(f"  {item}: {reason}")
        
        print("\n" + "=" * 50)
        print(f"Total not found/errors: {len(not_found)}")
        print(f"Total Hazard layers created: {created_count}")
        print(f"Total Hazard layers skipped (already exist): {skipped_count}")
        print(f"Total logged entries: {len(log_entries)}")
        print("=" * 50)
        print("\nHazard Classes (ARR):")
        print("  H1: Generally safe for vehicles, people and buildings")
        print("  H2: Unsafe for small vehicles")
        print("  H3: Unsafe for vehicles, children and the elderly")
        print("  H4: Unsafe for vehicles and people")
        print("  H5: Unsafe for vehicles and people, buildings vulnerable")
        print("  H6: All building types vulnerable to failure")
        
        if project.write():
            print("\nProject saved.")
            return True
        else:
            print("ERROR: Failed to save project.")
            return False
    finally:
        qgs.exitQgis()
        gdal.PopErrorHandler()


def main():
    parser = argparse.ArgumentParser(
        description="QGIS Project Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  manage.py select              Select all layers
  manage.py select "Flood maps" Select a group and all children recursively
  manage.py deselect            Deselect all layers
  manage.py crs         Set CRS to EPSG:7854 for Flood maps layers
  manage.py style_dump  Export styles from source layers to QML files
  manage.py style_load  Load styles from QML files and apply to groups
  manage.py vd          Create Velocity x Depth rasters
  manage.py hazard      Create Hazard classification rasters (H1-H6)
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Select command
    select_parser = subparsers.add_parser("select", help="Select (check) all layers, or a specific group recursively")
    select_parser.add_argument("group", nargs="?", default=None, help="Optional group name to select (selects all if omitted)")
    select_parser.set_defaults(func=cmd_select)
    
    # Deselect command
    deselect_parser = subparsers.add_parser("deselect", help="Deselect (uncheck) all layers")
    deselect_parser.set_defaults(func=cmd_deselect)
    
    # CRS command
    crs_parser = subparsers.add_parser("crs", help="Set CRS to EPSG:7854 for all 'Flood maps' layers")
    crs_parser.set_defaults(func=cmd_crs)
    
    # Style dump command
    style_dump_parser = subparsers.add_parser("style_dump", help="Export styles from source layers to QML files")
    style_dump_parser.set_defaults(func=cmd_style_dump)
    
    # Style load command
    style_load_parser = subparsers.add_parser("style_load", help="Load styles from QML files and apply to groups")
    style_load_parser.set_defaults(func=cmd_style_load)
    
    # VD command
    vd_parser = subparsers.add_parser("vd", help="Create Velocity x Depth rasters for each area and year")
    vd_parser.add_argument("--force", action="store_true", help="Force regeneration of existing VD files")
    vd_parser.set_defaults(func=cmd_vd)
    
    # Hazard command
    hazard_parser = subparsers.add_parser("hazard", help="Create Hazard classification rasters (H1-H6) using ARR method")
    hazard_parser.add_argument("--force", action="store_true", help="Force regeneration of existing Hazard files")
    hazard_parser.set_defaults(func=cmd_hazard)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    success = args.func(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
