"""Separa los grupos originales de la hoja para evitar solapamiento de sus vistas."""
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / "assets" / "visual"
source = ET.parse(root / "inspeccion_cuatro_vistas.svg").getroot()
ns = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")
groups = source.findall(ns + "g")
views = {"side": (0, "30 35 720 360"), "top": (1, "800 60 240 670"),
         "rear": (2, "120 520 470 280"), "front": (3, "885 520 470 280")}
for name, (index, box) in views.items():
    svg = ET.Element(ns + "svg", {"viewBox": box})
    svg.append(deepcopy(source.find(ns + "defs")))
    svg.append(deepcopy(groups[index]))
    ET.ElementTree(svg).write(root / f"inspection_{name}.svg", encoding="utf-8", xml_declaration=True)
