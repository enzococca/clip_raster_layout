# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import Qt, QPointF, pyqtSignal, QVariant, QSizeF
from qgis.PyQt.QtGui import QColor, QPen, QFont, QPolygonF, QTextDocument
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QFileDialog, QLineEdit, QHBoxLayout, QMessageBox, QDockWidget, QWidget, QAction, QTabWidget
from qgis.core import (QgsPointXY, QgsGeometry, QgsFeature,
                      QgsVectorLayer, QgsProject, QgsWkbTypes, QgsField,
                      QgsFields, QgsCoordinateTransform, QgsRasterLayer,
                      QgsLineString, QgsPoint, QgsRaster, QgsRasterIdentifyResult,
                      QgsSymbol, QgsSimpleLineSymbolLayer, QgsMarkerSymbol,
                      QgsSimpleMarkerSymbolLayer, QgsTextAnnotation, QgsMessageLog, Qgis)

# Try to import elevation profile tools (QGIS 3.26+)
try:
    from qgis.gui import QgsElevationProfileCanvas, QgsElevationProfilePlotItem
    from qgis.core import QgsProfileRequest, QgsProfilePlotRenderer
    HAS_ELEVATION_PROFILE = True
except ImportError:
    HAS_ELEVATION_PROFILE = False
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand, QgsMapCanvas, QgsMapTool, QgsMapCanvasAnnotationItem
import numpy as np
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import string

class ProfileTool(QgsMapTool):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        super().__init__(self.canvas)
        
        self.rubberBand = None
        self.start_point = None
        self.profile_count = 0
        self.profiles = []
        self.dem_layer = None
        self.profile_layer = None
        self.labels = []
        self.current_feature_id = None
        self.elevation_profiles = []  # Store QGIS elevation profile widgets
        self.profile_dock = None  # Single dock widget for all profiles
        
        # Create profile layer
        self.create_profile_layer()
        
    def create_profile_layer(self):
        # Create memory layer for profiles using project CRS
        project_crs = QgsProject.instance().crs()
        crs_string = project_crs.authid() if project_crs.isValid() else "EPSG:4326"
        self.profile_layer = QgsVectorLayer(
            f"LineString?crs={crs_string}&field=id:integer&field=name:string&field=length_2d:double&field=length_3d:double&field=elev_a:double&field=elev_b:double", 
            "Profili DEM", "memory")
        
        # Set dashed line style with arrows
        symbol = self.profile_layer.renderer().symbol()
        symbol.deleteSymbolLayer(0)
        
        # Black dashed line
        line_layer = QgsSimpleLineSymbolLayer()
        line_layer.setWidth(0.3)
        line_layer.setColor(QColor(0, 0, 0))  # Black
        line_layer.setPenStyle(Qt.DashLine)
        line_layer.setCustomDashVector([5, 3])
        symbol.appendSymbolLayer(line_layer)
        
        # Simple marker symbols for start and end points will be added via labels
        
        QgsProject.instance().addMapLayer(self.profile_layer)
        
    def activate(self):
        # Select DEM layer if not already selected
        if not self.dem_layer:
            dlg = DemSelectionDialog(self.iface)
            if dlg.exec_():
                self.dem_layer = dlg.selected_layer
                self.canvas.setMapTool(self)
        else:
            self.canvas.setMapTool(self)
        
    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        
        if self.start_point is None:
            # First click - start point
            self.start_point = point
            self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
            self.rubberBand.setColor(QColor(255, 0, 0))
            self.rubberBand.setWidth(2)
            self.rubberBand.setLineStyle(Qt.DashLine)
            self.rubberBand.addPoint(QgsPointXY(self.start_point))
        else:
            # Second click - end point
            end_point = point
            
            # Calculate 2D length
            line = QgsLineString([QgsPoint(self.start_point), QgsPoint(end_point)])
            length_2d = line.length()
            
            # Get elevations at start and end points
            if self.dem_layer:
                transform = QgsCoordinateTransform(
                    self.canvas.mapSettings().destinationCrs(),
                    self.dem_layer.crs(),
                    QgsProject.instance()
                )
                
                # Transform points if needed
                start_trans = self.start_point
                end_trans = end_point
                if transform.isValid():
                    start_trans = transform.transform(self.start_point)
                    end_trans = transform.transform(end_point)
                
                # Get elevation at start point
                result_a = self.dem_layer.dataProvider().identify(
                    start_trans,
                    QgsRaster.IdentifyFormatValue
                )
                elev_a = 0
                if result_a.isValid():
                    value = list(result_a.results().values())[0]
                    if value is not None and not np.isnan(value):
                        elev_a = value
                
                # Get elevation at end point
                result_b = self.dem_layer.dataProvider().identify(
                    end_trans,
                    QgsRaster.IdentifyFormatValue
                )
                elev_b = 0
                if result_b.isValid():
                    value = list(result_b.results().values())[0]
                    if value is not None and not np.isnan(value):
                        elev_b = value
            else:
                elev_a = 0
                elev_b = 0
            
            # Create profile line feature
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolylineXY([self.start_point, end_point]))
            
            # Set attributes including calculated values
            letter_pair = self.get_next_letter_pair()
            # Note: length_3d will be calculated after profile extraction
            feature.setAttributes([self.profile_count, letter_pair, float(length_2d), 0.0, float(elev_a), float(elev_b)])
            
            # Add to layer and get the new feature id
            success, features = self.profile_layer.dataProvider().addFeatures([feature])
            if success and features:
                self.current_feature_id = features[0].id()
            else:
                self.current_feature_id = None
                
            self.profile_layer.updateExtents()
            self.profile_layer.triggerRepaint()
            
            # Store profile info for later update
            self.current_profile_info = {
                'feature_id': self.current_feature_id,
                'profile_count': self.profile_count
            }
            
            # Add labels
            self.add_labels(self.start_point, end_point, letter_pair)
            
            # Extract and show profile (will update length_3d)
            self.extract_profile(self.start_point, end_point, letter_pair)
            
            # Store geometry for later use with elevation profile
            QgsProject.instance().writeEntry("ClipRasterLayout", f"profile_geom_{letter_pair}", feature.geometry().asWkt())
            
            # Reset
            self.canvas.scene().removeItem(self.rubberBand)
            self.rubberBand = None
            self.start_point = None
            self.profile_count += 1
            
    def canvasMoveEvent(self, event):
        if self.start_point and self.rubberBand:
            point = self.toMapCoordinates(event.pos())
            self.rubberBand.reset(QgsWkbTypes.LineGeometry)
            self.rubberBand.addPoint(QgsPointXY(self.start_point))
            self.rubberBand.addPoint(QgsPointXY(point))
            
    def get_next_letter_pair(self):
        letters = string.ascii_uppercase
        if self.profile_count < 13:  # A-B through Y-Z
            return f"{letters[self.profile_count*2]}-{letters[self.profile_count*2+1]}"
        else:
            # Use AA-AB, AC-AD, etc.
            idx = self.profile_count - 13
            return f"{letters[idx//26]}{letters[idx%26]}-{letters[idx//26]}{letters[(idx%26)+1]}"
            
    def add_labels(self, start_point, end_point, letter_pair):
        # Add text annotations for start and end points with arrow indicators
        letters = letter_pair.split('-')
        
        # Start point label with arrow →
        start_annotation = QgsTextAnnotation()
        start_doc = QTextDocument()
        start_doc.setHtml(f"<b>→ {letters[0]}</b>")
        start_annotation.setDocument(start_doc)
        start_annotation.setMapPosition(start_point)
        start_annotation.setMapPositionCrs(self.canvas.mapSettings().destinationCrs())
        start_annotation.setFrameSize(QSizeF(30, 20))
        
        start_item = QgsMapCanvasAnnotationItem(start_annotation, self.canvas)
        self.labels.append(start_item)
        
        # End point label with arrow →
        end_annotation = QgsTextAnnotation()
        end_doc = QTextDocument()
        end_doc.setHtml(f"<b>{letters[1]} ←</b>")
        end_annotation.setDocument(end_doc)
        end_annotation.setMapPosition(end_point)
        end_annotation.setMapPositionCrs(self.canvas.mapSettings().destinationCrs())
        end_annotation.setFrameSize(QSizeF(30, 20))
        
        end_item = QgsMapCanvasAnnotationItem(end_annotation, self.canvas)
        self.labels.append(end_item)
        
    def extract_profile(self, start_point, end_point, name):
        if not self.dem_layer:
            return
            
        # Create points along the line
        line = QgsLineString([QgsPoint(start_point), QgsPoint(end_point)])
        length = line.length()
        
        # Sample every meter (or adjust based on length)
        sample_interval = min(1.0, length / 1000)  # Max 1000 points
        distances = np.arange(0, length, sample_interval)
        
        elevations = []
        valid_distances = []
        
        # Transform to DEM CRS if needed
        transform = QgsCoordinateTransform(
            self.canvas.mapSettings().destinationCrs(),
            self.dem_layer.crs(),
            QgsProject.instance()
        )
        
        for dist in distances:
            point = line.interpolatePoint(dist)
            point_xy = QgsPointXY(point)
            
            # Transform point
            if transform.isValid():
                point_xy = transform.transform(point_xy)
                
            # Get elevation
            result = self.dem_layer.dataProvider().identify(
                point_xy,
                QgsRaster.IdentifyFormatValue
            )
            
            if result.isValid():
                value = list(result.results().values())[0]
                if value is not None and not np.isnan(value):
                    elevations.append(value)
                    valid_distances.append(dist)
                    
        # Create profile plot
        if elevations:
            # Calculate 3D length
            length_3d = 0.0
            if len(valid_distances) > 1:
                for i in range(1, len(valid_distances)):
                    dx = float(valid_distances[i] - valid_distances[i-1])
                    dz = float(elevations[i] - elevations[i-1])
                    length_3d += math.sqrt(dx*dx + dz*dz)
            
            # Update feature with 3D length
            if hasattr(self, 'current_profile_info') and self.current_profile_info:
                # Find feature by profile count (more reliable than feature id)
                for feature in self.profile_layer.getFeatures():
                    if feature['id'] == self.current_profile_info['profile_count']:
                        self.profile_layer.startEditing()
                        # Update length_3d field (index 3) - ensure it's a Python float
                        self.profile_layer.changeAttributeValue(feature.id(), 3, float(length_3d))
                        self.profile_layer.commitChanges()
                        QgsMessageLog.logMessage(f"Updated profile {feature['name']} with 3D length: {length_3d:.2f}m", "ClipRasterLayout", Qgis.Info)
                        break
            
            self.create_profile_plot(valid_distances, elevations, name)
            
    def create_profile_plot(self, distances, elevations, name):
        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot profile
        ax.plot(distances, elevations, 'b-', linewidth=2)
        ax.fill_between(distances, elevations, alpha=0.3)
        
        # Set y-axis limits with margin
        min_elev = min(elevations)
        max_elev = max(elevations)
        elev_range = max_elev - min_elev
        
        # Add 10% margin on top and bottom
        margin = elev_range * 0.1 if elev_range > 0 else 1
        ax.set_ylim(min_elev - margin, max_elev + margin)
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Labels
        ax.set_xlabel('Distanza (m)', fontsize=12)
        ax.set_ylabel('Elevazione (m)', fontsize=12)
        ax.set_title(f'Profilo Topografico {name}', fontsize=14, fontweight='bold')
        
        # Add min/max annotations
        min_elev = min(elevations)
        max_elev = max(elevations)
        min_idx = elevations.index(min_elev)
        max_idx = elevations.index(max_elev)
        
        ax.annotate(f'Min: {min_elev:.1f}m', 
                   xy=(distances[min_idx], min_elev),
                   xytext=(10, 10), textcoords='offset points',
                   ha='left', fontsize=10,
                   bbox=dict(boxstyle='round,pad=0.3', fc='yellow', alpha=0.7))
                   
        ax.annotate(f'Max: {max_elev:.1f}m', 
                   xy=(distances[max_idx], max_elev),
                   xytext=(10, -10), textcoords='offset points',
                   ha='left', fontsize=10,
                   bbox=dict(boxstyle='round,pad=0.3', fc='yellow', alpha=0.7))
        
        # Show plot
        plt.tight_layout()
        
        # Save plot to user-specified directory or temp
        import tempfile
        import os
        
        # Get save directory from project custom properties
        save_dir, _ = QgsProject.instance().readEntry("ClipRasterLayout", "profile_save_dir")
        if not save_dir or not os.path.exists(save_dir):
            # Ask user for directory
            dlg = ProfileSaveDialog()
            if dlg.exec_():
                save_dir = dlg.selected_path
                # Save for future use
                QgsProject.instance().writeEntry("ClipRasterLayout", "profile_save_dir", save_dir)
            else:
                # Use temp directory as fallback
                save_dir = tempfile.gettempdir()
        
        profile_path = os.path.join(save_dir, f"profile_{name}.png")
        fig.savefig(profile_path, dpi=300, bbox_inches='tight')
        
        # Debug: log where the file was saved
        QgsMessageLog.logMessage(f"Profile saved to: {profile_path}", "ClipRasterLayout", Qgis.Info)
        QgsMessageLog.logMessage(f"File exists: {os.path.exists(profile_path)}", "ClipRasterLayout", Qgis.Info)
        
        # Store profile data
        profile_data = {'name': name, 'figure': fig, 'distances': distances, 'elevations': elevations, 'image_path': profile_path}
        self.profiles.append(profile_data)
        
        # Store profile path in project custom properties
        QgsProject.instance().writeEntry("ClipRasterLayout", f"profile_{name}", profile_path)
        
        # Create or update profile dock widget
        try:
            if self.profile_dock is None:
                # Create the main dock widget if it doesn't exist
                self.profile_dock = ProfileTabDockWidget(self.iface)
                self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.profile_dock)
                self.profile_dock.show()
                QgsMessageLog.logMessage("Created main profile dock widget", "ClipRasterLayout", Qgis.Info)
            
            # Add new tab with the profile
            canvas = FigureCanvas(fig)
            self.profile_dock.add_profile_tab(canvas, name)
            
            QgsMessageLog.logMessage(f"Added profile tab for {name}", "ClipRasterLayout", Qgis.Info)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Failed to create/update dock widget: {str(e)}", "ClipRasterLayout", Qgis.Warning)
            # Fallback to dialog
            try:
                dlg = ProfileDialog(fig, name)
                dlg.show()
                QgsMessageLog.logMessage(f"Created profile dialog for {name} as fallback", "ClipRasterLayout", Qgis.Info)
            except Exception as e2:
                QgsMessageLog.logMessage(f"Failed to create profile dialog: {str(e2)}", "ClipRasterLayout", Qgis.Critical)
        
        
class DemSelectionDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.selected_layer = None
        self.setupUi()
        
    def setupUi(self):
        self.setWindowTitle("Seleziona DEM")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Seleziona il layer DEM:"))
        
        self.layer_combo = QComboBox()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                self.layer_combo.addItem(layer.name(), layer)
                
        layout.addWidget(self.layer_combo)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)
        
        self.setLayout(layout)
        
    def accept(self):
        self.selected_layer = self.layer_combo.currentData()
        super().accept()
        
class ProfileSaveDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleziona cartella per salvare i profili")
        self.selected_path = None
        self.setupUi()
        
    def setupUi(self):
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Seleziona dove salvare le immagini dei profili:"))
        
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        path_layout.addWidget(self.path_edit)
        
        browse_button = QPushButton("Sfoglia...")
        browse_button.clicked.connect(self.browse_folder)
        path_layout.addWidget(browse_button)
        
        layout.addLayout(path_layout)
        
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Annulla")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleziona cartella")
        if folder:
            self.path_edit.setText(folder)
            
    def accept(self):
        if self.path_edit.text():
            self.selected_path = self.path_edit.text()
            super().accept()
        else:
            QMessageBox.warning(self, "Attenzione", "Seleziona una cartella")

class ProfileTabDockWidget(QDockWidget):
    def __init__(self, iface, parent=None):
        super().__init__("Profili DEM", parent)
        self.iface = iface
        
        # Set object name for saving state
        self.setObjectName("ProfileTabDock")
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create main widget
        widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.tab_widget)
        
        # Add button bar
        button_layout = QHBoxLayout()
        
        # Add close all button
        close_all_btn = QPushButton("Chiudi tutti")
        close_all_btn.clicked.connect(self.close_all_profiles)
        button_layout.addWidget(close_all_btn)
        
        # Add elevation profile button
        elevation_btn = QPushButton("Apri Profilo Elevazione QGIS")
        elevation_btn.clicked.connect(self.open_elevation_profile)
        button_layout.addWidget(elevation_btn)
        
        # Add create all profiles button
        all_profiles_btn = QPushButton("Crea tutti i Profili Elevazione")
        all_profiles_btn.setToolTip("Crea un profilo elevazione QGIS per ogni sezione tracciata")
        all_profiles_btn.clicked.connect(self.create_all_elevation_profiles)
        button_layout.addWidget(all_profiles_btn)
        
        layout.addLayout(button_layout)
        
        widget.setLayout(layout)
        self.setWidget(widget)
        
        # Set size
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        # Allow docking on all sides
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        
    def add_profile_tab(self, canvas, name):
        """Add a new profile tab"""
        # Create widget for the tab
        tab_widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(canvas)
        tab_widget.setLayout(layout)
        
        # Add tab
        self.tab_widget.addTab(tab_widget, name)
        
        # Switch to new tab
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
        
    def close_all_profiles(self):
        """Close all profile tabs"""
        self.tab_widget.clear()
        
    def open_elevation_profile(self):
        """Open QGIS elevation profile panel and create profiles for all sections"""
        try:
            # First open the elevation profile panel
            opened = False
            
            # Try to find and trigger the elevation profile action
            actions = self.iface.mainWindow().findChildren(QAction)
            for action in actions:
                if 'elevation' in action.text().lower() and 'profile' in action.text().lower():
                    action.trigger()
                    opened = True
                    QgsMessageLog.logMessage("Triggered elevation profile action", "ClipRasterLayout", Qgis.Info)
                    break
                    
            if not opened:
                # Alternative: try through View menu
                view_menu = None
                for action in self.iface.mainWindow().menuBar().actions():
                    if action.text().lower() == 'view' or 'vista' in action.text().lower():
                        view_menu = action.menu()
                        break
                        
                if view_menu:
                    for action in view_menu.actions():
                        if action.menu():  # Panels submenu
                            for subaction in action.menu().actions():
                                if 'elevation' in subaction.text().lower() and 'profile' in subaction.text().lower():
                                    subaction.trigger()
                                    opened = True
                                    QgsMessageLog.logMessage("Triggered elevation profile through View menu", "ClipRasterLayout", Qgis.Info)
                                    break
            
            if not opened:
                QgsMessageLog.logMessage("Could not find elevation profile action", "ClipRasterLayout", Qgis.Warning)
                                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error opening elevation profile: {str(e)}", "ClipRasterLayout", Qgis.Warning)
    
    def create_all_elevation_profiles(self):
        """Create elevation profiles for all sections in the profile layer"""
        try:
            QgsMessageLog.logMessage("Starting creation of all elevation profiles...", "ClipRasterLayout", Qgis.Info)
            
            # Get the profile layer
            profile_layer = None
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Profili DEM":
                    profile_layer = layer
                    break
            
            if not profile_layer:
                QgsMessageLog.logMessage("Profile layer not found", "ClipRasterLayout", Qgis.Warning)
                return
            
            # Import necessary classes for creating multiple profile views
            from qgis.PyQt.QtCore import QTimer
            try:
                from qgis.gui import QgsElevationProfileCanvas
                from qgis.core import QgsCurve
            except ImportError:
                QgsMessageLog.logMessage("QGIS version does not support elevation profile API", "ClipRasterLayout", Qgis.Warning)
                return
            
            # Get all profile features
            profile_features = list(profile_layer.getFeatures())
            
            # Create a profile widget for each section
            def create_next_profile(index=0):
                if index >= len(profile_features):
                    QgsMessageLog.logMessage(f"Created {len(profile_features)} elevation profiles", "ClipRasterLayout", Qgis.Info)
                    return
                
                feature = profile_features[index]
                profile_name = feature['name']
                geometry = feature.geometry()
                
                try:
                    # Create new elevation profile canvas
                    profile_canvas = QgsElevationProfileCanvas()
                    profile_canvas.setWindowTitle(f"Profilo Elevazione {profile_name}")
                    
                    # Set the profile curve from the geometry
                    if geometry and geometry.type() == QgsWkbTypes.LineGeometry:
                        # Convert geometry to curve
                        curve = geometry.constGet()
                        if curve:
                            profile_canvas.setProfileCurve(curve)
                        else:
                            QgsMessageLog.logMessage(f"Could not get curve from geometry for {profile_name}", "ClipRasterLayout", Qgis.Warning)
                        
                        # Set CRS
                        profile_canvas.setCrs(profile_layer.crs())
                        
                        # Add layers (DEM)
                        dem_layers = []
                        for layer in QgsProject.instance().mapLayers().values():
                            if isinstance(layer, QgsRasterLayer) and layer.bandCount() == 1:
                                if 'dem' in layer.name().lower() or 'dtm' in layer.name().lower():
                                    dem_layers.append(layer)
                        
                        if dem_layers:
                            profile_canvas.setLayers(dem_layers)
                            QgsMessageLog.logMessage(f"Added {len(dem_layers)} DEM layers to profile {profile_name}", "ClipRasterLayout", Qgis.Info)
                        
                        # Show the profile
                        profile_canvas.show()
                        profile_canvas.refresh()
                        
                        # Store reference for layout
                        QgsProject.instance().writeEntry("ClipRasterLayout", f"elevation_profile_{profile_name}", "created")
                        
                        QgsMessageLog.logMessage(f"Created elevation profile for {profile_name}", "ClipRasterLayout", Qgis.Info)
                    
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error creating profile for {profile_name}: {str(e)}", "ClipRasterLayout", Qgis.Warning)
                
                # Create next profile after a delay
                QTimer.singleShot(100, lambda: create_next_profile(index + 1))
            
            # Start creating profiles
            QTimer.singleShot(500, lambda: create_next_profile(0))
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in create_all_elevation_profiles: {str(e)}", "ClipRasterLayout", Qgis.Warning)

class ProfileDockWidget(QDockWidget):
    def __init__(self, figure, name, iface, parent=None):
        super().__init__(f"Profilo {name}", parent)
        self.iface = iface
        self.name = name
        
        # Set object name for saving state
        self.setObjectName(f"ProfileDock_{name}")
        
        # Create widget to hold the plot
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Add matplotlib canvas
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)
        
        # Add close button
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        widget.setLayout(layout)
        self.setWidget(widget)
        
        # Set size
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        
        # Allow docking on all sides
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        
        # Make it floating by default if preferred
        self.setFloating(False)

class ProfileDialog(QDialog):
    def __init__(self, figure, name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Profilo {name}")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)
        
        # Add close button
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)