import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
TEMPLATES_DIR = str(PACKAGE_DIR / "templates")
RESULTS_DIR = str(PACKAGE_DIR / "results")

# OpenRocket Configuration
DEFAULT_OPENROCKET_JAR_PATH = "/Applications/OpenRocket.app/Contents/Resources/app/jar/OpenRocket-24.12.jar"


def resolve_openrocket_jar_path() -> str:
    """Locate an OpenRocket jar: OPENROCKET_JAR_PATH env var, the configured
    default path, then any jar cached/installed for orlab."""
    env_path = os.environ.get("OPENROCKET_JAR_PATH")
    if env_path:
        return env_path
    if os.path.exists(DEFAULT_OPENROCKET_JAR_PATH):
        return DEFAULT_OPENROCKET_JAR_PATH
    try:
        from orlab.jars import find_installed, jar_cache_dir

        installed = find_installed()
        if installed is not None:
            return str(installed.jar)
        cached = sorted(Path(jar_cache_dir()).glob("OpenRocket-*.jar"))
        if cached:
            return str(cached[-1])
    except Exception:
        pass
    return DEFAULT_OPENROCKET_JAR_PATH


OPENROCKET_JAR_PATH = resolve_openrocket_jar_path()

# Motor selection. The bundled template ships several flight configurations
# (A8, B4, C6); the motor actually flown is set explicitly so the simulated
# apogee matches the competition class instead of whatever the template's
# first simulation happened to use.
MOTOR_DESIGNATION = "C6"
MOTOR_MANUFACTURER = "Estes"
MOTOR_EJECTION_DELAY = 5.0

# Genetic Algorithm Parameters
POPULATION_SIZE = 50
NUM_GENERATIONS = 20
MUTATION_RATE = 0.4
MUTATION_GENE_PROBABILITY = 0.3
CROSSOVER_RATE = 0.8
ELITISM_COUNT = 5

# Quick-test mode: set ROCKET_OPTIMIZER_QUICK=1 for a fast smoke run
if os.environ.get("ROCKET_OPTIMIZER_QUICK"):
    POPULATION_SIZE = 4
    NUM_GENERATIONS = 2

# Target Altitude Optimization (Set to float, e.g. 140.0 or 76.0, or None for max altitude)
TARGET_ALTITUDE = None

# Competition Rule Constraints (Space Koshien 2026: length >= 300mm, mass <= 150g)
MIN_ROCKET_LENGTH = 0.3  # meters (300mm)
MAX_ROCKET_MASS = 0.15   # kg (150g)
MAX_TOTAL_IMPULSE = 10.0  # N*s

# Preset Configurations
COMPETITION_PRESETS = {
    "space-koshien-2026-c": {
        "description": "Space Koshien 2026 C-Motor Target (140m / 459ft)",
        "target_altitude": 140.0,
        "min_rocket_length": 0.3,
        "max_rocket_mass": 0.15,
        "motor": "C6",
        "motor_manufacturer": "Estes",
        "motor_delay": 5.0,
        "duration_window": (25.0, 28.0),
    },
    "space-koshien-2026-b": {
        "description": "Space Koshien 2026 B-Motor Target (76m / 250ft)",
        "target_altitude": 76.0,
        "min_rocket_length": 0.3,
        "max_rocket_mass": 0.15,
        "motor": "B6",
        "motor_manufacturer": "Estes",
        "motor_delay": 4.0,
        "duration_window": (16.0, 18.0),
    },
    "max-altitude": {
        "description": "Maximum Altitude Optimization Mode",
        "target_altitude": None,
        "min_rocket_length": 0.3,
        "max_rocket_mass": None,
        "motor": "C6",
        "motor_manufacturer": "Estes",
        "motor_delay": 5.0,
        "duration_window": None,
    },
}

# Rocket Design Constraints (override generated values when set)
FIXED_CONSTRAINTS = {}

# Optimization Objective
TARGET_STABILITY_MARGIN_CALIBERS = (1.0, 2.0)
ALTITUDE_WEIGHT = 1.0
STABILITY_WEIGHT = 0.5
DRAG_WEIGHT = 0.1

# Competition scoring weights (penalty points; lower penalty = higher fitness)
ALTITUDE_PENALTY_POINTS_PER_FT = 1.0
DURATION_PENALTY_POINTS_PER_SECOND = 4.0
STABILITY_PENALTY_POINTS_PER_CAL_UNDER = 100.0
STABILITY_PENALTY_POINTS_PER_CAL_OVER = 20.0
MASS_PENALTY_POINTS_PER_GRAM_OVER = 20.0
LANDING_BONUS_POINTS = 5.0
LANDING_BONUS_RADIUS_M = 5.0

# Design variable search bounds (SI units). Used for random initialization and
# to repair individuals produced by crossover/mutation.
DESIGN_BOUNDS = {
    "body_length": (0.20, 0.50),
    "body_diameter": (0.024, 0.040),
    "nose_cone_length": (0.05, 0.20),
    "fin_root_chord": (0.03, 0.12),
    "fin_tip_chord": (0.01, 0.12),
    "fin_sweep": (0.0, 0.12),
    "fin_thickness": (0.001, 0.004),
    "fin_height": (0.02, 0.06),
    "fin_position": (0.0, 1.0),
    "launch_lug_position": (0.0, 1.0),
    # Ballast is the primary lever for hitting a *target* altitude: with a
    # fixed motor the apogee is tuned by adding mass, not by drag alone.
    "ballast_mass": (0.0, 0.08),
    # Parachute size is the lever for the flight-duration window.
    "parachute_diameter": (0.15, 0.60),
}

# Simulation Parameters
SIMULATION_TIMEOUT_SECONDS = 120

# Data Storage
RESULTS_CSV = os.path.join(RESULTS_DIR, "optimization_results.csv")
BEST_ROCKET_FILE = os.path.join(RESULTS_DIR, "best_rocket.ork")


def create_run_directory(preset_name=None, target_altitude=None, run_name=None):
    """
    Creates a timestamped subfolder inside RESULTS_DIR for the optimization run.
    Example: results/run_20260814_143000_space-koshien-2026-c
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if run_name:
        tag = run_name
    elif preset_name:
        tag = preset_name
    elif target_altitude is not None:
        tag = f"target_{int(target_altitude)}m"
    else:
        tag = "max_altitude"

    folder_name = f"run_{timestamp}_{tag}"
    run_dir = os.path.join(RESULTS_DIR, folder_name)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir

