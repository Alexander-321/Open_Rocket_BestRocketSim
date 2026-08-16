"""Shared OpenRocket integration via orlab (JPype)."""

from __future__ import annotations

import os
from typing import Any, Optional

try:
    import orlab
except ModuleNotFoundError:  # pragma: no cover - only used in environments without OpenRocket bindings
    orlab = None

from .config import (
    MOTOR_DESIGNATION,
    MOTOR_EJECTION_DELAY,
    MOTOR_MANUFACTURER,
    OPENROCKET_JAR_PATH,
    TEMPLATES_DIR,
)
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
        motor_designation: str = MOTOR_DESIGNATION,
        motor_manufacturer: Optional[str] = MOTOR_MANUFACTURER,
        motor_delay: Optional[float] = MOTOR_EJECTION_DELAY,
    ):
        self.template_path = template_path or os.path.join(TEMPLATES_DIR, "base.ork")
        self.jar_path = jar_path
        self.motor_designation = motor_designation
        self.motor_manufacturer = motor_manufacturer
        self.motor_delay = motor_delay
        self._instance: Optional[orlab.OpenRocketInstance] = None
        self._helper: Optional[orlab.Helper] = None
        self._shape_enum = None
        self.last_geometry_report: Optional[dict[str, Any]] = None

    def start(self) -> None:
        if self._instance is not None:
            return
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Template not found: {self.template_path}")
        if not os.path.exists(self.jar_path):
            raise FileNotFoundError(f"OpenRocket JAR not found: {self.jar_path}")
        if orlab is None:
            raise ModuleNotFoundError("orlab is required to run OpenRocket integration")

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

        if "fin_height" in design_parameters:
            fins.setHeight(float(design_parameters["fin_height"]))

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
            self._apply_ballast(body_tubes, design_parameters)

    def _apply_ballast(self, body_tubes, design_parameters: dict[str, Any]) -> None:
        """Set the tunable nose-side ballast used to trim apogee to the target."""
        if not body_tubes:
            return
        ballast_mass = float(design_parameters.get("ballast_mass", 0.0))
        try:
            mass_comps = self.helper.get_components_of_type(body_tubes[0], "MassComponent")
            existing = next((m for m in mass_comps if "ballast" in str(m.getName()).lower()), None)
            if existing is None:
                mass_cls = self._instance.openrocket.rocketcomponent.MassComponent
                existing = mass_cls()
                existing.setName("Ballast")
                body_tubes[0].addChild(existing)
            existing.setComponentMass(ballast_mass)
        except Exception as e:
            logger.debug(f"Note on ballast application: {e}")

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

        if body_tubes:
            all_parachutes = self.helper.get_components_of_type(rocket, "Parachute")
            geometry = self._layout_and_validate_recovery_geometry(
                body_tubes=body_tubes,
                parachutes=all_parachutes,
                design_parameters=design_parameters,
            )
            self.last_geometry_report = geometry
            self._log_geometry_report(geometry)

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

    def _layout_and_validate_recovery_geometry(
        self,
        body_tubes,
        parachutes,
        design_parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Place parachutes from actual geometry and validate containment/overlap constraints."""
        if not body_tubes:
            raise ValueError("Cannot place recovery system without body tube")

        body_tube = body_tubes[0]
        body_length = self._safe_float(self._call_method(body_tube, "getLength"), float(design_parameters.get("body_length", 0.3)))
        body_outer_radius = self._body_outer_radius(body_tube, float(design_parameters.get("body_diameter", 0.03)) / 2.0)
        body_thickness = self._safe_float(self._call_method(body_tube, "getThickness"), 0.001)
        body_inner_radius = max(0.0, body_outer_radius - body_thickness)

        engine_mount = self._first_child_of_type(body_tube, "InnerTube")
        engine_front = None
        engine_rear = None
        if engine_mount is not None:
            engine_front, engine_rear = self._component_bounds_in_parent(engine_mount, body_length)
        else:
            engine_front = body_length
            engine_rear = body_length

        recovery_start = 0.0
        recovery_end = max(recovery_start, min(body_length, engine_front - 0.004))

        if recovery_end <= recovery_start:
            raise ValueError(
                "Invalid recovery compartment geometry: no axial room between nose-side start and engine mount."
            )

        parachute_items = list(parachutes or [])
        if len(parachute_items) < 2:
            raise ValueError("Dual recovery requirement violated: expected at least 2 parachutes.")

        default_packed_length = max(0.015, 0.14 * float(design_parameters.get("parachute_diameter", 0.30)))
        packed_radius_limit = max(0.0005, body_inner_radius - 0.0005)
        packed_radius_default = min(packed_radius_limit, max(0.003, 0.03 * float(design_parameters.get("parachute_diameter", 0.30))))

        placements: list[dict[str, Any]] = []
        cursor = recovery_start + 0.003
        for parachute in parachute_items:
            packed_length = self._safe_float(self._call_method(parachute, "getPackedLength"), default_packed_length)
            packed_length = max(0.008, packed_length)
            packed_radius = self._safe_float(self._call_method(parachute, "getPackedRadius"), packed_radius_default)
            packed_radius = min(packed_radius_limit, max(0.001, packed_radius))

            self._call_method(parachute, "setPackedLength", packed_length)
            self._call_method(parachute, "setPackedRadius", packed_radius)
            self._set_axial_method_top(parachute)
            self._call_method(parachute, "setAxialOffset", cursor)

            front = cursor
            rear = cursor + packed_length
            placements.append(
                {
                    "name": self._component_name(parachute),
                    "front": front,
                    "rear": rear,
                    "length": packed_length,
                    "packed_radius": packed_radius,
                    "diameter": self._safe_float(self._call_method(parachute, "getDiameter"), float(design_parameters.get("parachute_diameter", 0.30))),
                }
            )
            cursor = rear + 0.003

        for placement in placements:
            if placement["front"] < recovery_start or placement["rear"] > recovery_end:
                raise ValueError(
                    f"Parachute '{placement['name']}' outside recovery compartment: "
                    f"[{placement['front']:.4f}, {placement['rear']:.4f}] not inside "
                    f"[{recovery_start:.4f}, {recovery_end:.4f}]"
                )
            if placement["packed_radius"] > body_inner_radius:
                raise ValueError(
                    f"Parachute '{placement['name']}' packed radius {placement['packed_radius']:.4f} exceeds body inner radius {body_inner_radius:.4f}"
                )
            if placement["rear"] > engine_front and placement["front"] < engine_rear:
                raise ValueError(
                    f"Parachute '{placement['name']}' overlaps engine/motor region "
                    f"[{engine_front:.4f}, {engine_rear:.4f}]"
                )

        for i in range(len(placements)):
            for j in range(i + 1, len(placements)):
                a = placements[i]
                b = placements[j]
                if a["rear"] > b["front"] and b["rear"] > a["front"]:
                    raise ValueError(f"Parachute overlap detected between '{a['name']}' and '{b['name']}'")

        if cursor - 0.003 > recovery_end:
            raise ValueError(
                "Recovery system packing exceeds available compartment length: "
                f"required {(cursor - 0.003 - recovery_start):.4f} m, available {(recovery_end - recovery_start):.4f} m."
            )

        return {
            "coordinate_reference": "OpenRocket axial coordinate in parent BodyTube; x=0 at body tube front, +x toward tail",
            "body_tube": {
                "length": body_length,
                "outer_radius": body_outer_radius,
                "inner_radius": body_inner_radius,
                "inner_diameter": body_inner_radius * 2.0,
            },
            "recovery_compartment": {"start": recovery_start, "end": recovery_end},
            "engine_motor_bounds": {"front": engine_front, "rear": engine_rear},
            "parachutes": placements,
        }

    def _component_name(self, component) -> str:
        name = self._call_method(component, "getName")
        if name is not None:
            return str(name)
        return self._component_type(component)

    def _component_type(self, component) -> str:
        try:
            return str(component.getClass().getSimpleName())
        except Exception:
            return component.__class__.__name__

    def _first_child_of_type(self, parent, type_name: str):
        for child in self._iter_children(parent):
            if self._component_type(child).lower() == type_name.lower():
                return child
        return None

    def _iter_children(self, parent):
        children = self._call_method(parent, "getChildren")
        if children is None:
            return []
        try:
            return list(children)
        except Exception:
            return []

    def _component_bounds_in_parent(self, component, parent_length: float) -> tuple[float, float]:
        length = self._safe_float(self._call_method(component, "getLength"), 0.0)
        offset = self._safe_float(self._call_method(component, "getAxialOffset"), 0.0)
        method_name = str(self._call_method(component, "getAxialMethod") or "TOP").upper()

        if "BOTTOM" in method_name:
            rear = parent_length + offset
            front = rear - length
            return front, rear
        if "MIDDLE" in method_name:
            center = (parent_length / 2.0) + offset
            return center - (length / 2.0), center + (length / 2.0)
        front = offset
        return front, front + length

    def _body_outer_radius(self, body_tube, default_value: float) -> float:
        value = self._call_method(body_tube, "getOuterRadius")
        if value is None:
            value = self._call_method(body_tube, "getRadius")
        return self._safe_float(value, default_value)

    def _call_method(self, obj, method_name: str, *args):
        try:
            method = getattr(obj, method_name, None)
            if method is None:
                return None
            return method(*args)
        except Exception:
            return None

    def _set_axial_method_top(self, component) -> None:
        method_names = ["setAxialMethod", "setRelativePositionMethod"]
        enum_candidates = []
        if self._instance is not None:
            try:
                enum_candidates.append(self._instance.openrocket.rocketcomponent.position.AxialMethod.TOP)
            except Exception:
                pass
            try:
                enum_candidates.append(self._instance.openrocket.rocketcomponent.AxialMethod.TOP)
            except Exception:
                pass

        for method_name in method_names:
            setter = getattr(component, method_name, None)
            if setter is None:
                continue
            for enum_value in enum_candidates:
                try:
                    setter(enum_value)
                    return
                except Exception:
                    continue

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _log_geometry_report(self, geometry: dict[str, Any]) -> None:
        logger.info(
            "Geometry report | body_id=%.4f m | recovery=[%.4f, %.4f] m | engine=[%.4f, %.4f] m | parachutes=%s",
            geometry["body_tube"]["inner_diameter"],
            geometry["recovery_compartment"]["start"],
            geometry["recovery_compartment"]["end"],
            geometry["engine_motor_bounds"]["front"],
            geometry["engine_motor_bounds"]["rear"],
            [
                {
                    "name": p["name"],
                    "front": round(p["front"], 4),
                    "rear": round(p["rear"], 4),
                    "packed_radius": round(p["packed_radius"], 4),
                }
                for p in geometry["parachutes"]
            ],
        )

    def simulate_design(self, design_parameters: dict[str, Any], simulation_index: int = 0) -> dict[str, Any]:
        """Load template, apply parameters, run simulation, return comprehensive metrics."""
        doc = self.load_template()
        self.apply_design_params(doc, design_parameters)

        if doc.getSimulationCount() <= simulation_index:
            raise ValueError(f"Template has no simulation at index {simulation_index}")

        sim = doc.getSimulation(simulation_index)
        motor = self._apply_motor(sim)
        self.helper.run_simulation(sim)
        summary = self.helper.get_summary(sim)

        avg_drag = self._average_drag(sim)
        structure_mass = self._structure_mass(doc)
        motor_mass, total_impulse = self._motor_properties(motor)

        return {
            "max_altitude": summary.apogee,
            "flight_time": summary.flight_time,
            "min_stability": summary.min_stability_cal,
            "max_stability": summary.max_stability_cal,
            "stability_off_rod": summary.stability_off_rod_cal,
            "average_drag": avg_drag,
            "structure_mass": structure_mass,
            "total_mass": structure_mass + motor_mass,
            "total_impulse": total_impulse,
            "motor": self.motor_designation,
            "landing_distance": summary.landing_distance,
            "simulation_successful": True,
        }

    def _apply_motor(self, sim):
        """Fly the configured competition motor rather than whatever motor the
        template's first flight configuration happens to hold."""
        if not self.motor_designation:
            return None
        motor = self.helper.find_motor(self.motor_designation, manufacturer=self.motor_manufacturer)
        self.helper.set_motor(sim, motor, delay=self.motor_delay)
        return motor

    def _structure_mass(self, doc) -> float:
        """Dry (motorless) mass of the whole rocket in kg."""
        rocket = doc.getRocket()
        mass = self._safe_float(self._call_method(rocket, "getSectionMass"), 0.0)
        if mass > 0.0:
            return mass
        return self._safe_float(self._call_method(rocket, "getMass"), 0.0)

    def _motor_properties(self, motor) -> tuple[float, float]:
        """(launch mass kg, total impulse N*s) of the motor flown."""
        if motor is None:
            return 0.0, 0.0
        mass = self._safe_float(self._call_method(motor, "getLaunchMass"), 0.0)
        impulse = self._safe_float(self._call_method(motor, "getTotalImpulseEstimate"), 0.0)
        return mass, impulse

    def save_design(self, design_parameters: dict[str, Any], output_path: str) -> None:
        doc = self.load_template()
        self.apply_design_params(doc, design_parameters)
        for index in range(doc.getSimulationCount()):
            self._apply_motor(doc.getSimulation(index))
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


