# -*- coding: utf-8 -*-
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QComboBox, QListWidget, QListWidgetItem,
                               QPushButton, QCheckBox, QFileDialog,
                               QProgressBar, QMessageBox, QAbstractItemView)
from qgis.core import (QgsProject, QgsRasterLayer, QgsVectorLayer,
                      QgsProcessing, QgsProcessingFeedback)
from qgis.gui import QgsFileWidget
import processing
import os

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
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
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
        self.clip_button.setEnabled(False)
        
        clipped_layers = []
        
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
                    'NODATA': -9999,
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
                        QgsProject.instance().addMapLayer(clipped_layer)
                        clipped_layers.append(clipped_layer)
                        
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Errore nel clipping di {raster_layer.name()}: {str(e)}")
                
            self.progress_bar.setValue(i + 1)
            
        self.progress_bar.setVisible(False)
        self.clip_button.setEnabled(True)
        
        if clipped_layers:
            QMessageBox.information(self, "Completato", 
                f"Clipping completato! {len(clipped_layers)} raster clippati e aggiunti alla mappa.")
        else:
            QMessageBox.information(self, "Completato", "Clipping completato!")