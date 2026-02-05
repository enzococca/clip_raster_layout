# -----------------------------------------------------------------------------
# File: clip_raster_layout.py
# Compatible with QGIS 3.x (Qt5) and QGIS 4.x (Qt6)
# -----------------------------------------------------------------------------
from qgis.PyQt import QtWidgets, QtCore, QtGui
from qgis.PyQt.QtCore import QVariant, QRectF
from qgis.PyQt.QtGui import QFont, QColor
from qgis.core import (
    QgsProject, QgsMapLayer, QgsWkbTypes, QgsLayoutExporter,
    QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel,
    QgsLayoutItemPicture, QgsLayoutItemScaleBar, QgsUnitTypes,
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY,
    QgsLineSymbol, QgsMarkerLineSymbolLayer, QgsSimpleMarkerSymbolLayer,
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling,
    QgsFillSymbol, QgsSimpleFillSymbolLayer
)
from qgis.gui import QgsMapTool, QgsRubberBand
import processing, os, tempfile, numpy as np, matplotlib.pyplot as plt

# Qt5/Qt6 compatibility layer
try:
    from qgis.PyQt.QtCore import Qt
    # Test if we're in Qt6 by checking enum style
    _qt6 = hasattr(Qt, 'MouseButton')
except ImportError:
    _qt6 = False

if _qt6:
    # Qt6 style enums
    Qt_LeftButton = Qt.MouseButton.LeftButton
    Qt_RightButton = Qt.MouseButton.RightButton
    Qt_LeftDockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea
    Qt_AllDockWidgetAreas = Qt.DockWidgetArea.AllDockWidgetAreas
    Qt_CrossCursor = Qt.CursorShape.CrossCursor
    Qt_Checked = Qt.CheckState.Checked
    Qt_UserRole = Qt.ItemDataRole.UserRole
    Qt_Key_Escape = Qt.Key.Key_Escape
else:
    # Qt5 style enums
    from qgis.PyQt.QtCore import Qt
    Qt_LeftButton = Qt.LeftButton
    Qt_RightButton = Qt.RightButton
    Qt_LeftDockWidgetArea = Qt.LeftDockWidgetArea
    Qt_AllDockWidgetAreas = Qt.AllDockWidgetAreas
    Qt_CrossCursor = Qt.CrossCursor
    Qt_Checked = Qt.Checked
    Qt_UserRole = Qt.UserRole
    Qt_Key_Escape = Qt.Key_Escape


class ClipRasterLayoutPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None

    def initGui(self):
        icon = QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'icon.png'))
        self.action = QtWidgets.QAction(icon, 'Clip & Profile Layout', self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu('Clip Raster & Profile', self.action)

    def unload(self):
        if self.dock:
            self.iface.removeDockWidget(self.dock)
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu('Clip Raster & Profile', self.action)

    def run(self):
        if not self.dock:
            self.dock = ClipDockWidget(self.iface)
            self.dock.processRequested.connect(self.process)
            self.iface.addDockWidget(Qt_LeftDockWidgetArea, self.dock)
        self.dock.show()
        self.dock.raise_()
        self.dock.activateWindow()

    def process(self, rasters, poly_layer, output_dir, sections):
        """Process the clip operation with optional sections"""
        try:
            # 1) Clip rasters
            cropped = []
            clipped_layers = []
            total = len(rasters)

            for i, r in enumerate(rasters):
                try:
                    base = os.path.splitext(os.path.basename(r.source()))[0]
                    outp = os.path.join(output_dir, f"{base}_clipped.tif")
                    processing.run('gdal:cliprasterbymasklayer', {
                        'INPUT': r.source(),
                        'MASK': poly_layer,
                        'CROP_TO_CUTLINE': True,
                        'KEEP_RESOLUTION': True,
                        'OUTPUT': outp
                    })
                    cropped.append(outp)

                    # Load clipped raster to map
                    from qgis.core import QgsRasterLayer
                    clipped = QgsRasterLayer(outp, f"{base}_clipped")
                    if clipped.isValid():
                        QgsProject.instance().addMapLayer(clipped)
                        clipped_layers.append(clipped)
                except Exception as e:
                    QtWidgets.QMessageBox.warning(None, 'Warning', f'Error clipping {r.name()}: {str(e)}')

            # 2) Generate profiles (only if sections are provided)
            profiles = []
            last_png = None

            if sections is not None and sections.isValid() and sections.featureCount() > 0:
                # Find the first raster to use for elevation sampling
                dem_provider = None
                dem_crs = None
                if rasters:
                    dem_provider = rasters[0].dataProvider()
                    dem_crs = rasters[0].crs()

                if dem_provider:
                    # Setup distance calculator for accurate measurements
                    from qgis.core import QgsDistanceArea, QgsCoordinateTransformContext
                    distance_calc = QgsDistanceArea()
                    distance_calc.setSourceCrs(sections.crs(), QgsCoordinateTransformContext())
                    distance_calc.setEllipsoid(QgsProject.instance().ellipsoid())

                    for feat in sections.getFeatures():
                        try:
                            geom = feat.geometry()
                            label = feat.attribute('label')

                            # Calculate true length in meters using ellipsoidal calculation
                            length_meters = distance_calc.measureLength(geom)
                            # Also get the geometry length in CRS units for interpolation
                            length_crs = geom.length()

                            if length_meters <= 0 or length_crs <= 0:
                                continue

                            # Use more points for better resolution
                            npts = min(500, max(50, int(length_meters)))
                            interval_crs = length_crs / npts

                            pts = []
                            for j in range(npts + 1):
                                d = min(j * interval_crs, length_crs)
                                interp_geom = geom.interpolate(d)
                                if interp_geom and not interp_geom.isEmpty():
                                    pts.append(interp_geom.asPoint())

                            if len(pts) < 2:
                                continue

                            elev = []
                            valid_elevations = 0
                            for p in pts:
                                val = dem_provider.sample(QgsPointXY(p.x(), p.y()), 1)
                                if val[0] is not None and val[0] != 0:
                                    elev.append(float(val[0]))
                                    valid_elevations += 1
                                elif elev:  # Use previous value if available
                                    elev.append(elev[-1])
                                else:
                                    elev.append(0.0)

                            if len(elev) < 2 or valid_elevations < 2:
                                print(f"Section {label}: Not enough valid elevations ({valid_elevations})")
                                continue

                            # Use true distance in meters for x-axis
                            dist = np.linspace(0, length_meters, len(elev))

                            # Create profile plot
                            fig = plt.figure(figsize=(10, 4))
                            plt.plot(dist, elev, 'b-', linewidth=1.5)
                            plt.fill_between(dist, min(elev), elev, alpha=0.3)
                            plt.xlabel('Distance (m)')
                            plt.ylabel('Elevation (m)')
                            plt.title(f"Section {label}")
                            plt.grid(True, alpha=0.3)

                            # Add some padding to y-axis
                            elev_range = max(elev) - min(elev)
                            if elev_range > 0:
                                plt.ylim(min(elev) - elev_range * 0.1, max(elev) + elev_range * 0.1)

                            png = os.path.join(output_dir, f"profile_{label}.png")
                            fig.savefig(png, dpi=150, bbox_inches='tight')
                            plt.close(fig)
                            profiles.append((label, png, dist[-1], elev[-1] - elev[0]))
                            last_png = png
                            print(f"Section {label}: Length={length_meters:.1f}m, Points={len(pts)}, Elevations={valid_elevations}")
                        except Exception as e:
                            print(f"Error processing section {label}: {str(e)}")
                            import traceback
                            traceback.print_exc()
                            continue

                sections.commitChanges()

            # 3) Build result message
            msg = f"Clipping completed!\n\n"
            msg += f"Clipped rasters: {len(cropped)}\n"
            msg += f"Output folder: {output_dir}"

            if profiles:
                msg += f"\n\nProfiles created: {len(profiles)}"

            QtWidgets.QMessageBox.information(None, 'Done', msg)

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, 'Error', f'Processing error: {str(e)}')


