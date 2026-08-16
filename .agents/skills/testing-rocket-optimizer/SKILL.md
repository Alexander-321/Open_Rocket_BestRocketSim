---
name: testing-rocket-optimizer
description: How to run and verify the OpenRocket/DEAP rocket optimizer CLI end-to-end (presets, target altitude, saved .ork verification, artifacts).
---

# Testing the rocket optimizer CLI

## Running
- Always run from the repo root. The OpenRocket jar is resolved by
  `rocket_optimizer/config.py:resolve_openrocket_jar_path()`:
  `OPENROCKET_JAR_PATH` env var → `/Applications/OpenRocket.app/...` → the orlab jar cache
  (`~/.cache/orlab-jars/OpenRocket-*.jar`). On Linux boxes the cache path is what resolves, so
  the CLI works even with the env var unset — worth testing both ways.
- Typical runs are cheap: `--population 30 --generations 15` (~400 simulations) finishes in
  ~1.5 minutes on a single core; a `--population 4 --generations 2` smoke run takes ~7 s.
  `ROCKET_OPTIMIZER_QUICK=1` also forces pop 4 / gen 2.
- Useful invocations:
  - `python3 -m rocket_optimizer.main --preset space-koshien-2026-c|space-koshien-2026-b|max-altitude`
  - `python3 -m rocket_optimizer.main --target-altitude 120` (no preset → default C-class
    duration window 25–28 s, motor C6)
- Unit tests: `python3 -m unittest discover -s rocket_optimizer/tests` (~5 s, no JVM needed for most).

## Gotcha: run directories are keyed on whole seconds
`create_run_directory()` names folders `run_<YYYYmmdd_HHMMSS>_<tag>`. Two runs of the *same* preset
started in the same second share one directory and silently merge their CSVs / overwrite
`best_rocket.ork`. Never launch two identical-preset runs in parallel; stagger them or pass an
explicit `results_dir` when using `RocketOptimizer` directly.

## Verifying results (don't trust exit code 0)
Each run dir contains `run_summary.txt`, `optimization_results.csv` (23 columns incl. `Fin_Height`,
`Ballast_Mass`, `Parachute_Diameter`), 10 PNG plots and `best_rocket.ork`. Check against the
competition rules: mass ≤ 150 g, total length (body + nose) ≥ 300 mm, stability 1–2 cal,
duration window per preset (C: 25–28 s, B: 16–18 s), motor impulse ≤ 10 N·s.

To prove the saved model really is what was reported, reload and re-simulate it:

```python
from rocket_optimizer.openrocket_backend import OpenRocketBackend
b = OpenRocketBackend(motor_designation="C6")
with b:
    doc = b.helper.load_doc(f"{run_dir}/best_rocket.ork")
    print([b.helper.get_motor(doc.getSimulation(i)) for i in range(doc.getSimulationCount())])
    print([(str(m.getName()), float(m.getComponentMass())) for m in
           b.helper.get_components_of_type(doc.getRocket(), "MassComponent")])
    print([str(p.getName()) for p in b.helper.get_components_of_type(doc.getRocket(), "Parachute")])
    sim = doc.getSimulation(0); b.helper.run_simulation(sim); print(b.helper.get_summary(sim).apogee)
```
Re-simulated apogee should match the summary within a few tenths of a metre.

A strong contrast test for "is the configured motor actually flown": simulate the same design with
`OpenRocketBackend(motor_designation="A8")`. A C-class design that apogees at ~140 m on C6 apogees
at only ~12 m on A8, so a regression to the template's default motor is immediately visible.

## Java string gotcha
Component names come back as `java.lang.String`, which has no Python `.lower()`. Code doing
`component.getName().lower()` raises `AttributeError`; always use `str(c.getName()).lower()`.
Such failures are frequently swallowed by broad `except Exception: logger.debug(...)` blocks in
`openrocket_backend.py`, so silently missing components are a real failure mode — verify the saved
`.ork` component tree rather than trusting the logs.

## Devin Secrets Needed
None.
