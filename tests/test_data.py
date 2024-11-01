import pytest
import shapely.wkt

from skogdata import DataSourceCatalog

def load_example_polygon():
    # Same as Natura2000_coniferous, OBJECT_ID = 114206
    return shapely.wkt.loads(
        """POLYGON ((548991.9431999996 6932135.581700001, 548992.0570999999 6932135.5601, 549002.1120999996 6932206.4122, 
        549012.3381000003 6932278.4681, 549209.9330000002 6932191.524900001, 549238.9379000003 6932178.762800001, 
        549259.4271 6932169.747099999, 549290.71 6932146.763, 549290.7122999998 6932146.761300001, 549289.6810999997 
        6932144.971299998, 549286.2264999999 6932138.9901, 549267.6601 6932106.842099998, 549270.0450999998 
        6932105.238000002, 549308.1980999997 6932079.577100001, 549307.7741 6932078.0132, 549292.1961000003 6932020.548099998, 
        549293.4610000001 6932018.8451000005, 549313.6968999999 6931991.6000000015, 549339.3761 6931957.0260999985, 549244.8651999999 
        6931969.360199999, 549217.6842 6931972 6932096.2652, 548989.7801999999 6932133.418200001, 548990.2001999998 6932135.9056, 
        548990.2021000003 6932135.916999999, 548991.9431999996 6932135.581700001))
        """
    )

# @pytest.mark.skip(reason="not overload ftp server")
def test_las_namn_from_polygon1():
    polygon = load_example_polygon()
    res = DataSourceCatalog.Tradhojd.las_namn_from_polygon(polygon)
    assert res == ['19E031_69300_5475_25']

# @pytest.mark.skip(reason="not overload ftp server")
def test_las_namn_from_polygon2():
    polygon = shapely.Polygon([(542501, 6930000), (547001,6930000), (547001,6930050), (542501,6930050)])
    res = DataSourceCatalog.Tradhojd.las_namn_from_polygon(polygon)
    assert res == ['19E031_69300_5425_25', '19E031_69300_5450_25']