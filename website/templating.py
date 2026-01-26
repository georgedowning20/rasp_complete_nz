"""Template rendering helpers for the static site generator."""

import json
from pathlib import Path


def generate_html(domain_bounds, manifest, help_text, mapbox_token, param_info, sounding_sites):
    """Render index.html from the on-disk template."""
    template_path = Path(__file__).parent / "templates" / "index_template.html"
    template = template_path.read_text()
    replacements = {
        "__MAPBOX_TOKEN__": mapbox_token,
        "__PARAM_INFO__": json.dumps(param_info),
        "__DOMAIN_DATA__": json.dumps(domain_bounds),
        "__SOUNDING_SITES__": json.dumps(sounding_sites),
        "__MANIFEST__": json.dumps(manifest),
        "__HELP_TEXT__": json.dumps(help_text),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template
