"""
Load Style - QGIS Processing Script

Applies property.qml style to selected layer.

Setup:
    Processing Toolbox > Scripts > Add Script to Toolbox > browse to this file
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
)


class LoadStyleAlgorithm(QgsProcessingAlgorithm):
    
    INPUT = 'INPUT'
    QML_PATH = r'C:\Users\m.rahman\qgis\flood_property\scripts\qmls\property.qml'
    
    def tr(self, string):
        return string
    
    def createInstance(self):
        return LoadStyleAlgorithm()
    
    def name(self):
        return 'loadpropertystyle'
    
    def displayName(self):
        return self.tr('Load Property Style')
    
    def group(self):
        return self.tr('Flood Analysis')
    
    def groupId(self):
        return 'floodanalysis'
    
    def shortHelpString(self):
        return self.tr('Applies property.qml style to selected layer.')
    
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                self.tr('Layer to style'),
                [QgsProcessing.TypeVectorPolygon],
                defaultValue='Calculated'
            )
        )
    
    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        
        if layer:
            layer.loadNamedStyle(self.QML_PATH)
            layer.triggerRepaint()
            feedback.pushInfo(f'Style applied to {layer.name()}')
        else:
            feedback.pushInfo('No layer selected')
        
        return {}
