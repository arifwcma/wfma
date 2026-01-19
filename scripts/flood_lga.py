"""
Flood LGA Analysis - QGIS Processing Script

Analyzes flood-affected properties across ALL hazard rasters under "Flood maps\Hazard".
Reports statistics per LGA and total across all LGAs.
"""

from pathlib import Path
from collections import defaultdict

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFeatureSink,
    QgsProcessingException,
    QgsProject,
    QgsRasterLayer,
    QgsField,
    QgsFeature,
    QgsFields,
)
from qgis import processing
from PyQt5.QtCore import QVariant


# DEV MODE: Set to False when ready for full processing
DEV_MODE = False


class FloodLGAAlgorithm(QgsProcessingAlgorithm):
    
    INPUT_PROPERTIES = 'INPUT_PROPERTIES'
    INPUT_LGA = 'INPUT_LGA'
    OUTPUT = 'OUTPUT'
    
    def tr(self, string):
        return string
    
    def createInstance(self):
        return FloodLGAAlgorithm()
    
    def name(self):
        return 'floodlgaanalysis'
    
    def displayName(self):
        return self.tr('Flood LGA Analysis')
    
    def group(self):
        return self.tr('Flood Analysis')
    
    def groupId(self):
        return 'floodanalysis'
    
    def shortHelpString(self):
        return self.tr('Analyzes flood-affected properties across all hazard rasters, with per-LGA statistics.')
    
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_PROPERTIES,
                self.tr('Property Layer'),
                [QgsProcessing.TypeVectorPolygon],
                defaultValue='Properties'
            )
        )
        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_LGA,
                self.tr('LGA Layer'),
                [QgsProcessing.TypeVectorPolygon],
                defaultValue='LGA'
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Flood Affected Properties by LGA')
            )
        )
    
    def get_hazard_rasters(self, feedback):
        """Find all raster layers under 'Flood maps/Hazard' group recursively."""
        rasters = []
        root = QgsProject.instance().layerTreeRoot()
        
        # Find "Flood maps" group
        flood_group = root.findGroup('Flood maps')
        if not flood_group:
            raise QgsProcessingException('Layer group "Flood maps" not found')
        
        # Find "Hazard" subgroup
        hazard_group = flood_group.findGroup('Hazard')
        if not hazard_group:
            raise QgsProcessingException('Layer group "Flood maps/Hazard" not found')
        
        # Recursively collect all raster layers
        def collect_rasters(group):
            for child in group.children():
                if hasattr(child, 'layer'):
                    layer = child.layer()
                    if isinstance(layer, QgsRasterLayer):
                        rasters.append(layer)
                elif hasattr(child, 'children'):
                    collect_rasters(child)
        
        collect_rasters(hazard_group)
        
        if not rasters:
            raise QgsProcessingException('No raster layers found under "Flood maps/Hazard"')
        
        feedback.pushInfo(f'Found {len(rasters)} hazard raster(s)')
        for r in rasters:
            feedback.pushInfo(f'  - {r.name()}')
        
        # DEV MODE: only use first raster
        if DEV_MODE:
            feedback.pushInfo(f'\n*** DEV MODE: Using only first raster: {rasters[0].name()} ***\n')
            return rasters[:1]
        
        return rasters
    
    def processAlgorithm(self, parameters, context, feedback):
        
        property_layer = self.parameterAsVectorLayer(parameters, self.INPUT_PROPERTIES, context)
        lga_layer = self.parameterAsVectorLayer(parameters, self.INPUT_LGA, context)
        
        if not property_layer:
            raise QgsProcessingException('Invalid property layer')
        if not lga_layer:
            raise QgsProcessingException('Invalid LGA layer')
        
        feedback.pushInfo(f'Properties: {property_layer.name()} ({property_layer.featureCount()} features)')
        feedback.pushInfo(f'LGA: {lga_layer.name()} ({lga_layer.featureCount()} features)')
        
        # Get hazard rasters
        hazard_rasters = self.get_hazard_rasters(feedback)
        
        # Use first raster's CRS as reference
        ref_crs = hazard_rasters[0].crs()
        
        # Step 0: Reproject properties to match hazard CRS if needed
        working_properties = property_layer
        if property_layer.crs() != ref_crs:
            feedback.pushInfo(f'\nReprojecting properties from {property_layer.crs().authid()} to {ref_crs.authid()}...')
            
            reprojected = processing.run(
                'native:reprojectlayer',
                {
                    'INPUT': property_layer,
                    'TARGET_CRS': ref_crs,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )['OUTPUT']
            
            working_properties = context.getMapLayer(reprojected)
            if not working_properties:
                from qgis.core import QgsVectorLayer
                working_properties = QgsVectorLayer(reprojected, 'reprojected', 'ogr')
            
            feedback.pushInfo('Reprojection done.')
        
        # Step 1: Build combined hazard extent from all rasters
        feedback.pushInfo('\nBuilding combined hazard polygons...')
        
        all_hazard_polygons = None
        
        for i, raster in enumerate(hazard_rasters):
            feedback.pushInfo(f'  Polygonizing {raster.name()}...')
            
            polygonized = processing.run(
                'gdal:polygonize',
                {
                    'INPUT': raster,
                    'BAND': 1,
                    'FIELD': 'DN',
                    'EIGHT_CONNECTEDNESS': False,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )['OUTPUT']
            
            # Filter out NoData (DN = 0)
            filtered = processing.run(
                'native:extractbyexpression',
                {
                    'INPUT': polygonized,
                    'EXPRESSION': '"DN" > 0',
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )['OUTPUT']
            
            if all_hazard_polygons is None:
                all_hazard_polygons = filtered
            else:
                # Merge with previous
                all_hazard_polygons = processing.run(
                    'native:mergevectorlayers',
                    {
                        'LAYERS': [all_hazard_polygons, filtered],
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    },
                    context=context,
                    feedback=feedback,
                    is_child_algorithm=True
                )['OUTPUT']
        
        feedback.pushInfo('Polygonization done.')
        
        # Step 2: Extract properties that intersect any hazard polygon
        feedback.pushInfo('\nExtracting properties with hazard overlap...')
        
        extracted = processing.run(
            'native:extractbylocation',
            {
                'INPUT': working_properties,
                'PREDICATE': [0],  # intersects
                'INTERSECT': all_hazard_polygons,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        
        feedback.pushInfo('Extraction done.')
        
        # Step 3: Calculate zonal histogram for each raster
        feedback.pushInfo('\nCalculating pixel counts per hazard class...')
        
        current_layer = extracted
        histogram_prefixes = []
        
        for i, raster in enumerate(hazard_rasters):
            prefix = f'r{i}_'
            histogram_prefixes.append(prefix)
            feedback.pushInfo(f'  Zonal histogram for {raster.name()} (prefix: {prefix})...')
            
            result = processing.run(
                'native:zonalhistogram',
                {
                    'INPUT_VECTOR': current_layer,
                    'INPUT_RASTER': raster,
                    'RASTER_BAND': 1,
                    'COLUMN_PREFIX': prefix,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )['OUTPUT']
            
            current_layer = result
        
        feedback.pushInfo('Zonal histogram done.')
        
        # Step 4: Sum pixel counts across rasters and determine max class
        feedback.pushInfo('\nAggregating pixel counts and determining hazard class...')
        
        # Build expression to sum counts for each class (1-6) across all rasters
        # Then find the class with max count
        class_sum_expressions = []
        for hazard_class in range(1, 7):  # H1-H6
            parts = []
            for prefix in histogram_prefixes:
                field_name = f'{prefix}{hazard_class}'
                parts.append(f'coalesce("{field_name}", 0)')
            class_sum_expressions.append(f'({" + ".join(parts)})')
        
        # Expression: array of sums [sum_h1, sum_h2, ..., sum_h6]
        # Find index of max value, add 1 to get class number
        array_expr = f'array({", ".join(class_sum_expressions)})'
        max_class_expr = f'array_find({array_expr}, array_max({array_expr})) + 1'
        
        with_max = processing.run(
            'native:fieldcalculator',
            {
                'INPUT': current_layer,
                'FIELD_NAME': 'hazard_max',
                'FIELD_TYPE': 1,  # Integer
                'FIELD_LENGTH': 10,
                'FORMULA': max_class_expr,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        
        # Add hazard label (H1, H2, etc.)
        with_label = processing.run(
            'native:fieldcalculator',
            {
                'INPUT': with_max,
                'FIELD_NAME': 'hazard',
                'FIELD_TYPE': 2,  # String
                'FIELD_LENGTH': 10,
                'FORMULA': "'H' || to_string(\"hazard_max\")",
                'OUTPUT': 'TEMPORARY_OUTPUT'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        
        feedback.pushInfo('Aggregation done.')
        
        # Step 5: Spatial join with LGA to assign LGA name
        feedback.pushInfo('\nJoining with LGA layer...')
        
        # Get LGA name field (first string field or 'LGA_NAME' or 'name')
        lga_name_field = None
        for field in lga_layer.fields():
            if field.name().upper() in ['LGA_NAME', 'NAME', 'LGA']:
                lga_name_field = field.name()
                break
        if not lga_name_field:
            # Use first string field
            for field in lga_layer.fields():
                if field.type() == QVariant.String:
                    lga_name_field = field.name()
                    break
        if not lga_name_field:
            lga_name_field = lga_layer.fields()[0].name()
        
        feedback.pushInfo(f'  Using LGA field: {lga_name_field}')
        
        joined = processing.run(
            'native:joinattributesbylocation',
            {
                'INPUT': with_label,
                'JOIN': lga_layer,
                'PREDICATE': [0],  # intersects
                'JOIN_FIELDS': [lga_name_field],
                'METHOD': 0,  # one-to-one (first match)
                'PREFIX': 'lga_',
                'OUTPUT': parameters[self.OUTPUT]
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        
        feedback.pushInfo('Join done.')
        
        # Step 6: Calculate and log statistics
        self.log_statistics(context, joined['OUTPUT'], lga_name_field, feedback)
        
        return {self.OUTPUT: joined['OUTPUT']}
    
    def log_statistics(self, context, output_id, lga_name_field, feedback):
        """Log area statistics per LGA and totals."""
        
        output_layer = context.getMapLayer(output_id)
        if not output_layer:
            from qgis.core import QgsVectorLayer
            output_layer = QgsVectorLayer(output_id, 'temp', 'ogr')
        
        lga_field = f'lga_{lga_name_field}'
        
        # Collect stats: {lga: {hazard_class: {'count': n, 'area': a}}}
        stats = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'area': 0.0}))
        
        for feature in output_layer.getFeatures():
            lga = feature[lga_field] or 'Unknown'
            hazard = feature['hazard'] or 'Unknown'
            area = feature.geometry().area()
            
            stats[lga][hazard]['count'] += 1
            stats[lga][hazard]['area'] += area
        
        feedback.pushInfo('\n' + '=' * 50)
        feedback.pushInfo('FLOOD ANALYSIS STATISTICS')
        feedback.pushInfo('=' * 50)
        
        # (a) & (b) Per-LGA breakdown
        all_classes = defaultdict(lambda: {'count': 0, 'area': 0.0})
        grand_total_count = 0
        grand_total_area = 0.0
        
        for lga in sorted(stats.keys()):
            feedback.pushInfo(f'\n--- LGA: {lga} ---')
            
            lga_total_count = 0
            lga_total_area = 0.0
            
            for hazard_class in sorted(stats[lga].keys()):
                data = stats[lga][hazard_class]
                count = data['count']
                area_ha = data['area'] / 10000
                
                feedback.pushInfo(f'{hazard_class}: {count} properties, {area_ha:,.2f} ha')
                
                lga_total_count += count
                lga_total_area += data['area']
                
                # Accumulate for all-LGA totals
                all_classes[hazard_class]['count'] += count
                all_classes[hazard_class]['area'] += data['area']
            
            feedback.pushInfo(f'Subtotal: {lga_total_count} properties, {lga_total_area / 10000:,.2f} ha')
            
            grand_total_count += lga_total_count
            grand_total_area += lga_total_area
        
        # (c) & (d) All LGAs summary
        feedback.pushInfo('\n' + '=' * 50)
        feedback.pushInfo('ALL LGAs SUMMARY')
        feedback.pushInfo('=' * 50)
        
        for hazard_class in sorted(all_classes.keys()):
            data = all_classes[hazard_class]
            feedback.pushInfo(f'{hazard_class}: {data["count"]} properties, {data["area"] / 10000:,.2f} ha')
        
        feedback.pushInfo(f'\nGrand Total: {grand_total_count} properties, {grand_total_area / 10000:,.2f} ha')
        feedback.pushInfo('=' * 50)
    
    def postProcessAlgorithm(self, context, feedback):
        # Get QML path relative to project
        project_path = Path(QgsProject.instance().fileName()).parent
        qml_path = project_path / 'scripts' / 'qmls' / 'property.qml'
        
        # Apply style
        for layer_id in context.layersToLoadOnCompletion():
            layer = context.getMapLayer(layer_id)
            if layer and qml_path.exists():
                layer.loadNamedStyle(str(qml_path))
                layer.triggerRepaint()
                feedback.pushInfo(f'Style applied: {qml_path}')
                break
        return {}
