# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Clip Raster Layout** is a QGIS plugin for topographic analysis compatible with QGIS 3.x (Qt5) and QGIS 4.x (Qt6). It provides:
1. Batch raster clipping using polygon layers
2. Interactive polygon drawing on map canvas
3. DEM profile extraction with matplotlib visualization
4. Professional layout generation with elevation profiles

## Architecture

### Core Components

- **`__init__.py`**: Plugin entry point, exports `classFactory()` for QGIS
- **`clip_raster_layout.py`**: Main plugin with:
  - `ClipRasterLayoutPlugin`: Plugin main class
  - `ClipDockWidget`: Dock widget UI with auto-refresh layer lists
  - `SectionTool`: Map tool for drawing section lines
  - `PolygonDrawTool`: Map tool for drawing clip polygons
  - `TutorialDialog`: Built-in help system
- **`clip_raster_dialog.py`**: `ClipRasterDialog` - Batch raster clipping with progress tracking
- **`profile_tool.py`**: `ProfileTool` (QgsMapTool) - Interactive DEM profile creation
- **`layout_generator.py`**: `LayoutGenerator` - Creates QGIS print layouts

### Qt5/Qt6 Compatibility

The plugin uses a compatibility layer at the top of `clip_raster_layout.py`:
```python
if _qt6:
    Qt_LeftButton = Qt.MouseButton.LeftButton
    # ... other Qt6 enums
else:
    Qt_LeftButton = Qt.LeftButton
    # ... Qt5 enums
```

When adding new code, use the compatibility constants (e.g., `Qt_LeftButton` instead of `Qt.LeftButton`).

For `exec_()` calls, use:
```python
if hasattr(dlg, 'exec'):
    dlg.exec()
else:
    dlg.exec_()
```

### Key Technical Details

- Uses QGIS Processing framework (`gdal:cliprasterbymasklayer`) for raster operations
- Profile visualization uses matplotlib with `FigureCanvasQTAgg`
- Stores layer IDs instead of layer references to prevent "deleted C++ object" crashes
- Connects to `QgsProject.layersAdded/layersRemoved` signals for auto-refresh
- Template-based layouts supported via `.qpt` files

### Layer Naming Conventions

- Sections layer: `"Sections"` (memory layer with LineString geometry)
- Clip polygon layer: `"Clip Polygon"` (memory layer)
- Clipped layers grouped in: `"DEM clip"` and `"Orthophoto clip"`

## Development Commands

```bash
# Compile Qt resources (required after modifying resources.qrc)
python compile_resources.py
# or directly:
pyrcc5 -o resources.py resources.qrc
```

## Dependencies

- QGIS 3.0+ or 4.x
- PyQt5 or PyQt6 (via qgis.PyQt)
- numpy
- matplotlib

## Error Handling Pattern

Always use try/except blocks and show user-friendly messages:
```python
try:
    # operation
except Exception as e:
    QtWidgets.QMessageBox.warning(None, 'Error', f'Error message: {str(e)}')
```

## Language

All UI text is in English.
