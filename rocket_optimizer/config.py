import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
TEMPLATES_DIR = str(PACKAGE_DIR / "templates")
RESULTS_DIR = str(PACKAGE_DIR / "results")

# OpenRocket Configuration
OPENROCKET_JAR_PATH = "/Applications/OpenRocket.app/Contents/Resources/app/jar/OpenRocket-24.12.jar"

# Genetic Algorithm Parameters
POPULATION_SIZE = 50
NUM_GENERATIONS = 20
MUTATION_RATE = 0.1
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

# Preset Configurations
COMPETITION_PRESETS = {
    "space-koshien-2026-c": {
        "description": "Space Koshien 2026 C-Motor Target (140m / 459ft)",
        "target_altitude": 140.0,
        "min_rocket_length": 0.3,
        "max_rocket_mass": 0.15,
    },
    "space-koshien-2026-b": {
        "description": "Space Koshien 2026 B-Motor Target (76m / 250ft)",
        "target_altitude": 76.0,
        "min_rocket_length": 0.3,
        "max_rocket_mass": 0.15,
    },
    "max-altitude": {
        "description": "Maximum Altitude Optimization Mode",
        "target_altitude": None,
        "min_rocket_length": 0.3,
        "max_rocket_mass": None,
    },
}

# Rocket Design Constraints (override generated values when set)
FIXED_CONSTRAINTS = {}

# Optimization Objective
TARGET_STABILITY_MARGIN_CALIBERS = (1.0, 2.0)
ALTITUDE_WEIGHT = 1.0
STABILITY_WEIGHT = 0.5
DRAG_WEIGHT = 0.1

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

