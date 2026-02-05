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
        self.profile_features_to_process = []  # For sequential processing
        self.current_profile_index = 0
        
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
        self.elevation_profiles = []  # Store references to elevation profile windows
        
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
        all_profiles_btn = QPushButton("Prepara Profili per Layout")
        all_profiles_btn.setToolTip("Prepara i profili elevazione per l'uso nel layout")
        all_profiles_btn.clicked.connect(self.prepare_profiles_for_layout)
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
    
    def prepare_profiles_for_layout(self):
        """Open elevation profile panels sequentially and configure them"""
        try:
            from qgis.PyQt.QtCore import QTimer
            
            QgsMessageLog.logMessage("Starting sequential profile creation...", "ClipRasterLayout", Qgis.Info)
            
            # Get the profile layer
            profile_layer = None
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Profili DEM":
                    profile_layer = layer
                    break
            
            if not profile_layer:
                QgsMessageLog.logMessage("Profile layer not found", "ClipRasterLayout", Qgis.Warning)
                return
            
            # Get all profile features
            self.profile_features_to_process = list(profile_layer.getFeatures())
            self.current_profile_index = 0
            
            if not self.profile_features_to_process:
                QgsMessageLog.logMessage("No profiles found to process", "ClipRasterLayout", Qgis.Warning)
                return
            
            # Show instruction dialog
            QMessageBox.information(None, "Creazione Profili Elevazione", 
                f"Verranno creati {len(self.profile_features_to_process)} profili elevazione.\n\n"
                "Per ogni profilo:\n"
                "1. Si aprirà il pannello Profilo Elevazione\n"
                "2. Seleziona la sezione corrispondente nel pannello\n"
                "3. Il profilo verrà rinominato automaticamente\n\n"
                "Clicca OK per iniziare.")
            
            # Start processing first profile
            self.process_next_profile()
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error preparing profiles: {str(e)}", "ClipRasterLayout", Qgis.Warning)
    
    def process_next_profile(self):
        """Process the next profile in the sequence"""
        try:
            from qgis.PyQt.QtCore import QTimer
            
            if self.current_profile_index >= len(self.profile_features_to_process):
                # All profiles processed
                QgsMessageLog.logMessage(f"Completed processing {len(self.profile_features_to_process)} profiles", "ClipRasterLayout", Qgis.Info)
                QMessageBox.information(None, "Profili Completati", 
                    f"Tutti i {len(self.profile_features_to_process)} profili sono stati creati.\n\n"
                    "Ora puoi generare il layout.")
                return
            
            feature = self.profile_features_to_process[self.current_profile_index]
            profile_name = feature['name']
            
            QgsMessageLog.logMessage(f"Processing profile {self.current_profile_index + 1}/{len(self.profile_features_to_process)}: {profile_name}", "ClipRasterLayout", Qgis.Info)
            
            # Open elevation profile panel
            self.open_elevation_profile()
            
            # Give time for the panel to open, then configure it
            QTimer.singleShot(1000, lambda: self.configure_current_profile(feature))
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error processing profile: {str(e)}", "ClipRasterLayout", Qgis.Warning)
    
    def configure_current_profile(self, feature):
        """Configure the current elevation profile"""
        try:
            from qgis.PyQt.QtCore import QTimer
            from qgis.PyQt.QtWidgets import QWidget, QToolButton, QCheckBox, QTreeWidget, QTreeWidgetItem
            
            profile_name = feature['name']
            geometry = feature.geometry()
            
            # Find the elevation profile dock
            elevation_dock = None
            elevation_canvas = None
            
            for dock in self.iface.mainWindow().findChildren(QDockWidget):
                if 'elevation' in dock.windowTitle().lower() and 'profile' in dock.windowTitle().lower():
                    elevation_dock = dock
                    # Look for the elevation profile canvas inside the dock
                    if HAS_ELEVATION_PROFILE:
                        for canvas in dock.findChildren(QgsElevationProfileCanvas):
                            elevation_canvas = canvas
                            break
                    break
            
            if elevation_dock:
                # 1. Rename the dock with section name
                old_title = elevation_dock.windowTitle()
                elevation_dock.setWindowTitle(f"Profilo Elevazione {profile_name}")
                QgsMessageLog.logMessage(f"Renamed profile dock from '{old_title}' to: 'Profilo Elevazione {profile_name}'", "ClipRasterLayout", Qgis.Info)
                
                # Force update of the dock title
                elevation_dock.update()
                elevation_dock.repaint()
                
                # 2. Configure layer checkboxes - enable only the DEM used
                try:
                    # Find the layer tree widget in the elevation profile dock
                    tree_widgets = elevation_dock.findChildren(QTreeWidget)
                    if tree_widgets:
                        tree = tree_widgets[0]
                        QgsMessageLog.logMessage(f"Found layer tree widget with {tree.topLevelItemCount()} items", "ClipRasterLayout", Qgis.Info)
                        
                        # First, uncheck all items
                        for i in range(tree.topLevelItemCount()):
                            item = tree.topLevelItem(i)
                            if item.checkState(0) == Qt.Checked:
                                item.setCheckState(0, Qt.Unchecked)
                        
                        # Then check only the DEM layer
                        if self.dem_layer:
                            dem_name = self.dem_layer.name()
                            for i in range(tree.topLevelItemCount()):
                                item = tree.topLevelItem(i)
                                if item.text(0) == dem_name:
                                    item.setCheckState(0, Qt.Checked)
                                    QgsMessageLog.logMessage(f"Enabled DEM layer: {dem_name}", "ClipRasterLayout", Qgis.Info)
                                    break
                except Exception as e:
                    QgsMessageLog.logMessage(f"Could not configure layer checkboxes: {str(e)}", "ClipRasterLayout", Qgis.Warning)
                
                # 3. Select the profile line and capture it
                if elevation_canvas and HAS_ELEVATION_PROFILE:
                    try:
                        # First set the profile curve
                        if geometry and geometry.type() == QgsWkbTypes.LineGeometry:
                            elevation_canvas.setProfileCurve(geometry.constGet())
                            QgsMessageLog.logMessage(f"Set profile curve for {profile_name}", "ClipRasterLayout", Qgis.Info)
                            
                            # Give time for the curve to be set
                            QTimer.singleShot(500, lambda: self.capture_profile_curve(elevation_dock, feature))
                            return  # Don't process next profile yet
                    except Exception as e:
                        QgsMessageLog.logMessage(f"Could not set profile curve: {str(e)}", "ClipRasterLayout", Qgis.Warning)
                
                # If we couldn't set up the curve automatically, show message and continue
                self.show_profile_ready_message(profile_name)
            else:
                QgsMessageLog.logMessage("Elevation profile dock not found", "ClipRasterLayout", Qgis.Warning)
                # Move to next profile
                self.current_profile_index += 1
                self.process_next_profile()
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error configuring profile: {str(e)}", "ClipRasterLayout", Qgis.Warning)
            self.current_profile_index += 1
            self.process_next_profile()
    
    def capture_profile_curve(self, elevation_dock, feature):
        """Capture the profile curve by clicking the 'capture curve from feature' tool and selecting the feature"""
        try:
            from qgis.PyQt.QtWidgets import QToolButton
            from qgis.PyQt.QtCore import QTimer
            
            profile_name = feature['name']
            
            # Find and click the "capture curve from feature" button
            capture_button = None
            all_buttons = elevation_dock.findChildren(QToolButton)
            QgsMessageLog.logMessage(f"Found {len(all_buttons)} tool buttons in elevation dock", "ClipRasterLayout", Qgis.Info)
            
            for button in all_buttons:
                tooltip = button.toolTip()
                QgsMessageLog.logMessage(f"Button tooltip: '{tooltip}'", "ClipRasterLayout", Qgis.Info)
                
                # Check various possible texts for the capture from feature button
                tooltip_lower = tooltip.lower()
                if ('feature' in tooltip_lower) or \
                   ('elemento' in tooltip_lower and 'cattura' in tooltip_lower) or \
                   ('capture curve from selected feature' in tooltip_lower) or \
                   ('cattura curva dall\'elemento selezionato' in tooltip_lower) or \
                   ('from selected' in tooltip_lower):
                    capture_button = button
                    QgsMessageLog.logMessage(f"Selected capture button with tooltip: {tooltip}", "ClipRasterLayout", Qgis.Info)
                    break
            
            if capture_button:
                # Select the profile feature in the layer FIRST
                profile_layer = None
                for layer in QgsProject.instance().mapLayers().values():
                    if layer.name() == "Profili DEM":
                        profile_layer = layer
                        break
                
                if profile_layer:
                    # Clear any existing selection
                    profile_layer.removeSelection()
                    # Select only this feature
                    profile_layer.select(feature.id())
                    QgsMessageLog.logMessage(f"Selected feature {profile_name} in profile layer", "ClipRasterLayout", Qgis.Info)
                    
                    # Now click the capture button
                    # Some buttons need to be toggled rather than clicked
                    if capture_button.isCheckable():
                        capture_button.setChecked(True)
                        QgsMessageLog.logMessage(f"Toggled 'capture curve from feature' button ON for {profile_name}", "ClipRasterLayout", Qgis.Info)
                    else:
                        capture_button.click()
                        QgsMessageLog.logMessage(f"Clicked 'capture curve from feature' button for {profile_name}", "ClipRasterLayout", Qgis.Info)
                    
                    # Refresh the canvas to ensure selection is visible
                    self.iface.mapCanvas().refresh()
                    
                    # Give time for the capture to complete
                    QTimer.singleShot(1500, lambda: self.finish_profile_configuration(profile_name))
                else:
                    self.show_profile_ready_message(profile_name)
            else:
                QgsMessageLog.logMessage("Could not find 'capture curve from feature' button", "ClipRasterLayout", Qgis.Warning)
                # Log all button tooltips for debugging
                for button in elevation_dock.findChildren(QToolButton):
                    if button.toolTip():
                        QgsMessageLog.logMessage(f"Button tooltip: {button.toolTip()}", "ClipRasterLayout", Qgis.Info)
                self.show_profile_ready_message(profile_name)
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error capturing profile curve: {str(e)}", "ClipRasterLayout", Qgis.Warning)
            self.show_profile_ready_message(profile_name)
    
    def finish_profile_configuration(self, profile_name):
        """Finish configuration after curve capture"""
        try:
            # Clear selection
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Profili DEM":
                    layer.removeSelection()
                    break
            
            # Store that this profile is ready
            QgsProject.instance().writeEntry("ClipRasterLayout", f"profile_ready_{profile_name}", "yes")
            QgsMessageLog.logMessage(f"Profile {profile_name} configuration completed", "ClipRasterLayout", Qgis.Info)
            
            # Show completion message
            self.show_profile_ready_message(profile_name)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error finishing profile configuration: {str(e)}", "ClipRasterLayout", Qgis.Warning)
            self.show_profile_ready_message(profile_name)
    
    def show_profile_ready_message(self, profile_name):
        """Show message that profile is ready and move to next"""
        msg = QMessageBox.information(None, f"Profilo {profile_name}", 
            f"Profilo {profile_name} configurato.\n\n"
            f"Verifica che:\n"
            f"- Il profilo sia visibile\n"
            f"- Solo il DEM corretto sia attivo\n"
            f"- La sezione {profile_name} sia visualizzata\n\n"
            f"Clicca OK per continuare.")
        
        # Move to next profile
        self.current_profile_index += 1
        self.process_next_profile()
    

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