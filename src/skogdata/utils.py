import matplotlib.pyplot
import numpy
import rasterio
import rasterio.features
import rasterio.plot
import rasterio.transform
import shapely
import shapely.ops

from .data import DataSourceCatalog, RasterDataSource


def combine_raster_and_polygon(raster, polygon, transform) -> numpy.ndarray:
    """Combine a raster and a polygon into a single raster with the polygon as a mask."""
    img = rasterio.features.rasterize(
        [polygon], out_shape=raster.shape[1:], transform=transform
    )
    img2 = numpy.expand_dims(img, axis=0)
    return numpy.append(raster, img2, axis=0)


def plot_geometry_and_raster(
        geom,
        raster=None,
        transform=None,
        ax=None,
        geo_col="red",
        cmap=None,
        vmin=None,
        vmax=None,
        raster_source: RasterDataSource = DataSourceCatalog.Tradhojd
):
    """Plot a geometry over a raster"""
    ax = ax or matplotlib.pyplot.gca()

    if raster is None:
        raster, transform = raster_source(geom)
    else:
        assert transform is not None

    rasterio.plot.show(
        raster,
        transform=transform,
        ax=ax,
        cmap=cmap or "Greens",
        vmin=vmin or 0,
        vmax=vmax or raster.max(),
    )

    if isinstance(geom, shapely.MultiPolygon):
        for p in geom.geoms:
            ax.plot(*p.exterior.xy, geo_col)
            for interior in p.interiors:
                ax.plot(*interior.xy, geo_col)
    elif isinstance(geom, shapely.Polygon):
        ax.plot(*geom.exterior.xy, geo_col)
        for interior in geom.interiors:
            ax.plot(*interior.xy, geo_col)

    return ax
