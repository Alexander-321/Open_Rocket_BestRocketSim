import csv
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from rocket_optimizer.constraints import ConstraintHandler
from rocket_optimizer.optimizer import Rocket, RocketOptimizer, _get_rocket
from rocket_optimizer.parser import OpenRocketParser
from rocket_optimizer.scoring import FitnessCalculator


class TestConstraintHandler(unittest.TestCase):
    def test_valid_design(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "nose_cone_length": 0.1,
            "nose_cone_shape": "OGIVE",
            "fin_root_chord": 0.05,
            "fin_tip_chord": 0.02,
            "fin_sweep": 0.01,
            "fin_thickness": 0.003,
            "fin_count": 3,
            "fin_position": 0.5,
            "launch_lug_position": 0.3,
        }
        self.assertTrue(handler.validate_design(params))

    def test_rejects_tip_chord_larger_than_root(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "nose_cone_length": 0.1,
            "nose_cone_shape": "OGIVE",
            "fin_root_chord": 0.03,
            "fin_tip_chord": 0.05,
            "fin_sweep": 0.01,
            "fin_thickness": 0.003,
            "fin_count": 3,
            "fin_position": 0.5,
            "launch_lug_position": 0.3,
        }
        self.assertFalse(handler.validate_design(params))

    def test_applies_fixed_constraints(self):
        handler = ConstraintHandler(fixed_constraints={"fin_count": 4})
        params = {"fin_count": 3, "fin_root_chord": 0.05}
        updated = handler.apply_fixed_constraints(params)
        self.assertEqual(updated["fin_count"], 4)

    def test_rejects_sweep_exceeding_root_chord(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "nose_cone_length": 0.1,
            "nose_cone_shape": "OGIVE",
            "fin_root_chord": 0.03,
            "fin_tip_chord": 0.02,
            "fin_sweep": 0.05,  # sweep > root chord
            "fin_thickness": 0.003,
            "fin_count": 3,
            "fin_position": 0.5,
            "launch_lug_position": 0.3,
        }
        self.assertFalse(handler.validate_design(params))

    def test_rejects_root_chord_exceeding_body_length(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "nose_cone_length": 0.1,
            "nose_cone_shape": "OGIVE",
            "fin_root_chord": 0.35,  # >= default body length 0.3
            "fin_tip_chord": 0.02,
            "fin_sweep": 0.01,
            "fin_thickness": 0.003,
            "fin_count": 3,
            "fin_position": 0.5,
            "launch_lug_position": 0.3,
        }
        self.assertFalse(handler.validate_design(params))

    def test_accepts_zero_sweep(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "nose_cone_length": 0.1,
            "nose_cone_shape": "OGIVE",
            "fin_root_chord": 0.05,
            "fin_tip_chord": 0.02,
            "fin_sweep": 0.0,
            "fin_thickness": 0.003,
            "fin_count": 3,
            "fin_position": 0.5,
            "launch_lug_position": 0.3,
        }
        self.assertTrue(handler.validate_design(params))


    def test_rocket_under_300mm_fails(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "body_length": 0.15,
            "nose_cone_length": 0.10,  # Total = 0.25m < 0.3m
            "fin_root_chord": 0.05,
            "fin_tip_chord": 0.02,
            "fin_sweep": 0.01,
            "fin_thickness": 0.003,
            "fin_count": 3,
            "fin_position": 0.5,
            "launch_lug_position": 0.3,
        }
        self.assertFalse(handler.validate_design(params))

    def test_non_parachute_recovery_fails(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "body_length": 0.3,
            "nose_cone_length": 0.1,
            "recovery_type": "Streamer",
        }
        self.assertFalse(handler.validate_design(params))

    def test_single_recovery_system_fails(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "body_length": 0.3,
            "nose_cone_length": 0.1,
            "recovery_systems_count": 1,
        }
        self.assertFalse(handler.validate_design(params))

    def test_inseparable_sections_fail(self):
        handler = ConstraintHandler(fixed_constraints={})
        params = {
            "body_length": 0.3,
            "nose_cone_length": 0.1,
            "separable_sections": False,
        }
        self.assertFalse(handler.validate_design(params))

    def test_mass_over_150g_fails_sim_validation(self):
        handler = ConstraintHandler(fixed_constraints={})
        sim_results = {"simulation_successful": True, "total_mass": 0.160, "total_impulse": 8.0}
        self.assertFalse(handler.validate_simulation_constraints(sim_results))

    def test_impulse_over_10Ns_fails_sim_validation(self):
        handler = ConstraintHandler(fixed_constraints={})
        sim_results = {"simulation_successful": True, "total_mass": 0.120, "total_impulse": 12.0}
        self.assertFalse(handler.validate_simulation_constraints(sim_results))


