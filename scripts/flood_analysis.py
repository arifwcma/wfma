"""
Flood Affected Properties Analysis - QGIS Processing Script

Extracts properties that overlap with hazard raster.
One input property = one output property (if overlap exists).
"""

from pathlib import Path

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFeatureSink,
    QgsProcessingException,
    QgsProject,
)
from qgis import processing


class FloodAnalysisAlgorithm(QgsProcessingAlgorithm):
    
    INPUT_PROPERTIES = 'INPUT_PROPERTIES'
    INPUT_HAZARD = 'INPUT_HAZARD'
    OUTPUT = 'OUTPUT'
    
    def tr(self, string):
        return string
    
    def createInstance(self):
        return FloodAnalysisAlgorithm()
    
    def name(self):
        return 'floodaffectedproperties'
    
    def displayName(self):
        return self.tr('Flood Affected Properties Analysis')
    
    def group(self):
        return self.tr('Flood Analysis')
    
    def groupId(self):
        return 'floodanalysis'
    
    def shortHelpString(self):
        return self.tr('Extracts properties that overlap with hazard raster.')
    
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
            QgsProcessingParameterRasterLayer(
                self.INPUT_HAZARD,
                self.tr('Hazard Raster Layer'),
                defaultValue='Concongella_2015_5y_Hazard'
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Flood Affected Properties')
            )
        )
    
    def processAlgorithm(self, parameters, context, feedback):
        
        property_layer = self.parameterAsVectorLayer(parameters, self.INPUT_PROPERTIES, context)
        hazard_layer = self.parameterAsRasterLayer(parameters, self.INPUT_HAZARD, context)
        
        if not property_layer:
            raise QgsProcessingException('Invalid property layer')
        if not hazard_layer:
            raise QgsProcessingException('Invalid hazard layer')
        
        feedback.pushInfo(f'Properties: {property_layer.name()} ({property_layer.featureCount()} features)')
        feedback.pushInfo(f'Hazard: {hazard_layer.name()}')
        
        # Step 0: Reproject properties to match hazard CRS if needed
        if property_layer.crs() != hazard_layer.crs():
            feedback.pushInfo(f'\nReprojecting properties from {property_layer.crs().authid()} to {hazard_layer.crs().authid()}...')
            
            reprojected = processing.run(
                'native:reprojectlayer',
                {
                    'INPUT': property_layer,
                    'TARGET_CRS': hazard_layer.crs(),
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )['OUTPUT']
            
            property_layer = context.getMapLayer(reprojected)
            if not property_layer:
                from qgis.core import QgsVectorLayer
                property_layer = QgsVectorLayer(reprojected, 'reprojected', 'ogr')
            
            feedback.pushInfo('Reprojection done.')
        
        # Step 1: Polygonize hazard raster
        feedback.pushInfo('\nPolygonizing hazard raster...')
        
        polygonized = processing.run(
            'gdal:polygonize',
            {
                'INPUT': hazard_layer,
                'BAND': 1,
                'FIELD': 'DN',
                'EIGHT_CONNECTEDNESS': False,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        
        feedback.pushInfo('Polygonization done.')
        
        # Step 2: Filter out NoData (DN = 0)
        feedback.pushInfo('\nFiltering NoData...')
        
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
        
        feedback.pushInfo('Filtering done.')
        
        # Step 3: Extract properties that intersect hazard polygons
        feedback.pushInfo('\nExtracting properties with overlap...')
        
        extracted = processing.run(
            'native:extractbylocation',
            {
                'INPUT': property_layer,
                'PREDICATE': [0],  # intersects
                'INTERSECT': filtered,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        
        feedback.pushInfo('Extraction done.')
        
        # Step 4: Get MAX hazard class for each property from raster
        feedback.pushInfo('\nCalculating MAX hazard per property...')
        
        with_stats = processing.run(
            'native:zonalstatisticsfb',
            {
                'INPUT': extracted,
                'INPUT_RASTER': hazard_layer,
                'RASTER_BAND': 1,
                'COLUMN_PREFIX': 'hazard_',
                'STATISTICS': [6],  # 6 = max
                'OUTPUT': 'TEMPORARY_OUTPUT'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        
        feedback.pushInfo('Zonal stats done.')
        
        # Step 5: Add hazard label (H1, H2, etc.)
        feedback.pushInfo('\nAdding hazard labels...')
        
        result = processing.run(
            'native:fieldcalculator',
            {
                'INPUT': with_stats,
                'FIELD_NAME': 'hazard',
                'FIELD_TYPE': 2,  # String
                'FIELD_LENGTH': 10,
                'FORMULA': "'H' || to_string(to_int(\"hazard_max\"))",
                'OUTPUT': parameters[self.OUTPUT]
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        
        feedback.pushInfo('Done.')
        
        # Calculate and log area statistics
        feedback.pushInfo('\n--- Area Statistics ---')
        
        output_layer = context.getMapLayer(result['OUTPUT'])
        if not output_layer:
            from qgis.core import QgsVectorLayer
            output_layer = QgsVectorLayer(result['OUTPUT'], 'temp', 'ogr')
        
        area_by_class = {}
        count_by_class = {}
        total_area = 0.0
        
        for feature in output_layer.getFeatures():
            hazard = feature['hazard']
            area = feature.geometry().area()  # square meters (projected CRS)
            
            if hazard not in area_by_class:
                area_by_class[hazard] = 0.0
                count_by_class[hazard] = 0
            area_by_class[hazard] += area
            count_by_class[hazard] += 1
            total_area += area
        
        for hazard_class in sorted(area_by_class.keys()):
            area_ha = area_by_class[hazard_class] / 10000  # hectares
            count = count_by_class[hazard_class]
            feedback.pushInfo(f'{hazard_class}: {count} properties, {area_ha:,.2f} ha')
        
        total_count = sum(count_by_class.values())
        feedback.pushInfo(f'\nTotal: {total_count} properties, {total_area / 10000:,.2f} ha')
        feedback.pushInfo('--- End Statistics ---')
        
        return {self.OUTPUT: result['OUTPUT']}
    
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
