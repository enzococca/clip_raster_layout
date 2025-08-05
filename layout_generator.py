# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import Qt, QRectF, QPointF, QSizeF, QDateTime
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtGui import QFont, QColor, QPainter
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QComboBox, QPushButton, QCheckBox, QLineEdit,
                               QGroupBox, QFormLayout, QSpinBox, QMessageBox,
                               QTextEdit, QFileDialog, QDockWidget)
from qgis.core import (QgsProject, QgsLayout, QgsPrintLayout, QgsLayoutItemMap,
                      QgsLayoutItemLabel, QgsLayoutItemScaleBar, QgsLayoutItemPicture,
                      QgsLayoutItemLegend, QgsLayoutPoint, QgsLayoutSize,
                      QgsUnitTypes, QgsLayoutExporter, QgsLayoutItemShape,
                      QgsLayoutItemPolyline, QgsTextFormat, QgsVectorLayer,
                      QgsRasterLayer, QgsLayoutMeasurement, QgsLayoutItemPage,
                      QgsLayoutItemPicture, QgsLayoutNorthArrowHandler,
                      QgsLayoutItemAttributeTable, QgsLayoutTableColumn,
                      QgsLayoutFrame, QgsLayoutMultiFrame, QgsRectangle,
                      QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                      QgsLayoutRenderContext, QgsLayoutItem, QgsLayoutItemMapOverview,
                      QgsLayoutItemHtml, QgsSymbol, QgsScaleBarSettings, QgsMessageLog, Qgis,
                      QgsWkbTypes)

# Try to import elevation profile (QGIS 3.26+)
try:
    from qgis.core import QgsLayoutItemElevationProfile, QgsProfileRequest, QgsElevationProfileLayerSettings
    HAS_ELEVATION_PROFILE = True
except ImportError:
    HAS_ELEVATION_PROFILE = False
import os
from datetime import datetime