class ClipDockWidget(QtWidgets.QDockWidget):
    processRequested = QtCore.pyqtSignal(list, object, str, object)

    def __init__(self, iface):
        super().__init__('Clip & Profile Export', iface.mainWindow())
        self.iface = iface
        self.sections_layer_id = None
        self.clip_polygon_layer_id = None

        w = QtWidgets.QWidget()
        self.setWidget(w)
        v = QtWidgets.QVBoxLayout(w)

        # Help button
        help_btn = QtWidgets.QPushButton('? Tutorial')
        help_btn.setMaximumWidth(80)
        help_btn.clicked.connect(self.showTutorial)
        help_layout = QtWidgets.QHBoxLayout()
        help_layout.addStretch()
        help_layout.addWidget(help_btn)
        v.addLayout(help_layout)

        # Raster selection
        raster_group = QtWidgets.QGroupBox('1. Select DEM Rasters')
        raster_layout = QtWidgets.QVBoxLayout()
        self.rList = QtWidgets.QListWidget()
        self.rList.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.rList.setMaximumHeight(100)
        raster_layout.addWidget(self.rList)
        refresh_r_btn = QtWidgets.QPushButton('Refresh list')
        refresh_r_btn.clicked.connect(self.refreshRasterList)
        raster_layout.addWidget(refresh_r_btn)
        raster_group.setLayout(raster_layout)
        v.addWidget(raster_group)

        # Polygon selection
        poly_group = QtWidgets.QGroupBox('2. Clip Polygon')
        poly_layout = QtWidgets.QVBoxLayout()

        poly_h = QtWidgets.QHBoxLayout()
        self.pCombo = QtWidgets.QComboBox()
        poly_h.addWidget(self.pCombo)
        refresh_p_btn = QtWidgets.QPushButton('Refresh')
        refresh_p_btn.setMaximumWidth(70)
        refresh_p_btn.clicked.connect(self.refreshPolygonList)
        poly_h.addWidget(refresh_p_btn)
        poly_layout.addLayout(poly_h)

        self.drawPolyBtn = QtWidgets.QPushButton('Draw new clip polygon')
        self.drawPolyBtn.clicked.connect(self.startDrawPolygon)
        poly_layout.addWidget(self.drawPolyBtn)

        poly_group.setLayout(poly_layout)
        v.addWidget(poly_group)

        # Sections (optional)
        sec_group = QtWidgets.QGroupBox('3. Sections (optional)')
        sec_layout = QtWidgets.QVBoxLayout()

        self.createSectionsCheck = QtWidgets.QCheckBox('Create sections/profiles')
        self.createSectionsCheck.setChecked(False)
        self.createSectionsCheck.stateChanged.connect(self.toggleSectionsUI)
        sec_layout.addWidget(self.createSectionsCheck)

        self.secBtn = QtWidgets.QPushButton('Draw sections')
        self.secBtn.clicked.connect(self.startSections)
        self.secBtn.setEnabled(False)
        sec_layout.addWidget(self.secBtn)

        self.secCountLabel = QtWidgets.QLabel('Sections drawn: 0')
        sec_layout.addWidget(self.secCountLabel)

        sec_group.setLayout(sec_layout)
        v.addWidget(sec_group)

        # Output
        out_group = QtWidgets.QGroupBox('4. Output')
        out_layout = QtWidgets.QVBoxLayout()

        h = QtWidgets.QHBoxLayout()
        h.addWidget(QtWidgets.QLabel('Folder:'))
        self.outEdit = QtWidgets.QLineEdit()
        h.addWidget(self.outEdit)
        br = QtWidgets.QPushButton('Browse')
        br.clicked.connect(self.chooseFolder)
        h.addWidget(br)
        out_layout.addLayout(h)

        out_group.setLayout(out_layout)
        v.addWidget(out_group)

        # Run Clip button
        self.runBtn = QtWidgets.QPushButton('Run Clip')
        self.runBtn.setStyleSheet('QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }')
        self.runBtn.clicked.connect(self.emitProcess)
        v.addWidget(self.runBtn)

        # Layout generation section
        layout_group = QtWidgets.QGroupBox('5. Generate Layout (Atlas)')
        layout_layout = QtWidgets.QVBoxLayout()

        self.atlasCheck = QtWidgets.QCheckBox('Enable Atlas (one page per section)')
        self.atlasCheck.setChecked(True)
        self.atlasCheck.setToolTip('Generate one PDF page per section with automatic map extent')
        layout_layout.addWidget(self.atlasCheck)

        margin_h = QtWidgets.QHBoxLayout()
        margin_h.addWidget(QtWidgets.QLabel('Map margin:'))
        self.atlasMarginSpin = QtWidgets.QSpinBox()
        self.atlasMarginSpin.setRange(5, 50)
        self.atlasMarginSpin.setValue(10)
        self.atlasMarginSpin.setSuffix(' %')
        margin_h.addWidget(self.atlasMarginSpin)
        margin_h.addStretch()
        layout_layout.addLayout(margin_h)

        self.generateLayoutBtn = QtWidgets.QPushButton('Generate Atlas Layout')
        self.generateLayoutBtn.setStyleSheet('QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px; }')
        self.generateLayoutBtn.clicked.connect(self.generateAtlasLayout)
        layout_layout.addWidget(self.generateLayoutBtn)

        layout_group.setLayout(layout_layout)
        v.addWidget(layout_group)

        # Status label
        self.statusLabel = QtWidgets.QLabel('')
        self.statusLabel.setStyleSheet('color: gray; font-style: italic;')
        v.addWidget(self.statusLabel)

        v.addStretch()

        # Initialize layer lists
        self.refreshRasterList()
        self.refreshPolygonList()

        # Connect to project signals for auto-refresh
        QgsProject.instance().layersAdded.connect(self.onLayersChanged)
        QgsProject.instance().layersRemoved.connect(self.onLayersChanged)

    def onLayersChanged(self, layers=None):
        """Auto-refresh lists when layers are added/removed"""
        self.refreshRasterList()
        self.refreshPolygonList()
        self.updateStatus('Layer lists updated')

    def refreshRasterList(self):
        """Refresh the raster layer list"""
        self.rList.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.type() == QgsMapLayer.RasterLayer:
                it = QtWidgets.QListWidgetItem(lyr.name())
                it.setData(Qt_UserRole, lyr.id())
                self.rList.addItem(it)

    def refreshPolygonList(self):
        """Refresh the polygon layer list"""
        current_id = self.pCombo.currentData()
        self.pCombo.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.type() == QgsMapLayer.VectorLayer and lyr.geometryType() == QgsWkbTypes.PolygonGeometry:
                self.pCombo.addItem(lyr.name(), lyr.id())
        # Restore previous selection if still exists
        if current_id:
            idx = self.pCombo.findData(current_id)
            if idx >= 0:
                self.pCombo.setCurrentIndex(idx)

    def toggleSectionsUI(self, state):
        """Enable/disable sections UI"""
        enabled = state == Qt_Checked
        self.secBtn.setEnabled(enabled)
        if enabled and not self.sections_layer_id:
            self._createSectionsLayer()

    def updateStatus(self, message):
        """Update status label"""
        self.statusLabel.setText(message)
        QtCore.QTimer.singleShot(3000, lambda: self.statusLabel.setText(''))

    def showTutorial(self):
        """Show tutorial dialog"""
        dlg = TutorialDialog(self)
        # exec_() is deprecated in Qt6, exec() works in both
        if hasattr(dlg, 'exec'):
            dlg.exec()
        else:
            dlg.exec_()

    def startDrawPolygon(self):
        """Start drawing a clip polygon"""
        if not self.clip_polygon_layer_id:
            self._createClipPolygonLayer()
        layer = QgsProject.instance().mapLayer(self.clip_polygon_layer_id)
        if layer:
            tool = PolygonDrawTool(self.iface.mapCanvas(), layer, self)
            self.iface.mapCanvas().setMapTool(tool)
            self.updateStatus('Click on the map to draw the polygon. Double-click to finish.')

    def _createClipPolygonLayer(self):
        """Create a memory layer for clip polygons"""
        crs = QgsProject.instance().crs().authid() or 'EPSG:4326'
        layer = QgsVectorLayer(f'Polygon?crs={crs}&field=name:string', 'Clip Polygon', 'memory')

        # Style with semi-transparent fill
        symbol = QgsFillSymbol.createSimple({
            'color': '255,0,0,50',
            'outline_color': '255,0,0',
            'outline_width': '0.8'
        })
        layer.renderer().setSymbol(symbol)

        QgsProject.instance().addMapLayer(layer)
        self.clip_polygon_layer_id = layer.id()
        layer.startEditing()

        # Refresh polygon combo
        self.refreshPolygonList()

    def onPolygonDrawn(self):
        """Called when a polygon is finished drawing"""
        self.refreshPolygonList()
        # Select the newly created layer
        if self.clip_polygon_layer_id:
            idx = self.pCombo.findData(self.clip_polygon_layer_id)
            if idx >= 0:
                self.pCombo.setCurrentIndex(idx)
        self.updateStatus('Clip polygon created!')

    def _createSectionsLayer(self):
        """Create or recreate the sections memory layer"""
        try:
            crs = QgsProject.instance().crs().authid() or 'EPSG:4326'
            sections = QgsVectorLayer(f'LineString?crs={crs}', 'Sections', 'memory')
            dp = sections.dataProvider()
            dp.addAttributes([QgsField('label', QVariant.String)])
            sections.updateFields()
            QgsProject.instance().addMapLayer(sections)
            self.sections_layer_id = sections.id()
            sections.startEditing()

            # styling
            sym = QgsLineSymbol.createSimple({'line_style': 'dash', 'line_color': '0,0,0', 'line_width': '0.6'})
            m1 = QgsMarkerLineSymbolLayer()
            m1.setPlacement(QgsMarkerLineSymbolLayer.FirstVertex)
            m1.setRotateMarker(True)
            arr1 = QgsSimpleMarkerSymbolLayer.create({'name': 'arrowhead', 'size': '4', 'color': '0,0,0'})
            m1.subSymbol().changeSymbolLayer(0, arr1)
            sym.appendSymbolLayer(m1)
            m2 = QgsMarkerLineSymbolLayer()
            m2.setPlacement(QgsMarkerLineSymbolLayer.LastVertex)
            m2.setRotateMarker(True)
            arr2 = QgsSimpleMarkerSymbolLayer.create({'name': 'arrowhead', 'size': '4', 'color': '0,0,0'})
            m2.subSymbol().changeSymbolLayer(0, arr2)
            sym.appendSymbolLayer(m2)
            sections.renderer().setSymbol(sym)
            sections.triggerRepaint()

            # labeling
            pal = QgsPalLayerSettings()
            pal.fieldName = 'label'
            pal.isExpression = False
            pal.placement = QgsPalLayerSettings.Line
            fmt = QgsTextFormat()
            fmt.setFont(QFont('Arial', 8))
            pal.setFormat(fmt)
            lbl = QgsVectorLayerSimpleLabeling(pal)
            sections.setLabeling(lbl)
            sections.setLabelsEnabled(True)
            sections.triggerRepaint()
        except Exception as e:
            QtWidgets.QMessageBox.warning(None, 'Error', f'Error creating sections layer: {str(e)}')

    def _getSectionsLayer(self):
        """Get the sections layer, recreating it if it was deleted"""
        if self.sections_layer_id:
            layer = QgsProject.instance().mapLayer(self.sections_layer_id)
            if layer is not None:
                return layer
        # Layer was deleted, recreate it
        self._createSectionsLayer()
        return QgsProject.instance().mapLayer(self.sections_layer_id)

    def updateSectionCount(self):
        """Update the section count label"""
        layer = self._getSectionsLayer()
        if layer:
            count = layer.featureCount()
            self.secCountLabel.setText(f'Sections drawn: {count}')

    def startSections(self):
        """Start the section drawing tool"""
        sections = self._getSectionsLayer()
        if sections:
            tool = SectionTool(self.iface.mapCanvas(), sections, self)
            self.iface.mapCanvas().setMapTool(tool)
            self.updateStatus('Click two points to define a section')

    def chooseFolder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select output folder')
        if d:
            self.outEdit.setText(d)

    def emitProcess(self):
        """Validate inputs and emit process signal"""
        # Validate rasters
        ras = [QgsProject.instance().mapLayer(i.data(Qt_UserRole))
               for i in self.rList.selectedItems()]
        ras = [r for r in ras if r is not None]  # Filter out None values

        if not ras:
            QtWidgets.QMessageBox.warning(self, 'Warning', 'Select at least one raster to clip.')
            return

        # Validate polygon
        poly_id = self.pCombo.currentData()
        if not poly_id:
            QtWidgets.QMessageBox.warning(self, 'Warning', 'Select a clip polygon.')
            return

        poly = QgsProject.instance().mapLayer(poly_id)
        if poly is None:
            QtWidgets.QMessageBox.warning(self, 'Warning', 'The selected polygon is no longer available.')
            self.refreshPolygonList()
            return

        # Validate output folder
        out = self.outEdit.text()
        if not out:
            QtWidgets.QMessageBox.warning(self, 'Warning', 'Select an output folder.')
            return

        if not os.path.isdir(out):
            try:
                os.makedirs(out)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Error', f'Unable to create folder: {str(e)}')
                return

        # Get sections (optional)
        sections = None
        if self.createSectionsCheck.isChecked():
            sections = self._getSectionsLayer()

        self.processRequested.emit(ras, poly, out, sections)

    def generateAtlasLayout(self):
        """Generate a layout with Atlas enabled for sections"""
        try:
            # Find the sections layer
            sections_layer = self._getSectionsLayer() if self.createSectionsCheck.isChecked() else None

            # Also check for "Profili DEM" layer from profile_tool
            if not sections_layer or sections_layer.featureCount() == 0:
                for layer in QgsProject.instance().mapLayers().values():
                    if layer.name() == "Profili DEM" and layer.type() == QgsMapLayer.VectorLayer:
                        if layer.featureCount() > 0:
                            sections_layer = layer
                            break

            if not sections_layer or sections_layer.featureCount() == 0:
                QtWidgets.QMessageBox.warning(self, 'Warning',
                    'No sections found!\n\n'
                    'First create sections:\n'
                    '1. Enable "Create sections/profiles"\n'
                    '2. Click "Draw sections"\n'
                    '3. Click two points on the map for each section')
                return

            # Get selected raster for the layout
            selected_rasters = [QgsProject.instance().mapLayer(i.data(Qt_UserRole))
                               for i in self.rList.selectedItems()]
            selected_rasters = [r for r in selected_rasters if r is not None]

            if not selected_rasters:
                QtWidgets.QMessageBox.warning(self, 'Warning', 'Select at least one raster layer.')
                return

            raster_layer = selected_rasters[0]
            feature_count = sections_layer.featureCount()

            # Import required classes
            from qgis.core import (QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel,
                                   QgsLayoutItemPicture, QgsLayoutItemScaleBar, QgsLayoutSize,
                                   QgsLayoutPoint, QgsUnitTypes, QgsLayoutMeasurement,
                                   QgsLayoutAtlas, QgsLayoutObject, QgsProperty)
            from datetime import datetime

            # Create layout
            project = QgsProject.instance()
            layout_name = f"Atlas_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            layout = QgsPrintLayout(project)
            layout.initializeDefaults()
            layout.setName(layout_name)

            # Set page size (A3 Landscape)
            page = layout.pageCollection().page(0)
            page.setPageSize(QgsLayoutSize(420, 297, QgsUnitTypes.LayoutMillimeters))

            # Configure Atlas
            atlas = layout.atlas()
            atlas.setCoverageLayer(sections_layer)
            atlas.setEnabled(True)
            atlas.setFilenameExpression("'Section_' || \"label\"")
            atlas.setPageNameExpression("\"label\"")

            # ============================================================
            # A3 Landscape: 420mm x 297mm
            # Compact professional layout matching user's desired style
            # ============================================================

            from qgis.PyQt.QtGui import QFont

            # Page dimensions
            page_w = 420
            page_h = 297
            margin = 15  # margins from page edges

            # Layout structure (all within page bounds):
            # - Title: 12mm height
            # - Map + Right panel: 110mm height
            # - Profile: 110mm height
            # Total: 15 + 12 + 5 + 110 + 5 + 10 + 110 + 15 = ~282mm < 297mm OK

            # === TITLE ===
            title_y = margin
            title_h = 12
            title = QgsLayoutItemLabel(layout)
            title.setText("TOPOGRAPHIC SECTION  [% \"label\" %]")
            title.setFont(QFont("Arial", 16, QFont.Bold))
            title.attemptMove(QgsLayoutPoint(margin, title_y, QgsUnitTypes.LayoutMillimeters))
            title.attemptResize(QgsLayoutSize(page_w - 2*margin, title_h, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(title)

            # === MAP SECTION ===
            map_y = title_y + title_h + 5  # 32
            map_h = 110
            map_w = 250

            # Right panel position
            right_x = margin + map_w + 10  # 275
            right_w = page_w - right_x - margin  # 130

            # Main map
            map_item = QgsLayoutItemMap(layout)
            map_item.attemptMove(QgsLayoutPoint(margin, map_y, QgsUnitTypes.LayoutMillimeters))
            map_item.attemptResize(QgsLayoutSize(map_w, map_h, QgsUnitTypes.LayoutMillimeters))
            map_item.setExtent(raster_layer.extent())
            map_item.setFrameEnabled(True)
            map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))

            # Atlas: Auto scale to fit section line with small margin (0.05 = 5%)
            # This zooms the map to show the section line filling most of the frame
            map_item.setAtlasDriven(True)
            map_item.setAtlasScalingMode(QgsLayoutItemMap.Auto)
            map_item.setAtlasMargin(0.05)  # 5% margin - tight fit around section
            layout.addLayoutItem(map_item)

            # === RIGHT PANEL ===
            # North arrow (top right)
            north = QgsLayoutItemPicture(layout)
            north.setMode(QgsLayoutItemPicture.FormatSVG)
            north.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
            north.attemptMove(QgsLayoutPoint(right_x, map_y, QgsUnitTypes.LayoutMillimeters))
            north.attemptResize(QgsLayoutSize(25, 30, QgsUnitTypes.LayoutMillimeters))
            north.setFrameEnabled(True)
            layout.addLayoutItem(north)

            # Section info box
            info_label = QgsLayoutItemLabel(layout)
            info_label.setText(
                "SECTION INFO\n"
                "Label: [% \"label\" %]\n"
                "Page: [% @atlas_featurenumber %] / [% @atlas_totalfeatures %]"
            )
            info_label.setFont(QFont("Arial", 9))
            info_label.attemptMove(QgsLayoutPoint(right_x + 30, map_y, QgsUnitTypes.LayoutMillimeters))
            info_label.attemptResize(QgsLayoutSize(right_w - 30, 30, QgsUnitTypes.LayoutMillimeters))
            info_label.setFrameEnabled(True)
            info_label.setBackgroundEnabled(True)
            info_label.setBackgroundColor(QColor(255, 255, 255))
            layout.addLayoutItem(info_label)

            # Metadata box
            metadata_label = QgsLayoutItemLabel(layout)
            metadata_label.setText(
                f"Date: {datetime.now().strftime('%d/%m/%Y')}\n"
                f"CRS: {raster_layer.crs().authid()}\n"
                f"Raster: {raster_layer.name()}"
            )
            metadata_label.setFont(QFont("Arial", 8))
            metadata_label.attemptMove(QgsLayoutPoint(right_x, map_y + 35, QgsUnitTypes.LayoutMillimeters))
            metadata_label.attemptResize(QgsLayoutSize(right_w, 35, QgsUnitTypes.LayoutMillimeters))
            metadata_label.setFrameEnabled(True)
            metadata_label.setBackgroundEnabled(True)
            metadata_label.setBackgroundColor(QColor(255, 255, 255))
            layout.addLayoutItem(metadata_label)

            # Scale bar (adapts to segment - uses map's current scale)
            scalebar = QgsLayoutItemScaleBar(layout)
            scalebar.setLinkedMap(map_item)
            scalebar.setUnits(QgsUnitTypes.DistanceMeters)
            scalebar.setNumberOfSegments(2)
            scalebar.setNumberOfSegmentsLeft(0)
            scalebar.setStyle('Single Box')
            scalebar.setHeight(3)
            scalebar.attemptMove(QgsLayoutPoint(right_x, map_y + 75, QgsUnitTypes.LayoutMillimeters))
            scalebar.attemptResize(QgsLayoutSize(right_w, 15, QgsUnitTypes.LayoutMillimeters))
            # Let QGIS auto-calculate units per segment based on map scale
            scalebar.setUnitLabel('m')
            layout.addLayoutItem(scalebar)

            # === PROFILE SECTION ===
            profile_title_y = map_y + map_h + 5  # 147
            profile_y = profile_title_y + 10      # 157
            profile_h = page_h - profile_y - margin  # 125
            profile_w = page_w - 2 * margin       # 390

            # Profile title
            profile_title = QgsLayoutItemLabel(layout)
            profile_title.setText("ELEVATION PROFILE")
            profile_title.setFont(QFont("Arial", 11, QFont.Bold))
            profile_title.attemptMove(QgsLayoutPoint(margin, profile_title_y, QgsUnitTypes.LayoutMillimeters))
            profile_title.attemptResize(QgsLayoutSize(150, 8, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(profile_title)

            # Profile image
            profile_pic = QgsLayoutItemPicture(layout)

            save_dir = self.outEdit.text()
            if not save_dir:
                save_dir, _ = QgsProject.instance().readEntry("ClipRasterLayout", "profile_save_dir")
            if not save_dir:
                import tempfile
                save_dir = tempfile.gettempdir()

            save_dir = save_dir.replace('\\', '/')

            profile_pic.dataDefinedProperties().setProperty(
                QgsLayoutObject.PictureSource,
                QgsProperty.fromExpression(f"'{save_dir}/profile_' || \"label\" || '.png'")
            )

            profile_pic.attemptMove(QgsLayoutPoint(margin, profile_y, QgsUnitTypes.LayoutMillimeters))
            profile_pic.attemptResize(QgsLayoutSize(profile_w, profile_h, QgsUnitTypes.LayoutMillimeters))
            profile_pic.setFrameEnabled(True)
            profile_pic.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))
            profile_pic.setResizeMode(QgsLayoutItemPicture.Zoom)
            profile_pic.setBackgroundEnabled(True)
            profile_pic.setBackgroundColor(QColor(255, 255, 255))
            layout.addLayoutItem(profile_pic)

            # Add layout to project
            project.layoutManager().addLayout(layout)

            # Open layout designer
            self.iface.openLayoutDesigner(layout)

            self.updateStatus(f'Atlas layout created with {feature_count} sections!')

            QtWidgets.QMessageBox.information(self, 'Success',
                f'Atlas layout created!\n\n'
                f'Sections: {feature_count}\n\n'
                f'In Layout Designer:\n'
                f'- Use Atlas toolbar to preview pages\n'
                f'- Export → Export as PDF to generate all pages')

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Error creating Atlas layout: {str(e)}')
            import traceback
            traceback.print_exc()

    def closeEvent(self, event):
        """Disconnect signals on close"""
        try:
            QgsProject.instance().layersAdded.disconnect(self.onLayersChanged)
            QgsProject.instance().layersRemoved.disconnect(self.onLayersChanged)
        except:
            pass
        super().closeEvent(event)


