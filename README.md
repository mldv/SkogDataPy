# SkogDataPy
Facilitates the access to geospatial data about forests from specific providers, such as the Swedish Forest Agency - [Skogsstyrelsen](https://www.skogsstyrelsen.se/).

In the current version, just the Canopy Height Model (i.e., _Tradhojd_LaserdataSkog_) is supported.

## Description

Data is retrieved on-demand from the FTP server (`ftpsks.skogsstyrelsen.se`) and saved in the `cache` folder.
Alternatively, you can pre-download data from the FTP server with your favorite ftp client, such as FileZilla.
Note that the location of the cache folder can be set with the `.env` file.

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

