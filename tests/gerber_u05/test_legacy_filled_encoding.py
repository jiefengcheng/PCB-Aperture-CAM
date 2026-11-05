import sys
from pathlib import Path
import pytest
from src.gerber_u05 import pipeline
from src.growth_void_encoding import filled_surface
from shapely.geometry import Polygon,LineString,GeometryCollection,box

def test_zero_width_overlay_line_does_not_discard_minimum_grid_triangle():
 t=Polygon([(0,0),(.000001,0),(0,.000001)]);g=GeometryCollection([t,LineString([(0,0),(.000001,.000001)])]);result=filled_surface(g)
 assert result.equals(t) and result.area==.5e-12

def test_multiple_positive_surfaces_are_all_preserved():
 a,b=box(0,0,1,1),box(2,0,3,1);result=filled_surface(GeometryCollection([a,b,LineString([(1,0),(2,0)])]))
 assert len(result.geoms)==2 and result.area==2

def test_line_only_remedy_still_rejects():
 with pytest.raises(ValueError,match='FILLED_REMEDY_HAS_NO_SURFACE'):filled_surface(LineString([(0,0),(1,1)]))