class SectionTool(QgsMapTool):
    def __init__(self, canvas, layer, dock_widget=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.dock_widget = dock_widget
        self.rb = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.rb.setColor(QColor(255, 0, 0))
        self.rb.setWidth(2)
        self.points = []

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt_CrossCursor)

    def canvasPressEvent(self, e):
        if e.button() == Qt_LeftButton:
            p = self.toMapCoordinates(e.pos())
            self.points.append(p)
            self.rb.addPoint(p, True)
            if len(self.points) == 2:
                try:
                    feat = QgsFeature(self.layer.fields())
                    feat.setGeometry(QgsGeometry.fromPolylineXY(self.points))
                    idx = self.layer.featureCount() + 1
                    lbl = f"{chr(64 + 2 * idx - 1)}-{chr(64 + 2 * idx)}"
                    feat.setAttribute('label', lbl)
                    self.layer.addFeature(feat)
                    self.layer.updateExtents()
                    self.canvas.refresh()
                    if self.dock_widget:
                        self.dock_widget.updateSectionCount()
                        self.dock_widget.updateStatus(f'Section {lbl} created')
                except Exception as e:
                    QtWidgets.QMessageBox.warning(None, 'Error', f'Error creating section: {str(e)}')
                finally:
                    self.rb.reset(QgsWkbTypes.LineGeometry)
                    self.points = []
        elif e.button() == Qt_RightButton:
            # Cancel current drawing
            self.rb.reset(QgsWkbTypes.LineGeometry)
            self.points = []

    def deactivate(self):
        self.rb.reset(QgsWkbTypes.LineGeometry)
        super().deactivate()


