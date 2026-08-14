# Rocket Optimizer

This project aims to automatically optimize model rocket designs using OpenRocket simulations and a Genetic Algorithm.

## Project Goal
The program allows users to specify fixed constraints for a rocket design and then optimizes the remaining design variables to maximize performance, primarily altitude, while maintaining safe stability.

## Structure
```
rocket_optimizer/
│├── main.py
├── optimizer.py
├── generator.py
├── simulation.py
├── parser.py
├── constraints.py
├── scoring.py
├── visualization.py
├── config.py
├── utils.py
│├── templates/
│     base.ork
│├── results/
│└── README.md
```

## Installation

1.  **OpenRocket:** Download and install OpenRocket (ensure it's executable via command line).
2.  **Python:** Ensure you have Python 3.12+ installed.
3.  **Dependencies:** Install Python dependencies:
    ```bash
    pip install matplotlib lxml deap
    ```
4.  **Clone Repository:**
    ```bash
    git clone https://github.com/your-repo/rocket_optimizer.git
    cd rocket_optimizer
    ```
5.  **Configuration:**
    *   Edit `rocket_optimizer/config.py` to specify the path to your OpenRocket executable.
    *   Place your base OpenRocket `.ork` template file in `rocket_optimizer/templates/base.ork`. This template will be used as the starting point for design modifications.

## Usage

To run the optimization:

```bash
python main.py
```

The program will output results and visualizations to the `rocket_optimizer/results` directory.
