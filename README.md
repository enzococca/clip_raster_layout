# Clip Raster Layout Plugin for QGIS

A comprehensive QGIS plugin for topographic analysis that provides batch raster clipping, interactive polygon drawing, and elevation profile generation.

**Compatible with QGIS 3.x (Qt5) and QGIS 4.x (Qt6)**

## Features

### 1. Batch Raster Clipping
- Clip multiple raster layers simultaneously using a polygon mask
- Supports DEM, DTM, DSM, and orthophoto layers
- Automatic loading of clipped rasters to the map
- Progress tracking during batch operations

### 2. Interactive Polygon Drawing
- Draw clip polygons directly on the map canvas
- Left-click to add vertices
- Double-click or right-click to finish
- Press ESC to cancel
- Semi-transparent preview while drawing

### 3. Topographic Sections (Optional)
- Create cross-section lines by clicking two points
- Automatic labeling (A-B, C-D, E-F, etc.)
- Dashed line style with arrow markers
- Sections are optional - you can clip without creating them

### 4. Elevation Profiles
- Generate elevation charts along section lines
- Matplotlib-based visualization
- Shows distance vs elevation
- Exported as PNG images

### 5. Auto-refresh Layer Lists
- Layer lists update automatically when you add/remove layers in QGIS
- Manual refresh buttons available if needed
- No need to reload the plugin when loading new data

### 6. Built-in Tutorial
- Interactive help system with tabbed interface
- Quick start guide
- Detailed instructions for each feature
- Tips and best practices

## Installation

1. Copy the `clip_raster_layout` folder to your QGIS plugins directory:
   - **Windows**: `C:\Users\[username]\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

2. Restart QGIS or reload plugins

3. Enable the plugin from: Plugins → Manage and Install Plugins → Installed

## Requirements

- QGIS 3.0 or higher (tested up to QGIS 4.x)
- Python 3.x
- Required Python libraries: numpy, matplotlib

## Quick Start

1. Click the **Clip & Profile Layout** button in the toolbar or access via Plugins menu
2. **Select rasters**: Choose one or more DEM/raster layers from the list
3. **Choose clip polygon**: Select an existing polygon layer or draw a new one
4. **Sections (optional)**: Enable "Create sections/profiles" and draw section lines
5. **Output folder**: Select where to save clipped rasters and profiles
6. Click **Run Clip**

## Usage Tips

- Hold **Ctrl** while clicking to select multiple rasters
- Clipped rasters are saved with the suffix `_clipped`
- Layer lists refresh automatically when you load new layers
- Use the **?Tutorial** button for detailed help

## Keyboard Shortcuts

- **Left-click**: Add point (polygon/section drawing)
- **Right-click**: Finish polygon / Cancel section
- **Double-click**: Finish polygon
- **ESC**: Cancel current drawing operation

## Author

Enzo Cocca - enzo.ccc@gmail.com

## License

GPL v3