class PolygonDrawTool(QgsMapTool):
    """Tool for drawing clip polygons"""
    def __init__(self, canvas, layer, dock_widget=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.dock_widget = dock_widget
        self.rb = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rb.setColor(QColor(255, 0, 0, 100))
        self.rb.setWidth(2)
        self.points = []

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt_CrossCursor)

    def canvasPressEvent(self, e):
        if e.button() == Qt_LeftButton:
            p = self.toMapCoordinates(e.pos())
            self.points.append(p)
            self.rb.addPoint(p, True)
        elif e.button() == Qt_RightButton:
            # Finish polygon
            self.finishPolygon()

    def canvasDoubleClickEvent(self, e):
        """Finish polygon on double-click"""
        self.finishPolygon()

    def finishPolygon(self):
        """Create the polygon feature"""
        if len(self.points) >= 3:
            try:
                # Close the polygon
                self.points.append(self.points[0])
                feat = QgsFeature(self.layer.fields())
                feat.setGeometry(QgsGeometry.fromPolygonXY([self.points]))
                feat.setAttribute('name', f'Clip_{self.layer.featureCount() + 1}')
                self.layer.addFeature(feat)
                self.layer.updateExtents()
                self.layer.commitChanges()
                self.layer.startEditing()
                self.canvas.refresh()
                if self.dock_widget:
                    self.dock_widget.onPolygonDrawn()
            except Exception as e:
                QtWidgets.QMessageBox.warning(None, 'Error', f'Error creating polygon: {str(e)}')
        else:
            if self.dock_widget:
                self.dock_widget.updateStatus('At least 3 points are needed to create a polygon')

        self.rb.reset(QgsWkbTypes.PolygonGeometry)
        self.points = []
        self.canvas.unsetMapTool(self)

    def keyPressEvent(self, e):
        if e.key() == Qt_Key_Escape:
            self.rb.reset(QgsWkbTypes.PolygonGeometry)
            self.points = []
            self.canvas.unsetMapTool(self)
            if self.dock_widget:
                self.dock_widget.updateStatus('Drawing cancelled')

    def deactivate(self):
        self.rb.reset(QgsWkbTypes.PolygonGeometry)
        super().deactivate()


