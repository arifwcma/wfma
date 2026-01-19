"""
Extract Test - Simple extraction between Properties and Hazard
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProject,
)
from qgis import processing


class ExtractTestAlgorithm(QgsProcessingAlgorithm):
    
    OUTPUT = 'OUTPUT'
    
    def tr(self, string):
        return string
    
    def createInstance(self):
        return ExtractTestAlgorithm()
    
    def name(self):
        return 'extracttest'
    
    def displayName(self):
        return self.tr('Extract Test')
    
    def group(self):
        return self.tr('Flood Analysis')
    
    def groupId(self):
        return 'floodanalysis'
    
    def shortHelpString(self):
        return self.tr('Test extraction between Properties and Hazard.')
    
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Extracted Properties')
            )
        )
    
    def processAlgorithm(self, parameters, context, feedback):
        
        # Get layers by name
        props = QgsProject.instance().mapLayersByName('Properties')
        hazard = QgsProject.instance().mapLayersByName('Concongella_2015_5y_Hazard')
        
        if not props:
            feedback.pushInfo('ERROR: Properties layer not found')
            return {}
        if not hazard:
            feedback.pushInfo('ERROR: Concongella_2015_5y_Hazard layer not found')
            return {}
        
        property_layer = props[0]
        hazard_layer = hazard[0]
        
        feedback.pushInfo(f'Properties: {property_layer.name()} ({property_layer.featureCount()} features)')
        feedback.pushInfo(f'Properties CRS: {property_layer.crs().authid()}')
        feedback.pushInfo(f'Hazard: {hazard_layer.name()}')
        feedback.pushInfo(f'Hazard CRS: {hazard_layer.crs().authid()}')
        
        # Polygonize hazard raster
        feedback.pushInfo('\nPolygonizing hazard...')
        
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
        
        feedback.pushInfo('Done.')
        
        # Filter NoData
        feedback.pushInfo('\nFiltering DN > 0...')
        
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
        
        feedback.pushInfo('Done.')
        
        # Reproject properties to hazard CRS
        feedback.pushInfo(f'\nReprojecting properties to {hazard_layer.crs().authid()}...')
        
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
        
        feedback.pushInfo('Done.')
        
        # Extract by location
        feedback.pushInfo('\nExtracting by location...')
        
        result = processing.run(
            'native:extractbylocation',
            {
                'INPUT': reprojected,
                'PREDICATE': [0],  # intersects
                'INTERSECT': filtered,
                'OUTPUT': parameters[self.OUTPUT]
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        
        feedback.pushInfo('Done.')
        
        return {self.OUTPUT: result['OUTPUT']}
