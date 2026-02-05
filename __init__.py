def classFactory(iface):
    """
    QGIS calls this to instantiate the plugin.
    """
    from .clip_raster_layout import ClipRasterLayoutPlugin
    return ClipRasterLayoutPlugin(iface)
