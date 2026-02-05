# -*- coding: utf-8 -*-
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QComboBox, QListWidget, QListWidgetItem,
                               QPushButton, QCheckBox, QFileDialog,
                               QProgressBar, QMessageBox, QAbstractItemView)
from qgis.core import (QgsProject, QgsRasterLayer, QgsVectorLayer,
                      QgsProcessing, QgsProcessingFeedback, QgsLayerTreeGroup)
from qgis.gui import QgsFileWidget
import processing
import os
import re
from datetime import datetime

class ClipRasterDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setupUi()
        
    def setupUi(self):
        self.setWindowTitle("Clip Raster in Batch")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # Polygon selection
        poly_layout = QHBoxLayout()
        poly_layout.addWidget(QLabel("Poligono di clip:"))
        self.polygon_combo = QComboBox()
        poly_layout.addWidget(self.polygon_combo)
        layout.addLayout(poly_layout)
        
        # Raster list
        layout.addWidget(QLabel("Seleziona raster da clippare:"))
        self.raster_list = QListWidget()
        self.raster_list.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self.raster_list)
        
        # Select all checkbox
        self.select_all_check = QCheckBox("Seleziona tutti")
        self.select_all_check.stateChanged.connect(self.toggle_select_all)
        layout.addWidget(self.select_all_check)
        
        # Output folder
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Cartella output:"))
        self.output_folder = QgsFileWidget()
        self.output_folder.setStorageMode(QgsFileWidget.GetDirectory)
        out_layout.addWidget(self.output_folder)
        layout.addLayout(out_layout)
        
        # Add to map checkbox
        self.add_to_map_check = QCheckBox("Aggiungi raster clippati alla mappa")
        self.add_to_map_check.setChecked(True)
        layout.addWidget(self.add_to_map_check)
        
        # Progress bar with label
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.clip_button = QPushButton("Esegui Clip")
        self.clip_button.clicked.connect(self.run_clip)
        button_layout.addWidget(self.clip_button)
        
        self.close_button = QPushButton("Chiudi")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def showEvent(self, event):
        super().showEvent(event)
        self.populate_layers()
        
    def populate_layers(self):
        self.polygon_combo.clear()
        self.raster_list.clear()
        
        # Populate polygon layers
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == 2:  # Polygon
                self.polygon_combo.addItem(layer.name(), layer)
                
        # Populate raster layers
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                item = QListWidgetItem(layer.name())
                item.setData(Qt.UserRole, layer)
                self.raster_list.addItem(item)
                
    def toggle_select_all(self, state):
        for i in range(self.raster_list.count()):
            item = self.raster_list.item(i)
            if state == Qt.Checked:
                item.setSelected(True)
            else:
                item.setSelected(False)
                
    def run_clip(self):
        polygon_layer = self.polygon_combo.currentData()
        if not polygon_layer:
            QMessageBox.warning(self, "Attenzione", "Seleziona un poligono di clip")
            return
            
        selected_items = self.raster_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un raster")
            return
            
        output_folder = self.output_folder.filePath()
        if not output_folder:
            QMessageBox.warning(self, "Attenzione", "Seleziona una cartella di output")
            return
            
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_items))
        self.progress_label.setVisible(True)
        self.progress_label.setText(f"Clipping 0/{len(selected_items)} raster...")
        self.clip_button.setEnabled(False)
        
        # Lists to store clipped layers by type
        dem_layers = []
        ortho_layers = []
        
        for i, item in enumerate(selected_items):
            raster_layer = item.data(Qt.UserRole)
            output_path = os.path.join(output_folder, f"clipped_{raster_layer.name()}.tif")
            
            try:
                # Run clip raster by mask layer
                params = {
                    'INPUT': raster_layer,
                    'MASK': polygon_layer,
                    'SOURCE_CRS': raster_layer.crs(),
                    'TARGET_CRS': raster_layer.crs(),
                    'NODATA': None,
                    'ALPHA_BAND': False,
                    'CROP_TO_CUTLINE': True,
                    'KEEP_RESOLUTION': True,
                    'SET_RESOLUTION': False,
                    'MULTITHREADING': True,
                    'OUTPUT': output_path
                }
                
                result = processing.run("gdal:cliprasterbymasklayer", params)
                
                if self.add_to_map_check.isChecked() and result['OUTPUT']:
                    clipped_layer = QgsRasterLayer(result['OUTPUT'], f"clipped_{raster_layer.name()}")
                    if clipped_layer.isValid():
                        # Don't add to map yet, we'll organize them in groups
                        layer_name = raster_layer.name().lower()
                        if 'dem' in layer_name or 'dtm' in layer_name or 'dsm' in layer_name:
                            dem_layers.append((clipped_layer, raster_layer.name()))
                        else:
                            ortho_layers.append((clipped_layer, raster_layer.name()))
                        
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Errore nel clipping di {raster_layer.name()}: {str(e)}")
                
            self.progress_bar.setValue(i + 1)
            self.progress_label.setText(f"Clipping {i + 1}/{len(selected_items)} raster...")
            
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.clip_button.setEnabled(True)
        
        # Create groups and add layers
        total_layers = len(dem_layers) + len(ortho_layers)
        if total_layers > 0:
            self.organize_layers_in_groups(dem_layers, ortho_layers)
            QMessageBox.information(self, "Completato", 
                f"Clipping completato! {total_layers} raster clippati e organizzati in gruppi.")
        else:
            QMessageBox.information(self, "Completato", "Clipping completato!")
    
    def extract_date_from_filename(self, filename):
        """Extract date from filename for sorting"""
        # Try different date patterns
        patterns = [
            r'(\d{4}[-_]\d{2}[-_]\d{2})',  # YYYY-MM-DD or YYYY_MM_DD
            r'(\d{8})',  # YYYYMMDD
            r'(\d{2}[-_]\d{2}[-_]\d{4})',  # DD-MM-YYYY or DD_MM_YYYY
            r'(\d{4})',  # Just year
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                date_str = match.group(1)
                try:
                    # Try to parse the date
                    if len(date_str) == 4:  # Just year
                        return datetime(int(date_str), 1, 1)
                    elif len(date_str) == 8:  # YYYYMMDD
                        return datetime.strptime(date_str, '%Y%m%d')
                    elif '-' in date_str or '_' in date_str:
                        date_str = date_str.replace('_', '-')
                        if date_str.count('-') == 2:
                            parts = date_str.split('-')
                            if len(parts[0]) == 4:  # YYYY-MM-DD
                                return datetime.strptime(date_str, '%Y-%m-%d')
                            else:  # DD-MM-YYYY
                                return datetime.strptime(date_str, '%d-%m-%Y')
                except:
                    continue
        
        # If no date found, return a default old date
        return datetime(1900, 1, 1)
    
    def organize_layers_in_groups(self, dem_layers, ortho_layers):
        """Organize clipped layers in groups"""
        root = QgsProject.instance().layerTreeRoot()
        
        # Sort layers by date
        dem_layers.sort(key=lambda x: self.extract_date_from_filename(x[1]))
        ortho_layers.sort(key=lambda x: self.extract_date_from_filename(x[1]))
        
        # Create or get groups
        dem_group = None
        ortho_group = None
        
        # Check if groups already exist
        for child in root.children():
            if isinstance(child, QgsLayerTreeGroup):
                if child.name() == "DEM clip":
                    dem_group = child
                elif child.name() == "Orthophoto clip":
                    ortho_group = child
        
        # Create groups if they don't exist
        if not dem_group and dem_layers:
            dem_group = root.addGroup("DEM clip")
        if not ortho_group and ortho_layers:
            ortho_group = root.addGroup("Orthophoto clip")
        
        # Add DEM layers to group
        for layer, name in dem_layers:
            QgsProject.instance().addMapLayer(layer, False)
            dem_group.addLayer(layer)
        
        # Add Orthophoto layers to group
        for layer, name in ortho_layers:
            QgsProject.instance().addMapLayer(layer, False)
            ortho_group.addLayer(layer)