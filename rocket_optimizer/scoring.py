from typing import Dict, Any, Optional

from .utils import logger
from .config import (
    ALTITUDE_WEIGHT, STABILITY_WEIGHT, DRAG_WEIGHT, TARGET_STABILITY_MARGIN_CALIBERS, TARGET_ALTITUDE
)

class FitnessCalculator:
    """
    Calculates the competition score for a rocket design based on Space Koshien 2026 rules.
    Official Rules:
    - B-Motor Target: 250 ft (76 m), Flight Time: 16-18 s
    - C-Motor Target: 459 ft (140 m), Flight Time: 25-28 s
    - Altitude Penalty: |actual_ft - target_ft| (1 pt per 1 ft error)
    - Duration Penalty: 4 pts per 1/100 sec outside target duration window
    - Landing Bonus: -5 pts if egg+altimeter section lands within 5m radius of launch point
    """

    def __init__(self, target_altitude: Optional[float] = TARGET_ALTITUDE, motor_class: str = "C"):
        self.target_altitude = target_altitude
        self.motor_class = motor_class.upper() if motor_class else "C"
        self.target_stability_min = TARGET_STABILITY_MARGIN_CALIBERS[0]
        self.target_stability_max = TARGET_STABILITY_MARGIN_CALIBERS[1]

        # Targets based on Space Koshien rules
        if self.target_altitude is not None and abs(self.target_altitude - 76.0) < 10.0:
            self.target_altitude_ft = 250.0  # 76m B-motor target
            self.target_duration_window = (16.0, 18.0)
        else:
            self.target_altitude_ft = 459.0  # 140m C-motor target
            self.target_duration_window = (25.0, 28.0)

        logger.info(
            f"FitnessCalculator initialized (Target Alt: {self.target_altitude}m / {self.target_altitude_ft}ft, "
            f"Target Duration: {self.target_duration_window}s, Stability: {self.target_stability_min}-{self.target_stability_max} cal)"
        )

    def calculate_fitness(self,
                          altitude: float,
                          stability: float,
                          drag: float,
                          simulation_successful: bool,
                          flight_time: float = 20.0,
                          landing_distance: float = 0.0) -> float:
        """
        Calculates fitness score. Higher fitness is better (negated total penalty score).
        """
        if not simulation_successful:
            logger.debug("Penalizing due to simulation failure.")
            return -10000.0

        penalty_points = 0.0

        # 1. Altitude Penalty (1 point per 1 ft deviation from target altitude)
        if self.target_altitude is not None:
            actual_alt_ft = altitude * 3.28084
            alt_penalty = abs(actual_alt_ft - self.target_altitude_ft)
            penalty_points += alt_penalty
            logger.debug(f"Altitude: {actual_alt_ft:.1f}ft vs target {self.target_altitude_ft}ft -> Penalty: {alt_penalty:.2f} pts")
        else:
            # Maximum altitude mode: negative penalty for altitude
            penalty_points -= altitude * ALTITUDE_WEIGHT

        # 2. Flight Duration Penalty (4 pts per 1/100 sec outside window in target altitude mode)
        if self.target_altitude is not None:
            min_time, max_time = self.target_duration_window
            if min_time <= flight_time <= max_time:
                duration_penalty = 0.0
                logger.debug(f"Flight duration {flight_time:.2f}s within target window [{min_time}-{max_time}]s")
            elif flight_time < min_time:
                dur_error_sec = min_time - flight_time
                duration_penalty = (dur_error_sec * 100.0) * 4.0
                logger.debug(f"Flight duration {flight_time:.2f}s below min {min_time}s -> Penalty: {duration_penalty:.2f} pts")
            else:
                dur_error_sec = flight_time - max_time
                duration_penalty = (dur_error_sec * 100.0) * 4.0
                logger.debug(f"Flight duration {flight_time:.2f}s above max {max_time}s -> Penalty: {duration_penalty:.2f} pts")
            penalty_points += duration_penalty


        # 3. Landing Position Bonus (-5 points if landing within 5m of launch point)
        landing_bonus = 0.0
        if landing_distance <= 5.0:
            landing_bonus = 5.0
            penalty_points -= landing_bonus
            logger.debug(f"Landing distance {landing_distance:.2f}m <= 5.0m -> Bonus: -5.0 penalty pts")

        # 4. Stability Safety Penalty
        if not (self.target_stability_min <= stability <= self.target_stability_max):
            if stability < self.target_stability_min:
                penalty_points += (self.target_stability_min - stability) * 100.0
            else:
                penalty_points += (stability - self.target_stability_max) * 20.0

        # 5. Drag Penalty
        penalty_points += drag * DRAG_WEIGHT

        # Fitness is negated penalty points (higher is better for DEAP FitnessMax)
        fitness = 1000.0 - penalty_points
        return fitness


