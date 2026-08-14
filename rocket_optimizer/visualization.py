import matplotlib.pyplot as plt
import pandas as pd
import os
from typing import List, Tuple

from .utils import logger
from .config import RESULTS_CSV, RESULTS_DIR

class RocketVisualizer:
    """
    Generates plots and visualizations from the optimization results.
    """

    def __init__(self, results_csv_path: str = RESULTS_CSV, results_dir: str = RESULTS_DIR):
        self.results_csv_path = results_csv_path
        self.results_dir = results_dir
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

    def _load_results(self) -> pd.DataFrame:
        """
        Loads the optimization results from the CSV file into a pandas DataFrame.
        """
        if not os.path.exists(self.results_csv_path):
            logger.error(f"Results CSV file not found: {self.results_csv_path}")
            return pd.DataFrame()
        try:
            df = pd.read_csv(self.results_csv_path)
            logger.info("Results CSV loaded successfully.")
            return df
        except Exception as e:
            logger.error(f"Error loading results CSV from {self.results_csv_path}: {e}")
            return pd.DataFrame()

    def plot_fitness_over_generations(self, df: pd.DataFrame, file_name: str = "fitness_evolution.png"):
        """
        Plots the best and average fitness over generations.
        """
        if df.empty:
            logger.warning("DataFrame is empty, cannot plot fitness evolution.")
            return

        plt.figure(figsize=(12, 6))
        
        # Calculate best and average fitness per generation
        best_fitness_per_gen = df.groupby("Generation")["Fitness"].max()
        avg_fitness_per_gen = df.groupby("Generation")["Fitness"].mean()

        plt.plot(best_fitness_per_gen.index, best_fitness_per_gen.values, label="Best Fitness", marker='o')
        plt.plot(avg_fitness_per_gen.index, avg_fitness_per_gen.values, label="Average Fitness", marker='x')

        plt.title("Fitness Evolution Over Generations")
        plt.xlabel("Generation")
        plt.ylabel("Fitness")
        plt.grid(True)
        plt.legend()
        plot_path = os.path.join(self.results_dir, file_name)
        plt.savefig(plot_path)
        logger.info(f"Saved fitness evolution plot to {plot_path}")
        plt.close()

    def plot_altitude_distribution(self, df: pd.DataFrame, file_name: str = "altitude_distribution.png"):
        """
        Plots the distribution of maximum altitudes.
        """
        if df.empty or "Max_Altitude" not in df.columns:
            logger.warning("DataFrame is empty or missing 'Max_Altitude' column, cannot plot altitude distribution.")
            return

        plt.figure(figsize=(10, 6))
        plt.hist(df["Max_Altitude"], bins=30, edgecolor='black')
        plt.title("Distribution of Maximum Altitudes")
        plt.xlabel("Altitude (m)")
        plt.ylabel("Number of Rockets")
        plt.grid(True)
        plot_path = os.path.join(self.results_dir, file_name)
        plt.savefig(plot_path)
        logger.info(f"Saved altitude distribution plot to {plot_path}")
        plt.close()

    def plot_stability_distribution(self, df: pd.DataFrame, file_name: str = "stability_distribution.png"):
        """
        Plots the distribution of stability margins.
        """
        if df.empty or "Stability" not in df.columns:
            logger.warning("DataFrame is empty or missing 'Stability' column, cannot plot stability distribution.")
            return

        plt.figure(figsize=(10, 6))
        plt.hist(df["Stability"], bins=30, edgecolor='black')
        plt.title("Distribution of Stability Margins")
        plt.xlabel("Stability (cal)")
        plt.ylabel("Number of Rockets")
        plt.grid(True)
        plot_path = os.path.join(self.results_dir, file_name)
        plt.savefig(plot_path)
        logger.info(f"Saved stability distribution plot to {plot_path}")
        plt.close()

    def plot_parameter_evolution(self, df: pd.DataFrame, parameter_name: str, file_name: str):
        """
        Plots the evolution of a specific design parameter over generations.
        """
        if df.empty or parameter_name not in df.columns:
            logger.warning(f"DataFrame is empty or missing '{parameter_name}' column, cannot plot parameter evolution.")
            return

        plt.figure(figsize=(12, 6))
        # For numerical parameters, show average and std dev per generation
        if df[parameter_name].dtype in ['float64', 'int64']:
            avg_param_per_gen = df.groupby("Generation")[parameter_name].mean()
            std_param_per_gen = df.groupby("Generation")[parameter_name].std().fillna(0)
            
            plt.plot(avg_param_per_gen.index, avg_param_per_gen.values, label=f"Average {parameter_name}", marker='o')
            plt.fill_between(avg_param_per_gen.index, 
                             avg_param_per_gen - std_param_per_gen, 
                             avg_param_per_gen + std_param_per_gen, 
                             color='blue', alpha=0.2, label='Std Dev')
        else:
            # For categorical parameters, show counts or most common value
            # This is more complex to visualize on a line plot, might need a different plot type.
            logger.warning(f"Categorical parameter '{parameter_name}' not easily visualized with line plot. Skipping.")
            return

        plt.title(f"Evolution of {parameter_name} Over Generations")
        plt.xlabel("Generation")
        plt.ylabel(parameter_name)
        plt.grid(True)
        plt.legend()
        plot_path = os.path.join(self.results_dir, file_name)
        plt.savefig(plot_path)
        logger.info(f"Saved {parameter_name} evolution plot to {plot_path}")
        plt.close()

    def generate_all_plots(self):
        """
        Generates all standard plots from the optimization results.
        """
        df = self._load_results()
        if df.empty:
            return

        self.plot_fitness_over_generations(df)
        self.plot_altitude_distribution(df)
        self.plot_stability_distribution(df)

        # Example parameter evolutions - extend as needed
        self.plot_parameter_evolution(df, "Nose_Cone_Length", "nose_cone_length_evolution.png")
        self.plot_parameter_evolution(df, "Fin_Root_Chord", "fin_root_chord_evolution.png")
        self.plot_parameter_evolution(df, "Fin_Tip_Chord", "fin_tip_chord_evolution.png")
        self.plot_parameter_evolution(df, "Fin_Sweep", "fin_sweep_evolution.png")
        self.plot_parameter_evolution(df, "Fin_Thickness", "fin_thickness_evolution.png")
        self.plot_parameter_evolution(df, "Fin_Position", "fin_position_evolution.png")
        self.plot_parameter_evolution(df, "Launch_Lug_Position", "launch_lug_position_evolution.png")

        logger.info("All plots generated successfully.")

