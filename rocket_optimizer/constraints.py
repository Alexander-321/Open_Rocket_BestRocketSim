from typing import Dict, Any

from .config import FIXED_CONSTRAINTS, MAX_ROCKET_MASS, MAX_TOTAL_IMPULSE
from .utils import logger

VALID_NOSE_SHAPES = {"CONICAL", "OGIVE", "PARABOLIC"}

# Default body tube length in meters (matches template); used for geometric
# checks when no explicit body_length is provided in design_parameters.
DEFAULT_BODY_LENGTH = 0.3


class ConstraintHandler:
    """Manages and applies fixed design constraints to rocket parameters."""

    def __init__(self, fixed_constraints: Dict[str, Any] = FIXED_CONSTRAINTS):
        self.fixed_constraints = fixed_constraints
        logger.info(f"Initialized ConstraintHandler with fixed constraints: {self.fixed_constraints}")

    def apply_fixed_constraints(self, design_parameters: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in self.fixed_constraints.items():
            if key in design_parameters and design_parameters[key] != value:
                logger.debug(f"Overriding {key}: {design_parameters[key]} with fixed constraint value: {value}")
            design_parameters[key] = value
        return design_parameters

    def validate_design(self, design_parameters: Dict[str, Any]) -> bool:
        # --- Fixed constraint check ---
        for key, value in self.fixed_constraints.items():
            if key in design_parameters and design_parameters[key] != value:
                logger.warning(
                    f"Design violates fixed constraint: {key} expected {value}, got {design_parameters[key]}"
                )
                return False

        tip = design_parameters.get("fin_tip_chord")
        root = design_parameters.get("fin_root_chord")
        if tip is not None and root is not None and tip > root:
            logger.debug(f"Invalid fin geometry: tip_chord ({tip}) > root_chord ({root})")
            return False

        fin_count = design_parameters.get("fin_count")
        if fin_count is not None and fin_count not in (3, 4):
            logger.debug(f"Invalid fin count: {fin_count}")
            return False

        shape = design_parameters.get("nose_cone_shape")
        if shape is not None and str(shape).upper() not in VALID_NOSE_SHAPES:
            logger.debug(f"Invalid nose cone shape: {shape}")
            return False

        for key in ("nose_cone_length", "fin_root_chord", "fin_tip_chord", "fin_thickness", "body_length", "body_diameter"):
            value = design_parameters.get(key)
            if value is not None and value <= 0:
                logger.debug(f"Non-positive dimension: {key}={value}")
                return False

        # Body diameter upper/lower reasonable limits (0.015m to 0.10m)
        diameter = design_parameters.get("body_diameter")
        if diameter is not None and not (0.015 <= diameter <= 0.10):
            logger.debug(f"Body diameter out of bounds: {diameter}")
            return False

        sweep = design_parameters.get("fin_sweep")
        if sweep is not None and sweep < 0:
            logger.debug(f"Negative fin sweep: fin_sweep={sweep}")
            return False

        # --- Geometric attachment rules ---
        # Sweep must not exceed root chord (prevents fins extending behind
        # their mounting point).
        if sweep is not None and root is not None and sweep > root:
            logger.debug(
                f"Fin sweep ({sweep}) exceeds root chord ({root}); "
                "fin would extend past its mounting edge"
            )
            return False

        # Root chord must fit within the body tube.
        body_length = design_parameters.get("body_length", DEFAULT_BODY_LENGTH)
        if root is not None and root >= body_length:
            logger.debug(
                f"Fin root chord ({root}) >= body tube length ({body_length}); "
                "fin cannot be attached"
            )
            return False

        # Check overall rocket length (Nose cone + body tube) for competition requirements
        nose_len = design_parameters.get("nose_cone_length", 0.1)
        total_length = nose_len + body_length
        min_length = design_parameters.get("min_rocket_length", 0.3)
        if min_length is not None and total_length < min_length:
            logger.debug(
                f"Total rocket length ({total_length:.3f}m) violates minimum required length ({min_length:.3f}m)"
            )
            return False

        for key in ("fin_position", "launch_lug_position"):
            value = design_parameters.get(key)
            if value is not None and not (0.0 <= value <= 1.0):
                logger.debug(f"Out-of-range normalized position: {key}={value}")
                return False

        # --- Competition recovery system checks ---
        recovery_type = design_parameters.get("recovery_type", "Parachute")
        if recovery_type.lower() != "parachute":
            logger.debug(f"Invalid recovery type: {recovery_type}. Competition permits parachutes only.")
            return False

        recovery_systems_count = design_parameters.get("recovery_systems_count", 2)
        if recovery_systems_count < 2:
            logger.debug(f"Insufficient recovery systems ({recovery_systems_count}). Competition requires 2 separate recovery systems.")
            return False

        separable_sections = design_parameters.get("separable_sections", True)
        if not separable_sections:
            logger.debug("Sections cannot be separately recovered. Competition requires separable payload and engine sections.")
            return False

        return True

    def validate_simulation_constraints(
        self, sim_results: Dict[str, Any], enforce_mass: bool = True
    ) -> bool:
        """Validates simulated rocket mass and total motor impulse against Space Koshien 2026 rules.

        The optimizer calls this with ``enforce_mass=False``: an overweight design
        is scored with a graded mass penalty instead of being discarded, so the
        search can walk ballast back under the limit.
        """
        if not sim_results or not sim_results.get("simulation_successful", False):
            return False

        total_mass = sim_results.get("total_mass")
        if enforce_mass and total_mass is not None and total_mass > MAX_ROCKET_MASS:
            logger.warning(
                f"Total launch mass ({total_mass*1000:.1f}g) exceeds maximum competition limit "
                f"({MAX_ROCKET_MASS*1000:.0f}g)"
            )
            return False

        total_impulse = sim_results.get("total_impulse")
        if total_impulse is not None and total_impulse > MAX_TOTAL_IMPULSE:
            logger.warning(
                f"Motor total impulse ({total_impulse:.1f} N*s) exceeds maximum competition limit "
                f"({MAX_TOTAL_IMPULSE:.0f} N*s)"
            )
            return False

        return True