class LayoutGenerator(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setupUi()
        self.populate_layers()
        self.profile_path = None
        
    def setupUi(self):
        self.setWindowTitle("Genera Layout Professionale")
        self.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        
        # Raster selection
        raster_group = QGroupBox("Selezione Raster")
        raster_layout = QFormLayout()
        
        self.raster_combo = QComboBox()
        raster_layout.addRow("Raster principale:", self.raster_combo)
        
        self.use_clipped = QCheckBox("Usa raster clippato")
        self.use_clipped.setChecked(True)
        raster_layout.addRow(self.use_clipped)
        
        raster_group.setLayout(raster_layout)
        layout.addWidget(raster_group)
        
        # Profile selection
        profile_group = QGroupBox("Profilo")
        profile_layout = QFormLayout()
        
        self.profile_combo = QComboBox()
        profile_layout.addRow("Profilo da includere:", self.profile_combo)
        
        self.include_profile = QCheckBox("Includi profilo nel layout")
        self.include_profile.setChecked(True)
        profile_layout.addRow(self.include_profile)
        
        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)
        
        # Layout settings
        settings_group = QGroupBox("Impostazioni Layout")
        settings_layout = QFormLayout()
        
        self.title_edit = QLineEdit("Analisi Topografica")
        settings_layout.addRow("Titolo:", self.title_edit)
        
        self.author_edit = QLineEdit()
        settings_layout.addRow("Autore:", self.author_edit)
        
        self.scale_combo = QComboBox()
        scales = ["1:1", "1:10", "1:20", "1:50", "1:100", "1:200", "1:500", 
                  "1:1000", "1:2000", "1:5000", "1:10000", "1:25000", "1:50000", 
                  "1:100000", "1:250000", "1:500000"]
        self.scale_combo.addItems(scales)
        self.scale_combo.setEditable(True)  # Allow custom scales
        self.scale_combo.setCurrentIndex(7)  # Default 1:1000
        settings_layout.addRow("Scala:", self.scale_combo)
        
        self.paper_combo = QComboBox()
        self.paper_combo.addItems(["A4 Orizzontale", "A3 Orizzontale", "A2 Orizzontale", "A1 Orizzontale"])
        self.paper_combo.setCurrentIndex(1)  # Default A3
        settings_layout.addRow("Formato carta:", self.paper_combo)
        
        self.logo_path = QLineEdit()
        logo_button = QPushButton("Sfoglia...")
        logo_button.clicked.connect(self.select_logo)
        logo_layout = QHBoxLayout()
        logo_layout.addWidget(self.logo_path)
        logo_layout.addWidget(logo_button)
        settings_layout.addRow("Logo:", logo_layout)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        settings_layout.addRow("Note:", self.notes_edit)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Components to include
        components_group = QGroupBox("Componenti da includere")
        components_layout = QVBoxLayout()
        
        self.include_north = QCheckBox("Freccia del Nord")
        self.include_north.setChecked(True)
        components_layout.addWidget(self.include_north)
        
        self.include_scale = QCheckBox("Barra di scala")
        self.include_scale.setChecked(True)
        components_layout.addWidget(self.include_scale)
        
        self.include_legend = QCheckBox("Legenda")
        self.include_legend.setChecked(True)
        components_layout.addWidget(self.include_legend)
        
        self.include_overview = QCheckBox("Mappa di inquadramento")
        self.include_overview.setChecked(True)
        components_layout.addWidget(self.include_overview)
        
        self.include_grid = QCheckBox("Griglia coordinate")
        self.include_grid.setChecked(True)
        components_layout.addWidget(self.include_grid)
        
        self.include_metadata = QCheckBox("Tabella metadati")
        self.include_metadata.setChecked(True)
        components_layout.addWidget(self.include_metadata)
        
        components_group.setLayout(components_layout)
        layout.addWidget(components_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.generate_button = QPushButton("Genera Layout")
        self.generate_button.clicked.connect(self.generate_layout)
        button_layout.addWidget(self.generate_button)
        
        self.export_button = QPushButton("Esporta PDF")
        self.export_button.clicked.connect(self.export_pdf)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)
        
        self.close_button = QPushButton("Chiudi")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        # Template selection
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))
        self.template_checkbox = QCheckBox("Usa template_layout.qpt")
        self.template_checkbox.setChecked(True)
        template_layout.addWidget(self.template_checkbox)
        layout.addLayout(template_layout)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self.current_layout = None
        
    def showEvent(self, event):
        super().showEvent(event)
        self.populate_layers()
        
    def populate_layers(self):
        self.raster_combo.clear()
        self.profile_combo.clear()
        
        # Populate raster layers
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                self.raster_combo.addItem(layer.name(), layer)
                
        # Add profile options
        self.profile_combo.addItem("Nessuno", None)
        
        # Check for profile layer
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Profili DEM" and isinstance(layer, QgsVectorLayer):
                # Add each profile feature
                for feature in layer.getFeatures():
                    profile_name = feature['name']
                    if profile_name:
                        self.profile_combo.addItem(profile_name, feature)
        
    def select_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleziona Logo", "", "Immagini (*.png *.jpg *.jpeg *.svg)")
        if file_path:
            self.logo_path.setText(file_path)
            
    def generate_layout(self):
        raster_layer = self.raster_combo.currentData()
        if not raster_layer:
            QMessageBox.warning(self, "Attenzione", "Seleziona un raster")
            return
            
        # Create layout
        project = QgsProject.instance()
        layout_name = f"Layout_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Check if we should use template
        if self.template_checkbox.isChecked():
            # Load template
            template_path = os.path.join(os.path.dirname(__file__), "template_layout.qpt")
            if os.path.exists(template_path):
                layout = self.load_template_layout(template_path, layout_name)
                if layout:
                    # Layout is already in the manager from load_template_layout
                    self.current_layout = layout
                    
                    # Populate it with data
                    self.populate_template_layout(layout, raster_layer)
                    
                    self.export_button.setEnabled(True)
                    
                    # Open layout designer
                    self.iface.openLayoutDesigner(layout)
                    
                    QMessageBox.information(self, "Successo", "Layout generato con successo dal template!")
                    return
                else:
                    QgsMessageLog.logMessage("Failed to load template, creating new layout", "ClipRasterLayout", Qgis.Warning)
        
        # Create new layout if template not used or failed
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName(layout_name)
        
        # Set page size based on selection
        page = layout.pageCollection().page(0)
        paper_sizes = {
            "A4 Orizzontale": (297, 210),
            "A3 Orizzontale": (420, 297),
            "A2 Orizzontale": (594, 420),
            "A1 Orizzontale": (841, 594)
        }
        
        size = paper_sizes[self.paper_combo.currentText()]
        page.setPageSize(QgsLayoutSize(size[0], size[1], QgsUnitTypes.LayoutMillimeters))
        
        # Main map - using template coordinates for A3
        map_item = QgsLayoutItemMap(layout)
        if self.paper_combo.currentText() == "A3 Orizzontale":
            map_item.setRect(2.15, 14.18, 292.59, 146.92)
        else:
            # Scale proportionally for other sizes
            map_item.setRect(20, 40, size[0] * 0.7, size[1] * 0.65)
        
        # Calculate extent based on raster and profiles
        extent = raster_layer.extent()
        
        # Check if we need to include profile lines
        profile_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Profili DEM":
                profile_layer = layer
                # Expand extent to include all profiles
                profile_extent = layer.extent()
                if not profile_extent.isEmpty():
                    extent.combineExtentWith(profile_extent)
                break
        
        # Add 10% buffer
        extent = extent.buffered(extent.width() * 0.1)
        map_item.setExtent(extent)
        
        # Set scale
        scale_text = self.scale_combo.currentText()
        scale_value = int(scale_text.split(':')[1])
        map_item.setScale(scale_value)
        
        # Add grid if requested
        if self.include_grid.isChecked():
            map_item.grid().setEnabled(True)
            map_item.grid().setIntervalX(extent.width() / 10)
            map_item.grid().setIntervalY(extent.height() / 10)
            map_item.grid().setGridLineWidth(0.1)
            map_item.grid().setGridLineColor(QColor(100, 100, 100, 100))
            
        # Add frame to map
        map_item.setFrameEnabled(True)
        map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
            
        layout.addLayoutItem(map_item)
        
        # Title - centered at top
        title = QgsLayoutItemLabel(layout)
        title.setText(self.title_edit.text())
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setHAlign(Qt.AlignHCenter)
        title.attemptMove(QgsLayoutPoint(size[0]/2 - 50, 4, QgsUnitTypes.LayoutMillimeters))
        title.attemptResize(QgsLayoutSize(100, 18, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(title)
        
        # North arrow
        if self.include_north.isChecked():
            north = QgsLayoutItemPicture(layout)
            north.setMode(QgsLayoutItemPicture.FormatSVG)
            north.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
            north.setReferencePoint(QgsLayoutItem.UpperRight)
            north.attemptMove(QgsLayoutPoint(12.7, 18.9, QgsUnitTypes.LayoutMillimeters))
            north.attemptResize(QgsLayoutSize(8.7, 11.6, QgsUnitTypes.LayoutMillimeters))
            north.setFrameEnabled(True)
            north.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(north)
            
        # Scale bar
        if self.include_scale.isChecked():
            scalebar = QgsLayoutItemScaleBar(layout)
            scalebar.setLinkedMap(map_item)
            scalebar.setUnits(QgsUnitTypes.DistanceMeters)
            scalebar.setNumberOfSegments(4)
            scalebar.setNumberOfSegmentsLeft(0)
            
            # Calculate appropriate segment size based on scale
            # For scales, we want nice round numbers
            if scale_value <= 100:
                units_per_segment = 10
            elif scale_value <= 500:
                units_per_segment = 50
            elif scale_value <= 1000:
                units_per_segment = 100
            elif scale_value <= 2000:
                units_per_segment = 200
            elif scale_value <= 5000:
                units_per_segment = 500
            elif scale_value <= 10000:
                units_per_segment = 1000
            elif scale_value <= 25000:
                units_per_segment = 2500
            elif scale_value <= 50000:
                units_per_segment = 5000
            elif scale_value <= 100000:
                units_per_segment = 10000
            else:
                units_per_segment = 25000
                
            scalebar.setUnitsPerSegment(units_per_segment)
            scalebar.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFixed)
            scalebar.setMinimumBarWidth(50)
            scalebar.setMaximumBarWidth(150)
            
            # Set style
            scalebar.setStyle('Single Box')
            scalebar.setFont(QFont("Arial", 10))
            scalebar.setHeight(3)
            
            if self.paper_combo.currentText() == "A3 Orizzontale":
                scalebar.attemptMove(QgsLayoutPoint(88.96, 150.16, QgsUnitTypes.LayoutMillimeters))
            else:
                scalebar.attemptMove(QgsLayoutPoint(20, size[1] - 40, QgsUnitTypes.LayoutMillimeters))
                
            scalebar.setFrameEnabled(True)
            scalebar.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(scalebar)
            
        # Legend
        if self.include_legend.isChecked():
            legend = QgsLayoutItemLegend(layout)
            legend.setLinkedMap(map_item)
            legend.setTitle("Legenda")
            
            # Only show layers that are in the map
            legend.setAutoUpdateModel(False)
            
            # Remove all existing layers from legend
            root = legend.model().rootGroup()
            root.removeAllChildren()
            
            # Add only the selected raster layer
            if raster_layer:
                root.addLayer(raster_layer)
                
            # Add profile layer if it exists
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Profili DEM":
                    root.addLayer(layer)
                    break
                    
            if self.paper_combo.currentText() == "A3 Orizzontale":
                legend.attemptMove(QgsLayoutPoint(209.9, 70, QgsUnitTypes.LayoutMillimeters))
                legend.attemptResize(QgsLayoutSize(80, 30, QgsUnitTypes.LayoutMillimeters))
            else:
                legend.attemptMove(QgsLayoutPoint(size[0] * 0.75, 70, QgsUnitTypes.LayoutMillimeters))
                legend.attemptResize(QgsLayoutSize(size[0] * 0.2, 40, QgsUnitTypes.LayoutMillimeters))
            legend.setFrameEnabled(True)
            legend.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(legend)
            
        # Overview map
        if self.include_overview.isChecked():
            overview = QgsLayoutItemMap(layout)
            if self.paper_combo.currentText() == "A3 Orizzontale":
                overview.setRect(246.39, 19.15, 44.55, 46.44)
            else:
                overview.setRect(size[0] * 0.75, 20, size[0] * 0.2, size[1] * 0.25)
            
            # Set larger extent for overview
            overview_extent = extent.buffered(extent.width() * 0.5)
            overview.setExtent(overview_extent)
            
            # Add frame
            overview.setFrameEnabled(True)
            overview.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
            
            # Add overview indicator
            overview_item = QgsLayoutItemMapOverview('overview', overview)
            overview_item.setLinkedMap(map_item)
            overview.overviews().addOverview(overview_item)
            layout.addLayoutItem(overview)
            
        # Profile graph
        if self.include_profile.isChecked() and self.profile_combo.currentData():
            # Check if native elevation profile is available
            if HAS_ELEVATION_PROFILE:
                try:
                    self.add_native_elevation_profile(layout, size)
                    QgsMessageLog.logMessage("Using native QGIS elevation profile", "ClipRasterLayout", Qgis.Info)
                except Exception as e:
                    QgsMessageLog.logMessage(f"Native profile failed: {e}, using custom matplotlib method", "ClipRasterLayout", Qgis.Warning)
                    self.add_profile_graph(layout, size)
            else:
                # Use custom method for older QGIS versions
                QgsMessageLog.logMessage("QGIS elevation profile not available, using custom matplotlib method", "ClipRasterLayout", Qgis.Info)
                self.add_profile_graph(layout, size)
            
        # Metadata table
        if self.include_metadata.isChecked():
            self.add_metadata_table(layout, raster_layer, size)
            
        # Logo
        if self.logo_path.text():
            logo = QgsLayoutItemPicture(layout)
            logo.setPicturePath(self.logo_path.text())
            logo.setReferencePoint(QgsLayoutItem.UpperRight)
            logo.attemptMove(QgsLayoutPoint(size[0] - 50, size[1] - 40, QgsUnitTypes.LayoutMillimeters))
            logo.attemptResize(QgsLayoutSize(40, 30, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(logo)
            
        # Add layout to project
        project.layoutManager().addLayout(layout)
        
        self.current_layout = layout
        self.export_button.setEnabled(True)
        
        # Open layout designer
        self.iface.openLayoutDesigner(layout)
        
        QMessageBox.information(self, "Successo", "Layout generato con successo!")
        
    def add_native_elevation_profile(self, layout, page_size):
        """Add elevation profile using QGIS native elevation profile tool"""
        profile_feature = self.profile_combo.currentData()
        if not profile_feature:
            return
            
        # Get the profile line geometry
        profile_geom = profile_feature.geometry()
        
        # Create elevation profile item
        profile_item = QgsLayoutItemElevationProfile(layout)
        
        # Set size and position
        if self.paper_combo.currentText() == "A3 Orizzontale":
            profile_item.attemptMove(QgsLayoutPoint(3.99, 168.75, QgsUnitTypes.LayoutMillimeters))
            profile_item.attemptResize(QgsLayoutSize(287.19, 38.87, QgsUnitTypes.LayoutMillimeters))
        else:
            profile_item.attemptMove(QgsLayoutPoint(10, page_size[1] - 50, QgsUnitTypes.LayoutMillimeters))
            profile_item.attemptResize(QgsLayoutSize(page_size[0] - 20, 40, QgsUnitTypes.LayoutMillimeters))
        
        # Find DEM layer
        dem_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer) and layer.bandCount() == 1:
                # Check if it's a DEM by looking at the name or checking if it has elevation data
                if 'dem' in layer.name().lower() or 'dtm' in layer.name().lower() or 'elevation' in layer.name().lower():
                    dem_layer = layer
                    break
        
        if not dem_layer:
            # If no DEM found by name, use the first single-band raster
            for layer in QgsProject.instance().mapLayers().values():
                if isinstance(layer, QgsRasterLayer) and layer.bandCount() == 1:
                    dem_layer = layer
                    break
        
        # Set the profile curve from the line geometry
        profile_item.setProfileCurve(profile_geom)
        
        # Configure layers for the profile
        if dem_layer:
            try:
                # Try the newer API first (QGIS 3.30+)
                layers = profile_item.layers()
                layers.setLayerEnabled(dem_layer, True)
            except AttributeError:
                try:
                    # Try older API
                    layers = profile_item.profileLayers()
                    layer_settings = layers.profileLayerSettings(dem_layer.id())
                    if layer_settings:
                        layer_settings.setEnabled(True)
                        layers.setProfileLayerSettings(dem_layer.id(), layer_settings)
                except:
                    # Fallback - just add the layer
                    QgsMessageLog.logMessage("Could not configure elevation profile layers, using default settings", "ClipRasterLayout", Qgis.Warning)
        
        # Set profile title
        profile_name = profile_feature['name']
        profile_item.setPlotArea(QRectF(0.1, 0.1, 0.8, 0.8))
        
        # Add frame
        profile_item.setFrameEnabled(True)
        profile_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
        
        # Add to layout
        layout.addLayoutItem(profile_item)
        
        QgsMessageLog.logMessage(f"Native elevation profile added for {profile_name}", "ClipRasterLayout", Qgis.Info)
        
    def add_profile_graph(self, layout, page_size):
        """Add the selected profile graph to the layout"""
        profile_feature = self.profile_combo.currentData()
        if not profile_feature:
            QgsMessageLog.logMessage("No profile feature selected", "ClipRasterLayout", Qgis.Warning)
            return
            
        # Get clean profile name (without path if present)
        profile_name = profile_feature['name']
        if '|' in profile_name:
            profile_name = profile_name.split('|')[0]
        
        QgsMessageLog.logMessage(f"Adding profile: {profile_name}", "ClipRasterLayout", Qgis.Info)
        
        # Import at the beginning
        import os
        import tempfile
        
        # First try to get path from project custom properties
        profile_path, _ = QgsProject.instance().readEntry("ClipRasterLayout", f"profile_{profile_name}")
        
        if not profile_path or not os.path.exists(profile_path):
            # Try profile save directory
            save_dir, _ = QgsProject.instance().readEntry("ClipRasterLayout", "profile_save_dir")
            if save_dir and os.path.exists(save_dir):
                profile_path = os.path.join(save_dir, f"profile_{profile_name}.png")
            else:
                # Fallback to temp directory
                temp_dir = tempfile.gettempdir()
                profile_path = os.path.join(temp_dir, f"profile_{profile_name}.png")
        
        # Debug: check if file exists
        QgsMessageLog.logMessage(f"Looking for profile at: {profile_path}", "ClipRasterLayout", Qgis.Info)
        QgsMessageLog.logMessage(f"File exists: {os.path.exists(profile_path)}", "ClipRasterLayout", Qgis.Info)
        
        # List all profile files in directory where we're looking
        profile_dir = os.path.dirname(profile_path)
        if os.path.exists(profile_dir):
            QgsMessageLog.logMessage(f"Available profile files in {profile_dir}:", "ClipRasterLayout", Qgis.Info)
            for file in os.listdir(profile_dir):
                if file.startswith("profile_") and file.endswith(".png"):
                    QgsMessageLog.logMessage(f"  - {file}", "ClipRasterLayout", Qgis.Info)
        
        if os.path.exists(profile_path):
            # Add image to layout
            profile_pic = QgsLayoutItemPicture(layout)
            profile_pic.setPicturePath(profile_path)
            
            # Position at bottom of page
            if self.paper_combo.currentText() == "A3 Orizzontale":
                profile_pic.attemptMove(QgsLayoutPoint(3.99, 168.75, QgsUnitTypes.LayoutMillimeters))
                profile_pic.attemptResize(QgsLayoutSize(287.19, 38.87, QgsUnitTypes.LayoutMillimeters))
            else:
                # Adapt for other page sizes
                profile_pic.attemptMove(QgsLayoutPoint(10, page_size[1] - 50, QgsUnitTypes.LayoutMillimeters))
                profile_pic.attemptResize(QgsLayoutSize(page_size[0] - 20, 40, QgsUnitTypes.LayoutMillimeters))
                
            profile_pic.setFrameEnabled(True)
            profile_pic.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
            
            # Set resize mode to zoom
            profile_pic.setResizeMode(QgsLayoutItemPicture.Zoom)
            
            layout.addLayoutItem(profile_pic)
            QgsMessageLog.logMessage("Profile image added to layout", "ClipRasterLayout", Qgis.Info)
        else:
            QgsMessageLog.logMessage(f"Profile image not found at {profile_path}", "ClipRasterLayout", Qgis.Warning)
            QMessageBox.warning(None, "Attenzione", 
                f"Immagine del profilo non trovata.\n"
                f"Assicurati di aver generato il profilo '{profile_name}' prima di creare il layout.")
    
    def add_metadata_table(self, layout, raster_layer, page_size):
        # Create frame for metadata  
        # Metadata position based on template
        frame_x = 209.9
        frame_y = 107
        frame_width = 80
        frame_height = 36
        
        # Create metadata box with frame
        metadata_box = QgsLayoutItemShape(layout)
        metadata_box.setShapeType(QgsLayoutItemShape.Rectangle)
        metadata_box.attemptMove(QgsLayoutPoint(frame_x, frame_y, QgsUnitTypes.LayoutMillimeters))
        metadata_box.attemptResize(QgsLayoutSize(frame_width, frame_height, QgsUnitTypes.LayoutMillimeters))
        metadata_box.setFrameEnabled(True)
        metadata_box.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(metadata_box)
        
        # Add metadata labels
        y_offset = 2
        metadata = [
            ("Data:", datetime.now().strftime("%d/%m/%Y")),
            ("Sistema di riferimento:", raster_layer.crs().authid()),
            ("Scala:", self.scale_combo.currentText()),
            ("Autore:", self.author_edit.text() or "N/D"),
            ("Formato:", os.path.splitext(raster_layer.source())[1].upper()),
            ("Dimensioni:", f"{raster_layer.width()} x {raster_layer.height()} px")
        ]
        
        for label_text, value_text in metadata:
            label = QgsLayoutItemLabel(layout)
            label.setText(f"{label_text} {value_text}")
            label.setFont(QFont("Arial", 7))
            label.attemptMove(QgsLayoutPoint(
                frame_x + 2, 
                frame_y + y_offset,
                QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(label)
            y_offset += 6
            
    def export_pdf(self):
        if not self.current_layout:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Esporta PDF", "", "PDF Files (*.pdf)")
        if file_path:
            exporter = QgsLayoutExporter(self.current_layout)
            
            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = 300
            settings.rasterizeWholeImage = False
            
            result = exporter.exportToPdf(file_path, settings)
            
            if result == QgsLayoutExporter.Success:
                QMessageBox.information(self, "Successo", "PDF esportato con successo!")
            else:
                QMessageBox.warning(self, "Errore", "Errore nell'esportazione del PDF")
    
    def load_template_layout(self, template_path, layout_name):
        """Load layout from template file"""
        try:
            # Use QGIS built-in method to duplicate from template
            project = QgsProject.instance()
            manager = project.layoutManager()
            
            # First, try to create an empty layout and add it
            layout = QgsPrintLayout(project)
            layout.initializeDefaults()
            layout.setName(layout_name)
            
            # Add the empty layout first
            if not manager.addLayout(layout):
                QgsMessageLog.logMessage("Could not add empty layout", "ClipRasterLayout", Qgis.Critical)
                return None
            
            # Now load the template content into the existing layout
            from qgis.core import QgsReadWriteContext
            from qgis.PyQt.QtXml import QDomDocument
            
            # Read template content
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            doc = QDomDocument()
            if not doc.setContent(template_content):
                QgsMessageLog.logMessage("Failed to parse template XML", "ClipRasterLayout", Qgis.Critical)
                manager.removeLayout(layout)
                return None
            
            # Get the layout back from manager to ensure we have valid reference
            layout = manager.layoutByName(layout_name)
            if not layout:
                QgsMessageLog.logMessage("Could not retrieve layout from manager", "ClipRasterLayout", Qgis.Critical)
                return None
            
            # Clear the layout and load template
            layout.clear()
            context = QgsReadWriteContext()
            
            # Load the template XML into the layout
            if not layout.readLayoutXml(doc.documentElement(), doc, context):
                QgsMessageLog.logMessage("Failed to read layout XML", "ClipRasterLayout", Qgis.Critical)
                manager.removeLayout(layout)
                return None
            
            QgsMessageLog.logMessage(f"Successfully loaded template into layout: {layout_name}", "ClipRasterLayout", Qgis.Info)
            
            return layout
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error loading template: {str(e)}", "ClipRasterLayout", Qgis.Critical)
            import traceback
            QgsMessageLog.logMessage(traceback.format_exc(), "ClipRasterLayout", Qgis.Critical)
            return None
    
    def populate_template_layout(self, layout, raster_layer):
        """Populate the template layout with data"""
        try:
            # Update main map on first page
            main_map = None
            for item in layout.items():
                if isinstance(item, QgsLayoutItemMap) and item.page() == 0:
                    main_map = item
                    # Assuming the first map is the main map
                    extent = raster_layer.extent()
                    
                    # Check if we need to include profile lines
                    profile_layer = None
                    for layer in QgsProject.instance().mapLayers().values():
                        if layer.name() == "Profili DEM":
                            profile_layer = layer
                            # Expand extent to include all profiles
                            profile_extent = layer.extent()
                            if not profile_extent.isEmpty():
                                extent.combineExtentWith(profile_extent)
                            break
                    
                    # Add 10% buffer
                    extent = extent.buffered(extent.width() * 0.1)
                    item.setExtent(extent)
                    item.refresh()
                    break
            
            # Add labels for section endpoints
            if profile_layer and main_map:
                self.add_section_labels(layout, profile_layer, main_map)
            
            # Update text labels
            for item in layout.items():
                if isinstance(item, QgsLayoutItemLabel):
                    text = item.text()
                    # Replace placeholders
                    if "[title]" in text:
                        item.setText(text.replace("[title]", self.title_edit.text()))
                    elif "[author]" in text:
                        item.setText(text.replace("[author]", self.author_edit.text()))
                    elif "[date]" in text:
                        item.setText(text.replace("[date]", datetime.now().strftime("%d/%m/%Y")))
                    elif "[scale]" in text:
                        item.setText(text.replace("[scale]", self.scale_combo.currentText()))
            
            # Handle elevation profiles on page 2
            self.populate_elevation_profiles(layout)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error populating template: {str(e)}", "ClipRasterLayout", Qgis.Critical)
    
    def populate_elevation_profiles(self, layout):
        """Populate elevation profiles on page 2 of the template"""
        try:
            # Get all profile features
            profile_features = []
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Profili DEM" and isinstance(layer, QgsVectorLayer):
                    for feature in layer.getFeatures():
                        profile_features.append(feature)
                    break
            
            # Limit to 6 profiles
            profile_features = profile_features[:6]
            
            if not profile_features:
                QgsMessageLog.logMessage("No profiles found to add to layout", "ClipRasterLayout", Qgis.Info)
                return
            
            # Find elevation profile items on page 2
            profile_items = []
            
            # Since the template might not have native elevation profiles,
            # we should check for picture items that might be placeholders
            for item in layout.items():
                if HAS_ELEVATION_PROFILE and isinstance(item, QgsLayoutItemElevationProfile):
                    # Check if it's on page 2
                    if item.page() == 1:  # Page index starts at 0
                        profile_items.append(item)
                        
            # If no elevation profile items found, look for picture placeholders
            if not profile_items:
                QgsMessageLog.logMessage("No elevation profile items found, looking for picture placeholders", "ClipRasterLayout", Qgis.Info)
                # Look for picture items that might be profile placeholders
                picture_items = []
                for item in layout.items():
                    if isinstance(item, QgsLayoutItemPicture):
                        # Check if it's on page 2
                        if item.page() == 1:  # Page index starts at 0
                            picture_items.append(item)
                            QgsMessageLog.logMessage(f"Found picture item: {item.id()}", "ClipRasterLayout", Qgis.Info)
                                
                if picture_items:
                    QgsMessageLog.logMessage(f"Found {len(picture_items)} picture items for profiles on page 2", "ClipRasterLayout", Qgis.Info)
                    # Sort picture items by their position on page (top to bottom, left to right)
                    picture_items.sort(key=lambda x: (x.positionWithUnits().y(), x.positionWithUnits().x()))
                    
                    # Populate picture items with matplotlib profiles
                    for i, (pic_item, profile_feature) in enumerate(zip(picture_items[:len(profile_features)], profile_features)):
                        profile_name = profile_feature['name']
                        
                        # Get profile image path
                        profile_path, _ = QgsProject.instance().readEntry("ClipRasterLayout", f"profile_{profile_name}")
                        
                        if not profile_path or not os.path.exists(profile_path):
                            # Try profile save directory
                            save_dir, _ = QgsProject.instance().readEntry("ClipRasterLayout", "profile_save_dir")
                            if save_dir and os.path.exists(save_dir):
                                profile_path = os.path.join(save_dir, f"profile_{profile_name}.png")
                            else:
                                # Fallback to temp directory
                                import tempfile
                                temp_dir = tempfile.gettempdir()
                                profile_path = os.path.join(temp_dir, f"profile_{profile_name}.png")
                        
                        if os.path.exists(profile_path):
                            pic_item.setPicturePath(profile_path)
                            pic_item.setVisibility(True)
                            QgsMessageLog.logMessage(f"Set profile image {i+1} to {profile_path}", "ClipRasterLayout", Qgis.Info)
                            
                            # Add title label above the profile
                            self.add_profile_title(layout, pic_item, f"Profilo {profile_name}")
                        else:
                            QgsMessageLog.logMessage(f"Profile image not found: {profile_path}", "ClipRasterLayout", Qgis.Warning)
                            pic_item.setVisibility(False)
                    
                    # Hide unused picture items
                    for i in range(len(profile_features), len(picture_items)):
                        picture_items[i].setVisibility(False)
                        QgsMessageLog.logMessage(f"Hidden unused profile picture {i+1}", "ClipRasterLayout", Qgis.Info)
                return
            
            QgsMessageLog.logMessage(f"Found {len(profile_items)} elevation profile items on page 2", "ClipRasterLayout", Qgis.Info)
            
            # Populate profiles
            for i, (profile_item, profile_feature) in enumerate(zip(profile_items, profile_features)):
                try:
                    profile_name = profile_feature['name']
                    
                    # Try to copy from the elevation profile dock
                    try:
                        # Get the main elevation profile dock
                        profile_dock = None
                        for dock in self.iface.mainWindow().findChildren(QDockWidget):
                            if 'elevation' in dock.windowTitle().lower() and 'profile' in dock.windowTitle().lower():
                                profile_dock = dock
                                break
                        
                        if profile_dock and profile_dock.isVisible():
                            # Try to use copyProfileFromExisting if available
                            if hasattr(profile_item, 'copyFromProfileWidget'):
                                profile_item.copyFromProfileWidget(profile_dock)
                                QgsMessageLog.logMessage(f"Copied profile {i+1} from elevation profile widget", "ClipRasterLayout", Qgis.Info)
                            else:
                                # Fallback: set the curve manually
                                profile_item.setProfileCurve(profile_feature.geometry())
                                QgsMessageLog.logMessage(f"Set profile curve manually for {i+1}", "ClipRasterLayout", Qgis.Info)
                        else:
                            # No profile dock, set curve manually
                            profile_item.setProfileCurve(profile_feature.geometry())
                            
                            # Find DEM layer
                            dem_layer = None
                            for layer in QgsProject.instance().mapLayers().values():
                                if isinstance(layer, QgsRasterLayer) and layer.bandCount() == 1:
                                    if 'dem' in layer.name().lower() or 'dtm' in layer.name().lower():
                                        dem_layer = layer
                                        break
                            
                            if dem_layer:
                                try:
                                    layers = profile_item.layers()
                                    layers.setLayerEnabled(dem_layer, True)
                                except AttributeError:
                                    QgsMessageLog.logMessage(f"Could not set layer for profile {i+1}", "ClipRasterLayout", Qgis.Warning)
                                    
                    except Exception as e:
                        QgsMessageLog.logMessage(f"Error copying from profile dock: {str(e)}", "ClipRasterLayout", Qgis.Warning)
                        # Fallback to setting curve
                        profile_item.setProfileCurve(profile_feature.geometry())
                    
                    # Update title if it's a label
                    # Look for associated label
                    for label_item in layout.items():
                        if isinstance(label_item, QgsLayoutItemLabel):
                            if f"profile_{i+1}" in label_item.id().lower() or f"profilo_{i+1}" in label_item.id().lower():
                                label_item.setText(f"Profilo {profile_name}")
                                break
                    
                    QgsMessageLog.logMessage(f"Populated profile {i+1} with {profile_name}", "ClipRasterLayout", Qgis.Info)
                    
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error setting profile {i+1}: {str(e)}", "ClipRasterLayout", Qgis.Warning)
            
            # Hide unused profile items
            for i in range(len(profile_features), len(profile_items)):
                profile_items[i].setVisibility(False)
                QgsMessageLog.logMessage(f"Hidden unused profile {i+1}", "ClipRasterLayout", Qgis.Info)
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error populating elevation profiles: {str(e)}", "ClipRasterLayout", Qgis.Critical)
    
    def add_section_labels(self, layout, profile_layer, map_item):
        """Add labels at the endpoints of sections on the map"""
        try:
            for feature in profile_layer.getFeatures():
                profile_name = feature['name']
                if not profile_name or '-' not in profile_name:
                    continue
                
                # Get the start and end letters
                start_letter, end_letter = profile_name.split('-')
                geometry = feature.geometry()
                
                if geometry.type() == QgsWkbTypes.LineGeometry:
                    # Get the line points
                    line = geometry.asPolyline()
                    if len(line) >= 2:
                        start_point = line[0]
                        end_point = line[-1]
                        
                        # Convert map coordinates to layout coordinates
                        start_layout = map_item.mapToItemCoords(QPointF(start_point.x(), start_point.y()))
                        end_layout = map_item.mapToItemCoords(QPointF(end_point.x(), end_point.y()))
                        
                        # Create start label
                        start_label = QgsLayoutItemLabel(layout)
                        start_label.setText(f"→ {start_letter}")
                        start_label.setFont(QFont("Arial", 10, QFont.Bold))
                        
                        # Position relative to map item
                        start_pos = QgsLayoutPoint(
                            map_item.positionWithUnits().x() + start_layout.x() - 5,
                            map_item.positionWithUnits().y() + start_layout.y() - 5,
                            QgsUnitTypes.LayoutMillimeters
                        )
                        start_label.attemptMove(start_pos)
                        start_label.attemptResize(QgsLayoutSize(10, 10, QgsUnitTypes.LayoutMillimeters))
                        layout.addLayoutItem(start_label)
                        
                        # Create end label
                        end_label = QgsLayoutItemLabel(layout)
                        end_label.setText(f"{end_letter} ←")
                        end_label.setFont(QFont("Arial", 10, QFont.Bold))
                        
                        # Position relative to map item
                        end_pos = QgsLayoutPoint(
                            map_item.positionWithUnits().x() + end_layout.x() - 5,
                            map_item.positionWithUnits().y() + end_layout.y() - 5,
                            QgsUnitTypes.LayoutMillimeters
                        )
                        end_label.attemptMove(end_pos)
                        end_label.attemptResize(QgsLayoutSize(10, 10, QgsUnitTypes.LayoutMillimeters))
                        layout.addLayoutItem(end_label)
                        
                        QgsMessageLog.logMessage(f"Added labels for section {profile_name}", "ClipRasterLayout", Qgis.Info)
                        
        except Exception as e:
            QgsMessageLog.logMessage(f"Error adding section labels: {str(e)}", "ClipRasterLayout", Qgis.Warning)
    
    def add_profile_title(self, layout, profile_item, title):
        """Add title label above a profile picture item"""
        try:
            # Create title label
            title_label = QgsLayoutItemLabel(layout)
            title_label.setText(title)
            title_label.setFont(QFont("Arial", 12, QFont.Bold))
            title_label.setHAlign(Qt.AlignHCenter)
            
            # Position above the profile item
            profile_pos = profile_item.positionWithUnits()
            title_pos = QgsLayoutPoint(
                profile_pos.x(),
                profile_pos.y() - 8,  # 8mm above the profile
                QgsUnitTypes.LayoutMillimeters
            )
            
            title_label.attemptMove(title_pos)
            title_label.attemptResize(QgsLayoutSize(
                profile_item.sizeWithUnits().width(),
                8,
                QgsUnitTypes.LayoutMillimeters
            ))
            
            layout.addLayoutItem(title_label)
            QgsMessageLog.logMessage(f"Added title '{title}' to profile", "ClipRasterLayout", Qgis.Info)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error adding profile title: {str(e)}", "ClipRasterLayout", Qgis.Warning)