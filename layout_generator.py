# -*- coding: utf-8 -*-
# Compatible with QGIS 3.x (Qt5) and QGIS 4.x (Qt6)
from qgis.PyQt.QtCore import QRectF, QPointF, QSizeF, QDateTime
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
                      QgsWkbTypes, QgsLayoutAtlas, QgsLayoutObject, QgsProperty)

# Qt5/Qt6 compatibility
try:
    from qgis.PyQt.QtCore import Qt
    _qt6 = hasattr(Qt, 'AlignmentFlag')
except ImportError:
    _qt6 = False

if _qt6:
    Qt_AlignHCenter = Qt.AlignmentFlag.AlignHCenter
else:
    from qgis.PyQt.QtCore import Qt
    Qt_AlignHCenter = Qt.AlignHCenter

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
        self.setWindowTitle("Generate Professional Layout")
        self.setMinimumWidth(600)

        layout = QVBoxLayout()

        # Raster selection
        raster_group = QGroupBox("Raster Selection")
        raster_layout = QFormLayout()

        self.raster_combo = QComboBox()
        raster_layout.addRow("Main raster:", self.raster_combo)

        self.use_clipped = QCheckBox("Use clipped raster")
        self.use_clipped.setChecked(True)
        raster_layout.addRow(self.use_clipped)

        raster_group.setLayout(raster_layout)
        layout.addWidget(raster_group)

        # Profile selection
        profile_group = QGroupBox("Profile")
        profile_layout = QFormLayout()

        self.profile_combo = QComboBox()
        profile_layout.addRow("Profile to include:", self.profile_combo)

        self.include_profile = QCheckBox("Include profile in layout")
        self.include_profile.setChecked(True)
        profile_layout.addRow(self.include_profile)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # Layout settings
        settings_group = QGroupBox("Layout Settings")
        settings_layout = QFormLayout()

        self.title_edit = QLineEdit("Topographic Analysis")
        settings_layout.addRow("Title:", self.title_edit)

        self.author_edit = QLineEdit()
        settings_layout.addRow("Author:", self.author_edit)

        self.scale_combo = QComboBox()
        scales = ["1:1", "1:10", "1:20", "1:50", "1:100", "1:200", "1:500",
                  "1:1000", "1:2000", "1:5000", "1:10000", "1:25000", "1:50000",
                  "1:100000", "1:250000", "1:500000"]
        self.scale_combo.addItems(scales)
        self.scale_combo.setEditable(True)  # Allow custom scales
        self.scale_combo.setCurrentIndex(7)  # Default 1:1000
        settings_layout.addRow("Scale:", self.scale_combo)

        self.paper_combo = QComboBox()
        self.paper_combo.addItems(["A4 Landscape", "A3 Landscape", "A2 Landscape", "A1 Landscape"])
        self.paper_combo.setCurrentIndex(1)  # Default A3
        settings_layout.addRow("Paper format:", self.paper_combo)

        self.logo_path = QLineEdit()
        logo_button = QPushButton("Browse...")
        logo_button.clicked.connect(self.select_logo)
        logo_layout = QHBoxLayout()
        logo_layout.addWidget(self.logo_path)
        logo_layout.addWidget(logo_button)
        settings_layout.addRow("Logo:", logo_layout)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        settings_layout.addRow("Notes:", self.notes_edit)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Components to include
        components_group = QGroupBox("Components to include")
        components_layout = QVBoxLayout()

        self.include_north = QCheckBox("North arrow")
        self.include_north.setChecked(True)
        components_layout.addWidget(self.include_north)

        self.include_scale = QCheckBox("Scale bar")
        self.include_scale.setChecked(True)
        components_layout.addWidget(self.include_scale)

        self.include_legend = QCheckBox("Legend")
        self.include_legend.setChecked(True)
        components_layout.addWidget(self.include_legend)

        self.include_overview = QCheckBox("Overview map")
        self.include_overview.setChecked(True)
        components_layout.addWidget(self.include_overview)

        self.include_grid = QCheckBox("Coordinate grid")
        self.include_grid.setChecked(True)
        components_layout.addWidget(self.include_grid)

        self.include_metadata = QCheckBox("Metadata table")
        self.include_metadata.setChecked(True)
        components_layout.addWidget(self.include_metadata)

        components_group.setLayout(components_layout)
        layout.addWidget(components_group)

        # Atlas options
        atlas_group = QGroupBox("Atlas (One page per section)")
        atlas_layout = QVBoxLayout()

        self.enable_atlas = QCheckBox("Enable Atlas mode")
        self.enable_atlas.setChecked(False)
        self.enable_atlas.setToolTip("Generate one PDF page per section with automatic map extent")
        atlas_layout.addWidget(self.enable_atlas)

        self.atlas_margin = QSpinBox()
        self.atlas_margin.setRange(5, 50)
        self.atlas_margin.setValue(10)
        self.atlas_margin.setSuffix(" %")
        atlas_margin_layout = QHBoxLayout()
        atlas_margin_layout.addWidget(QLabel("Map margin:"))
        atlas_margin_layout.addWidget(self.atlas_margin)
        atlas_layout.addLayout(atlas_margin_layout)

        atlas_group.setLayout(atlas_layout)
        layout.addWidget(atlas_group)
        
        # Buttons
        button_layout = QHBoxLayout()

        self.generate_button = QPushButton("Generate Layout")
        self.generate_button.clicked.connect(self.generate_layout)
        button_layout.addWidget(self.generate_button)

        self.export_button = QPushButton("Export PDF")
        self.export_button.clicked.connect(self.export_pdf)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        # Template selection
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))
        self.template_checkbox = QCheckBox("Use template_layout.qpt")
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
        self.profile_combo.addItem("None", None)
        
        # Check for profile layer
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Profili DEM" and isinstance(layer, QgsVectorLayer):
                # Add each profile feature
                for feature in layer.getFeatures():
                    profile_name = feature['name']
                    if profile_name:
                        self.profile_combo.addItem(profile_name, feature)
        
    def select_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg *.svg)")
        if file_path:
            self.logo_path.setText(file_path)
            
    def generate_layout(self):
        raster_layer = self.raster_combo.currentData()
        if not raster_layer:
            QMessageBox.warning(self, "Warning", "Select a raster")
            return

        # Check if Atlas mode is enabled
        if self.enable_atlas.isChecked():
            self.generate_atlas_layout(raster_layer)
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
            "A4 Landscape": (297, 210),
            "A3 Landscape": (420, 297),
            "A2 Landscape": (594, 420),
            "A1 Landscape": (841, 594)
        }
        
        size = paper_sizes[self.paper_combo.currentText()]
        page.setPageSize(QgsLayoutSize(size[0], size[1], QgsUnitTypes.LayoutMillimeters))
        
        # Main map - using template coordinates for A3
        map_item = QgsLayoutItemMap(layout)
        if self.paper_combo.currentText() == "A3 Landscape":
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
            
            if self.paper_combo.currentText() == "A3 Landscape":
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
                    
            if self.paper_combo.currentText() == "A3 Landscape":
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
            if self.paper_combo.currentText() == "A3 Landscape":
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
        if self.paper_combo.currentText() == "A3 Landscape":
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
            if self.paper_combo.currentText() == "A3 Landscape":
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

        # Check if Atlas is enabled
        atlas = self.current_layout.atlas()
        if atlas and atlas.enabled():
            self.export_atlas_pdf()
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "", "PDF Files (*.pdf)")
        if file_path:
            exporter = QgsLayoutExporter(self.current_layout)

            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = 300
            settings.rasterizeWholeImage = False

            result = exporter.exportToPdf(file_path, settings)

            if result == QgsLayoutExporter.Success:
                QMessageBox.information(self, "Success", "PDF exported successfully!")
            else:
                QMessageBox.warning(self, "Error", "Error exporting PDF")

    def export_atlas_pdf(self):
        """Export Atlas to PDF (one page per section)"""
        if not self.current_layout:
            return

        atlas = self.current_layout.atlas()
        if not atlas or not atlas.enabled():
            QMessageBox.warning(self, "Warning", "Atlas is not enabled")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Atlas PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return

        try:
            exporter = QgsLayoutExporter(self.current_layout)

            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = 300
            settings.rasterizeWholeImage = False

            # Export all Atlas pages to single PDF
            result = exporter.exportToPdf(atlas, file_path, settings)

            if result == QgsLayoutExporter.Success:
                feature_count = atlas.count()
                QMessageBox.information(self, "Success",
                    f"Atlas PDF exported successfully!\n\n"
                    f"Pages: {feature_count}\n"
                    f"File: {file_path}")
            else:
                QMessageBox.warning(self, "Error", f"Error exporting Atlas PDF: {result}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error exporting Atlas: {str(e)}")

    def generate_atlas_layout(self, raster_layer):
        """Generate a layout with Atlas enabled for sections"""
        try:
            # Find the sections/profile layer
            profile_layer = None
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() in ["Profili DEM", "Sections"] and isinstance(layer, QgsVectorLayer):
                    if layer.featureCount() > 0:
                        profile_layer = layer
                        break

            if not profile_layer:
                QMessageBox.warning(self, "Warning",
                    "No sections found.\n\n"
                    "First create sections using the 'Create DEM Profile' tool or "
                    "the 'Draw sections' button in Clip & Profile Export.")
                return

            feature_count = profile_layer.featureCount()
            QgsMessageLog.logMessage(f"Found {feature_count} sections in {profile_layer.name()}", "ClipRasterLayout", Qgis.Info)

            # Create layout
            project = QgsProject.instance()
            layout_name = f"Atlas_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            layout = QgsPrintLayout(project)
            layout.initializeDefaults()
            layout.setName(layout_name)

            # Set page size
            page = layout.pageCollection().page(0)
            paper_sizes = {
                "A4 Landscape": (297, 210),
                "A3 Landscape": (420, 297),
                "A2 Landscape": (594, 420),
                "A1 Landscape": (841, 594)
            }
            size = paper_sizes.get(self.paper_combo.currentText(), (420, 297))
            page.setPageSize(QgsLayoutSize(size[0], size[1], QgsUnitTypes.LayoutMillimeters))

            # Configure Atlas
            atlas = layout.atlas()
            atlas.setCoverageLayer(profile_layer)
            atlas.setEnabled(True)
            atlas.setFilenameExpression("'Section_' || \"name\"")
            atlas.setPageNameExpression("\"name\"")

            # Main map - atlas driven
            map_item = QgsLayoutItemMap(layout)
            map_item.setRect(10, 40, size[0] * 0.65, size[1] * 0.5)
            map_item.attemptMove(QgsLayoutPoint(10, 40, QgsUnitTypes.LayoutMillimeters))
            map_item.attemptResize(QgsLayoutSize(size[0] * 0.65, size[1] * 0.5, QgsUnitTypes.LayoutMillimeters))
            map_item.setExtent(raster_layer.extent())
            map_item.setFrameEnabled(True)
            map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))

            # Configure map to follow Atlas feature
            map_item.setAtlasDriven(True)
            map_item.setAtlasScalingMode(QgsLayoutItemMap.Auto)
            map_item.setAtlasMargin(self.atlas_margin.value() / 100.0)

            layout.addLayoutItem(map_item)

            # Title with Atlas expression
            title = QgsLayoutItemLabel(layout)
            title.setText(f"[% '{self.title_edit.text()}' %] - Section [% \"name\" %]")
            title.setFont(QFont("Arial", 18, QFont.Bold))
            title.setHAlign(Qt_AlignHCenter)
            title.attemptMove(QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters))
            title.attemptResize(QgsLayoutSize(size[0] - 20, 15, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(title)

            # Section info label with Atlas expressions
            info_label = QgsLayoutItemLabel(layout)
            info_label.setText(
                "Section: [% \"name\" %]\n"
                "2D Length: [% round(\"length_2d\", 2) %] m\n"
                "3D Length: [% round(\"length_3d\", 2) %] m\n"
                "Elevation A: [% round(\"elev_a\", 1) %] m\n"
                "Elevation B: [% round(\"elev_b\", 1) %] m\n"
                "Elevation Change: [% round(\"elev_b\" - \"elev_a\", 1) %] m"
            )
            info_label.setFont(QFont("Arial", 10))
            info_label.attemptMove(QgsLayoutPoint(size[0] * 0.7, 40, QgsUnitTypes.LayoutMillimeters))
            info_label.attemptResize(QgsLayoutSize(size[0] * 0.25, 60, QgsUnitTypes.LayoutMillimeters))
            info_label.setFrameEnabled(True)
            info_label.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(info_label)

            # Profile image with Atlas expression for path
            profile_pic = QgsLayoutItemPicture(layout)

            # Get profile save directory
            save_dir, _ = QgsProject.instance().readEntry("ClipRasterLayout", "profile_save_dir")
            if save_dir:
                # Use expression to get profile image based on section name
                profile_pic.setDataDefinedProperty(
                    QgsLayoutObject.PictureSource,
                    QgsProperty.fromExpression(f"'{save_dir}/profile_' || \"name\" || '.png'")
                )
            else:
                # Fallback to temp directory
                import tempfile
                temp_dir = tempfile.gettempdir()
                profile_pic.setDataDefinedProperty(
                    QgsLayoutObject.PictureSource,
                    QgsProperty.fromExpression(f"'{temp_dir}/profile_' || \"name\" || '.png'")
                )

            profile_pic.attemptMove(QgsLayoutPoint(10, size[1] * 0.6, QgsUnitTypes.LayoutMillimeters))
            profile_pic.attemptResize(QgsLayoutSize(size[0] - 20, size[1] * 0.3, QgsUnitTypes.LayoutMillimeters))
            profile_pic.setFrameEnabled(True)
            profile_pic.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
            profile_pic.setResizeMode(QgsLayoutItemPicture.Zoom)
            layout.addLayoutItem(profile_pic)

            # North arrow
            if self.include_north.isChecked():
                north = QgsLayoutItemPicture(layout)
                north.setMode(QgsLayoutItemPicture.FormatSVG)
                north.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
                north.attemptMove(QgsLayoutPoint(size[0] - 30, 40, QgsUnitTypes.LayoutMillimeters))
                north.attemptResize(QgsLayoutSize(15, 20, QgsUnitTypes.LayoutMillimeters))
                north.setFrameEnabled(True)
                layout.addLayoutItem(north)

            # Scale bar
            if self.include_scale.isChecked():
                scalebar = QgsLayoutItemScaleBar(layout)
                scalebar.setLinkedMap(map_item)
                scalebar.setUnits(QgsUnitTypes.DistanceMeters)
                scalebar.setNumberOfSegments(4)
                scalebar.setStyle('Single Box')
                scalebar.attemptMove(QgsLayoutPoint(10, size[1] * 0.55, QgsUnitTypes.LayoutMillimeters))
                scalebar.setFrameEnabled(True)
                layout.addLayoutItem(scalebar)

            # Metadata
            if self.include_metadata.isChecked():
                metadata_label = QgsLayoutItemLabel(layout)
                metadata_label.setText(
                    f"Date: {datetime.now().strftime('%d/%m/%Y')}\n"
                    f"CRS: {raster_layer.crs().authid()}\n"
                    f"Author: {self.author_edit.text() or 'N/A'}\n"
                    f"Page: [% @atlas_featurenumber %] / [% @atlas_totalfeatures %]"
                )
                metadata_label.setFont(QFont("Arial", 8))
                metadata_label.attemptMove(QgsLayoutPoint(size[0] * 0.7, size[1] - 40, QgsUnitTypes.LayoutMillimeters))
                metadata_label.attemptResize(QgsLayoutSize(size[0] * 0.25, 30, QgsUnitTypes.LayoutMillimeters))
                layout.addLayoutItem(metadata_label)

            # Add layout to project
            project.layoutManager().addLayout(layout)

            self.current_layout = layout
            self.export_button.setEnabled(True)

            # Open layout designer
            self.iface.openLayoutDesigner(layout)

            QMessageBox.information(self, "Success",
                f"Atlas layout created with {feature_count} sections!\n\n"
                f"The map will automatically zoom to each section.\n"
                f"Click 'Export PDF' to generate all pages.")

        except Exception as e:
            QgsMessageLog.logMessage(f"Error creating Atlas layout: {str(e)}", "ClipRasterLayout", Qgis.Critical)
            QMessageBox.warning(self, "Error", f"Error creating Atlas layout: {str(e)}")
    
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
            # Find and update maps
            main_map = None
            overview_map = None
            
            # Find all maps and identify them
            for item in layout.items():
                if isinstance(item, QgsLayoutItemMap):
                    item_id = item.id()
                    QgsMessageLog.logMessage(f"Found map with ID: '{item_id}' on page {item.page()}, size: {item.rect().width()}x{item.rect().height()}", "ClipRasterLayout", Qgis.Info)
                    
                    # Check by ID
                    if item_id.lower() == "map":
                        main_map = item
                        QgsMessageLog.logMessage("Identified as main map by ID", "ClipRasterLayout", Qgis.Info)
                    elif item_id.lower() == "map2" or "overview" in item_id.lower():
                        overview_map = item
                        QgsMessageLog.logMessage("Identified as overview map by ID", "ClipRasterLayout", Qgis.Info)
                    # If no clear ID, use size heuristic on page 0
                    elif item.page() == 0:
                        if item.rect().width() > 150:  # Larger maps are usually main maps
                            if not main_map:
                                main_map = item
                                QgsMessageLog.logMessage("Identified as main map by size", "ClipRasterLayout", Qgis.Info)
                        else:
                            if not overview_map:
                                overview_map = item
                                QgsMessageLog.logMessage("Identified as overview map by size", "ClipRasterLayout", Qgis.Info)
            
            # Update main map
            if main_map:
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
                main_map.setExtent(extent)
                main_map.refresh()
                
                # Add labels for section endpoints on MAIN MAP
                if profile_layer:
                    self.add_section_labels(layout, profile_layer, main_map)
                    QgsMessageLog.logMessage("Added section labels to main map", "ClipRasterLayout", Qgis.Info)
            
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
            
            # Look for elevation profile items on page 2
            for item in layout.items():
                if HAS_ELEVATION_PROFILE and isinstance(item, QgsLayoutItemElevationProfile):
                    # Check if it's on page 2
                    if item.page() == 1:  # Page index starts at 0
                        profile_items.append(item)
                        QgsMessageLog.logMessage(f"Found elevation profile item: {item.id()} at position {item.positionWithUnits()}", "ClipRasterLayout", Qgis.Info)
                        
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
            QgsMessageLog.logMessage(f"Have {len(profile_features)} profile features to populate", "ClipRasterLayout", Qgis.Info)
            
            # Sort profile items by position (top to bottom, left to right)
            profile_items.sort(key=lambda x: (x.positionWithUnits().y(), x.positionWithUnits().x()))
            
            # Populate profiles
            for i, profile_feature in enumerate(profile_features):
                if i >= len(profile_items):
                    QgsMessageLog.logMessage(f"No more profile items available for feature {i+1}", "ClipRasterLayout", Qgis.Warning)
                    break
                    
                profile_item = profile_items[i]
                try:
                    profile_name = profile_feature['name']
                    
                    # Check if this profile was marked as ready
                    profile_ready, _ = QgsProject.instance().readEntry("ClipRasterLayout", f"profile_ready_{profile_name}")
                    
                    if profile_ready == "yes":
                        QgsMessageLog.logMessage(f"Profile {profile_name} was marked as ready", "ClipRasterLayout", Qgis.Info)
                    
                    # Try to find the specific elevation profile dock for this profile
                    profile_dock = None
                    for dock in self.iface.mainWindow().findChildren(QDockWidget):
                        dock_title = dock.windowTitle()
                        if 'elevation' in dock_title.lower() and 'profile' in dock_title.lower():
                            # Check if this is the dock for our specific profile
                            if profile_name in dock_title:
                                profile_dock = dock
                                QgsMessageLog.logMessage(f"Found specific dock for {profile_name}", "ClipRasterLayout", Qgis.Info)
                                break
                            # If no specific dock found, use any elevation profile dock
                            elif not profile_dock:
                                profile_dock = dock
                    
                    if profile_dock and profile_dock.isVisible():
                        try:
                            # Get the elevation profile canvas from the dock
                            elevation_canvas = None
                            for widget in profile_dock.findChildren(QWidget):
                                if hasattr(widget, 'plotItem') or hasattr(widget, 'plot'):
                                    elevation_canvas = widget
                                    break
                            
                            if elevation_canvas:
                                # Try to use copyFromProfileCanvas if available
                                if hasattr(profile_item, 'copyFromProfileCanvas'):
                                    profile_item.copyFromProfileCanvas(elevation_canvas)
                                    QgsMessageLog.logMessage(f"Copied profile {profile_name} using copyFromProfileCanvas", "ClipRasterLayout", Qgis.Info)
                                elif hasattr(profile_item, 'copyFromProfileWidget'):
                                    profile_item.copyFromProfileWidget(elevation_canvas)
                                    QgsMessageLog.logMessage(f"Copied profile {profile_name} using copyFromProfileWidget", "ClipRasterLayout", Qgis.Info)
                                else:
                                    # Fallback: set the curve manually
                                    self.setup_profile_item_manually(profile_item, profile_feature)
                                    QgsMessageLog.logMessage(f"Set profile {profile_name} manually (no copy method available)", "ClipRasterLayout", Qgis.Info)
                            else:
                                self.setup_profile_item_manually(profile_item, profile_feature)
                                QgsMessageLog.logMessage(f"Could not find elevation canvas in dock for {profile_name}", "ClipRasterLayout", Qgis.Warning)
                        except Exception as e:
                            QgsMessageLog.logMessage(f"Error copying from profile dock: {str(e)}", "ClipRasterLayout", Qgis.Warning)
                            self.setup_profile_item_manually(profile_item, profile_feature)
                    else:
                        # No profile dock found or not visible, set curve manually
                        QgsMessageLog.logMessage(f"No visible profile dock for {profile_name}, setting up manually", "ClipRasterLayout", Qgis.Info)
                        self.setup_profile_item_manually(profile_item, profile_feature)
                    
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
            
            # Hide or remove unused profile items (max 6 profiles)
            for i in range(len(profile_features), len(profile_items)):
                profile_items[i].setVisibility(False)
                QgsMessageLog.logMessage(f"Hidden unused profile {i+1}", "ClipRasterLayout", Qgis.Info)
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error populating elevation profiles: {str(e)}", "ClipRasterLayout", Qgis.Critical)
    
    def setup_profile_item_manually(self, profile_item, profile_feature):
        """Manually setup elevation profile item when dock copy is not available"""
        try:
            # Set the profile curve
            profile_item.setProfileCurve(profile_feature.geometry().constGet())
            
            # Find DEM layer
            dem_layer = None
            for layer in QgsProject.instance().mapLayers().values():
                if isinstance(layer, QgsRasterLayer) and layer.bandCount() == 1:
                    if 'dem' in layer.name().lower() or 'dtm' in layer.name().lower() or 'elevation' in layer.name().lower():
                        dem_layer = layer
                        break
            
            # If no DEM found by name, use the first single-band raster
            if not dem_layer:
                for layer in QgsProject.instance().mapLayers().values():
                    if isinstance(layer, QgsRasterLayer) and layer.bandCount() == 1:
                        dem_layer = layer
                        break
            
            if dem_layer:
                try:
                    # Try newer API
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
                        QgsMessageLog.logMessage(f"Could not configure layers for profile", "ClipRasterLayout", Qgis.Warning)
                        
            # Set display options
            try:
                profile_item.setPlotArea(profile_item.rect())
                profile_item.refresh()
            except:
                pass
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error setting up profile manually: {str(e)}", "ClipRasterLayout", Qgis.Warning)
    
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
                        
                        # Create start label with circular white background
                        start_label = QgsLayoutItemLabel(layout)
                        start_label.setText(f"{start_letter}")
                        start_label.setFont(QFont("Arial", 12, QFont.Bold))
                        
                        # Set white circular background
                        start_label.setBackgroundEnabled(True)
                        start_label.setBackgroundColor(QColor(255, 255, 255))  # White background
                        start_label.setFrameEnabled(True)
                        start_label.setFrameStrokeColor(QColor(0, 0, 0))  # Black border
                        start_label.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
                        
                        # Center text alignment
                        start_label.setHAlign(Qt.AlignHCenter)
                        start_label.setVAlign(Qt.AlignVCenter)
                        start_label.setMarginX(0)
                        start_label.setMarginY(0)
                        
                        # Position relative to map item - circular size
                        label_size = 8  # Size for circular label in mm
                        start_pos = QgsLayoutPoint(
                            map_item.positionWithUnits().x() + start_layout.x() - label_size/2,
                            map_item.positionWithUnits().y() + start_layout.y() - label_size/2,
                            QgsUnitTypes.LayoutMillimeters
                        )
                        start_label.attemptMove(start_pos)
                        start_label.attemptResize(QgsLayoutSize(label_size, label_size, QgsUnitTypes.LayoutMillimeters))
                        
                        # Try to set rounded corners
                        try:
                            start_label.setFrameJoinStyle(Qt.RoundJoin)
                        except:
                            pass
                        
                        layout.addLayoutItem(start_label)
                        
                        # Create end label with circular white background
                        end_label = QgsLayoutItemLabel(layout)
                        end_label.setText(f"{end_letter}")
                        end_label.setFont(QFont("Arial", 12, QFont.Bold))
                        
                        # Set white circular background
                        end_label.setBackgroundEnabled(True)
                        end_label.setBackgroundColor(QColor(255, 255, 255))  # White background
                        end_label.setFrameEnabled(True)
                        end_label.setFrameStrokeColor(QColor(0, 0, 0))  # Black border
                        end_label.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
                        
                        # Center text alignment
                        end_label.setHAlign(Qt.AlignHCenter)
                        end_label.setVAlign(Qt.AlignVCenter)
                        end_label.setMarginX(0)
                        end_label.setMarginY(0)
                        
                        # Position relative to map item - circular size
                        end_pos = QgsLayoutPoint(
                            map_item.positionWithUnits().x() + end_layout.x() - label_size/2,
                            map_item.positionWithUnits().y() + end_layout.y() - label_size/2,
                            QgsUnitTypes.LayoutMillimeters
                        )
                        end_label.attemptMove(end_pos)
                        end_label.attemptResize(QgsLayoutSize(label_size, label_size, QgsUnitTypes.LayoutMillimeters))
                        
                        # Try to set rounded corners
                        try:
                            end_label.setFrameJoinStyle(Qt.RoundJoin)
                        except:
                            pass
                        
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