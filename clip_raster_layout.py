# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ClipRasterLayout
                                 A QGIS plugin
 Plugin per clipping raster, profili DEM e layout professionale
                              -------------------
        begin                : 2025-01-08
        copyright            : (C) 2025 by Enzo
        email                : enzo@example.com
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QPointF
from qgis.PyQt.QtGui import QIcon, QAction, QPainter, QPen, QFont, QColor
from qgis.PyQt.QtWidgets import QAction, QToolBar, QMenu
from qgis.core import * #(QgsProject, QgsRasterLayer, QgsVectorLayer,
                       #QgsPointXY, QgsGeometry, QgsFeature, QgsVectorFileWriter,
                       #QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       #QgsWkbTypes, QgsFields, QgsField, QgsRectangle,
                       #QgsLayoutItemMap, QgsLayoutItemLabel, QgsLayoutItemScaleBar,
                       #QgsLayoutItemPicture, QgsLayoutItemLegend, QgsLayout,
                       #QgsLayoutExporter, QgsPrintLayout, QgsLayoutPoint,
                       #QgsLayoutSize, QgsUnitTypes, QgsLayoutItemPolyline,
                       #QgsLayoutItemShape, QgsTextFormat, QgsMarkerSymbol,
                       #QgsLineSymbol, QgsFillSymbol, QgsSimpleLineSymbolLayer,
                       #QgsArrowSymbolLayer, QgsRasterBandStats)
from qgis.gui import * #rBand, QgsMapTool
import os.path
import processing
from .resources import *
from .clip_raster_dialog import ClipRasterDialog
from .profile_tool import ProfileTool
from .layout_generator import LayoutGenerator

class ClipRasterLayout:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ClipRasterLayout_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&Clip Raster Layout')
        self.toolbar = self.iface.addToolBar(u'ClipRasterLayout')
        self.toolbar.setObjectName(u'ClipRasterLayout')
        
        self.profile_tool = None
        self.dlg = None
        self.layout_generator = None
        self.generated_profiles = []  # Store generated profiles

    def tr(self, message):
        return QCoreApplication.translate('ClipRasterLayout', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToRasterMenu(
                self.menu,
                action)

        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = ':/plugins/clip_raster_layout/icon.png'
        
        self.add_action(
            icon_path,
            text=self.tr(u'Clip Raster in Batch'),
            callback=self.run_clip_raster,
            parent=self.iface.mainWindow())
            
        self.add_action(
            icon_path,
            text=self.tr(u'Crea Profilo DEM'),
            callback=self.run_profile_tool,
            parent=self.iface.mainWindow())
            
        self.add_action(
            icon_path,
            text=self.tr(u'Genera Layout Professionale'),
            callback=self.run_layout_generator,
            parent=self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginRasterMenu(
                self.tr(u'&Clip Raster Layout'),
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run_clip_raster(self):
        if not self.dlg:
            self.dlg = ClipRasterDialog(self.iface)
        self.dlg.show()
        
    def run_profile_tool(self):
        if self.profile_tool is None:
            self.profile_tool = ProfileTool(self.iface)
        self.profile_tool.activate()
        
    def run_layout_generator(self):
        if not self.layout_generator:
            self.layout_generator = LayoutGenerator(self.iface)
        self.layout_generator.show()