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
def classFactory(iface):
    from .clip_raster_layout import ClipRasterLayout
    return ClipRasterLayout(iface)