#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def clean_label(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_") or "item"


def maybe_number(value: str) -> Any:
    text = str(value)
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer() and re.fullmatch(r"[-+]?\d+", text):
        return int(number)
    return number


def to_float_list(values: list[Any]) -> list[float]:
    return [float(value) for value in values]


def first(values: list[Any], default=None):
    return values[0] if values else default


def last_nonempty(values: list[Any], default=None):
    for value in reversed(values):
        if str(value) != "":
            return value
    return default


def rgb_to_hex(values: list[Any]) -> str | None:
    if len(values) < 3:
        return None
    ints = [max(0, min(255, round(float(channel) * 255))) for channel in values[:3]]
    return "#{:02X}{:02X}{:02X}".format(*ints)


def pyvista_camera_position(camera: dict[str, Any]) -> list[list[float]]:
    return [
        list(camera["position"]),
        list(camera["focal_point"]),
        list(camera["view_up"]),
    ]


def is_identity_transform(transform: dict[str, Any]) -> bool:
    position = transform.get("position") or [0.0, 0.0, 0.0]
    scale = transform.get("scale") or [1.0, 1.0, 1.0]
    orientation = transform.get("orientation") or [0.0, 0.0, 0.0]
    origin = transform.get("origin") or [0.0, 0.0, 0.0]
    matrix = transform.get("user_transform") or [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    identity_matrix = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    return (
        all(abs(float(value)) < 1e-12 for value in position)
        and all(abs(float(value) - 1.0) < 1e-12 for value in scale)
        and all(abs(float(value)) < 1e-12 for value in orientation)
        and all(abs(float(value)) < 1e-12 for value in origin)
        and all(abs(float(value) - identity_matrix[index]) < 1e-12 for index, value in enumerate(matrix))
    )


class ParaViewState:
    def __init__(self, path: Path):
        self.path = path
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()
        self.state = self.root.find(".//ServerManagerState")
        self.version = None if self.state is None else self.state.attrib.get("version")
        self.proxies = {
            proxy.attrib["id"]: proxy
            for proxy in self.root.findall(".//Proxy")
            if "id" in proxy.attrib
        }
        self.collections: dict[str, list[str]] = {}
        self.item_names: dict[str, list[dict[str, str | None]]] = {}
        self._load_proxy_collection_names()

    def _load_proxy_collection_names(self) -> None:
        for collection in self.root.findall(".//ProxyCollection"):
            collection_name = collection.attrib.get("name", "")
            for item in collection.findall("Item"):
                proxy_id = item.attrib.get("id")
                if not proxy_id:
                    continue
                self.collections.setdefault(collection_name, []).append(proxy_id)
                self.item_names.setdefault(proxy_id, []).append(
                    {
                        "collection": collection_name,
                        "name": item.attrib.get("name"),
                        "logname": item.attrib.get("logname"),
                    }
                )

    def proxy_name(self, proxy_id: str) -> str:
        preferred_collections = (
            "sources",
            "views",
            "representations",
            "lookup_tables",
            "scalar_bars",
            "layouts",
        )
        candidates = self.item_names.get(proxy_id, [])
        for collection_name in preferred_collections:
            for item in candidates:
                if item["collection"] == collection_name and item["name"]:
                    return str(item["name"])
        for item in candidates:
            if item["name"]:
                return str(item["name"])
        proxy = self.proxies.get(proxy_id)
        if proxy is not None:
            return f"{proxy.attrib.get('type', 'Proxy')}_{proxy_id}"
        return proxy_id

    def proxy_logname(self, proxy_id: str) -> str | None:
        for item in self.item_names.get(proxy_id, []):
            if item["logname"]:
                return str(item["logname"])
        return None

    def prop(self, proxy_id: str, name: str):
        proxy = self.proxies[proxy_id]
        for prop in proxy.findall("Property"):
            if prop.attrib.get("name") == name:
                return prop
        return None

    def values(self, proxy_id: str, name: str) -> list[Any]:
        prop = self.prop(proxy_id, name)
        if prop is None:
            return []

        elements = []
        for element in prop.findall("Element"):
            if "value" not in element.attrib:
                continue
            index = int(element.attrib.get("index", len(elements)))
            elements.append((index, maybe_number(element.attrib["value"])))
        if elements:
            return [value for _, value in sorted(elements)]
        if "value" in prop.attrib:
            return [maybe_number(prop.attrib["value"])]
        return []

    def proxy_refs(self, proxy_id: str, name: str) -> list[str]:
        prop = self.prop(proxy_id, name)
        if prop is None:
            return []
        refs = []
        for proxy in prop.findall("Proxy"):
            if "value" in proxy.attrib:
                refs.append(proxy.attrib["value"])
        return refs

    def proxies_by(self, *, group: str | None = None, proxy_type: str | None = None):
        for proxy_id, proxy in self.proxies.items():
            if group is not None and proxy.attrib.get("group") != group:
                continue
            if proxy_type is not None and proxy.attrib.get("type") != proxy_type:
                continue
            yield proxy_id, proxy

    def scalar_name(self, proxy_id: str) -> str | None:
        return last_nonempty(
            self.values(proxy_id, "SelectInputScalars")
            or self.values(proxy_id, "InputScalars")
            or self.values(proxy_id, "Scalars")
        )

    def source_summary(self) -> list[dict[str, Any]]:
        sources = []
        for proxy_id, proxy in self.proxies_by(group="sources"):
            file_names = (
                self.values(proxy_id, "FileName")
                or self.values(proxy_id, "FileNames")
                or self.values(proxy_id, "CaseFileName")
            )
            timestep_values = [
                float(value)
                for value in self.values(proxy_id, "TimestepValues")
                if isinstance(value, (int, float)) and abs(float(value)) > 1e-15
            ]
            if not file_names and not timestep_values:
                continue
            sources.append(
                {
                    "id": proxy_id,
                    "name": self.proxy_name(proxy_id),
                    "logname": self.proxy_logname(proxy_id),
                    "type": proxy.attrib.get("type"),
                    "file_names": file_names,
                    "timestep_values": timestep_values,
                }
            )
        return sources

    def contour_summary(self) -> list[dict[str, Any]]:
        contours = []
        for proxy_id, proxy in self.proxies_by(group="filters", proxy_type="Contour"):
            input_id = first(self.proxy_refs(proxy_id, "Input"))
            contours.append(
                {
                    "id": proxy_id,
                    "name": self.proxy_name(proxy_id),
                    "logname": self.proxy_logname(proxy_id),
                    "type": proxy.attrib.get("type"),
                    "input_id": input_id,
                    "input_name": self.proxy_name(input_id) if input_id else None,
                    "field": self.scalar_name(proxy_id),
                    "values": to_float_list(self.values(proxy_id, "ContourValues")),
                    "compute_normals": bool(first(self.values(proxy_id, "ComputeNormals"), 0)),
                    "compute_gradients": bool(first(self.values(proxy_id, "ComputeGradients"), 0)),
                    "compute_scalars": bool(first(self.values(proxy_id, "ComputeScalars"), 0)),
                    "generate_triangles": bool(first(self.values(proxy_id, "GenerateTriangles"), 0)),
                }
            )
        return contours

    def representation_summary(self) -> list[dict[str, Any]]:
        representations = []
        for proxy_id, proxy in self.proxies_by(group="representations", proxy_type="GeometryRepresentation"):
            input_id = first(self.proxy_refs(proxy_id, "Input"))
            diffuse_color = to_float_list(self.values(proxy_id, "DiffuseColor"))
            ambient_color = to_float_list(self.values(proxy_id, "AmbientColor"))
            color_array_values = self.values(proxy_id, "ColorArrayName")
            opacity_array_values = self.values(proxy_id, "OpacityArray")
            transform = {
                "position": to_float_list(self.values(proxy_id, "Position") or [0.0, 0.0, 0.0]),
                "scale": to_float_list(self.values(proxy_id, "Scale") or [1.0, 1.0, 1.0]),
                "orientation": to_float_list(self.values(proxy_id, "Orientation") or [0.0, 0.0, 0.0]),
                "origin": to_float_list(self.values(proxy_id, "Origin") or [0.0, 0.0, 0.0]),
                "user_transform": to_float_list(
                    self.values(proxy_id, "UserTransform")
                    or [
                        1.0, 0.0, 0.0, 0.0,
                        0.0, 1.0, 0.0, 0.0,
                        0.0, 0.0, 1.0, 0.0,
                        0.0, 0.0, 0.0, 1.0,
                    ]
                ),
            }
            representations.append(
                {
                    "id": proxy_id,
                    "name": self.proxy_name(proxy_id),
                    "logname": self.proxy_logname(proxy_id),
                    "input_id": input_id,
                    "input_name": self.proxy_name(input_id) if input_id else None,
                    "visible": bool(first(self.values(proxy_id, "Visibility"), 0)),
                    "representation": first(self.values(proxy_id, "Representation")),
                    "opacity": float(first(self.values(proxy_id, "Opacity"), 1.0)),
                    "diffuse_color": diffuse_color,
                    "diffuse_hex": rgb_to_hex(diffuse_color),
                    "ambient_color": ambient_color,
                    "ambient_hex": rgb_to_hex(ambient_color),
                    "color_array": last_nonempty(color_array_values),
                    "opacity_array": last_nonempty(opacity_array_values),
                    "line_width": first(self.values(proxy_id, "LineWidth")),
                    "mesh_visible": bool(first(self.values(proxy_id, "MeshVisibility"), 0)),
                    "transform": transform,
                    "transform_is_identity": is_identity_transform(transform),
                }
            )
        return representations

    def camera_summary(self) -> list[dict[str, Any]]:
        views = []
        for proxy_id, proxy in self.proxies_by(group="views", proxy_type="RenderView"):
            camera = {
                "position": to_float_list(self.values(proxy_id, "CameraPosition")),
                "focal_point": to_float_list(self.values(proxy_id, "CameraFocalPoint")),
                "view_up": to_float_list(self.values(proxy_id, "CameraViewUp")),
                "parallel_projection": bool(first(self.values(proxy_id, "CameraParallelProjection"), 0)),
                "parallel_scale": float(first(self.values(proxy_id, "CameraParallelScale"), 0.0)),
                "view_angle": float(first(self.values(proxy_id, "CameraViewAngle"), 30.0)),
            }
            views.append(
                {
                    "id": proxy_id,
                    "name": self.proxy_name(proxy_id),
                    "logname": self.proxy_logname(proxy_id),
                    "type": proxy.attrib.get("type"),
                    "camera": camera,
                    "pyvista_camera_position": pyvista_camera_position(camera),
                    "view_size": [int(value) for value in self.values(proxy_id, "ViewSize")],
                    "center_of_rotation": to_float_list(self.values(proxy_id, "CenterOfRotation")),
                    "representation_ids": self.proxy_refs(proxy_id, "Representations"),
                }
            )
        return views

    def lookup_table_summary(self) -> list[dict[str, Any]]:
        tables = []
        for proxy_id, proxy in self.proxies_by(group="lookup_tables"):
            rgb_points = self.values(proxy_id, "RGBPoints")
            tables.append(
                {
                    "id": proxy_id,
                    "name": self.proxy_name(proxy_id),
                    "logname": self.proxy_logname(proxy_id),
                    "type": proxy.attrib.get("type"),
                    "color_space": first(self.values(proxy_id, "ColorSpace")),
                    "rgb_points": rgb_points,
                    "opacity_mapping": bool(first(self.values(proxy_id, "EnableOpacityMapping"), 0)),
                    "nan_opacity": first(self.values(proxy_id, "NanOpacity")),
                }
            )
        return tables

    def animation_summary(self) -> dict[str, Any]:
        scenes = list(self.proxies_by(group="animation", proxy_type="AnimationScene"))
        if not scenes:
            return {}
        proxy_id, _ = scenes[0]
        return {
            "id": proxy_id,
            "animation_time": first(self.values(proxy_id, "AnimationTime")),
            "start_time": first(self.values(proxy_id, "StartTime")),
            "end_time": first(self.values(proxy_id, "EndTime")),
            "number_of_frames": first(self.values(proxy_id, "NumberOfFrames")),
            "frames_per_timestep": first(self.values(proxy_id, "FramesPerTimestep")),
            "play_mode": first(self.values(proxy_id, "PlayMode")),
        }

    def summary(self) -> dict[str, Any]:
        contours = self.contour_summary()
        representations = self.representation_summary()
        contour_by_id = {contour["id"]: contour for contour in contours}
        for representation in representations:
            representation["filter"] = contour_by_id.get(representation["input_id"])
        return {
            "source_file": str(self.path),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "paraview_version": self.version,
            "animation": self.animation_summary(),
            "sources": self.source_summary(),
            "contours": contours,
            "representations": representations,
            "visible_representations": [rep for rep in representations if rep["visible"]],
            "views": self.camera_summary(),
            "lookup_tables": self.lookup_table_summary(),
        }


def camera_json(summary: dict[str, Any]) -> dict[str, Any]:
    camera_views = {}
    for view in summary["views"]:
        name = clean_label(view["name"])
        camera = dict(view["camera"])
        camera["pyvista_camera_position"] = view["pyvista_camera_position"]
        camera_views[name] = camera
    return {"camera_views": camera_views}


def render_config(summary: dict[str, Any]) -> dict[str, Any]:
    visible_contours = []
    iso_colors: dict[str, str] = {}
    iso_opacities: dict[str, float] = {}

    for representation in summary["visible_representations"]:
        contour = representation.get("filter")
        if not contour or contour.get("type") != "Contour":
            continue
        field = contour.get("field")
        if not field:
            continue
        for value in contour.get("values", []):
            visible_contours.append((field, float(value)))
        if representation.get("diffuse_hex"):
            iso_colors.setdefault(field, representation["diffuse_hex"])
        iso_opacities.setdefault(field, float(representation.get("opacity", 1.0)))

    unique_specs = []
    seen = set()
    for field, value in visible_contours:
        key = (field, value)
        if key in seen:
            continue
        seen.add(key)
        unique_specs.append(f"{field}={value:g}")

    view_names = [clean_label(view["name"]) for view in summary["views"]]
    scene = {
        "name": f"{clean_label(Path(summary['source_file']).stem)}_visible_contours",
        "iso_specs": [],
        "iso_colors": iso_colors,
        "iso_opacities": iso_opacities,
        "compositions": [
            {
                "name": "paraview_visible",
                "iso_specs": unique_specs,
                "views": view_names,
                "resolutions": ["fullhd", "2k", "4k"],
            }
        ],
        "roi": "auto",
        "views": view_names,
        "resolutions": ["fullhd", "2k", "4k"],
        "camera_zoom": 1.0,
        "show_bounds": False,
    }
    return {
        "_generated_from": summary["source_file"],
        "_note": (
            "This maps visible ParaView contour settings into the auto_snp renderer. "
            "If the ParaView state contains multiple data sources, run the renderer once per Nek snapshot."
        ),
        **camera_json(summary),
        "scenes": [scene],
    }


def write_json(path: Path, payload: dict[str, Any], indent: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=indent)
        handle.write("\n")


def print_report(summary: dict[str, Any], written: list[Path]) -> None:
    print(f"ParaView state: {summary['source_file']}")
    print(f"ParaView version: {summary.get('paraview_version')}")
    print(f"Sources: {len(summary['sources'])}")
    for source in summary["sources"]:
        files = ", ".join(str(item) for item in source.get("file_names", []))
        print(f"  - {source['name']} ({source['type']}): {files}")
    print(f"Contours: {len(summary['contours'])}")
    for contour in summary["contours"]:
        values = ", ".join(f"{value:g}" for value in contour["values"])
        print(f"  - {contour['name']}: {contour['field']} = {values} from {contour['input_name']}")
    print(f"Visible geometry representations: {len(summary['visible_representations'])}")
    for rep in summary["visible_representations"]:
        contour = rep.get("filter") or {}
        target = contour.get("name", rep.get("input_name"))
        transform_note = ""
        if not rep["transform_is_identity"]:
            transform = rep["transform"]
            transform_note = (
                f", transform position={transform['position']}, "
                f"orientation={transform['orientation']}, scale={transform['scale']}"
            )
        print(
            f"  - {rep['name']} -> {target}: "
            f"opacity={rep['opacity']}, color={rep.get('diffuse_hex')}, "
            f"mesh_visible={rep['mesh_visible']}{transform_note}"
        )
    print(f"Views: {len(summary['views'])}")
    for view in summary["views"]:
        camera = view["camera"]
        print(
            f"  - {view['name']}: position={camera['position']}, "
            f"focal_point={camera['focal_point']}, parallel_scale={camera['parallel_scale']}"
        )
        print(f"    PyVista camera_position={view['pyvista_camera_position']}")
    for path in written:
        print(f"Wrote {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract cameras, contours, sources, and visible representation settings from a ParaView .pvsm state."
    )
    parser.add_argument("pvsm", type=Path, help="ParaView .pvsm state file")
    parser.add_argument("--summary-json", type=Path, help="Detailed extracted summary JSON")
    parser.add_argument("--camera-json", type=Path, help="Camera JSON usable as PYVISTA_CAMERA_FILE")
    parser.add_argument("--render-config", type=Path, help="auto_snp render config generated from visible contours")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    parser.add_argument("--no-write", action="store_true", help="Only print the report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = ParaViewState(args.pvsm)
    summary = state.summary()

    stem = args.pvsm.with_suffix("")
    summary_path = args.summary_json or stem.with_name(f"{stem.name}_paraview_summary.json")
    camera_path = args.camera_json or stem.with_name(f"{stem.name}_camera_views.json")
    config_path = args.render_config or stem.with_name(f"{stem.name}_render_config.json")

    written = []
    if not args.no_write:
        write_json(summary_path, summary, args.indent)
        write_json(camera_path, camera_json(summary), args.indent)
        write_json(config_path, render_config(summary), args.indent)
        written.extend([summary_path, camera_path, config_path])

    print_report(summary, written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
