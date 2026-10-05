# SkogDataPy
Facilitates the access to geospatial data about forests from specific providers, such as the Swedish Forest Agency - [Skogsstyrelsen](https://www.skogsstyrelsen.se/).

In the current version, just the Canopy Height Model (i.e., _Tradhojd_LaserdataSkog_) is supported.

## Description

Data is retrieved on demand from Skogsstyrelsen's FTP server (`ftpsks.skogsstyrelsen.se`) and saved in a cache folder.
Files already in the cache are never downloaded again.

### Configuration

Settings are read from environment variables or from a `.env` file in the working directory (see [.env-example](.env-example)):

- `CACHE`: absolute path of the cache folder. Default is `{project_root}/cache`.
- `SKOGDATA_OFFLINE=1`: never connect to the FTP server. Missing files raise a `FileNotFoundError` that lists them.

### Downloading the data manually

You can download the data with any FTP client (e.g. FileZilla or `lftp`) instead.
The server uses implicit FTPS on port 990. The public credentials are published by
[Skogsstyrelsen](https://www.skogsstyrelsen.se/sjalvservice/karttjanster/geodatatjanster/ftp/) and are also in [ftp.py](src/skogdata/ftp.py).
Keep the folder structure of the server below the cache folder, for example:

```
$CACHE/Tradhojd_LaserdataSkog/Metadata/TradHojdLaserdataSkogMetadata_20250131.{shp,dbf,shx,prj}
$CACHE/Tradhojd_LaserdataSkog/2021/65_7/THL_21C032_65800_7000_2021.{mrf,lrc,idx}
```

To find which files are needed for an area, download the metadata files first, then:

```python
from skogdata import DataSourceCatalog
DataSourceCatalog.Tradhojd.metadata_source.files          # metadata files
DataSourceCatalog.Tradhojd.required_files(polygon)        # CHM files covering the polygon
```

### Reproducibility: metadata version and cutoff date

The CHM is updated as new laser scans are made. The metadata lists one scan per 2.5 x 2.5 km square,
and for each square the most recent scan is used. To always get the same data, fix both the metadata version and a cutoff date:

```python
DataSourceCatalog.Tradhojd.configure(metadata="20250131", cutoff="2025-01-31")
```

Scans made after the cutoff are ignored. The available metadata versions are listed in `skogdata.data.TRADHOJD_METADATA`;
by default the latest one is used, without cutoff.

## Setup

### 1. Create a Python virtual environment and install dependencies

The first time:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[all]
```

Activate the environment

```bash
source .venv/bin/activate
```

### 2. Run the tests

```bash
pytest
```

### 3. Run a simple example

Open Python console and run:

```python
import shapely
import matplotlib.pyplot as plt
from skogdata import DataSourceCatalog, plot_geometry_and_raster 

polygon = shapely.box(394775.27, 6281550.40, 394907.35, 6281605.49)  # Coordinates are in SWEREF99 geodetic system
plot_geometry_and_raster(polygon)
plt.show()
```


### 4. Run a simple notebook

If you want to run everything in the virtual environment, install Jupyter Notebook, first:

```bash
pip install notebook ipywidgets IProgress
```

Then, open and run the [example_usage.ipynb](example_usage.ipynb) notebook:

```bash
jupyter notebook example_usage.ipynb
```

