import argparse
import os
import sys

from .optimizer import RocketOptimizer
from .visualization import RocketVisualizer
from .config import (
    OPENROCKET_JAR_PATH, TEMPLATES_DIR, RESULTS_DIR, POPULATION_SIZE, NUM_GENERATIONS,
    COMPETITION_PRESETS, TARGET_ALTITUDE, PROJECT_ROOT, PACKAGE_DIR
)
from .utils import logger


def run_interactive_menu():
    print("=" * 60)
    print("       🚀 ROCKET OPTIMIZER & DESIGN GENERATOR 🚀       ")
    print("=" * 60)
    print("Select Optimization Mode:")
    print("  1) Space Koshien 2026 C-Motor Target (140m / 459ft)")
    print("  2) Space Koshien 2026 B-Motor Target (76m / 250ft)")
    print("  3) Custom Target Altitude")
    print("  4) Maximum Altitude (No Target Limit)")
    print("-" * 60)

    try:
        choice = input("Enter choice (1-4) [default: 1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if choice == "2":
        preset_key = "space-koshien-2026-b"
        target_alt = COMPETITION_PRESETS[preset_key]["target_altitude"]
    elif choice == "3":
        preset_key = None
        alt_str = input("Enter target altitude in meters (e.g., 140.0): ").strip()
        try:
            target_alt = float(alt_str)
        except ValueError:
            print("Invalid altitude entered, defaulting to 140.0m.")
            target_alt = 140.0
    elif choice == "4":
        preset_key = "max-altitude"
        target_alt = None
    else:
        preset_key = "space-koshien-2026-c"
        target_alt = COMPETITION_PRESETS[preset_key]["target_altitude"]

    pop_str = input(f"Enter population size [{POPULATION_SIZE}]: ").strip()
    pop_size = int(pop_str) if pop_str.isdigit() else POPULATION_SIZE

    gen_str = input(f"Enter generations count [{NUM_GENERATIONS}]: ").strip()
    num_gens = int(gen_str) if gen_str.isdigit() else NUM_GENERATIONS

    return target_alt, pop_size, num_gens, preset_key


def main():
    parser = argparse.ArgumentParser(description="Rocket Optimizer using Genetic Algorithm")
    parser.add_argument(
        "--population",
        type=int,
        default=POPULATION_SIZE,
        help="Population size for the genetic algorithm",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=NUM_GENERATIONS,
        help="Number of generations to run",
    )
    parser.add_argument(
        "--template",
        type=str,
        default=os.path.join(TEMPLATES_DIR, "base.ork"),
        help="Path to the base OpenRocket template (.ork)",
    )
    parser.add_argument(
        "--target-altitude",
        type=float,
        default=TARGET_ALTITUDE,
        help="Target altitude in meters for target altitude optimization (e.g., 140.0 for Space Koshien C-Motor)",
    )
    parser.add_argument(
        "--preset",
        type=str,
        choices=list(COMPETITION_PRESETS.keys()),
        default=None,
        help="Competition preset configuration (e.g., space-koshien-2026-c, space-koshien-2026-b, max-altitude)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive setup menu",
    )
    args = parser.parse_args()

    target_altitude = args.target_altitude
    pop_size = args.population
    num_gens = args.generations
    preset_key = args.preset

    if args.interactive:
        target_altitude, pop_size, num_gens, preset_key = run_interactive_menu()
    elif preset_key in COMPETITION_PRESETS:
        target_altitude = COMPETITION_PRESETS[preset_key]["target_altitude"]

    logger.info("Starting Rocket Optimization Application")
    logger.info(f"Loaded rocket_optimizer module from: {PACKAGE_DIR}")
    logger.info(f"Project root resolved to: {PROJECT_ROOT}")
    if preset_key:
        logger.info(f"Using Preset: {preset_key} - {COMPETITION_PRESETS[preset_key]['description']}")
    if target_altitude is not None:
        logger.info(f"Optimization Mode: Target Altitude Matching ({target_altitude:.1f} m)")
    else:
        logger.info("Optimization Mode: Maximum Altitude")

    if not os.path.exists(OPENROCKET_JAR_PATH):
        logger.error(
            f"OpenRocket JAR not found at {OPENROCKET_JAR_PATH}. "
            "Please update OPENROCKET_JAR_PATH in config.py"
        )
        return 1

    if not os.path.exists(args.template):
        logger.error(
            f"Base OpenRocket template not found at {args.template}. "
            "Please provide a valid template path."
        )
        return 1

    os.makedirs(RESULTS_DIR, exist_ok=True)

    optimizer = RocketOptimizer(
        population_size=pop_size,
        num_generations=num_gens,
        template_path=args.template,
        target_altitude=target_altitude,
        preset_name=preset_key,
    )
    best_rocket = optimizer.run_optimization()

    logger.info("\n" + "=" * 60)
    logger.info("              --- OPTIMIZATION SUMMARY ---")
    logger.info("=" * 60)
    logger.info(f"Body Length:        {best_rocket.body_length * 1000:.1f} mm")
    logger.info(f"Body Diameter:      {best_rocket.body_diameter * 1000:.1f} mm")
    logger.info(f"Nose Cone Length:   {best_rocket.nose_cone_length * 1000:.1f} mm")
    logger.info(f"Nose Cone Shape:    {best_rocket.nose_cone_shape}")
    logger.info(f"Fin Count:          {best_rocket.fin_count}")
    logger.info(f"Fin Root Chord:     {best_rocket.fin_root_chord * 1000:.1f} mm")
    logger.info(f"Fin Tip Chord:      {best_rocket.fin_tip_chord * 1000:.1f} mm")
    logger.info(f"Fin Sweep:          {best_rocket.fin_sweep * 1000:.1f} mm")
    logger.info(f"Fin Thickness:      {best_rocket.fin_thickness * 1000:.2f} mm")
    logger.info(f"Fin Height:         {best_rocket.fin_height * 1000:.1f} mm")
    logger.info(f"Fin Position:       {best_rocket.fin_position * 100:.1f}%")
    logger.info(f"Launch Lug Pos:     {best_rocket.launch_lug_position * 100:.1f}%")
    logger.info(f"Ballast Mass:       {best_rocket.ballast_mass * 1000:.1f} g")
    logger.info(f"Parachute Diameter: {best_rocket.parachute_diameter * 1000:.0f} mm")
    logger.info(f"Motor:              {optimizer.motor_designation} ({optimizer.motor_manufacturer})")
    logger.info("-" * 60)
    logger.info(f"Simulated Altitude: {best_rocket.max_altitude:.2f} m")
    if target_altitude is not None:
        diff = abs(best_rocket.max_altitude - target_altitude)
        logger.info(f"Target Altitude:    {target_altitude:.2f} m (Error: {diff:.2f} m)")
    logger.info(f"Flight Duration:    {best_rocket.flight_time:.2f} s")
    logger.info(f"Total Launch Mass:  {best_rocket.total_mass * 1000:.1f} g")
    logger.info(f"Stability Margin:   {best_rocket.stability:.2f} cal")
    logger.info(f"Average Drag Force: {best_rocket.drag:.3f} N")
    logger.info(f"Fitness Score:      {optimizer.best_fitness:.2f}")
    logger.info("=" * 60)

    logger.info("\nGenerating evolution plots...")
    visualizer = RocketVisualizer(
        results_csv_path=optimizer.results_csv,
        results_dir=optimizer.results_dir
    )
    visualizer.generate_all_plots()
    logger.info(f"All run artifacts saved to: {optimizer.results_dir}")


    logger.info("Rocket Optimization Application Finished Successfully!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
