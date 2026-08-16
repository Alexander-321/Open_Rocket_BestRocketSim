import random
import os
import csv
from copy import deepcopy
from dataclasses import dataclass, asdict, fields
from typing import List, Dict, Any, Tuple, Optional

from deap import base, creator, tools, algorithms

from datetime import datetime

from .utils import logger
from .config import (
    MUTATION_RATE, MUTATION_GENE_PROBABILITY, CROSSOVER_RATE, ELITISM_COUNT,
    RESULTS_DIR, RESULTS_CSV, BEST_ROCKET_FILE, FIXED_CONSTRAINTS,
    POPULATION_SIZE as DEFAULT_POPULATION_SIZE,
    NUM_GENERATIONS as DEFAULT_NUM_GENERATIONS,
    MIN_ROCKET_LENGTH, MAX_ROCKET_MASS, TARGET_STABILITY_MARGIN_CALIBERS,
    COMPETITION_PRESETS, DESIGN_BOUNDS, MOTOR_DESIGNATION, MOTOR_MANUFACTURER,
    MOTOR_EJECTION_DELAY,
    create_run_directory
)
from .generator import RocketGenerator
from .simulation import OpenRocketSimulator
from .scoring import FitnessCalculator
from .constraints import ConstraintHandler
from .openrocket_backend import OpenRocketBackend

DESIGN_FIELDS = {
    "body_length",
    "body_diameter",
    "nose_cone_length",
    "nose_cone_shape",
    "fin_root_chord",
    "fin_tip_chord",
    "fin_sweep",
    "fin_thickness",
    "fin_height",
    "fin_count",
    "fin_position",
    "launch_lug_position",
    "ballast_mass",
    "parachute_diameter",
}

# Fitness returned for designs that cannot be simulated. Finite so tournament
# selection and statistics stay well-defined.
FAILED_FITNESS = -1.0e6

METRIC_FIELDS = {
    "max_altitude",
    "flight_time",
    "stability",
    "drag",
    "total_mass",
    "landing_distance",
    "is_valid",
    "simulation_successful",
}


@dataclass
class Rocket:
    """A single rocket design individual for the genetic algorithm."""
    body_length: float = 0.3
    body_diameter: float = 0.03
    nose_cone_length: float = 0.1
    nose_cone_shape: str = "OGIVE"
    fin_root_chord: float = 0.05
    fin_tip_chord: float = 0.025
    fin_sweep: float = 0.01
    fin_thickness: float = 0.002
    fin_height: float = 0.03
    fin_count: int = 3
    fin_position: float = 0.5
    launch_lug_position: float = 0.3
    ballast_mass: float = 0.0
    parachute_diameter: float = 0.30
    max_altitude: float = 0.0
    flight_time: float = 0.0
    stability: float = 0.0
    drag: float = 0.0
    total_mass: float = 0.0
    landing_distance: float = 0.0
    is_valid: bool = False
    simulation_successful: bool = False


    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, params: Dict[str, Any]) -> "Rocket":
        design = {f.name: params[f.name] for f in fields(cls) if f.name in DESIGN_FIELDS and f.name in params}
        rocket = cls(**design)
        for metric in METRIC_FIELDS:
            if metric in params:
                setattr(rocket, metric, params[metric])
        return rocket


if not hasattr(creator, "FitnessMax"):
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMax)


def _get_rocket(individual: creator.Individual) -> Rocket:
    """DEAP individuals store a single Rocket at index 0."""
    return individual[0]


