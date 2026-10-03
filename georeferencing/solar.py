"""Solar elevation (degrees) for a point and UTC instant — NOAA approximation,
within ~0.5° of the values in the project's NASA lists."""
import math


def sun_elevation(lat, lon, dt):
    doy = dt.timetuple().tm_yday
    hours = dt.hour + dt.minute / 60 + dt.second / 3600
    g = math.radians(360 / 365.25 * (doy - 1 + (hours - 12) / 24))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                    - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    tst = hours * 60 + eqt + 4 * lon
    ha = math.radians(tst / 4 - 180)
    latr = math.radians(lat)
    cos_z = math.sin(latr) * math.sin(decl) + math.cos(latr) * math.cos(decl) * math.cos(ha)
    return math.degrees(math.asin(max(-1.0, min(1.0, cos_z))))
