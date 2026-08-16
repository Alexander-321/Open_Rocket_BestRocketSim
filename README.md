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
    cd Open_Rocket_BestRocketSim
    ```
5.  **Configuration:**
    *   The OpenRocket jar is located automatically: `OPENROCKET_JAR_PATH` env var, then `DEFAULT_OPENROCKET_JAR_PATH` in `rocket_optimizer/config.py`, then any jar installed/cached for `orlab`.
    *   Place your base OpenRocket `.ork` template file in `rocket_optimizer/templates/base.ork`. This template will be used as the starting point for design modifications.

## Usage

To run the optimization:

```bash
python3 -m rocket_optimizer.main --preset space-koshien-2026-c
python3 -m rocket_optimizer.main --preset space-koshien-2026-b
python3 -m rocket_optimizer.main --target-altitude 120
```

The program will output results and visualizations to the `rocket_optimizer/results` directory.

## Target altitude matching

Each preset defines the motor that is actually flown (C6 for the C class, B6 for the B class),
the target altitude and the required flight-duration window; `--target-altitude` scores against
exactly the altitude you pass. Because the motor is fixed, the optimizer trims apogee mainly with
nose ballast (`ballast_mass`) and drag/geometry, and trims descent time with `parachute_diameter`.
The score is the competition score: 1 pt per foot of altitude error, plus penalties for flight time
outside the window, stability outside 1-2 cal, and launch mass above 150 g, minus the 5 pt landing
bonus.
