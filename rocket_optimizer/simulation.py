import os
from typing import Any, Dict, Optional

from .openrocket_backend import OpenRocketBackend
from .utils import logger
from .config import OPENROCKET_JAR_PATH, RESULTS_DIR, SIMULATION_TIMEOUT_SECONDS


class OpenRocketSimulator:
    """Runs OpenRocket simulations via orlab."""

    def __init__(
        self,
        backend: Optional[OpenRocketBackend] = None,
        openrocket_jar_path: str = OPENROCKET_JAR_PATH,
        results_dir: str = RESULTS_DIR,
        timeout: int = SIMULATION_TIMEOUT_SECONDS,
    ):
        self.backend = backend
        self.openrocket_jar_path = openrocket_jar_path
        self.results_dir = results_dir
        self.timeout = timeout

        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

    def run_simulation(
        self,
        design_parameters: Dict[str, Any],
        output_csv_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Simulate a rocket design and return parsed metrics.

        Args:
            design_parameters: Rocket design parameter dict from the optimizer.
            output_csv_path: Unused (kept for API compatibility).

        Returns:
            Dict of simulation metrics on success, None on failure.
        """
        if self.backend is None:
            logger.error("OpenRocketSimulator requires an OpenRocketBackend instance")
            return None

        try:
            results = self.backend.simulate_design(design_parameters)
            logger.info(
                f"Simulation successful. Altitude: {results['max_altitude']:.2f} m, "
                f"Stability: {(results['min_stability'] + results['max_stability']) / 2:.2f} cal"
            )
            return results
        except Exception as e:
            logger.error(f"OpenRocket simulation failed: {e}")
            return None