class RocketOptimizer:
    """Orchestrates the genetic algorithm for optimizing rocket designs."""

    def __init__(
        self,
        population_size: int = DEFAULT_POPULATION_SIZE,
        num_generations: int = DEFAULT_NUM_GENERATIONS,
        template_path: Optional[str] = None,
        target_altitude: Optional[float] = None,
        preset_name: Optional[str] = None,
        results_dir: Optional[str] = None,
    ):
        self.population_size = population_size
        self.num_generations = num_generations
        self.template_path = template_path
        self.target_altitude = target_altitude
        self.preset_name = preset_name

        preset = COMPETITION_PRESETS.get(preset_name or "", {})
        self.motor_designation = preset.get("motor", MOTOR_DESIGNATION)
        self.motor_manufacturer = preset.get("motor_manufacturer", MOTOR_MANUFACTURER)
        self.motor_delay = preset.get("motor_delay", MOTOR_EJECTION_DELAY)
        self.duration_window = preset.get("duration_window")
        self.max_mass = preset.get("max_rocket_mass", MAX_ROCKET_MASS)

        if results_dir is not None:
            self.results_dir = results_dir
            os.makedirs(self.results_dir, exist_ok=True)
        else:
            self.results_dir = create_run_directory(preset_name=preset_name, target_altitude=target_altitude)

        self.results_csv = os.path.join(self.results_dir, "optimization_results.csv")
        self.best_rocket_file = os.path.join(self.results_dir, "best_rocket.ork")
        self.summary_file = os.path.join(self.results_dir, "run_summary.txt")

        self.backend = OpenRocketBackend(
            template_path=self.template_path,
            motor_designation=self.motor_designation,
            motor_manufacturer=self.motor_manufacturer,
            motor_delay=self.motor_delay,
        )
        self.generator = RocketGenerator(backend=self.backend)
        self.simulator = OpenRocketSimulator(backend=self.backend, results_dir=self.results_dir)
        self.fitness_calculator = FitnessCalculator(
            target_altitude=self.target_altitude,
            motor_class=str(self.motor_designation)[0] if self.motor_designation else "C",
            duration_window=self.duration_window,
            max_mass=self.max_mass,
        )
        self.constraint_handler = ConstraintHandler()
        self._fitness_cache: Dict[Tuple[Any, ...], Tuple[float, Dict[str, Any]]] = {}

        self.toolbox = base.Toolbox()
        self._register_toolbox()

        self.population: List[creator.Individual] = []
        self.hof = tools.HallOfFame(1)
        self.best_fitness: float = float("-inf")

        self._initialize_results_csv()

    def _initialize_results_csv(self) -> None:
        os.makedirs(self.results_dir, exist_ok=True)
        if not os.path.exists(self.results_csv):
            with open(self.results_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Generation", "Individual_ID", "Fitness", "Max_Altitude", "Flight_Time",
                    "Stability", "Drag", "Total_Mass",
                    "Body_Length", "Body_Diameter",
                    "Nose_Cone_Length", "Nose_Cone_Shape", "Fin_Root_Chord", "Fin_Tip_Chord",
                    "Fin_Sweep", "Fin_Thickness", "Fin_Height", "Fin_Count", "Fin_Position",
                    "Launch_Lug_Position", "Ballast_Mass", "Parachute_Diameter",
                    "Is_Valid", "Simulation_Successful",
                ])

    def _log_rocket_to_csv(
        self,
        generation: int,
        individual_id: int,
        rocket: Rocket,
        fitness: Optional[float] = None,
    ) -> None:
        os.makedirs(self.results_dir, exist_ok=True)
        with open(self.results_csv, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                generation,
                individual_id,
                fitness if fitness is not None else FAILED_FITNESS,
                rocket.max_altitude,
                rocket.flight_time,
                rocket.stability,
                rocket.drag,
                rocket.total_mass,
                rocket.body_length,
                rocket.body_diameter,
                rocket.nose_cone_length,
                rocket.nose_cone_shape,
                rocket.fin_root_chord,
                rocket.fin_tip_chord,
                rocket.fin_sweep,
                rocket.fin_thickness,
                rocket.fin_height,
                rocket.fin_count,
                rocket.fin_position,
                rocket.launch_lug_position,
                rocket.ballast_mass,
                rocket.parachute_diameter,
                rocket.is_valid,
                rocket.simulation_successful,
            ])


    def _generate_random_rocket_params(self) -> Dict[str, Any]:
        body_len = random.uniform(*DESIGN_BOUNDS["body_length"])
        body_dia = random.uniform(*DESIGN_BOUNDS["body_diameter"])
        root_chord = random.uniform(
            DESIGN_BOUNDS["fin_root_chord"][0],
            min(DESIGN_BOUNDS["fin_root_chord"][1], body_len * 0.4),
        )
        tip_chord = random.uniform(DESIGN_BOUNDS["fin_tip_chord"][0], root_chord)
        sweep = random.uniform(0.0, root_chord)
        return {
            "body_length": body_len,
            "body_diameter": body_dia,
            "nose_cone_length": random.uniform(*DESIGN_BOUNDS["nose_cone_length"]),
            "nose_cone_shape": random.choice(["CONICAL", "OGIVE", "PARABOLIC"]),
            "fin_root_chord": root_chord,
            "fin_tip_chord": tip_chord,
            "fin_sweep": sweep,
            "fin_thickness": random.uniform(*DESIGN_BOUNDS["fin_thickness"]),
            "fin_height": random.uniform(*DESIGN_BOUNDS["fin_height"]),
            "fin_count": random.choice([3, 4]),
            "fin_position": random.uniform(0.3, 0.7),
            "launch_lug_position": random.uniform(0.2, 0.5),
            "ballast_mass": random.uniform(*DESIGN_BOUNDS["ballast_mass"]),
            "parachute_diameter": random.uniform(*DESIGN_BOUNDS["parachute_diameter"]),
        }

    def _repair_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Pull a design back inside its bounds and geometric rules.

        Crossover and mutation routinely push genes out of range; repairing is
        what keeps the search moving, because a rejected individual carries no
        gradient information at all.
        """
        for key, (low, high) in DESIGN_BOUNDS.items():
            if key in params and isinstance(params[key], (int, float)):
                params[key] = min(max(float(params[key]), low), high)

        # Fins must fit the body tube and keep tip <= root, sweep <= root.
        max_root = max(DESIGN_BOUNDS["fin_root_chord"][0], params["body_length"] * 0.4)
        params["fin_root_chord"] = min(params["fin_root_chord"], max_root)
        params["fin_tip_chord"] = min(params["fin_tip_chord"], params["fin_root_chord"])
        params["fin_sweep"] = min(params["fin_sweep"], params["fin_root_chord"])

        if params.get("fin_count") not in (3, 4):
            params["fin_count"] = min(4, max(3, int(params.get("fin_count", 3))))

        if str(params.get("nose_cone_shape", "")).upper() not in {"CONICAL", "OGIVE", "PARABOLIC"}:
            params["nose_cone_shape"] = "OGIVE"

        # Total length must satisfy the competition minimum; grow the nose cone
        # first, then the body tube.
        shortfall = MIN_ROCKET_LENGTH - (params["nose_cone_length"] + params["body_length"])
        if shortfall > 0:
            nose_headroom = DESIGN_BOUNDS["nose_cone_length"][1] - params["nose_cone_length"]
            grow_nose = min(shortfall, nose_headroom)
            params["nose_cone_length"] += grow_nose
            shortfall -= grow_nose
            if shortfall > 0:
                params["body_length"] = min(
                    DESIGN_BOUNDS["body_length"][1], params["body_length"] + shortfall
                )

        return self.constraint_handler.apply_fixed_constraints(params)

    def _attr_rocket(self) -> Rocket:
        while True:
            raw_params = self._generate_random_rocket_params()
            final_params = self._repair_params(raw_params.copy())
            if self.constraint_handler.validate_design(final_params):
                rocket = Rocket(**{k: final_params[k] for k in DESIGN_FIELDS})
                rocket.is_valid = True
                return rocket

    def _register_toolbox(self) -> None:
        self.toolbox.register("attr_rocket", self._attr_rocket)
        self.toolbox.register("individual", tools.initRepeat, creator.Individual, self.toolbox.attr_rocket, 1)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
        self.toolbox.register("clone", deepcopy)

        self.toolbox.register("evaluate", self._evaluate_rocket)
        self.toolbox.register("mate_rocket", self._crossover_rocket, indpb=0.5)
        self.toolbox.register("mutate_rocket", self._mutate_rocket, indpb=MUTATION_GENE_PROBABILITY)

    def _design_key(self, rocket: Rocket) -> Tuple[Any, ...]:
        """Cache key over the design genes, rounded to sub-manufacturing precision."""
        key = []
        for field_name in sorted(DESIGN_FIELDS):
            value = getattr(rocket, field_name)
            key.append(round(value, 5) if isinstance(value, float) else value)
        return tuple(key)

    def _evaluate_rocket(self, individual: creator.Individual) -> Tuple[float]:
        rocket = _get_rocket(individual)

        if not rocket.is_valid:
            rocket.simulation_successful = False
            return (FAILED_FITNESS,)

        cache_key = self._design_key(rocket)
        cached = self._fitness_cache.get(cache_key)
        if cached is not None:
            fitness, metrics = cached
            for name, value in metrics.items():
                setattr(rocket, name, value)
            return (fitness,)

        try:
            simulation_results = self.simulator.run_simulation(rocket.to_dict())
            if simulation_results and simulation_results.get("simulation_successful", False):
                # Validate competition simulation constraints (total impulse <= 10 N*s).
                # Mass is scored as a graded penalty instead of a hard rejection.
                if not self.constraint_handler.validate_simulation_constraints(
                    simulation_results, enforce_mass=False
                ):
                    rocket.simulation_successful = False
                    return (-10000.0,)

                rocket.max_altitude = simulation_results["max_altitude"]
                # Stability leaving the launch rod is the meaningful safety
                # figure; the in-flight minimum dips arbitrarily after burnout.
                rocket.stability = simulation_results.get(
                    "stability_off_rod",
                    (simulation_results["min_stability"] + simulation_results["max_stability"]) / 2,
                )
                rocket.drag = simulation_results["average_drag"]
                rocket.flight_time = simulation_results.get("flight_time", 20.0)
                rocket.landing_distance = simulation_results.get("landing_distance", 0.0)
                rocket.total_mass = simulation_results.get("total_mass", 0.10)
                rocket.simulation_successful = True

                calculated_fitness = self.fitness_calculator.calculate_fitness(
                    altitude=rocket.max_altitude,
                    stability=rocket.stability,
                    drag=rocket.drag,
                    simulation_successful=True,
                    flight_time=rocket.flight_time,
                    landing_distance=rocket.landing_distance,
                    total_mass=rocket.total_mass,
                )
                logger.info(
                    f"Evaluated Rocket (Alt: {rocket.max_altitude:.2f}m, "
                    f"Time: {rocket.flight_time:.1f}s, Stab: {rocket.stability:.2f}cal, "
                    f"Mass: {rocket.total_mass * 1000:.1f}g, "
                    f"Landing Dist: {rocket.landing_distance:.1f}m, Fitness: {calculated_fitness:.2f})"
                )
                self._fitness_cache[cache_key] = (
                    calculated_fitness,
                    {name: getattr(rocket, name) for name in METRIC_FIELDS},
                )
                return (calculated_fitness,)

            rocket.simulation_successful = False
            return (-10000.0,)
        except Exception as e:
            rocket.simulation_successful = False
            logger.error(f"Error during rocket evaluation: {e}")
            return (-10000.0,)


    def _crossover_rocket(
        self,
        ind1: creator.Individual,
        ind2: creator.Individual,
        indpb: float,
    ) -> Tuple[creator.Individual, creator.Individual]:
        rocket1 = _get_rocket(ind1)
        rocket2 = _get_rocket(ind2)

        for attr in DESIGN_FIELDS:
            if attr in self.constraint_handler.fixed_constraints:
                continue
            if random.random() >= indpb:
                continue

            val1 = getattr(rocket1, attr)
            val2 = getattr(rocket2, attr)

            if isinstance(val1, float):
                alpha = random.uniform(-0.5, 1.5)
                new1 = max(0.0, (1 - alpha) * val1 + alpha * val2)
                new2 = max(0.0, alpha * val1 + (1 - alpha) * val2)
                setattr(rocket1, attr, new1)
                setattr(rocket2, attr, new2)
            elif isinstance(val1, int):
                setattr(rocket1, attr, val2)
                setattr(rocket2, attr, val1)
            elif isinstance(val1, str):
                setattr(rocket1, attr, val2)
                setattr(rocket2, attr, val1)

        for rocket, individual in ((rocket1, ind1), (rocket2, ind2)):
            params = self._repair_params(rocket.to_dict())
            validated = self.constraint_handler.validate_design(params)
            updated = Rocket.from_dict({**params, "is_valid": validated})
            individual[0] = updated

        del ind1.fitness.values
        del ind2.fitness.values
        return ind1, ind2

    def _mutate_rocket(
        self,
        individual: creator.Individual,
        indpb: float,
    ) -> Tuple[creator.Individual]:
        rocket = _get_rocket(individual)
        mutated_params = rocket.to_dict()

        mutation_scales = {
            "body_length": 0.03,
            "body_diameter": 0.003,
            "nose_cone_length": 0.02,
            "fin_root_chord": 0.008,
            "fin_tip_chord": 0.008,
            "fin_sweep": 0.004,
            "fin_thickness": 0.0005,
            "fin_height": 0.006,
            "fin_position": 0.08,
            "launch_lug_position": 0.08,
            "ballast_mass": 0.008,
            "parachute_diameter": 0.05,
        }


        for attr in DESIGN_FIELDS:
            if attr in self.constraint_handler.fixed_constraints:
                continue
            if random.random() >= indpb:
                continue

            if isinstance(mutated_params[attr], float):
                std_dev = mutation_scales.get(attr, 0.001)
                mutated_params[attr] = max(0.0, mutated_params[attr] + random.gauss(0, std_dev))
            elif isinstance(mutated_params[attr], int) and attr == "fin_count":
                mutated_params[attr] += random.choice([-1, 1])
                mutated_params[attr] = max(3, min(mutated_params[attr], 4))
            elif isinstance(mutated_params[attr], str) and attr == "nose_cone_shape":
                choices = [s for s in ["CONICAL", "OGIVE", "PARABOLIC"] if s != mutated_params[attr]]
                if choices:
                    mutated_params[attr] = random.choice(choices)

        final_params = self._repair_params(mutated_params)
        validated = self.constraint_handler.validate_design(final_params)
        individual[0] = Rocket.from_dict({**final_params, "is_valid": validated})
        del individual.fitness.values
        return (individual,)

    def run_optimization(self) -> Rocket:
        logger.info("Starting rocket design optimization...")

        with self.backend:
            self.population = self.toolbox.population(n=self.population_size)

            fitnesses = list(map(self.toolbox.evaluate, self.population))
            for idx, (ind, fit) in enumerate(zip(self.population, fitnesses)):
                ind.fitness.values = fit
                self._log_rocket_to_csv(0, idx, _get_rocket(ind), fit[0])

            self.hof.update(self.population)
            self.best_fitness = self.hof[0].fitness.values[0]

            for gen in range(1, self.num_generations + 1):
                logger.info(f"--- Generation {gen} ---")
                offspring = self.toolbox.select(self.population, len(self.population) - ELITISM_COUNT)
                offspring = list(map(self.toolbox.clone, offspring))

                for child1, child2 in zip(offspring[::2], offspring[1::2]):
                    if random.random() < CROSSOVER_RATE:
                        self.toolbox.mate_rocket(child1, child2)

                for mutant in offspring:
                    if random.random() < MUTATION_RATE:
                        self.toolbox.mutate_rocket(mutant)

                invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
                fitnesses = map(self.toolbox.evaluate, invalid_ind)
                for idx, (ind, fit) in enumerate(zip(invalid_ind, fitnesses)):
                    ind.fitness.values = fit
                    self._log_rocket_to_csv(gen, idx, _get_rocket(ind), fit[0])

                elite = tools.selBest(self.population, ELITISM_COUNT)
                self.population[:] = elite + offspring
                self.hof.update(self.population)

                best_rocket = _get_rocket(tools.selBest(self.population, 1)[0])
                logger.info(
                    f"Generation {gen}: Best Altitude: {best_rocket.max_altitude:.2f}m, "
                    f"Stability: {best_rocket.stability:.2f}cal"
                )

            best_overall_rocket = _get_rocket(self.hof[0])
            self.best_fitness = self.hof[0].fitness.values[0]
            logger.info(
                f"Best overall rocket found: Altitude = {best_overall_rocket.max_altitude:.2f}m, "
                f"Stability = {best_overall_rocket.stability:.2f}cal"
            )

            self.generator.save_rocket(best_overall_rocket.to_dict(), self.best_rocket_file)
            logger.info(f"Best rocket saved to {self.best_rocket_file}")

            self._write_run_summary(best_overall_rocket)

        return best_overall_rocket

    def _write_run_summary(self, rocket: Rocket) -> None:
        try:
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            preset_desc = self.preset_name or "Custom / Max Altitude"
            target_str = f"{self.target_altitude:.1f} m" if self.target_altitude is not None else "None (Max Altitude)"
            alt_diff_str = (
                f"{abs(rocket.max_altitude - self.target_altitude):.2f} m"
                if self.target_altitude is not None
                else "N/A"
            )

            summary_content = f"""================================================================================
                    🚀 ROCKET OPTIMIZATION RUN SUMMARY 🚀
