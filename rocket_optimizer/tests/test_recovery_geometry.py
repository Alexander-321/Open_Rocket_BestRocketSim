import unittest

from rocket_optimizer.openrocket_backend import OpenRocketBackend


class _FakeClass:
    def __init__(self, simple_name: str):
        self._simple_name = simple_name

    def getSimpleName(self):
        return self._simple_name


class _FakeComponent:
    def __init__(self, name: str, simple_type: str):
        self._name = name
        self._simple_type = simple_type

    def getName(self):
        return self._name

    def getClass(self):
        return _FakeClass(self._simple_type)


class _FakeInnerTube(_FakeComponent):
    def __init__(self, length: float, axial_offset: float, axial_method: str = "BOTTOM"):
        super().__init__("Inner Tube", "InnerTube")
        self._length = length
        self._axial_offset = axial_offset
        self._axial_method = axial_method

    def getLength(self):
        return self._length

    def getAxialOffset(self):
        return self._axial_offset

    def getAxialMethod(self):
        return self._axial_method


class _FakeBodyTube(_FakeComponent):
    def __init__(self, length: float, outer_radius: float, thickness: float, children=None):
        super().__init__("Body tube", "BodyTube")
        self._length = length
        self._outer_radius = outer_radius
        self._thickness = thickness
        self._children = list(children or [])

    def getLength(self):
        return self._length

    def getOuterRadius(self):
        return self._outer_radius

    def getThickness(self):
        return self._thickness

    def getChildren(self):
        return self._children


class _FakeParachute(_FakeComponent):
    def __init__(self, name: str, diameter: float, packed_length: float, packed_radius: float):
        super().__init__(name, "Parachute")
        self._diameter = diameter
        self._packed_length = packed_length
        self._packed_radius = packed_radius
        self._axial_offset = 0.0

    def getDiameter(self):
        return self._diameter

    def setDiameter(self, value: float):
        self._diameter = value

    def getPackedLength(self):
        return self._packed_length

    def setPackedLength(self, value: float):
        self._packed_length = value

    def getPackedRadius(self):
        return self._packed_radius

    def setPackedRadius(self, value: float):
        self._packed_radius = value

    def getAxialOffset(self):
        return self._axial_offset

    def setAxialOffset(self, value: float):
        self._axial_offset = value


class TestRecoveryGeometryPlacement(unittest.TestCase):
    def setUp(self):
        self.backend = OpenRocketBackend()

    def test_dual_parachutes_are_placed_inside_recovery_compartment(self):
        body = _FakeBodyTube(
            length=0.30,
            outer_radius=0.015,
            thickness=0.001,
            children=[_FakeInnerTube(length=0.075, axial_offset=0.005, axial_method="BOTTOM")],
        )
        p1 = _FakeParachute("Payload Parachute", diameter=0.30, packed_length=0.042, packed_radius=0.009)
        p2 = _FakeParachute("Engine Section Parachute", diameter=0.30, packed_length=0.042, packed_radius=0.009)

        report = self.backend._layout_and_validate_recovery_geometry(
            body_tubes=[body],
            parachutes=[p1, p2],
            design_parameters={"parachute_diameter": 0.30},
        )

        compartment = report["recovery_compartment"]
        self.assertLess(compartment["start"], compartment["end"])
        self.assertEqual(len(report["parachutes"]), 2)
        for chute in report["parachutes"]:
            self.assertGreaterEqual(chute["front"], compartment["start"])
            self.assertLessEqual(chute["rear"], compartment["end"])
            self.assertLessEqual(chute["packed_radius"], report["body_tube"]["inner_radius"])

    def test_rejects_impossible_axial_packing(self):
        body = _FakeBodyTube(
            length=0.30,
            outer_radius=0.015,
            thickness=0.001,
            children=[_FakeInnerTube(length=0.075, axial_offset=0.005, axial_method="BOTTOM")],
        )
        p1 = _FakeParachute("Payload Parachute", diameter=0.30, packed_length=0.14, packed_radius=0.009)
        p2 = _FakeParachute("Engine Section Parachute", diameter=0.30, packed_length=0.14, packed_radius=0.009)

        with self.assertRaises(ValueError):
            self.backend._layout_and_validate_recovery_geometry(
                body_tubes=[body],
                parachutes=[p1, p2],
                design_parameters={"parachute_diameter": 0.30},
            )


if __name__ == "__main__":
    unittest.main()