class TestFitnessCalculator(unittest.TestCase):
    def test_good_design_scores_high(self):
        calc = FitnessCalculator()
        score = calc.calculate_fitness(
            altitude=140.0,
            stability=1.5,
            drag=0.5,
            simulation_successful=True,
            flight_time=26.0,
            landing_distance=4.0,
        )
        self.assertGreater(score, 900.0)

    def test_failed_simulation_penalized(self):
        calc = FitnessCalculator()
        score = calc.calculate_fitness(
            altitude=100.0,
            stability=1.5,
            drag=0.5,
            simulation_successful=False,
        )
        self.assertEqual(score, -10000.0)

    def test_target_altitude_scoring(self):
        calc_exact = FitnessCalculator(target_altitude=140.0)
        score_exact = calc_exact.calculate_fitness(altitude=140.0, stability=1.5, drag=0.5, simulation_successful=True, flight_time=26.0)

        calc_far = FitnessCalculator(target_altitude=140.0)
        score_far = calc_far.calculate_fitness(altitude=180.0, stability=1.5, drag=0.5, simulation_successful=True, flight_time=26.0)

        self.assertGreater(score_exact, score_far)

    def test_landing_bonus_applied(self):
        calc = FitnessCalculator(target_altitude=140.0)
        score_close = calc.calculate_fitness(altitude=140.0, stability=1.5, drag=0.5, simulation_successful=True, flight_time=26.0, landing_distance=3.0)
        score_far = calc.calculate_fitness(altitude=140.0, stability=1.5, drag=0.5, simulation_successful=True, flight_time=26.0, landing_distance=10.0)

        self.assertEqual(score_close - score_far, 5.0)




class TestOpenRocketParser(unittest.TestCase):
    def test_parses_orlab_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["TYPE_TIME (s)", "TYPE_ALTITUDE (m)", "TYPE_STABILITY", "TYPE_DRAG_FORCE (N)"])
            writer.writerow(["0.0", "0.0", "1.2", "0.1"])
            writer.writerow(["1.0", "50.0", "1.8", "0.2"])
            writer.writerow(["2.0", "40.0", "1.0", "0.15"])
            path = f.name

        try:
            parser = OpenRocketParser()
            results = parser.parse_simulation_results(path)
            self.assertTrue(results["simulation_successful"])
            self.assertEqual(results["max_altitude"], 50.0)
            self.assertEqual(results["min_stability"], 1.0)
            self.assertEqual(results["max_stability"], 1.8)
        finally:
            os.remove(path)


class TestRocketOptimizer(unittest.TestCase):
    def test_attr_rocket_produces_valid_individual(self):
        optimizer = RocketOptimizer()
        rocket = optimizer._attr_rocket()
        self.assertTrue(rocket.is_valid)
        self.assertLessEqual(rocket.fin_tip_chord, rocket.fin_root_chord)

    def test_crossover_swaps_genes(self):
        optimizer = RocketOptimizer()
        r1 = optimizer._attr_rocket()
        r2 = optimizer._attr_rocket()
        from deap import creator

        ind1 = creator.Individual([r1])
        ind2 = creator.Individual([r2])
        ind1.fitness.values = (1.0,)
        ind2.fitness.values = (2.0,)

        original_shape = r1.nose_cone_shape
        other_shape = r2.nose_cone_shape
        with patch("random.random", return_value=0.0):
            optimizer._crossover_rocket(ind1, ind2, indpb=1.0)

        self.assertEqual(_get_rocket(ind1).nose_cone_shape, other_shape)
        self.assertEqual(_get_rocket(ind2).nose_cone_shape, original_shape)

    @patch("rocket_optimizer.optimizer.OpenRocketBackend")
    def test_evaluate_rocket_uses_simulator(self, mock_backend_cls):
        mock_backend = MagicMock()
        mock_backend_cls.return_value = mock_backend

        optimizer = RocketOptimizer(target_altitude=None)
        optimizer.simulator.run_simulation = MagicMock(
            return_value={
                "max_altitude": 75.0,
                "min_stability": 1.1,
                "max_stability": 1.9,
                "average_drag": 0.3,
                "total_mass": 0.10,
                "total_impulse": 5.0,
                "flight_time": 20.0,
                "landing_distance": 0.0,
                "simulation_successful": True,
            }
        )

        rocket = optimizer._attr_rocket()
        from deap import creator

        individual = creator.Individual([rocket])
        fitness = optimizer._evaluate_rocket(individual)

        self.assertGreater(fitness[0], 0)
        self.assertEqual(rocket.max_altitude, 75.0)
        self.assertTrue(rocket.simulation_successful)

    def test_log_rocket_to_csv_recreates_missing_results_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = os.path.join(temp_dir, "missing_results_dir")
            optimizer = RocketOptimizer(results_dir=results_dir)
            shutil.rmtree(results_dir)

            rocket = optimizer._attr_rocket()
            optimizer._log_rocket_to_csv(0, 0, rocket, 1.23)

            self.assertTrue(os.path.isdir(results_dir))
            self.assertTrue(os.path.exists(optimizer.results_csv))



if __name__ == "__main__":
    unittest.main()
