from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Callable

import fiona
import geopandas
import numpy
import rasterio
import shapely
from affine import Affine
from rasterio.mask import mask
from rasterio.merge import merge
from shapely.geometry import shape
from dotenv import dotenv_values
from shapely.geometry.base import BaseGeometry
from shapely.geometry.multipolygon import MultiPolygon

from . import ftp as skog_ftp

_config = dotenv_values()

CACHE_PATH = (Path(__file__).parent.parent.parent / Path("cache")).resolve()
if 'CACHE' in _config:
    CACHE_PATH = (Path(_config['CACHE'])).resolve()  # type: ignore


def lasnamn2path(lasnamn: str) -> str:
    """Converts the LasNamn to the path.
    Example:
    '21D013_66600_5000_25' -> 'Tradhojd_LaserdataSkog/2021/66_5/THL_21D013_66600_5000_2021.mrf'
    """
    BASEDIR = "Tradhojd_LaserdataSkog"
    dir1 = "20" + lasnamn[:2]
    splits = lasnamn.split("_")
    n1 = splits[1][:2]
    n2 = splits[2][0]
    directory = BASEDIR + "/" + dir1 + "/" + n1 + "_" + n2 + "/"
    fname = "THL_" + lasnamn[:-3] + "_" + dir1
    return directory + fname + ".mrf"


def _additional_files(filename: str | Path, other_suffixes: list) -> list[Path]:
    """Returns list of files that are missing in cache"""
    filename_path = Path(filename)
    fname = filename_path.stem
    suffixes = [filename_path.suffix] + ["." + x for x in other_suffixes]
    filenames = [
        filename_path.parent / Path(str(fname) + suffix) for suffix in suffixes
    ]
    return filenames


def get_file(
        filename: str | Path, other_suffixes: list | None = None, ftp: str | None = "SGD"
) -> Path:
    """Retrieve the file(s) from the cache or download if missed.
    other_suffixes allows to download also files with same name but other suffixes (e.g. fname.shp -> fname.dbf, fname.shx)
    """
    path = CACHE_PATH / filename
    other_suffixes = other_suffixes or []
    filenames = _additional_files(filename, other_suffixes)
    files_to_download = [x for x in filenames if not (CACHE_PATH / x).is_file()]
    if files_to_download:
        skog_ftp.download_from_ftp(files_to_download)

    assert all((CACHE_PATH / x).is_file() for x in filenames)
    return path


@dataclass
class DataSourceSpec:
    name: str
    type: str  # 'raster' of 'shapefile'
    other_suffixes: list[str] | None = None
    ftp_connection: str | None = "SGD"
    metadata_source: Callable | None = None

    def __hash__(self) -> int:
        return hash(repr(self))


class RasterDataSource(ABC):
    @abstractmethod
    def __call__(self, polygon: BaseGeometry, padding: int = 0) -> tuple[numpy.ndarray, Affine]:
        pass


class SingleFileDataLoader(DataSourceSpec):
    @property
    def path(self):
        return get_file(self.name, self.other_suffixes, ftp=self.ftp_connection)

    def as_geodataframe(self):
        assert self.type in ["shapefile", "gpkg"]
        return geopandas.read_file(self.path)

    def __call__(self, *args, **kwds):
        if self.type in ["shapefile", "gpkg"]:
            return fiona.open(self.path)


class TradhojdDataLoader(DataSourceSpec, RasterDataSource):
    def __init__(self) -> None:
        self._metadata = None
        self._mapped_region = None
        super().__init__("Tradhojd_LaserdataSkog", "raster")

    @property
    def metadata(self):
        assert self.metadata_source is not None
        if self._metadata is None:
            self._metadata = geopandas.read_file(self.metadata_source().path)
        return self._metadata

    @property
    def mapped_region(self):
        if self._mapped_region is None:
            self._mapped_region = shapely.union_all(
                [shape(x.geometry) for i, x in self.metadata.iterrows()]
            )
        return self._mapped_region

    @staticmethod
    def _sanitize_polygon(polygon: BaseGeometry | shapely.Polygon | shapely.MultiPolygon | fiona.Feature) -> BaseGeometry:
        assert (
                isinstance(polygon, shapely.Polygon)
                or isinstance(polygon, shapely.MultiPolygon)
                or isinstance(polygon, fiona.Feature)
        )
        if isinstance(polygon, fiona.Feature):
            if polygon.geometry is None:
                raise ValueError("Feature geometry is None")
            return shape(polygon.geometry)
        else:
            return polygon

    def las_namn_from_polygon(self, polygon: BaseGeometry):
        pol = self._sanitize_polygon(polygon)
        limits = [int(x / 100) // 25 * 25 for x in pol.bounds]
        square_list = [
            f"{x}_{y}_25"
            for x, y in product(
                range(limits[1], limits[3] + 25, 25),
                range(limits[0], limits[2] + 25, 25),
            )
        ]
        if all(x in self.metadata['square'].values for x in square_list):
            # Get only the last entry for each square
            res = self.metadata.query("square in @square_list").sort_values("Unixday").groupby("square").last()
            res = res["Las_namn"].to_list()
            return res
        else:
            return []

    def filenames_from_polygon(self, polygon: BaseGeometry):
        return [lasnamn2path(x) for x in self.las_namn_from_polygon(polygon)]

    def contains(self, polygon):
        return len(self.las_namn_from_polygon(polygon)) > 0

    def is_available_in_cache(self, polygon):
        return all(
            (CACHE_PATH / x).is_file() for x in self.filenames_from_polygon(polygon)
        )

    def cache_misses(self, polygon):
        return [
            y
            for x in self.filenames_from_polygon(polygon)
            for y in _additional_files(x, ["idx", "lrc"])
            if not (CACHE_PATH / y).is_file()
        ]

    def __call__(
            self, polygon: BaseGeometry | fiona.Feature, padding: int = 20
    ) -> tuple[numpy.ndarray, Affine]:
        pol = self._sanitize_polygon(polygon)
        nn = self.filenames_from_polygon(pol.envelope)
        if not nn:
            raise FileNotFoundError("Data not available for this polygon")
        datasets = [rasterio.open(get_file(f, ["lrc", "idx"])) for f in nn]
        merged, transform = merge(datasets)
        total = merged[0, :, :]

        with rasterio.MemoryFile() as memfile:
            dataset = memfile.open(
                driver="GTiff",
                height=total.shape[0],
                width=total.shape[1],
                count=1,
                crs=datasets[0].crs,
                transform=transform,
                dtype=merged.dtype,
            )
            dataset.write(total, 1)

            bbox = shapely.box(*pol.buffer(distance=padding).bounds)
            cropped, crop_trans = mask(dataset, [bbox], crop=True)
        return cropped, crop_trans


_suffixes = ("shx", "sbx", "sbn", "prj", "dbf", "cpg")


@dataclass
class DataSourceCatalog:
    Tradhojd_metadata = SingleFileDataLoader(
        "Tradhojd_LaserdataSkog/Metadata/TradhojdLaserdataSkogMetadata_20250131.shp",
        "shapefile",
        ["dbf", "shx"],
    )
    Tradhojd = TradhojdDataLoader()


DataSourceCatalog.Tradhojd.metadata_source = DataSourceCatalog.Tradhojd_metadata
