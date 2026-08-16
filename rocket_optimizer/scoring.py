import math
from typing import Optional, Tuple

from .utils import logger
from .config import (
    ALTITUDE_PENALTY_POINTS_PER_FT,
    ALTITUDE_WEIGHT,
    DRAG_WEIGHT,
    DURATION_PENALTY_POINTS_PER_SECOND,
    LANDING_BONUS_POINTS,
    LANDING_BONUS_RADIUS_M,
    MASS_PENALTY_POINTS_PER_GRAM_OVER,
    MAX_ROCKET_MASS,
    STABILITY_PENALTY_POINTS_PER_CAL_OVER,
    STABILITY_PENALTY_POINTS_PER_CAL_UNDER,
    TARGET_ALTITUDE,
    TARGET_STABILITY_MARGIN_CALIBERS,
)

METERS_PER_FOOT = 0.3048
FEET_PER_METER = 1.0 / METERS_PER_FOOT

# Duration windows by motor class when a preset does not supply one.
DEFAULT_DURATION_WINDOWS = {"B": (16.0, 18.0), "C": (25.0, 28.0)}


class FitnessCalculator:
    """
    Calculates the competition score for a rocket design based on Space Koshien 2026 rules.
    Official Rules:
    - B-Motor Target: 250 ft (76 m), Flight Time: 16-18 s
    - C-Motor Target: 459 ft (140 m), Flight Time: 25-28 s
    - Altitude Penalty: |actual_ft - target_ft| (1 pt per 1 ft error)
    - Duration Penalty: points per second outside the target duration window
    - Landing Bonus: -5 pts if egg+altimeter section lands within 5m radius of launch point
    """

    def __init__(
        self,
        target_altitude: Optional[float] = TARGET_ALTITUDE,
        motor_class: str = "C",
        duration_window: Optional[Tuple[float, float]] = None,
        max_mass: Optional[float] = MAX_ROCKET_MASS,
    ):
        self.target_altitude = target_altitude
        self.motor_class = motor_class.upper() if motor_class else "C"
        self.max_mass = max_mass
        self.target_stability_min = TARGET_STABILITY_MARGIN_CALIBERS[0]
        self.target_stability_max = TARGET_STABILITY_MARGIN_CALIBERS[1]

        # The scored target is the target the caller asked for, not a preset
        # constant: a 120 m run must be scored against 120 m.
        self.target_altitude_ft = (
            target_altitude * FEET_PER_METER if target_altitude is not None else None
        )
        self.target_duration_window = duration_window or DEFAULT_DURATION_WINDOWS.get(
            self.motor_class, DEFAULT_DURATION_WINDOWS["C"]
        )

        target_ft_str = (
            f"{self.target_altitude_ft:.1f}ft" if self.target_altitude_ft is not None else "n/a"
        )
        logger.info(
            f"FitnessCalculator initialized (Target Alt: {self.target_altitude}m / {target_ft_str}, "
            f"Target Duration: {self.target_duration_window}s, "
            f"Stability: {self.target_stability_min}-{self.target_stability_max} cal)"
        )

    def calculate_fitness(self,
                          altitude: float,
                          stability: float,
                          drag: float,
                          simulation_successful: bool,
                          flight_time: float = 20.0,
                          landing_distance: float = 0.0,
                          total_mass: Optional[float] = None) -> float:
        """
        Calculates fitness score. Higher fitness is better (negated total penalty score).
        """
        if not simulation_successful:
            logger.debug("Penalizing due to simulation failure.")
            return -10000.0

        penalty_points = 0.0

        # 1. Altitude Penalty (1 point per 1 ft deviation from target altitude)
        if self.target_altitude_ft is not None:
            actual_alt_ft = altitude * FEET_PER_METER
            alt_penalty = abs(actual_alt_ft - self.target_altitude_ft) * ALTITUDE_PENALTY_POINTS_PER_FT
            penalty_points += alt_penalty
            logger.debug(
                f"Altitude: {actual_alt_ft:.1f}ft vs target {self.target_altitude_ft:.1f}ft "
                f"-> Penalty: {alt_penalty:.2f} pts"
            )
        else:
            # Maximum altitude mode: negative penalty for altitude
            penalty_points -= altitude * ALTITUDE_WEIGHT

        # 2. Flight Duration Penalty (only meaningful in target altitude mode)
        if self.target_altitude is not None and not math.isnan(flight_time):
            min_time, max_time = self.target_duration_window
            dur_error_sec = max(0.0, min_time - flight_time, flight_time - max_time)
            duration_penalty = dur_error_sec * DURATION_PENALTY_POINTS_PER_SECOND
            penalty_points += duration_penalty
            logger.debug(
                f"Flight duration {flight_time:.2f}s vs window [{min_time}-{max_time}]s "
                f"-> Penalty: {duration_penalty:.2f} pts"
            )

        # 3. Landing Position Bonus (within 5m of launch point)
        if not math.isnan(landing_distance) and landing_distance <= LANDING_BONUS_RADIUS_M:
            penalty_points -= LANDING_BONUS_POINTS
            logger.debug(f"Landing distance {landing_distance:.2f}m -> Bonus: -{LANDING_BONUS_POINTS} pts")

        # 4. Stability Safety Penalty
        if not math.isnan(stability) and not (self.target_stability_min <= stability <= self.target_stability_max):
            if stability < self.target_stability_min:
                penalty_points += (self.target_stability_min - stability) * STABILITY_PENALTY_POINTS_PER_CAL_UNDER
            else:
                penalty_points += (stability - self.target_stability_max) * STABILITY_PENALTY_POINTS_PER_CAL_OVER

        # 5. Mass Penalty (graded, so the search can walk back under the limit)
        if self.max_mass is not None and total_mass is not None and total_mass > self.max_mass:
            grams_over = (total_mass - self.max_mass) * 1000.0
            penalty_points += grams_over * MASS_PENALTY_POINTS_PER_GRAM_OVER

        # 6. Drag Penalty
        penalty_points += drag * DRAG_WEIGHT

        # Fitness is negated penalty points (higher is better for DEAP FitnessMax)
        fitness = 1000.0 - penalty_points
        return fitness