class TutorialDialog(QtWidgets.QDialog):
    """Tutorial dialog with usage instructions"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Tutorial - Clip & Profile')
        self.setMinimumSize(500, 400)
        self.setupUi()

    def setupUi(self):
        layout = QtWidgets.QVBoxLayout()

        # Tab widget for different sections
        tabs = QtWidgets.QTabWidget()

        # Quick Start tab
        quick_tab = QtWidgets.QWidget()
        quick_layout = QtWidgets.QVBoxLayout()
        quick_text = QtWidgets.QTextBrowser()
        quick_text.setHtml('''
        <h2>Quick Start Guide</h2>
        <ol>
            <li><b>Select rasters</b> - Choose one or more DEM rasters from the list</li>
            <li><b>Choose clip polygon</b> - Select an existing polygon or create a new one</li>
            <li><b>Sections (optional)</b> - Enable and draw sections for topographic profiles</li>
            <li><b>Output folder</b> - Select where to save the results</li>
            <li><b>Execute</b> - Click "Run Clip"</li>
        </ol>
        ''')
        quick_layout.addWidget(quick_text)
        quick_tab.setLayout(quick_layout)
        tabs.addTab(quick_tab, 'Quick Start')

        # Draw Polygon tab
        poly_tab = QtWidgets.QWidget()
        poly_layout = QtWidgets.QVBoxLayout()
        poly_text = QtWidgets.QTextBrowser()
        poly_text.setHtml('''
        <h2>Drawing a Clip Polygon</h2>
        <ol>
            <li>Click on <b>"Draw new clip polygon"</b></li>
            <li><b>Left-click</b> on the map to add vertices</li>
            <li><b>Double-click</b> or <b>right-click</b> to finish</li>
            <li>Press <b>ESC</b> to cancel</li>
        </ol>
        <p><i>The polygon will be automatically selected for clipping.</i></p>
        ''')
        poly_layout.addWidget(poly_text)
        poly_tab.setLayout(poly_layout)
        tabs.addTab(poly_tab, 'Polygon')

        # Sections tab
        sec_tab = QtWidgets.QWidget()
        sec_layout = QtWidgets.QVBoxLayout()
        sec_text = QtWidgets.QTextBrowser()
        sec_text.setHtml('''
        <h2>Creating Topographic Sections</h2>
        <ol>
            <li>Enable <b>"Create sections/profiles"</b></li>
            <li>Click on <b>"Draw sections"</b></li>
            <li><b>Left-click</b> for the start point (A)</li>
            <li><b>Left-click</b> for the end point (B)</li>
            <li>The section is created automatically (A-B, C-D, etc.)</li>
            <li><b>Right-click</b> to cancel the current section</li>
        </ol>
        <p><i>Sections are optional. You can clip rasters without creating sections.</i></p>
        ''')
        sec_layout.addWidget(sec_text)
        sec_tab.setLayout(sec_layout)
        tabs.addTab(sec_tab, 'Sections')

        # Tips tab
        tips_tab = QtWidgets.QWidget()
        tips_layout = QtWidgets.QVBoxLayout()
        tips_text = QtWidgets.QTextBrowser()
        tips_text.setHtml('''
        <h2>Tips</h2>
        <ul>
            <li>Layer lists update automatically when you add/remove layers</li>
            <li>Use the <b>"Refresh"</b> button if lists are not updated</li>
            <li>You can select multiple rasters by holding <b>Ctrl</b></li>
            <li>Clipped rasters are saved with the original name prefix + "_clipped"</li>
            <li>For full DEM profile, use the separate "Create DEM Profile" tool</li>
        </ul>
        ''')
        tips_layout.addWidget(tips_text)
        tips_tab.setLayout(tips_layout)
        tabs.addTab(tips_tab, 'Tips')

        layout.addWidget(tabs)

        # Close button
        close_btn = QtWidgets.QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)
