"""Shared OpenRocket integration via orlab (JPype)."""

from __future__ import annotations

import os
from typing import Any, Optional

import orlab

from .config import OPENROCKET_JAR_PATH, TEMPLATES_DIR
from .utils import logger

NOSE_SHAPE_MAP = {
    "CONICAL": "CONICAL",
    "OGIVE": "OGIVE",
    "PARABOLIC": "PARABOLIC",
}


class OpenRocketBackend:
    """Manages a single JVM/OpenRocket instance for the optimization run."""

    def __init__(
        self,
        template_path: Optional[str] = None,
        jar_path: str = OPENROCKET_JAR_PATH,
    ):
        self.template_path = template_path or os.path.join(TEMPLATES_DIR, "base.ork")
        self.jar_path = jar_path
        self._instance: Optional[orlab.OpenRocketInstance] = None
        self._helper: Optional[orlab.Helper] = None
        self._shape_enum = None

    def start(self) -> None:
        if self._instance is not None:
            return
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Template not found: {self.template_path}")
        if not os.path.exists(self.jar_path):
            raise FileNotFoundError(f"OpenRocket JAR not found: {self.jar_path}")

        self._instance = orlab.OpenRocketInstance(jar_path=self.jar_path)
        self._instance.__enter__()
        self._helper = orlab.Helper(self._instance)
        self._shape_enum = self._instance.openrocket.rocketcomponent.NoseCone.Shape
        logger.info("OpenRocket backend started")

    def stop(self) -> None:
        if self._instance is not None:
            self._instance.__exit__(None, None, None)
            self._instance = None
            self._helper = None
            self._shape_enum = None
            logger.info("OpenRocket backend stopped")

    def __enter__(self) -> OpenRocketBackend:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    @property
    def helper(self) -> orlab.Helper:
        if self._helper is None:
            raise RuntimeError("OpenRocket backend not started")
        return self._helper

    def load_template(self):
        return self.helper.load_doc(self.template_path)

    def apply_design_params(self, doc, design_parameters: dict[str, Any]) -> None:
        """Apply optimizer parameters to an OpenRocket document."""
        rocket = doc.getRocket()
        nose_cones = self.helper.get_components_of_type(rocket, "NoseCone")
        fin_sets = self.helper.get_components_of_type(rocket, "TrapezoidFinSet")
        launch_lugs = self.helper.get_components_of_type(rocket, "LaunchLug")
        body_tubes = self.helper.get_components_of_type(rocket, "BodyTube")
        parachutes = self.helper.get_components_of_type(rocket, "Parachute")

        if not nose_cones or not fin_sets:
            raise ValueError("Template is missing required nose cone or fin set components")

        nose = nose_cones[0]
        fins = fin_sets[0]

        # Ensure designer metadata includes competition JAR license requirement
        rocket.setDesigner("JAR License: JAR-2026-SK-0123")
        rocket.setComment(
            "Space Koshien 2026 Dual Section & Recovery System. "
            "Engine Section & Payload Section separate. Parachutes only. Mechanical Engine Retention."
        )

        total_body_length = float(design_parameters.get("body_length", 0.3))
        body_diameter = float(design_parameters.get("body_diameter", 0.03))
        radius = body_diameter / 2.0

        # Adjust nose cone dimensions
        if "nose_cone_length" in design_parameters:
            nose.setLength(float(design_parameters["nose_cone_length"]))
        nose.setAftRadius(radius)

        if "nose_cone_shape" in design_parameters:
            shape_name = NOSE_SHAPE_MAP.get(
                str(design_parameters["nose_cone_shape"]).upper(),
                str(design_parameters["nose_cone_shape"]).upper(),
            )
            nose.setShapeType(getattr(self._shape_enum, shape_name))

        # Adjust body tubes (Payload Section + Engine Section)
        if body_tubes:
            # Sizing body tubes
            if len(body_tubes) >= 2:
                payload_bt = body_tubes[0]
                engine_bt = body_tubes[1]
                payload_bt.setLength(total_body_length * 0.4)
                engine_bt.setLength(total_body_length * 0.6)
                payload_bt.setOuterRadius(radius)
                engine_bt.setOuterRadius(radius)
            else:
                main_bt = body_tubes[0]
                main_bt.setLength(total_body_length)
                main_bt.setOuterRadius(radius)

        # Adjust fin set dimensions
        if "fin_root_chord" in design_parameters:
            fins.setRootChord(float(design_parameters["fin_root_chord"]))

        if "fin_tip_chord" in design_parameters:
            fins.setTipChord(float(design_parameters["fin_tip_chord"]))

        if "fin_sweep" in design_parameters:
            fins.setSweep(float(design_parameters["fin_sweep"]))

        if "fin_thickness" in design_parameters:
            fins.setThickness(float(design_parameters["fin_thickness"]))

        if "fin_count" in design_parameters:
            fins.setFinCount(int(design_parameters["fin_count"]))

        if "fin_position" in design_parameters:
            root_chord = float(design_parameters.get("fin_root_chord", fins.getRootChord()))
            engine_bt_length = body_tubes[-1].getLength() if body_tubes else total_body_length
            available_length = max(0.0, engine_bt_length - root_chord)
            offset = float(design_parameters["fin_position"]) * available_length
            fins.setAxialOffset(offset)

        if launch_lugs and "launch_lug_position" in design_parameters:
            lug_length = launch_lugs[0].getLength()
            engine_bt_length = body_tubes[-1].getLength() if body_tubes else total_body_length
            available_length = max(0.0, engine_bt_length - lug_length)
            offset = float(design_parameters["launch_lug_position"]) * available_length
            launch_lugs[0].setAxialOffset(offset)

        # Ensure Dual Recovery Systems (Parachute 1 in Payload Section, Parachute 2 in Engine Section)
        if self._instance is not None:
            self._ensure_dual_recovery_systems(rocket, body_tubes, parachutes, design_parameters)

    def _ensure_dual_recovery_systems(self, rocket, body_tubes, parachutes, design_parameters: dict[str, Any]) -> None:
        """Ensures both Payload Section and Engine Section have independent parachutes."""
        p_diam = float(design_parameters.get("parachute_diameter", 0.30))
        if parachutes:
            for p in parachutes:
                p.setDiameter(p_diam)

        # If only 1 parachute exists, add a 2nd parachute to ensure separate recovery
        if len(parachutes) == 1 and body_tubes:
            try:
                parachute_cls = self._instance.openrocket.rocketcomponent.Parachute
                p2 = parachute_cls()
                p2.setName("Engine Section Parachute")
                p2.setDiameter(p_diam)
                body_tubes[-1].addChild(p2)
            except Exception as e:
                logger.debug(f"Note on secondary parachute addition: {e}")

        # Ensure Payload Mass Components (Quail Egg 10g + Altimeter 8g) exist in upper section
        try:
            mass_comps = self.helper.get_components_of_type(rocket, "MassComponent")
            egg_exists = any("egg" in m.getName().lower() for m in mass_comps)
            alt_exists = any("altimeter" in m.getName().lower() for m in mass_comps)
            
            if not egg_exists and body_tubes:
                mass_cls = self._instance.openrocket.rocketcomponent.MassComponent
                egg = mass_cls()
                egg.setName("Raw Quail Egg (10g)")
                egg.setComponentMass(0.010)
                body_tubes[0].addChild(egg)

            if not alt_exists and body_tubes:
                mass_cls = self._instance.openrocket.rocketcomponent.MassComponent
                alt = mass_cls()
                alt.setName("Altimeter (8g)")
                alt.setComponentMass(0.008)
                body_tubes[0].addChild(alt)
        except Exception as e:
            logger.debug(f"Note on payload mass component addition: {e}")

    def simulate_design(self, design_parameters: dict[str, Any], simulation_index: int = 0) -> dict[str, Any]:
        """Load template, apply parameters, run simulation, return comprehensive metrics."""
        doc = self.load_template()
        self.apply_design_params(doc, design_parameters)

        if doc.getSimulationCount() <= simulation_index:
            raise ValueError(f"Template has no simulation at index {simulation_index}")

        sim = doc.getSimulation(simulation_index)
        self.helper.run_simulation(sim)
        summary = self.helper.get_summary(sim)

        avg_drag = self._average_drag(sim)
        landing_dist = self._extract_landing_distance(sim)
        total_mass = doc.getRocket().getMass()

        # Motor total impulse
        total_impulse = 5.0 # Default fallback B/C motor impulse
        try:
            motor_conf = sim.getOptions().getMotorConfiguration()
            if motor_conf is not None:
                total_impulse = float(motor_conf.getTotalImpulse())
        except Exception:
            pass

        return {
            "max_altitude": summary.apogee,
            "flight_time": getattr(summary, "flight_time", 20.0),
            "min_stability": summary.min_stability_cal,
            "max_stability": summary.max_stability_cal,
            "average_drag": avg_drag,
            "total_mass": total_mass,
            "total_impulse": total_impulse,
            "landing_distance": landing_dist,
            "simulation_successful": True,
        }

    def save_design(self, design_parameters: dict[str, Any], output_path: str) -> None:
        doc = self.load_template()
        self.apply_design_params(doc, design_parameters)
        self.helper.save_doc(output_path, doc)

    def _average_drag(self, sim) -> float:
        sim_data = sim.getSimulatedData()
        if sim_data is None or sim_data.getBranchCount() == 0:
            return 0.0
        branch = sim_data.getBranch(0)
        drag_type = self.helper.translate_flight_data_type("TYPE_DRAG_FORCE")
        drag_values = branch.get(drag_type)
        if drag_values is None or len(drag_values) == 0:
            return 0.0
        total = sum(float(v) for v in drag_values)
        return total / len(drag_values)

    def _extract_landing_distance(self, sim) -> float:
        """Extract final landing distance (displacement from launch pad in meters)."""
        try:
            sim_data = sim.getSimulatedData()
            if sim_data is None or sim_data.getBranchCount() == 0:
                return 0.0
            branch = sim_data.getBranch(0)
            x_type = self.helper.translate_flight_data_type("TYPE_POSITION_X")
            y_type = self.helper.translate_flight_data_type("TYPE_POSITION_Y")
            x_vals = branch.get(x_type)
            y_vals = branch.get(y_type)
            if x_vals and y_vals and len(x_vals) > 0 and len(y_vals) > 0:
                final_x = float(x_vals[-1])
                final_y = float(y_vals[-1])
                return (final_x**2 + final_y**2)**0.5
            return 0.0
        except Exception as e:
            logger.debug(f"Could not extract landing distance: {e}")
            return 0.0


