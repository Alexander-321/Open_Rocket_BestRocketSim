"""Integration tests requiring OpenRocket and orlab."""

import os
import unittest

from rocket_optimizer.config import OPENROCKET_JAR_PATH, TEMPLATES_DIR
from rocket_optimizer.openrocket_backend import OpenRocketBackend


@unittest.skipUnless(
    os.path.exists(OPENROCKET_JAR_PATH) and os.path.exists(os.path.join(TEMPLATES_DIR, "base.ork")),
    "OpenRocket JAR or base template not available",
)
class TestOpenRocketIntegration(unittest.TestCase):
    def test_simulate_base_template(self):
        params = {
            "nose_cone_length": 0.1,
            "nose_cone_shape": "OGIVE",
            "fin_root_chord": 0.05,
            "fin_tip_chord": 0.025,
            "fin_sweep": 0.02,
            "fin_thickness": 0.002,
            "fin_count": 3,
            "fin_position": 0.6,
            "launch_lug_position": 0.4,
        }
        with OpenRocketBackend() as backend:
            results = backend.simulate_design(params)
        self.assertTrue(results["simulation_successful"])
        self.assertGreater(results["max_altitude"], 10.0)
        self.assertGreater(results["max_stability"], 0.5)


if __name__ == "__main__":
    unittest.main()
