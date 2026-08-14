import csv
import os
from typing import Dict, Any, Optional

from .utils import logger

# orlab CSV export uses TYPE_* column names with SI units in parentheses.
ALTITUDE_COLUMNS = ("Altitude (m)", "TYPE_ALTITUDE (m)")
STABILITY_COLUMNS = ("Stability (cal)", "TYPE_STABILITY")
VELOCITY_Z_COLUMNS = ("Vertical velocity (m/s)", "TYPE_VELOCITY_Z (m/s)")
ACCELERATION_COLUMNS = ("Vertical acceleration (m/s²)", "TYPE_ACCELERATION_Z (m/s²)")
DRAG_COLUMNS = ("Drag (N)", "TYPE_DRAG_FORCE (N)")


class OpenRocketParser:
    """Parses OpenRocket simulation CSV output (orlab or legacy format)."""

    def parse_simulation_results(self, csv_file_path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(csv_file_path):
            logger.error(f"CSV file not found: {csv_file_path}")
            return None

        try:
            max_altitude = 0.0
            min_stability = float("inf")
            max_stability = float("-inf")
            max_velocity = 0.0
            max_acceleration = 0.0
            total_drag = 0.0
            drag_data_points = 0

            with open(csv_file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers: list[str] = []
                data_started = False

                for row in reader:
                    if not row:
                        continue

                    if not data_started:
                        if row[0].startswith("Time") or row[0].startswith("TYPE_TIME"):
                            headers = [h.strip() for h in row]
                            data_started = True
                        continue

                    if row[0].startswith("#"):
                        continue

                    try:
                        row_data = {headers[i]: float(val) for i, val in enumerate(row) if i < len(headers)}

                        altitude = self._first_value(row_data, ALTITUDE_COLUMNS)
                        stability = self._first_value(row_data, STABILITY_COLUMNS)
                        vertical_velocity = self._first_value(row_data, VELOCITY_Z_COLUMNS)
                        acceleration = self._first_value(row_data, ACCELERATION_COLUMNS)
                        drag = self._first_value(row_data, DRAG_COLUMNS)

                        max_altitude = max(max_altitude, altitude)
                        if stability < min_stability:
                            min_stability = stability
                        if stability > max_stability:
                            max_stability = stability
                        max_velocity = max(max_velocity, abs(vertical_velocity))
                        max_acceleration = max(max_acceleration, abs(acceleration))
                        total_drag += drag
                        drag_data_points += 1
                    except ValueError as ve:
                        logger.warning(f"Skipping row due to data conversion error: {ve} in row: {row}")

            if drag_data_points == 0:
                return {"simulation_successful": False, "error": "No data rows parsed"}

            avg_drag = total_drag / drag_data_points
            if min_stability == float("inf"):
                min_stability = 0.0
            if max_stability == float("-inf"):
                max_stability = 0.0

            results = {
                "max_altitude": max_altitude,
                "min_stability": min_stability,
                "max_stability": max_stability,
                "max_velocity": max_velocity,
                "max_acceleration": max_acceleration,
                "average_drag": avg_drag,
                "simulation_successful": True,
            }
            logger.info(f"Successfully parsed simulation results from {csv_file_path}")
            return results

        except Exception as e:
            logger.error(f"Error parsing simulation results from {csv_file_path}: {e}")
            return {"simulation_successful": False, "error": str(e)}

    @staticmethod
    def _first_value(row_data: Dict[str, float], column_names: tuple[str, ...]) -> float:
        for name in column_names:
            if name in row_data:
                return row_data[name]
        return 0.0