================================================================================
Date/Time:           {timestamp_str}
Preset / Tag:        {preset_desc}
Optimization Mode:   Target Altitude Matching ({target_str})

--- CONSTRAINTS ENFORCED ---
Minimum Total Length: {MIN_ROCKET_LENGTH * 1000:.1f} mm ({MIN_ROCKET_LENGTH:.3f} m)
Maximum Total Mass:   {MAX_ROCKET_MASS * 1000:.1f} g ({MAX_ROCKET_MASS:.3f} kg)
Target Stability:     {TARGET_STABILITY_MARGIN_CALIBERS[0]:.2f} - {TARGET_STABILITY_MARGIN_CALIBERS[1]:.2f} calibers

--- BEST ROCKET DESIGN FOUND ---
Body Length:          {rocket.body_length * 1000:.1f} mm
Body Diameter:        {rocket.body_diameter * 1000:.1f} mm
Nose Cone Length:     {rocket.nose_cone_length * 1000:.1f} mm
Nose Cone Shape:      {rocket.nose_cone_shape}
Fin Count:            {rocket.fin_count}
Fin Root Chord:       {rocket.fin_root_chord * 1000:.1f} mm
Fin Tip Chord:        {rocket.fin_tip_chord * 1000:.1f} mm
Fin Sweep:            {rocket.fin_sweep * 1000:.1f} mm
Fin Thickness:        {rocket.fin_thickness * 1000:.2f} mm
Fin Height:           {rocket.fin_height * 1000:.1f} mm
Fin Axial Position:   {rocket.fin_position * 100:.1f}%
Launch Lug Position:  {rocket.launch_lug_position * 100:.1f}%
Ballast Mass:         {rocket.ballast_mass * 1000:.1f} g
Parachute Diameter:   {rocket.parachute_diameter * 1000:.0f} mm
Motor:                {self.motor_designation} ({self.motor_manufacturer})

--- SIMULATION PERFORMANCE METRICS ---
Simulated Altitude:   {rocket.max_altitude:.2f} m
Target Altitude:      {target_str} (Error: {alt_diff_str})
Flight Duration:      {rocket.flight_time:.2f} s
Total Launch Mass:    {rocket.total_mass * 1000:.1f} g
Stability Margin:     {rocket.stability:.2f} calibers
Average Drag Force:   {rocket.drag:.3f} N
Fitness Score:        {self.best_fitness:.2f}

--- GENERATED OUTPUT FILES ---
Output Folder:        {self.results_dir}
OpenRocket Model:     best_rocket.ork
Optimization CSV:     optimization_results.csv
Run Summary:          run_summary.txt
Evolution Plots:      fitness_evolution.png, altitude_distribution.png, etc.
================================================================================
"""
            with open(self.summary_file, "w", encoding="utf-8") as f:
                f.write(summary_content)
            logger.info(f"Run summary written to {self.summary_file}")
        except Exception as e:
            logger.error(f"Error writing run summary: {e}")
