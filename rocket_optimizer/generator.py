import os
from typing import Any, Dict, Optional

from .openrocket_backend import OpenRocketBackend
from .utils import logger
from .config import TEMPLATES_DIR


class RocketGenerator:
    """Creates and saves OpenRocket designs from optimizer parameters."""

    def __init__(
        self,
        template_path: str = os.path.join(TEMPLATES_DIR, "base.ork"),
        backend: Optional[OpenRocketBackend] = None,
    ):
        self.template_path = template_path
        self.backend = backend

    def modify_rocket(self, design_parameters: Dict[str, Any], doc=None):
        """Apply design parameters to a document (loads template if doc is None)."""
        logger.info("Applying design modifications...")
        if self.backend is None:
            raise RuntimeError("RocketGenerator requires an OpenRocketBackend instance")
        if doc is None:
            doc = self.backend.load_template()
        self.backend.apply_design_params(doc, design_parameters)
        return doc

    def save_rocket(
        self,
        design_parameters: Optional[Dict[str, Any]],
        output_path: str,
    ) -> None:
        """Save a template, optionally applying design parameters first."""
        if self.backend is None:
            raise RuntimeError("RocketGenerator requires an OpenRocketBackend instance")
        if design_parameters is None:
            doc = self.backend.load_template()
            self.backend.helper.save_doc(output_path, doc)
        else:
            self.backend.save_design(design_parameters, output_path)
        logger.info(f"Saved modified rocket to {output_path}")
