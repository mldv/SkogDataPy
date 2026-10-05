import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Callable

import geopandas
import numpy
import rasterio
import shapely
from affine import Affine
from rasterio.mask import mask
from rasterio.merge import merge
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.geometry.multipolygon import MultiPolygon

from . import ftp as skog_ftp
from .ftp import CACHE_PATH


TRADHOJD_METADATA = {
    "20250131": "Tradhojd_LaserdataSkog/Metadata/TradHojdLaserdataSkogMetadata_20250131.shp",
    "20260331": "Tradhojd_LaserdataSkog/Metadata/TradHojdLaserdataSkogMetadata_20260331_Omdrev2.shp",
}
TRADHOJD_METADATA_LATEST = "20260331"


def normalize_lasnamn(lasnamn: str) -> str:
    """Converts a LasNamn in the naming used since mid-2022 to the one used for the file names.
    Example:
    '23B032_658_46_7525' -> '23B032_65875_4625_25'
    """
    block, north, east, rest = lasnamn.split("_")
    if len(north) == 3:
        return f"{block}_{north}{rest[:2]}_{east}{rest[2:]}_25"
    return lasnamn


def lasnamn2path(lasnamn: str) -> str:
    """Converts the LasNamn to the path.
    Example:
    '21D013_66600_5000_25' -> 'Tradhojd_LaserdataSkog/2021/66_5/THL_21D013_66600_5000_2021.mrf'
    """
    lasnamn = normalize_lasnamn(lasnamn)
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
        if skog_ftp.OFFLINE:
            raise FileNotFoundError(
                f"Offline mode, files missing in {CACHE_PATH}: " + ", ".join(map(str, files_to_download))
            )
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
    def files(self) -> list[Path]:
        """All files (relative to the cache folder and the FTP root) of this data source."""
        return _additional_files(self.name, self.other_suffixes or [])

    @property
    def path(self):
        return get_file(self.name, self.other_suffixes, ftp=self.ftp_connection)

    def as_geodataframe(self):
        assert self.type in ["shapefile", "gpkg"]
        return geopandas.read_file(self.path)

    def __call__(self, *args, **kwds):
        return self.as_geodataframe()


def _tradhojd_metadata_loader(version: str) -> SingleFileDataLoader:
    return SingleFileDataLoader(TRADHOJD_METADATA[version], "shapefile", ["dbf", "shx", "prj"])


class TradhojdDataLoader(DataSourceSpec, RasterDataSource):
    def __init__(self) -> None:
        self._metadata = None
        self._mapped_region = None
        self.cutoff: str | None = None
        super().__init__("Tradhojd_LaserdataSkog", "raster")

    def configure(self, metadata: str = TRADHOJD_METADATA_LATEST, cutoff: str | datetime.date | None = None) -> None:
        """Select the metadata version (a key of TRADHOJD_METADATA) and ignore scans made after the cutoff date.

        For reproducible results, fix both: the metadata lists one scan per square, so a newer version may
        replace scans that a cutoff alone cannot bring back.
        """
        self.metadata_source = _tradhojd_metadata_loader(metadata)
        self.cutoff = None if cutoff is None else datetime.date.fromisoformat(str(cutoff)).isoformat()
        self._metadata = None
        self._mapped_region = None

    @property
    def metadata(self):
        """Available scans: one row per scan, with `square` derived from `Las_namn`, scans after the cutoff removed."""
        assert self.metadata_source is not None
        if self._metadata is None:
            metadata = geopandas.read_file(self.metadata_source.path)
            metadata["square"] = metadata["Las_namn"].map(lambda x: normalize_lasnamn(x).split("_", 1)[1])
            if self.cutoff is not None:
                metadata = metadata[metadata["Skanndat"] <= self.cutoff]
            self._metadata = metadata
        return self._metadata

    @property
    def mapped_region(self):
        if self._mapped_region is None:
            self._mapped_region = shapely.union_all(self.metadata.geometry.values)
        return self._mapped_region

    @staticmethod
    def _sanitize_polygon(polygon) -> BaseGeometry:
        """Accept a shapely (Multi)Polygon or any object with a GeoJSON-like `__geo_interface__` (e.g. a fiona Feature)."""
        if not isinstance(polygon, BaseGeometry):
            geometry = getattr(polygon, "__geo_interface__", polygon)
            if geometry.get("type") == "Feature":
                geometry = geometry.get("geometry")
            if geometry is None:
                raise ValueError("Feature geometry is None")
            polygon = shape(geometry)
        assert isinstance(polygon, (shapely.Polygon, shapely.MultiPolygon))
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

    def required_files(self, polygon) -> list[Path]:
        """All files (relative to the cache folder and the FTP root) needed to read the CHM for the polygon."""
        return [y for x in self.filenames_from_polygon(polygon) for y in _additional_files(x, ["idx", "lrc"])]

    def cache_misses(self, polygon):
        return [x for x in self.required_files(polygon) if not (CACHE_PATH / x).is_file()]

    def __call__(
            self, polygon: BaseGeometry, padding: int = 20
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
    Tradhojd = TradhojdDataLoader()


DataSourceCatalog.Tradhojd.configure()
