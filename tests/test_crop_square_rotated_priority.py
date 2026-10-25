"""Rotated support-line geometry and complete-round priority constraints."""
import math
import unittest

from shapely.geometry import Point

from src.crop_square_neighbor_experiment import (
    Settings, construct, facing_square_side, inscribed_square,
    largest_feasible_round, square_facing_lobe, verify_addition,
)


class RotatedPriorityTests(unittest.TestCase):
    def test_rotated_square_vertices_and_sides_follow_the_enlarged_radius(self):
        for radius in (.15,.225,.3):
            square=inscribed_square((1.3,-14.7),radius,orientation_degrees=-45)
            points=list(square.exterior.coords)[:4]
            for i,point in enumerate(points):
                self.assertAlmostEqual(math.dist((1.3,-14.7),point),radius)
                self.assertAlmostEqual(math.dist(point,points[(i+1)%4]),math.sqrt(2)*radius)
            self.assertAlmostEqual(square.area,2*radius**2)

    def test_facing_side_is_the_side_nearest_the_diagonal_neighbor(self):
        square=inscribed_square((0,0),1.5,orientation_degrees=-45)
        side=facing_square_side(square,(0,0),(-3,-3))
        self.assertAlmostEqual(side["normal"][0],-1/math.sqrt(2))
        self.assertAlmostEqual(side["normal"][1],-1/math.sqrt(2))
        self.assertAlmostEqual(math.dist((0,0),side["midpoint"]),1.5/math.sqrt(2))

    def test_quarter_turn_does_not_change_the_physical_selected_halfplane(self):
        envelope=Point(0,0).buffer(1.5,quad_segs=128)
        a,_=square_facing_lobe(envelope,inscribed_square((0,0),1.5),(0,0),(3,0))
        b,_=square_facing_lobe(envelope,inscribed_square((0,0),1.5,orientation_degrees=90),(0,0),(3,0))
        self.assertLess(a.symmetric_difference(b).area,1e-12)

    def test_priority_reduces_radius_instead_of_clipping_its_round_outline(self):
        core=Point(0,0).buffer(1,quad_segs=128)
        neighbor=Point(2.5,0).buffer(1,quad_segs=128)
        obstacles=[{"source_id":"neighbor","geometry":neighbor}]
        result=largest_feasible_round(core,(0,0),1,1.5,obstacles)
        self.assertEqual(result["decision"],"ROUND_GROW")
        self.assertGreater(result["radius_mm"],1.4)
        self.assertLess(result["radius_mm"],1.5)
        self.assertLess(core.difference(result["candidate"]).area,1e-10)
        self.assertLess(result["roundness_residual_mm"],1e-12)
        self.assertTrue(verify_addition(core,result["candidate"],result["candidate"],obstacles)["passed"])
        self.assertGreaterEqual(result["candidate"].distance(neighbor),.020)

    def test_rotated_recession_changes_growth_without_damaging_source_or_gap(self):
        core=Point(2.8,0).buffer(1,quad_segs=128)
        earlier=Point(0,0).buffer(1.5,quad_segs=128)
        obstacles=[{"source_id":"A","geometry":earlier}]
        results=[]
        for angle in (0,-45):
            settings=Settings(orientation_degrees=angle)
            result=construct(core,(2.8,0),1.5,obstacles,earlier_neighbor_id="A",
                             earlier_neighbor_center=(0,0),settings=settings)
            self.assertTrue(result["square_consumed"])
            self.assertTrue(verify_addition(core,result["candidate"],result["envelope"],obstacles,settings=settings)["passed"])
            results.append(result["candidate"])
        self.assertGreater(results[0].symmetric_difference(results[1]).area,1e-8)


if __name__ == "__main__":
    unittest.main()
