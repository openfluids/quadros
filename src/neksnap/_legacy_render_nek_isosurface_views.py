#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")

import numpy as np
from PIL import Image
from pymech.neksuite import readnek
import pyvista as pv
import vtk


def env_bool(name: str, default: bool) -> bool:
    fallback = "1" if default else "0"
    return os.environ.get(name, fallback).lower() not in {"0", "false", "no", "off", "none"}


SCRIPT_DIR = Path(__file__).resolve().parent
OUT_ROOT = Path(os.environ.get("PYVISTA_FIGURE_DIR", SCRIPT_DIR))
IMAGE_FORMAT = os.environ.get("PYVISTA_IMAGE_FORMAT", "png").lower().lstrip(".")
IMAGE_QUALITY = int(os.environ.get("PYVISTA_IMAGE_QUALITY", "95"))
PNG_COMPRESS_LEVEL = int(os.environ.get("PYVISTA_PNG_COMPRESS_LEVEL", "6"))
WINDOW_WIDTH = int(os.environ.get("PYVISTA_WINDOW_WIDTH", "1200"))
WINDOW_HEIGHT = int(os.environ.get("PYVISTA_WINDOW_HEIGHT", "850"))
RESOLUTION_PRESETS_TEXT = os.environ.get(
    "PYVISTA_RESOLUTION_PRESETS",
    os.environ.get("PYVISTA_RESOLUTION_PRESET", "fullhd,2k,4k"),
)
RESOLUTION_SCALE = int(os.environ.get("PYVISTA_RESOLUTION_SCALE", "1"))
HIGH_RES_SUBDIR_MIN_WIDTH = int(os.environ.get("PYVISTA_HIGH_RES_SUBDIR_MIN_WIDTH", "2560"))
HIGH_RES_SUBDIR_MIN_HEIGHT = int(os.environ.get("PYVISTA_HIGH_RES_SUBDIR_MIN_HEIGHT", "1440"))
SCENE_SUBDIRS = env_bool("PYVISTA_SCENE_SUBDIRS", False)
CLEAN_SNAPSHOT_OUTPUT = env_bool("NEK_CLEAN_SNAPSHOT_OUTPUT", True)
CAMERA_FILE = os.environ.get("PYVISTA_CAMERA_FILE", os.environ.get("NEK_CAMERA_FILE", ""))
VIEW_NAMES_TEXT = os.environ.get(
    "PYVISTA_VIEWS",
    "top,side,front,iso,side_iso_left,side_iso_right",
)
SHOW_BOUNDS = env_bool("PYVISTA_SHOW_BOUNDS", False)
SKIP_MISSING_ISO = env_bool("NEK_SKIP_MISSING_ISO", True)
ANTI_ALIASING = os.environ.get("PYVISTA_ANTI_ALIASING", "msaa").lower()
ANTI_ALIASING_SAMPLES = int(os.environ.get("PYVISTA_ANTI_ALIASING_SAMPLES", "8"))

ISO_FIELD = os.environ.get("NEK_ISO_FIELD", "u")
ISO_VALUE = os.environ.get("NEK_ISO_VALUE", "0.0")
DEFAULT_ISO_SPECS_TEXT = "u=+-0.01;v=+-0.02;w=+-0.01"
ISO_SPECS_TEXT = os.environ.get(
    "NEK_ISO_SPECS",
    f"{ISO_FIELD}={ISO_VALUE}" if "NEK_ISO_FIELD" in os.environ or "NEK_ISO_VALUE" in os.environ else DEFAULT_ISO_SPECS_TEXT,
)
BODY_OBJECT = os.environ.get("NEK_OBJECT", "auto").lower()
BODY_DIAMETER = float(os.environ.get("NEK_BODY_D", "1.0"))
BODY_CENTER = tuple(float(x) for x in os.environ.get("NEK_BODY_CENTER", "0,0,0").split(","))
ROI_TEXT = os.environ.get("NEK_ROI", "auto")
ROI_UPSTREAM_D = float(os.environ.get("NEK_ROI_UPSTREAM_D", "1.5"))
ROI_DOWNSTREAM_D = float(os.environ.get("NEK_ROI_DOWNSTREAM_D", "12.0"))
ROI_RADIUS_D = float(os.environ.get("NEK_ROI_RADIUS_D", "4.0"))
CASE_LABEL_OVERRIDE = os.environ.get("NEK_CASE_LABEL", "auto")
CAMERA_ZOOM = float(os.environ.get("PYVISTA_CAMERA_ZOOM", "1.18"))
ISO_COLOR_OVERRIDE = os.environ.get("NEK_ISO_COLOR", "auto")
ISO_COLORS_TEXT = os.environ.get("NEK_ISO_COLORS", "")
ISO_OPACITY = float(os.environ.get("NEK_ISO_OPACITY", "0.62"))
ISO_OPACITIES_TEXT = os.environ.get("NEK_ISO_OPACITIES", "")
ISO_SMOOTH_SHADING = env_bool("NEK_ISO_SMOOTH_SHADING", True)
ISO_SPLIT_SHARP_EDGES = env_bool("NEK_ISO_SPLIT_SHARP_EDGES", False)
ISO_LIGHTING = env_bool("NEK_ISO_LIGHTING", True)
ISO_AMBIENT = float(os.environ.get("NEK_ISO_AMBIENT", "0.30"))
ISO_DIFFUSE = float(os.environ.get("NEK_ISO_DIFFUSE", "0.75"))
ISO_SPECULAR = float(os.environ.get("NEK_ISO_SPECULAR", "0.22"))
ISO_SPECULAR_POWER = float(os.environ.get("NEK_ISO_SPECULAR_POWER", "24"))
CONTOUR_METHOD = os.environ.get("NEK_CONTOUR_METHOD", "contour").lower()
CONTOUR_COMPUTE_NORMALS = env_bool("NEK_CONTOUR_COMPUTE_NORMALS", True)
CONTOUR_COMPUTE_GRADIENTS = env_bool("NEK_CONTOUR_COMPUTE_GRADIENTS", False)
CONTOUR_COMPUTE_SCALARS = env_bool("NEK_CONTOUR_COMPUTE_SCALARS", True)
SURFACE_CLEAN = env_bool("NEK_SURFACE_CLEAN", True)
SURFACE_CLEAN_TOLERANCE = float(os.environ.get("NEK_SURFACE_CLEAN_TOLERANCE", "1e-10"))
SURFACE_SMOOTH_METHOD = os.environ.get("NEK_SURFACE_SMOOTH_METHOD", "laplacian").lower()
SURFACE_SMOOTH_ITERATIONS = int(os.environ.get("NEK_SURFACE_SMOOTH_ITERATIONS", "0"))
SURFACE_SMOOTH_RELAXATION = float(os.environ.get("NEK_SURFACE_SMOOTH_RELAXATION", "0.01"))
SURFACE_TAUBIN_PASS_BAND = float(os.environ.get("NEK_SURFACE_TAUBIN_PASS_BAND", "0.1"))
SURFACE_SMOOTH_EDGE_ANGLE = float(os.environ.get("NEK_SURFACE_SMOOTH_EDGE_ANGLE", "15"))
SURFACE_SMOOTH_FEATURE_ANGLE = float(os.environ.get("NEK_SURFACE_SMOOTH_FEATURE_ANGLE", "45"))
SURFACE_SMOOTH_BOUNDARY = env_bool("NEK_SURFACE_SMOOTH_BOUNDARY", True)
SURFACE_SMOOTH_FEATURE = env_bool("NEK_SURFACE_SMOOTH_FEATURE", False)
BODY_COLOR = os.environ.get("NEK_BODY_COLOR", "#8A8A8A")
BODY_LIGHTING = env_bool("NEK_BODY_LIGHTING", True)
BODY_AMBIENT = float(os.environ.get("NEK_BODY_AMBIENT", "0.40"))
BODY_DIFFUSE = float(os.environ.get("NEK_BODY_DIFFUSE", "0.70"))
BODY_SPECULAR = float(os.environ.get("NEK_BODY_SPECULAR", "0.08"))
BODY_SPECULAR_POWER = float(os.environ.get("NEK_BODY_SPECULAR_POWER", "16"))
# Optional wake-axis centerline at y=0, z=0. NEK_CENTERLINE="x0,x1" enables it
# (line from (x0,0,0) to (x1,0,0)); empty string = off.
CENTERLINE = os.environ.get("NEK_CENTERLINE", "")
CENTERLINE_COLOR = os.environ.get("NEK_CENTERLINE_COLOR", "#E04040")
CENTERLINE_WIDTH = float(os.environ.get("NEK_CENTERLINE_WIDTH", "2"))

# Bake the in-render text overlay? Set NEK_ANNOTATION=off to render clean
# frames (time/labels then added crisply in post via ffmpeg drawtext, which
# avoids the per-frame VTK text flicker and repeated headers in composites).
ANNOTATION = env_bool("NEK_ANNOTATION", True)
# Depth peeling: correct order-independent transparency for semi-transparent
# isosurfaces (opacity < 1). Without it, overlapping transparent layers
# composite in the wrong order and look muddy. NEK_DEPTH_PEELING=on to enable.
DEPTH_PEELING = env_bool("NEK_DEPTH_PEELING", False)
DEPTH_PEELS = int(os.environ.get("NEK_DEPTH_PEELS", "8"))
# Screen-space ambient occlusion adds contact shadows / depth cues.
SSAO = env_bool("NEK_SSAO", False)
# Physically-based rendering: metallic/roughness material + image-based lighting
# from an HDRI environment map -> glossy reflections without a ray tracer (no GPU).
# NEK_ISO_PBR=on + NEK_ENVIRONMENT=/path/to/equirectangular.(hdr|png) for reflections.
ISO_PBR = env_bool("NEK_ISO_PBR", False)
ISO_METALLIC = float(os.environ.get("NEK_ISO_METALLIC", "0.40"))
ISO_ROUGHNESS = float(os.environ.get("NEK_ISO_ROUGHNESS", "0.35"))
ENVIRONMENT_TEXTURE = os.environ.get("NEK_ENVIRONMENT", "")
RENDER_CONFIG = os.environ.get("NEK_RENDER_CONFIG", "")
LOG_LEVEL = os.environ.get("NEK_LOG_LEVEL", "info").lower()


if len(BODY_CENTER) != 3:
    raise ValueError("NEK_BODY_CENTER must have three comma-separated values")

if IMAGE_FORMAT == "jpg":
    IMAGE_FORMAT = "jpeg"

if IMAGE_FORMAT not in {"png", "jpeg", "webp", "tiff"}:
    raise ValueError("PYVISTA_IMAGE_FORMAT must be one of: png, jpg, jpeg, webp, tiff")

if ANTI_ALIASING not in {"", "0", "false", "none", "ssaa", "msaa", "fxaa"}:
    raise ValueError("PYVISTA_ANTI_ALIASING must be one of: none, ssaa, msaa, fxaa")

if CONTOUR_METHOD != "contour":
    raise ValueError(
        "NEK_CONTOUR_METHOD must be 'contour' for native Nek StructuredGrid elements. "
        "PyVista marching_cubes/flying_edges require vtkImageData."
    )

if SURFACE_SMOOTH_METHOD in {"", "0", "false", "off"}:
    SURFACE_SMOOTH_METHOD = "none"

if SURFACE_SMOOTH_METHOD not in {"none", "laplacian", "taubin"}:
    raise ValueError("NEK_SURFACE_SMOOTH_METHOD must be one of: none, laplacian, taubin")


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}

RESOLUTION_PRESETS = {
    "custom": (WINDOW_WIDTH, WINDOW_HEIGHT),
    "hd": (1280, 720),
    "720p": (1280, 720),
    "fullhd": (1920, 1080),
    "fhd": (1920, 1080),
    "1080p": (1920, 1080),
    "2k": (2560, 1440),
    "qhd": (2560, 1440),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
    "uhd": (3840, 2160),
    "2160p": (3840, 2160),
}

RESOLUTION_CANONICAL_LABELS = {
    "720p": "hd",
    "fhd": "fullhd",
    "1080p": "fullhd",
    "qhd": "2k",
    "1440p": "2k",
    "uhd": "4k",
    "2160p": "4k",
}

BUILTIN_VIEWS = {
    # Flow convention: x streamwise, y vertical, z spanwise.
    "top": ("axis", "xz"),
    "side": ("axis", "xy"),
    "front": ("axis", "yz"),
    "iso": ("axis", "iso"),
    "side_iso": ("direction", (1.0, 0.35, 1.0), (0.0, 1.0, 0.0)),
    "side_iso_left": ("direction", (1.0, 0.35, 1.0), (0.0, 1.0, 0.0)),
    "side_iso_right": ("direction", (1.0, 0.35, -1.0), (0.0, 1.0, 0.0)),
    "front_iso": ("direction", (1.0, 0.35, 0.45), (0.0, 1.0, 0.0)),
    "rear_iso": ("direction", (-1.0, 0.35, 0.45), (0.0, 1.0, 0.0)),
    "top_iso": ("direction", (0.75, 1.0, 0.75), (0.0, 0.0, 1.0)),
}

VIEWS = dict(BUILTIN_VIEWS)
REGISTERED_CAMERA_VIEWS: dict[str, tuple] = {}

FIELD_ALIASES = {
    "ux": "u",
    "velx": "u",
    "velocity_x": "u",
    "uy": "v",
    "vely": "v",
    "velocity_y": "v",
    "uz": "w",
    "velz": "w",
    "velocity_z": "w",
    "pressure": "p",
    "temperature": "temp",
    "t": "temp",
    "velocity_magnitude": "speed",
    "velmag": "speed",
    "mag": "speed",
    "magnitude": "speed",
}

FIELD_STYLE_ALIASES = {
    "u": ("ux", "velx", "velocity_x"),
    "v": ("uy", "vely", "velocity_y"),
    "w": ("uz", "velz", "velocity_z"),
    "p": ("pressure",),
    "temp": ("temperature", "t"),
    "temp0": ("temperature", "t"),
    "speed": ("velocity_magnitude", "velmag", "mag", "magnitude"),
}

DERIVED_FIELD_REQUIREMENTS = {
    "speed": ("u", "v", "w"),
}


@dataclass(frozen=True)
class RenderResolution:
    label: str
    width: int
    height: int
    scale: int
    use_subdir: bool


@dataclass(frozen=True)
class IsoSpec:
    field: str
    value: float
    label: str
    color: str
    opacity: float


@dataclass(frozen=True)
class CompositionSpec:
    name: str
    iso_specs_text: str
    view_names: tuple[str, ...] | None
    resolutions: tuple[RenderResolution, ...] | None


@dataclass(frozen=True)
class SceneSpec:
    name: str
    iso_specs_text: str
    iso_colors: dict[str, str]
    iso_opacities: dict[str, float]
    compositions: tuple[CompositionSpec, ...]
    view_names: tuple[str, ...]
    resolutions: tuple[RenderResolution, ...]
    roi_bounds: tuple[float, float, float, float, float, float] | None
    camera_zoom: float
    show_bounds: bool
    use_scene_subdir: bool
    surface_smooth_method: str
    surface_smooth_iterations: int
    surface_smooth_relaxation: float
    surface_taubin_pass_band: float
    surface_smooth_edge_angle: float
    surface_smooth_feature_angle: float
    surface_smooth_boundary: bool
    surface_smooth_feature: bool


@dataclass(frozen=True)
class RenderCase:
    field_path: Path
    output_dir: Path
    file_label: str
    object_name: str


class RunLogger:
    def __init__(self, log_path: Path, events_path: Path):
        self.log_path = log_path
        self.events_path = events_path
        self.log_handle = log_path.open("w", encoding="utf-8")
        self.events_handle = events_path.open("w", encoding="utf-8")
        self.run_start = time.perf_counter()
        self.timings: list[dict] = []

    def close(self) -> None:
        self.log_handle.close()
        self.events_handle.close()

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def event(self, event_type: str, **metadata) -> None:
        record = {
            "ts": self._timestamp(),
            "elapsed_s": round(time.perf_counter() - self.run_start, 6),
            "event": event_type,
            **metadata,
        }
        self.events_handle.write(json.dumps(record, sort_keys=True) + "\n")
        self.events_handle.flush()

    def info(self, message: str, **metadata) -> None:
        line = f"{self._timestamp()} [INFO] {message}"
        print(line, flush=True)
        self.log_handle.write(line + "\n")
        self.log_handle.flush()
        self.event("log", level="info", message=message, **metadata)

    def warning(self, message: str, **metadata) -> None:
        line = f"{self._timestamp()} [WARN] {message}"
        print(line, flush=True)
        self.log_handle.write(line + "\n")
        self.log_handle.flush()
        self.event("log", level="warning", message=message, **metadata)

    @contextmanager
    def timed(self, label: str, **metadata):
        start = time.perf_counter()
        self.info(f"START {label}", **metadata)
        self.event("timer_start", label=label, **metadata)
        try:
            yield
        finally:
            seconds = time.perf_counter() - start
            record = {"label": label, "seconds": seconds, **metadata}
            self.timings.append(record)
            self.info(f"DONE  {label}: {seconds:.3f} s", **metadata)
            self.event("timer_done", label=label, seconds=seconds, **metadata)


LOGGER: RunLogger | None = None


def log() -> RunLogger:
    if LOGGER is None:
        raise RuntimeError("logger not initialized")
    return LOGGER


def clean_label(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def value_label(value: float) -> str:
    if abs(value) < 1e-14:
        return "0"
    prefix = "p" if value > 0 else "m"
    body = f"{abs(value):g}".replace(".", "p").replace("+", "").replace("-", "")
    return f"{prefix}{body}"


def parse_roi(
    text: str,
    upstream_d: float = ROI_UPSTREAM_D,
    downstream_d: float = ROI_DOWNSTREAM_D,
    radius_d: float = ROI_RADIUS_D,
) -> tuple[float, float, float, float, float, float] | None:
    text = str(text).strip().lower()
    if text in {"none", "full", "all", "0", "false"}:
        return None

    cx, cy, cz = BODY_CENTER
    if text == "auto":
        return (
            cx - upstream_d * BODY_DIAMETER,
            cx + downstream_d * BODY_DIAMETER,
            cy - radius_d * BODY_DIAMETER,
            cy + radius_d * BODY_DIAMETER,
            cz - radius_d * BODY_DIAMETER,
            cz + radius_d * BODY_DIAMETER,
        )

    values = tuple(float(x) for x in re.split(r"[, ]+", text) if x)
    if len(values) != 6:
        raise ValueError("NEK_ROI must be auto, none, or six values: xmin,xmax,ymin,ymax,zmin,zmax")
    return values


def parse_resolutions(text) -> tuple[RenderResolution, ...]:
    if isinstance(text, (list, tuple)):
        text = ",".join(str(item) for item in text)

    names = [name.strip().lower() for name in str(text).split(",") if name.strip()]
    if not names:
        raise ValueError("PYVISTA_RESOLUTION_PRESETS produced no resolutions")

    resolutions = []
    for name in names:
        if name not in RESOLUTION_PRESETS:
            raise ValueError(f"unknown resolution preset {name!r}; choose from {sorted(RESOLUTION_PRESETS)}")
        width, height = RESOLUTION_PRESETS[name]
        label = RESOLUTION_CANONICAL_LABELS.get(name, name)
        if name == "custom":
            label = f"custom_{width}x{height}"
        if RESOLUTION_SCALE != 1:
            label = f"{label}_x{RESOLUTION_SCALE}"
        use_subdir = (
            width * RESOLUTION_SCALE >= HIGH_RES_SUBDIR_MIN_WIDTH
            or height * RESOLUTION_SCALE >= HIGH_RES_SUBDIR_MIN_HEIGHT
        )
        resolutions.append(RenderResolution(label, width, height, RESOLUTION_SCALE, use_subdir))

    return tuple(resolutions)


def group_resolutions_by_aspect(resolution_set: tuple[RenderResolution, ...]):
    groups = defaultdict(list)
    for resolution in resolution_set:
        width = resolution.width * resolution.scale
        height = resolution.height * resolution.scale
        groups[round(width / height, 6)].append(resolution)
    return tuple(tuple(group) for group in groups.values())


def csv_list(value, default: str) -> tuple[str, ...]:
    if value is None:
        value = default
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return tuple(str(item).strip() for item in value if str(item).strip())


def parse_setting_map(raw, value_parser=str) -> dict[str, object]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(key).strip().lower(): value_parser(value) for key, value in raw.items()}
    if isinstance(raw, (list, tuple)):
        raw = ",".join(str(item) for item in raw)

    mapping = {}
    for entry in re.split(r"[,;\n]+", str(raw)):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(f"style-map entries must look like key=value, got {entry!r}")
        key, value = entry.split("=", 1)
        mapping[key.strip().lower()] = value_parser(value.strip())
    return mapping


def parse_compositions(raw) -> tuple[CompositionSpec, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = [entry.strip() for entry in raw.split("|") if entry.strip()]

    compositions = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, str):
            if ":" in item:
                name, iso_text = item.split(":", 1)
                name = name.strip()
            else:
                name = f"composition_{index}"
                iso_text = item
            compositions.append(
                CompositionSpec(
                    name=clean_label(name),
                    iso_specs_text=iso_text.strip(),
                    view_names=None,
                    resolutions=None,
                )
            )
            continue

        if not isinstance(item, dict):
            raise ValueError("composition entries must be strings or objects")

        name = clean_label(item.get("name", f"composition_{index}"))
        iso_text = item.get("iso_specs")
        if iso_text is None:
            raise ValueError(f"composition {name!r} is missing iso_specs")
        if isinstance(iso_text, (list, tuple)):
            iso_text = ";".join(str(part) for part in iso_text)

        compositions.append(
            CompositionSpec(
                name=name,
                iso_specs_text=str(iso_text),
                view_names=csv_list(item.get("views"), "") if item.get("views") is not None else None,
                resolutions=parse_resolutions(item["resolutions"]) if "resolutions" in item else None,
            )
        )

    return tuple(compositions)


def float_tuple(raw, expected: int | None = None) -> tuple[float, ...]:
    if raw is None:
        raise ValueError("missing numeric tuple")
    if isinstance(raw, str):
        values = tuple(float(part) for part in re.split(r"[, ]+", raw.strip()) if part)
    else:
        values = tuple(float(part) for part in raw)
    if expected is not None and len(values) != expected:
        raise ValueError(f"expected {expected} values, got {len(values)}")
    return values


def bool_from_paraview_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text not in {"", "0", "false", "no", "off"}


def pyvista_camera_position_tuple(raw) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    if isinstance(raw, str):
        pieces = [piece.strip() for piece in raw.split(";") if piece.strip()]
    else:
        pieces = list(raw)
    if len(pieces) != 3:
        raise ValueError("PyVista camera_position must contain position, focal_point, and view_up")
    return (
        float_tuple(pieces[0], 3),
        float_tuple(pieces[1], 3),
        float_tuple(pieces[2], 3),
    )


def camera_view_spec(raw: dict):
    pyvista_camera_position = raw.get("pyvista_camera_position", raw.get("camera_position"))
    if pyvista_camera_position is not None:
        position, focal_point, view_up = pyvista_camera_position_tuple(pyvista_camera_position)
    else:
        position = float_tuple(raw.get("position", raw.get("CameraPosition")), 3)
        focal_point = float_tuple(raw.get("focal_point", raw.get("CameraFocalPoint", raw.get("focalPoint"))), 3)
        view_up = float_tuple(raw.get("view_up", raw.get("CameraViewUp", raw.get("viewUp", (0, 1, 0)))), 3)
    camera = {
        "position": position,
        "focal_point": focal_point,
        "view_up": view_up,
    }
    for source_key, target_key in (
        ("parallel_scale", "parallel_scale"),
        ("CameraParallelScale", "parallel_scale"),
        ("view_angle", "view_angle"),
        ("CameraViewAngle", "view_angle"),
        ("zoom", "zoom"),
    ):
        if source_key in raw and raw[source_key] is not None:
            camera[target_key] = float(raw[source_key])
    for source_key, target_key in (
        ("parallel_projection", "parallel_projection"),
        ("CameraParallelProjection", "parallel_projection"),
        ("apply_scene_zoom", "apply_scene_zoom"),
    ):
        if source_key in raw and raw[source_key] is not None:
            camera[target_key] = bool_from_paraview_value(raw[source_key])
    return ("camera", camera)


def camera_values_from_xml_property(proxy, name: str) -> list[str]:
    for prop in proxy.findall(".//Property"):
        if prop.attrib.get("name") != name:
            continue
        elements = []
        for element in prop.findall("Element"):
            if "value" not in element.attrib:
                continue
            index = int(element.attrib.get("index", len(elements)))
            elements.append((index, element.attrib["value"]))
        if elements:
            return [value for _, value in sorted(elements)]
        if "value" in prop.attrib:
            return [prop.attrib["value"]]
    return []


def parse_paraview_camera_views(path: Path) -> dict[str, tuple]:
    tree = ET.parse(path)
    root = tree.getroot()
    views = {}
    view_index = 0
    for proxy in root.findall(".//Proxy"):
        has_camera = bool(camera_values_from_xml_property(proxy, "CameraPosition"))
        if not has_camera:
            continue
        view_index += 1
        name = (
            proxy.attrib.get("registrationName")
            or proxy.attrib.get("name")
            or proxy.attrib.get("id")
            or f"paraview_{view_index}"
        )
        raw = {
            "CameraPosition": camera_values_from_xml_property(proxy, "CameraPosition"),
            "CameraFocalPoint": camera_values_from_xml_property(proxy, "CameraFocalPoint"),
            "CameraViewUp": camera_values_from_xml_property(proxy, "CameraViewUp") or (0, 1, 0),
        }
        optional = {
            "CameraParallelScale": camera_values_from_xml_property(proxy, "CameraParallelScale"),
            "CameraViewAngle": camera_values_from_xml_property(proxy, "CameraViewAngle"),
            "CameraParallelProjection": camera_values_from_xml_property(proxy, "CameraParallelProjection"),
        }
        for key, values in optional.items():
            if values:
                raw[key] = values[0] if len(values) == 1 else values
        views[clean_label(name)] = camera_view_spec(raw)
    return views


def parse_json_camera_views(config: dict) -> dict[str, tuple]:
    raw_views = config.get("camera_views", config.get("cameras"))
    if raw_views is None and "scenes" not in config:
        raw_views = config.get("views", config)
    if raw_views is None:
        raw_views = {}
    if isinstance(raw_views, list):
        raw_views = {item.get("name", f"camera_{index}"): item for index, item in enumerate(raw_views, start=1)}
    if not isinstance(raw_views, dict):
        raise ValueError("camera_views/cameras must be a JSON object or list")
    views = {}
    for name, raw in raw_views.items():
        if not isinstance(raw, dict):
            continue
        views[clean_label(name)] = camera_view_spec(raw)
    return views


def resolve_input_path(path_text: str, base_dir: Path | None = None) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path


def load_camera_views_from_path(path: Path) -> dict[str, tuple]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as handle:
            return parse_json_camera_views(json.load(handle))
    return parse_paraview_camera_views(path)


def register_camera_views(config: dict | None = None, base_dir: Path | None = None) -> dict[str, tuple]:
    loaded = {}
    if CAMERA_FILE:
        loaded.update(load_camera_views_from_path(resolve_input_path(CAMERA_FILE, base_dir)))
    if config:
        if "camera_file" in config:
            loaded.update(load_camera_views_from_path(resolve_input_path(config["camera_file"], base_dir)))
        loaded.update(parse_json_camera_views(config))
    VIEWS.update(loaded)
    REGISTERED_CAMERA_VIEWS.update(loaded)
    return loaded


def scene_from_dict(raw: dict, use_scene_subdir: bool) -> SceneSpec:
    name = clean_label(raw.get("name", "scene"))
    iso_text = raw.get("iso_specs", ISO_SPECS_TEXT)
    if isinstance(iso_text, (list, tuple)):
        iso_text = ";".join(str(item) for item in iso_text)
    smooth_method = str(raw.get("surface_smooth_method", SURFACE_SMOOTH_METHOD)).lower()
    if smooth_method in {"", "0", "false", "off"}:
        smooth_method = "none"
    if smooth_method not in {"none", "laplacian", "taubin"}:
        raise ValueError(f"scene {name!r} has unknown surface_smooth_method {smooth_method!r}")

    roi_bounds = parse_roi(
        raw.get("roi", ROI_TEXT),
        float(raw.get("roi_upstream_d", ROI_UPSTREAM_D)),
        float(raw.get("roi_downstream_d", ROI_DOWNSTREAM_D)),
        float(raw.get("roi_radius_d", ROI_RADIUS_D)),
    )

    return SceneSpec(
        name=name,
        iso_specs_text=str(iso_text),
        iso_colors=parse_setting_map(raw.get("iso_colors", ISO_COLORS_TEXT), str),
        iso_opacities=parse_setting_map(raw.get("iso_opacities", ISO_OPACITIES_TEXT), float),
        compositions=parse_compositions(raw.get("compositions")),
        view_names=csv_list(raw.get("views"), VIEW_NAMES_TEXT),
        resolutions=parse_resolutions(raw.get("resolutions", RESOLUTION_PRESETS_TEXT)),
        roi_bounds=roi_bounds,
        camera_zoom=float(raw.get("camera_zoom", CAMERA_ZOOM)),
        show_bounds=str(raw.get("show_bounds", SHOW_BOUNDS)).lower() not in {"0", "false", "no"},
        use_scene_subdir=str(raw.get("use_scene_subdir", use_scene_subdir)).lower()
        not in {"0", "false", "no"},
        surface_smooth_method=smooth_method,
        surface_smooth_iterations=int(raw.get("surface_smooth_iterations", SURFACE_SMOOTH_ITERATIONS)),
        surface_smooth_relaxation=float(raw.get("surface_smooth_relaxation", SURFACE_SMOOTH_RELAXATION)),
        surface_taubin_pass_band=float(raw.get("surface_taubin_pass_band", SURFACE_TAUBIN_PASS_BAND)),
        surface_smooth_edge_angle=float(raw.get("surface_smooth_edge_angle", SURFACE_SMOOTH_EDGE_ANGLE)),
        surface_smooth_feature_angle=float(raw.get("surface_smooth_feature_angle", SURFACE_SMOOTH_FEATURE_ANGLE)),
        surface_smooth_boundary=bool_from_paraview_value(
            raw.get("surface_smooth_boundary", SURFACE_SMOOTH_BOUNDARY)
        ),
        surface_smooth_feature=bool_from_paraview_value(
            raw.get("surface_smooth_feature", SURFACE_SMOOTH_FEATURE)
        ),
    )


def load_scenes() -> tuple[SceneSpec, ...]:
    if RENDER_CONFIG:
        config_path = resolve_input_path(RENDER_CONFIG)
        with config_path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        register_camera_views(config, config_path.parent)
        raw_scenes = config.get("scenes", [])
        if not raw_scenes:
            raise ValueError(f"{config_path} must contain a non-empty scenes array")
        return tuple(scene_from_dict(raw, use_scene_subdir=SCENE_SUBDIRS) for raw in raw_scenes)

    return (
        SceneSpec(
            name="default",
            iso_specs_text=ISO_SPECS_TEXT,
            iso_colors=parse_setting_map(ISO_COLORS_TEXT, str),
            iso_opacities=parse_setting_map(ISO_OPACITIES_TEXT, float),
            compositions=parse_compositions(os.environ.get("NEK_COMPOSITIONS")),
            view_names=csv_list(VIEW_NAMES_TEXT, VIEW_NAMES_TEXT),
            resolutions=parse_resolutions(RESOLUTION_PRESETS_TEXT),
            roi_bounds=parse_roi(ROI_TEXT),
            camera_zoom=CAMERA_ZOOM,
            show_bounds=SHOW_BOUNDS,
            use_scene_subdir=False,
            surface_smooth_method=SURFACE_SMOOTH_METHOD,
            surface_smooth_iterations=SURFACE_SMOOTH_ITERATIONS,
            surface_smooth_relaxation=SURFACE_SMOOTH_RELAXATION,
            surface_taubin_pass_band=SURFACE_TAUBIN_PASS_BAND,
            surface_smooth_edge_angle=SURFACE_SMOOTH_EDGE_ANGLE,
            surface_smooth_feature_angle=SURFACE_SMOOTH_FEATURE_ANGLE,
            surface_smooth_boundary=SURFACE_SMOOTH_BOUNDARY,
            surface_smooth_feature=SURFACE_SMOOTH_FEATURE,
        ),
    )


def available_field_names(field) -> tuple[str, ...]:
    if not field.elem:
        return ()

    elem = field.elem[0]
    names: list[str] = []
    for index, name in enumerate(("u", "v", "w")):
        if elem.vel.shape[0] > index:
            names.append(name)
    if elem.pres.shape[0] > 0:
        names.append("p")
    for index in range(elem.temp.shape[0]):
        names.append("temp" if elem.temp.shape[0] == 1 and index == 0 else f"temp{index}")
    for index in range(elem.scal.shape[0]):
        names.append(f"scal{index}")
    return tuple(names)


def canonical_field_name(field_name: str) -> str:
    name = str(field_name).strip().lower().replace("-", "_")
    if name.startswith("s") and name[1:].isdigit():
        return f"scal{name[1:]}"
    return FIELD_ALIASES.get(name, name)


def renderable_field_names(available_fields: tuple[str, ...]) -> tuple[str, ...]:
    available = set(available_fields)
    names = list(available_fields)
    for field_name, requirements in DERIVED_FIELD_REQUIREMENTS.items():
        if field_name not in available and all(requirement in available for requirement in requirements):
            names.append(field_name)
    return tuple(names)


def resolve_field_name(
    requested_field: str,
    available_fields: tuple[str, ...],
) -> tuple[str | None, str | None]:
    available = set(available_fields)
    field_name = canonical_field_name(requested_field)

    if field_name == "temp" and field_name not in available and "temp0" in available:
        field_name = "temp0"

    if field_name in available:
        return field_name, None

    requirements = DERIVED_FIELD_REQUIREMENTS.get(field_name)
    if requirements is not None:
        missing = [name for name in requirements if name not in available]
        if not missing:
            return field_name, None
        return (
            None,
            f"derived field {field_name!r} requires missing fields: {', '.join(missing)}",
        )

    return (
        None,
        f"field {field_name!r} is not available and no derived-field implementation is registered",
    )


def expand_field_names(field_text: str, available_fields: tuple[str, ...]) -> list[str]:
    fields = []
    tokens = [token for token in re.split(r"[,/| +]+", field_text.lower()) if token]
    for token in tokens:
        if token in {"all", "fields", "file", "available"}:
            fields.extend(available_fields)
        elif token in {"renderable", "known"}:
            fields.extend(renderable_field_names(available_fields))
        elif token in {"derived", "computed"}:
            fields.extend(name for name in renderable_field_names(available_fields) if name not in available_fields)
        elif token in {"velocity", "vel", "uvw"}:
            fields.extend(name for name in ("u", "v", "w") if name in available_fields)
        else:
            fields.append(canonical_field_name(token))

    seen = set()
    unique_fields = []
    for field in fields:
        if field not in seen:
            seen.add(field)
            unique_fields.append(field)
    return unique_fields


def style_map_candidates(field: str, value: float) -> tuple[str, ...]:
    sign = "0" if abs(value) < 1e-14 else ("+" if value > 0 else "-")
    label = value_label(value)
    field = canonical_field_name(field)
    names = (field, *FIELD_STYLE_ALIASES.get(field, ()))
    candidates = []
    for name in names:
        candidates.extend(
            (
                f"{name}:{value:g}",
                f"{name}:{label}",
                f"{name}{sign}",
                name,
            )
        )
    candidates.extend(("*", "all"))
    return tuple(candidates)


def lookup_style_setting(mapping: dict, field: str, value: float):
    for key in style_map_candidates(field, value):
        if key in mapping:
            return mapping[key]
    return None


def auto_iso_color(field: str, value: float, color_map: dict[str, str] | None = None) -> str:
    mapped_color = lookup_style_setting(color_map or {}, field, value)
    if mapped_color is not None:
        return str(mapped_color)
    if ISO_COLOR_OVERRIDE != "auto":
        return ISO_COLOR_OVERRIDE

    colors = {
        ("u", -1): "#1F77B4",
        ("u", 1): "#FF7F0E",
        ("u", 0): "#5B8FF9",
        ("v", -1): "#D62728",
        ("v", 1): "#2CA02C",
        ("w", -1): "#7B61FF",
        ("w", 1): "#17BECF",
        ("p", -1): "#8C564B",
        ("p", 1): "#E377C2",
        ("speed", 1): "#17BECF",
    }
    sign = 0 if abs(value) < 1e-14 else (1 if value > 0 else -1)
    return colors.get((field, sign), colors.get((field, 1), "#5B8FF9"))


def iso_opacity(field: str, value: float, opacity_map: dict[str, float] | None = None) -> float:
    mapped_opacity = lookup_style_setting(opacity_map or {}, field, value)
    if mapped_opacity is not None:
        return float(mapped_opacity)
    return ISO_OPACITY


def parse_iso_specs(
    text: str,
    available_fields: tuple[str, ...],
    color_map: dict[str, str] | None = None,
    opacity_map: dict[str, float] | None = None,
    allow_empty: bool = False,
) -> tuple[IsoSpec, ...]:
    specs: list[IsoSpec] = []
    chunks = [part.strip() for part in text.replace(";", "\n").splitlines() if part.strip()]
    for chunk in chunks:
        if "=" not in chunk:
            raise ValueError(
                "NEK_ISO_SPECS entries must look like field=value[,value], "
                "for example: all=0 or u=0;w=+-0.01;v=+-0.02"
            )
        field_text, values_text = chunk.split("=", 1)
        fields = expand_field_names(field_text.strip(), available_fields)
        for raw_value in values_text.split(","):
            token = raw_value.strip().replace("−", "-")
            if token.startswith("+-"):
                values = [-abs(float(token[2:])), abs(float(token[2:]))]
            elif token.startswith("±"):
                values = [-abs(float(token[1:])), abs(float(token[1:]))]
            else:
                values = [float(token)]

            for field_name in fields:
                resolved_field, missing_reason = resolve_field_name(field_name, available_fields)
                if resolved_field is None:
                    message = f"unavailable iso field {field_name!r}: {missing_reason}"
                    if SKIP_MISSING_ISO:
                        log().warning(
                            f"Skipping {message}",
                            requested_field=field_name,
                            reason=missing_reason,
                            available_fields=list(available_fields),
                            renderable_fields=list(renderable_field_names(available_fields)),
                        )
                        continue
                    raise ValueError(message.capitalize())

                for value in values:
                    specs.append(
                        IsoSpec(
                            field=resolved_field,
                            value=value,
                            label=f"{resolved_field}_{value_label(value)}",
                            color=auto_iso_color(resolved_field, value, color_map),
                            opacity=iso_opacity(resolved_field, value, opacity_map),
                        )
                    )

    if not specs and not allow_empty:
        message = "NEK_ISO_SPECS produced no renderable isosurfaces"
        if SKIP_MISSING_ISO:
            log().warning(
                message,
                available_fields=list(available_fields),
                renderable_fields=list(renderable_field_names(available_fields)),
            )
            return ()
        raise ValueError(message)
    return tuple(specs)


def group_iso_specs(specs: tuple[IsoSpec, ...]):
    grouped = defaultdict(list)
    for spec in specs:
        grouped[spec.field].append(spec)
    return grouped


def unique_iso_specs(spec_groups) -> tuple[IsoSpec, ...]:
    unique = {}
    for specs in spec_groups:
        for spec in specs:
            unique.setdefault((spec.field, spec.value), spec)
    return tuple(unique.values())


def iso_summary(specs: tuple[IsoSpec, ...]) -> str:
    grouped = defaultdict(list)
    for spec in specs:
        grouped[spec.field].append(spec.value)
    parts = []
    for field_name in sorted(grouped):
        values = ",".join(f"{value:g}" for value in sorted(grouped[field_name]))
        parts.append(f"{field_name}={values}")
    return "; ".join(parts)


def infer_case_label(path: Path) -> str:
    if CASE_LABEL_OVERRIDE != "auto":
        return clean_label(CASE_LABEL_OVERRIDE)

    re_part = path.parent.name
    case_part = path.parent.parent.name if path.parent.parent != path.parent else "case"
    if re_part.isdigit():
        return clean_label(f"{case_part}_Re_{re_part}")
    return clean_label(f"{case_part}_{re_part}")


def infer_object_name(path: Path) -> str:
    if BODY_OBJECT != "auto":
        return BODY_OBJECT

    joined = "_".join(part.lower() for part in path.parts)
    if "cube" in joined:
        return "cube"
    if "sphere" in joined:
        return "sphere"
    raise ValueError("Could not infer object; set NEK_OBJECT=cube or NEK_OBJECT=sphere")


def make_render_case(path: Path) -> RenderCase:
    if not path.exists():
        raise FileNotFoundError(path)
    return RenderCase(
        field_path=path,
        output_dir=OUT_ROOT / infer_case_label(path),
        file_label=clean_label(path.name.replace(".", "_")),
        object_name=infer_object_name(path),
    )


def scalar_values(elem, field_name: str):
    field_name = canonical_field_name(field_name)
    if field_name == "temp0":
        field_name = "temp"
    if field_name == "temp" and elem.temp.shape[0] == 0:
        raise ValueError("temperature field requested, but this element has no temperature data")
    if field_name in {"u", "v", "w"}:
        return elem.vel[{"u": 0, "v": 1, "w": 2}[field_name]]
    if field_name in {"p", "pressure"}:
        return elem.pres[0]
    if field_name in {"t", "temp", "temperature"}:
        return elem.temp[0]
    if field_name.startswith("temp"):
        return elem.temp[int(field_name[4:])]
    if field_name.startswith("scal"):
        return elem.scal[int(field_name[4:])]
    if field_name.startswith("s") and field_name[1:].isdigit():
        return elem.scal[int(field_name[1:])]
    if field_name in {"speed", "velocity_magnitude", "mag"}:
        return np.sqrt(elem.vel[0] ** 2 + elem.vel[1] ** 2 + elem.vel[2] ** 2)
    raise ValueError(f"unsupported field {field_name!r}")


def structured_grid_from_elem(elem, scalars, field_name: str):
    grid = pv.StructuredGrid(elem.pos[0], elem.pos[1], elem.pos[2])
    grid.point_data[field_name] = scalars.ravel(order="F")
    return grid


def append_polydata(pieces):
    append = vtk.vtkAppendPolyData()
    for piece in pieces:
        if piece.n_points > 0:
            append.AddInputData(piece)
    append.Update()
    return pv.wrap(append.GetOutput())


def postprocess_surface(surface, scene: SceneSpec):
    if SURFACE_CLEAN and surface.n_points > 0:
        surface = surface.clean(
            point_merging=True,
            tolerance=SURFACE_CLEAN_TOLERANCE,
            absolute=True,
        )

    if scene.surface_smooth_iterations > 0 and surface.n_points > 0:
        if scene.surface_smooth_method == "taubin":
            surface = surface.smooth_taubin(
                n_iter=scene.surface_smooth_iterations,
                pass_band=scene.surface_taubin_pass_band,
                edge_angle=scene.surface_smooth_edge_angle,
                feature_angle=scene.surface_smooth_feature_angle,
                boundary_smoothing=scene.surface_smooth_boundary,
                feature_smoothing=scene.surface_smooth_feature,
            )
        elif scene.surface_smooth_method == "laplacian":
            surface = surface.smooth(
                n_iter=scene.surface_smooth_iterations,
                relaxation_factor=scene.surface_smooth_relaxation,
                edge_angle=scene.surface_smooth_edge_angle,
                feature_angle=scene.surface_smooth_feature_angle,
                boundary_smoothing=scene.surface_smooth_boundary,
                feature_smoothing=scene.surface_smooth_feature,
            )

    if CONTOUR_COMPUTE_NORMALS and surface.n_points > 0:
        surface = surface.compute_normals(
            point_normals=True,
            cell_normals=True,
            split_vertices=False,
            consistent_normals=True,
        )

    return surface


def elem_intersects_roi(elem, bounds) -> bool:
    if bounds is None:
        return True

    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    exmin = float(np.nanmin(elem.pos[0]))
    exmax = float(np.nanmax(elem.pos[0]))
    eymin = float(np.nanmin(elem.pos[1]))
    eymax = float(np.nanmax(elem.pos[1]))
    ezmin = float(np.nanmin(elem.pos[2]))
    ezmax = float(np.nanmax(elem.pos[2]))
    return not (
        exmax < xmin
        or exmin > xmax
        or eymax < ymin
        or eymin > ymax
        or ezmax < zmin
        or ezmin > zmax
    )


def extract_isosurfaces_for_field(field, specs: list[IsoSpec], scene: SceneSpec):
    field_name = specs[0].field
    bounds = scene.roi_bounds
    pieces_by_spec = {spec: [] for spec in specs}
    candidates_by_spec = {spec: 0 for spec in specs}
    roi_elements = 0

    for elem in field.elem:
        if not elem_intersects_roi(elem, bounds):
            continue
        roi_elements += 1

        values = scalar_values(elem, field_name)
        vmin = float(np.nanmin(values))
        vmax = float(np.nanmax(values))
        active_specs = [spec for spec in specs if vmin <= spec.value <= vmax]
        if not active_specs:
            continue

        grid = structured_grid_from_elem(elem, values, field_name)
        for spec in active_specs:
            candidates_by_spec[spec] += 1
            piece = grid.contour(
                isosurfaces=[spec.value],
                scalars=field_name,
                compute_normals=CONTOUR_COMPUTE_NORMALS,
                compute_gradients=CONTOUR_COMPUTE_GRADIENTS,
                compute_scalars=CONTOUR_COMPUTE_SCALARS,
                method=CONTOUR_METHOD,
            )
            if piece.n_points > 0:
                pieces_by_spec[spec].append(piece)

    surfaces = {}
    stats = {}
    for spec in specs:
        pieces = pieces_by_spec[spec]
        if not pieces:
            message = f"No {spec.field}={spec.value:g} isosurface pieces found"
            if SKIP_MISSING_ISO:
                log().warning(message, field=spec.field, value=spec.value)
                stats[spec] = {
                    "field": spec.field,
                    "value": spec.value,
                    "label": spec.label,
                    "candidates": candidates_by_spec[spec],
                    "roi_elements": roi_elements,
                    "points": 0,
                    "cells": 0,
                    "skipped": True,
                }
                continue
            raise RuntimeError(message)

        raw_surface = append_polydata(pieces)
        surface = postprocess_surface(raw_surface, scene)
        surfaces[spec] = surface
        stats[spec] = {
            "field": spec.field,
            "value": spec.value,
            "label": spec.label,
            "candidates": candidates_by_spec[spec],
            "roi_elements": roi_elements,
            "raw_points": int(raw_surface.n_points),
            "raw_cells": int(raw_surface.n_cells),
            "points": int(surface.n_points),
            "cells": int(surface.n_cells),
            "skipped": False,
            "contour_method": CONTOUR_METHOD,
            "compute_normals": CONTOUR_COMPUTE_NORMALS,
            "surface_clean": SURFACE_CLEAN,
            "surface_clean_tolerance": SURFACE_CLEAN_TOLERANCE,
            "surface_smooth_method": scene.surface_smooth_method,
            "surface_smooth_iterations": scene.surface_smooth_iterations,
            "surface_smooth_relaxation": scene.surface_smooth_relaxation,
            "surface_taubin_pass_band": scene.surface_taubin_pass_band,
            "surface_smooth_edge_angle": scene.surface_smooth_edge_angle,
            "surface_smooth_feature_angle": scene.surface_smooth_feature_angle,
            "surface_smooth_boundary": scene.surface_smooth_boundary,
            "surface_smooth_feature": scene.surface_smooth_feature,
        }
        log().info(
            (
                f"Extracted {spec.field}={spec.value:g}: "
                f"{candidates_by_spec[spec]} candidate elements from {roi_elements} ROI elements, "
                f"{surface.n_points} points, {surface.n_cells} cells"
            ),
            field=spec.field,
            value=spec.value,
            candidates=candidates_by_spec[spec],
            roi_elements=roi_elements,
            raw_points=int(raw_surface.n_points),
            raw_cells=int(raw_surface.n_cells),
            points=int(surface.n_points),
            cells=int(surface.n_cells),
            contour_method=CONTOUR_METHOD,
            surface_clean=SURFACE_CLEAN,
            surface_smooth_method=scene.surface_smooth_method,
            surface_smooth_iterations=scene.surface_smooth_iterations,
            surface_taubin_pass_band=scene.surface_taubin_pass_band,
        )

    return surfaces, stats


def make_body_mesh(object_name: str):
    cx, cy, cz = BODY_CENTER
    radius = BODY_DIAMETER / 2.0
    if object_name == "cube":
        return pv.Cube(
            bounds=(cx - radius, cx + radius, cy - radius, cy + radius, cz - radius, cz + radius)
        ).triangulate()
    if object_name == "sphere":
        return pv.Sphere(radius=radius, center=BODY_CENTER, theta_resolution=96, phi_resolution=48)
    raise ValueError("NEK_OBJECT must be cube, sphere, or auto")


def set_view(plotter, view_spec, zoom: float) -> None:
    mode = view_spec[0]
    if mode == "axis":
        view_name = view_spec[1]
        if view_name == "xy":
            plotter.view_xy()
        elif view_name == "xz":
            plotter.view_xz()
        elif view_name == "yz":
            plotter.view_yz()
        elif view_name == "iso":
            plotter.view_isometric()
        else:
            raise ValueError(f"unknown axis view: {view_name}")
    elif mode == "direction":
        direction = np.asarray(view_spec[1], dtype=float)
        viewup = tuple(float(x) for x in view_spec[2])
        direction /= np.linalg.norm(direction)
        xmin, xmax, ymin, ymax, zmin, zmax = plotter.bounds
        center = np.array([0.5 * (xmin + xmax), 0.5 * (ymin + ymax), 0.5 * (zmin + zmax)])
        span = np.linalg.norm([xmax - xmin, ymax - ymin, zmax - zmin])
        distance = max(span, BODY_DIAMETER) * 1.8
        plotter.camera_position = [tuple(center + direction * distance), tuple(center), viewup]
    elif mode == "camera":
        camera = view_spec[1]
        plotter.camera_position = [
            tuple(camera["position"]),
            tuple(camera["focal_point"]),
            tuple(camera["view_up"]),
        ]
        if "parallel_projection" in camera:
            plotter.camera.parallel_projection = bool(camera["parallel_projection"])
        if "parallel_scale" in camera:
            plotter.camera.parallel_scale = float(camera["parallel_scale"])
        if "view_angle" in camera:
            plotter.camera.view_angle = float(camera["view_angle"])
        if "zoom" in camera:
            plotter.camera.zoom(float(camera["zoom"]))
        if camera.get("apply_scene_zoom", False):
            plotter.camera.zoom(zoom)
        return
    else:
        raise ValueError(f"unknown view mode: {mode}")
    plotter.camera.zoom(zoom)


def save_image(image: Image.Image, output: Path) -> None:
    save_kwargs = {}
    if IMAGE_FORMAT in {"jpeg", "webp"}:
        save_kwargs["quality"] = IMAGE_QUALITY
        save_kwargs["optimize"] = True
    elif IMAGE_FORMAT == "png":
        save_kwargs["compress_level"] = PNG_COMPRESS_LEVEL
    image.save(output, format=IMAGE_FORMAT.upper(), **save_kwargs)


def image_for_resolution(source_image: Image.Image, resolution: RenderResolution) -> Image.Image:
    target_size = (resolution.width * resolution.scale, resolution.height * resolution.scale)
    if source_image.size == target_size:
        return source_image
    return source_image.resize(target_size, Image.Resampling.LANCZOS)


def output_dir_for_resolution(case: RenderCase, scene: SceneSpec, resolution: RenderResolution) -> Path:
    base_dir = case.output_dir / scene.name if scene.use_scene_subdir else case.output_dir
    if resolution.use_subdir:
        return base_dir / resolution.label
    return base_dir


def output_name_for_resolution(
    case: RenderCase,
    scene: SceneSpec,
    image_label: str,
    view_label: str,
    resolution: RenderResolution,
    resolution_set: tuple[RenderResolution, ...],
    extension: str,
) -> str:
    stem_parts = [case.file_label]
    if scene.name != "default" and not scene.use_scene_subdir:
        stem_parts.append(scene.name)
    stem_parts.extend([clean_label(image_label), view_label])

    low_resolution_count = sum(not item.use_subdir for item in resolution_set)
    if not resolution.use_subdir and low_resolution_count > 1:
        stem_parts.append(resolution.label)

    return f"{'_'.join(stem_parts)}.{extension}"


def clean_snapshot_outputs(case: RenderCase) -> None:
    if not CLEAN_SNAPSHOT_OUTPUT or not case.output_dir.exists():
        return

    removed_paths = []
    removed_bytes = 0
    for path in sorted(case.output_dir.rglob("*")):
        if not path.is_file():
            continue
        if not path.name.startswith(f"{case.file_label}_"):
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        size = path.stat().st_size
        path.unlink()
        removed_paths.append(str(path.relative_to(case.output_dir)))
        removed_bytes += size

    pruned_dirs = []
    for path in sorted(case.output_dir.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                continue
            pruned_dirs.append(str(path.relative_to(case.output_dir)))

    if removed_paths or pruned_dirs:
        log().info(
            "Cleaned previous snapshot images",
            removed_files=len(removed_paths),
            removed_bytes=removed_bytes,
            pruned_dirs=pruned_dirs,
            sample_removed=removed_paths[:25],
        )


def iso_spec_record(spec: IsoSpec) -> dict:
    return {
        "field": spec.field,
        "value": spec.value,
        "label": spec.label,
        "color": spec.color,
        "opacity": spec.opacity,
    }


def resolution_record(resolution: RenderResolution) -> dict:
    return {
        "label": resolution.label,
        "width": resolution.width,
        "height": resolution.height,
        "scale": resolution.scale,
        "output_width": resolution.width * resolution.scale,
        "output_height": resolution.height * resolution.scale,
        "uses_resolution_subdir": resolution.use_subdir,
    }


def camera_record(view_spec) -> dict:
    mode = view_spec[0]
    if mode != "camera":
        return {"mode": mode}
    camera = view_spec[1]
    return {
        "mode": "camera",
        "position": list(camera["position"]),
        "focal_point": list(camera["focal_point"]),
        "view_up": list(camera["view_up"]),
        **{
            key: camera[key]
            for key in ("parallel_projection", "parallel_scale", "view_angle", "zoom", "apply_scene_zoom")
            if key in camera
        },
    }


def composition_record(composition: CompositionSpec, specs: tuple[IsoSpec, ...], scene: SceneSpec) -> dict:
    resolutions = composition.resolutions or scene.resolutions
    return {
        "name": composition.name,
        "iso_specs_text": composition.iso_specs_text,
        "views": list(composition.view_names or scene.view_names),
        "resolutions": [resolution_record(resolution) for resolution in resolutions],
        "iso_specs": [iso_spec_record(spec) for spec in specs],
    }


def validate_view_names(view_names: tuple[str, ...], context: str) -> None:
    for view_label in view_names:
        if view_label not in VIEWS:
            raise ValueError(f"unknown view {view_label!r} in {context}; choose from {sorted(VIEWS)}")


def render_view(
    layers: tuple[tuple[IsoSpec, object], ...],
    body,
    case: RenderCase,
    scene: SceneSpec,
    image_label: str,
    title_label: str,
    view_label: str,
    view_spec,
    resolution_set: tuple[RenderResolution, ...],
    snapshot_time: float,
    snapshot_istep: int,
    image_kind: str = "single_iso",
    composition_name: str | None = None,
) -> list[dict]:
    extension = "jpg" if IMAGE_FORMAT == "jpeg" else IMAGE_FORMAT
    image_records = []
    primary_spec = layers[0][0]
    layer_records = [
        {
            "field": spec.field,
            "value": spec.value,
            "label": spec.label,
            "color": spec.color,
            "opacity": spec.opacity,
            "points": int(surface.n_points),
            "cells": int(surface.n_cells),
        }
        for spec, surface in layers
    ]

    for aspect_group in group_resolutions_by_aspect(resolution_set):
        render_resolution = max(
            aspect_group,
            key=lambda item: item.width * item.scale * item.height * item.scale,
        )
        with log().timed(
            "render_view",
            scene=scene.name,
            image=image_label,
            view=view_label,
            render_resolution=render_resolution.label,
            layers=len(layers),
            image_kind=image_kind,
        ):
            plotter = pv.Plotter(
                off_screen=True,
                border=False,
                window_size=(render_resolution.width, render_resolution.height),
            )
            plotter.set_background("white")
            if ANTI_ALIASING not in {"", "0", "false", "none"}:
                anti_aliasing_kwargs = {}
                if ANTI_ALIASING == "msaa":
                    anti_aliasing_kwargs["multi_samples"] = ANTI_ALIASING_SAMPLES
                plotter.enable_anti_aliasing(ANTI_ALIASING, **anti_aliasing_kwargs)
            if DEPTH_PEELING:
                try:
                    plotter.enable_depth_peeling(
                        number_of_peels=DEPTH_PEELS, occlusion_ratio=0.0
                    )
                except Exception:
                    pass
            if SSAO:
                try:
                    plotter.enable_ssao()
                except Exception:
                    pass
            if ENVIRONMENT_TEXTURE:
                try:
                    plotter.set_environment_texture(pv.read_texture(ENVIRONMENT_TEXTURE))
                except Exception:
                    pass
            iso_pbr_kwargs = (
                dict(pbr=True, metallic=ISO_METALLIC, roughness=ISO_ROUGHNESS)
                if ISO_PBR else {}
            )
            for spec, surface in layers:
                plotter.add_mesh(
                    surface,
                    color=spec.color,
                    opacity=spec.opacity,
                    smooth_shading=ISO_SMOOTH_SHADING,
                    split_sharp_edges=ISO_SPLIT_SHARP_EDGES,
                    lighting=ISO_LIGHTING,
                    ambient=ISO_AMBIENT,
                    diffuse=ISO_DIFFUSE,
                    specular=ISO_SPECULAR,
                    specular_power=ISO_SPECULAR_POWER,
                    **iso_pbr_kwargs,
                )
            plotter.add_mesh(
                body,
                color=BODY_COLOR,
                show_edges=False,
                edge_color="white",
                line_width=0.9,
                smooth_shading=(case.object_name == "sphere"),
                lighting=BODY_LIGHTING,
                ambient=BODY_AMBIENT,
                diffuse=BODY_DIFFUSE,
                specular=BODY_SPECULAR,
                specular_power=BODY_SPECULAR_POWER,
            )
            if CENTERLINE:
                _cx0, _cx1 = (float(v) for v in CENTERLINE.split(","))
                plotter.add_mesh(
                    pv.Line((_cx0, 0.0, 0.0), (_cx1, 0.0, 0.0)),
                    color=CENTERLINE_COLOR,
                    line_width=CENTERLINE_WIDTH,
                    lighting=False,
                )
            if ANNOTATION:
                plotter.add_text(
                    (
                        f"{case.field_path.name}: t={snapshot_time:.6g}, step={snapshot_istep}\n"
                        f"{scene.name}: {title_label}, {view_label}"
                    ),
                    position="upper_left",
                    font_size=12,
                    color="black",
                )
            if scene.show_bounds:
                plotter.show_bounds(
                    grid="front",
                    location="outer",
                    ticks="outside",
                    xtitle="x",
                    ytitle="y",
                    ztitle="z",
                    font_size=8,
                )
            set_view(plotter, view_spec, scene.camera_zoom)
            image_array = plotter.screenshot(return_img=True, scale=render_resolution.scale)
            plotter.close()
            source_image = Image.fromarray(image_array).convert("RGB")

        for resolution in aspect_group:
            output_dir = output_dir_for_resolution(case, scene, resolution)
            output_dir.mkdir(parents=True, exist_ok=True)
            output = output_dir / output_name_for_resolution(
                case,
                scene,
                image_label,
                view_label,
                resolution,
                resolution_set,
                extension,
            )
            with log().timed(
                "save_image",
                scene=scene.name,
                image=image_label,
                view=view_label,
                resolution=resolution.label,
                layers=len(layers),
                image_kind=image_kind,
            ):
                save_image(image_for_resolution(source_image, resolution), output)
            if not output.exists() or output.stat().st_size == 0:
                raise RuntimeError(f"failed to write {output}")
            record = {
                "path": str(output),
                "path_relative_to_output_root": str(output.relative_to(OUT_ROOT)),
                "bytes": output.stat().st_size,
                "image_format": "jpg" if IMAGE_FORMAT == "jpeg" else IMAGE_FORMAT,
                "resolution": resolution.label,
                "width": resolution.width * resolution.scale,
                "height": resolution.height * resolution.scale,
                "rendered_from_resolution": render_resolution.label,
                "view": view_label,
                "scene": scene.name,
                "image_kind": image_kind,
                "composition_name": composition_name,
                "time": snapshot_time,
                "istep": snapshot_istep,
                "field": primary_spec.field,
                "value": primary_spec.value,
                "iso_label": image_label,
                "iso_color": primary_spec.color,
                "iso_opacity": primary_spec.opacity,
                "layers": layer_records,
            }
            image_records.append(record)
            log().info(f"Wrote {output} ({output.stat().st_size} bytes)", **record)

    return image_records


def render_case(case: RenderCase, scenes: tuple[SceneSpec, ...]) -> None:
    global LOGGER

    case.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = case.output_dir / f"{case.file_label}_render.log"
    events_path = case.output_dir / f"{case.file_label}_render_events.jsonl"
    LOGGER = RunLogger(log_path, events_path)
    source_stat = case.field_path.stat()

    try:
        log().info(
            "Render job started",
            source_file=str(case.field_path),
            output_dir=str(case.output_dir),
            log_path=str(log_path),
            events_path=str(events_path),
        )
        log().info(
            "Configuration",
            image_format=IMAGE_FORMAT,
            quality=IMAGE_QUALITY,
            png_compress_level=PNG_COMPRESS_LEVEL,
            high_res_subdir_min_width=HIGH_RES_SUBDIR_MIN_WIDTH,
            high_res_subdir_min_height=HIGH_RES_SUBDIR_MIN_HEIGHT,
            scene_subdirs=SCENE_SUBDIRS,
            clean_snapshot_output=CLEAN_SNAPSHOT_OUTPUT,
            anti_aliasing=ANTI_ALIASING or None,
            anti_aliasing_samples=ANTI_ALIASING_SAMPLES if ANTI_ALIASING == "msaa" else None,
            contour_method=CONTOUR_METHOD,
            contour_compute_normals=CONTOUR_COMPUTE_NORMALS,
            contour_compute_gradients=CONTOUR_COMPUTE_GRADIENTS,
            contour_compute_scalars=CONTOUR_COMPUTE_SCALARS,
            skip_missing_iso=SKIP_MISSING_ISO,
            surface_clean=SURFACE_CLEAN,
            surface_clean_tolerance=SURFACE_CLEAN_TOLERANCE,
            default_surface_smooth_method=SURFACE_SMOOTH_METHOD,
            surface_smooth_iterations=SURFACE_SMOOTH_ITERATIONS,
            surface_smooth_relaxation=SURFACE_SMOOTH_RELAXATION,
            surface_taubin_pass_band=SURFACE_TAUBIN_PASS_BAND,
            surface_smooth_edge_angle=SURFACE_SMOOTH_EDGE_ANGLE,
            surface_smooth_feature_angle=SURFACE_SMOOTH_FEATURE_ANGLE,
            iso_smooth_shading=ISO_SMOOTH_SHADING,
            iso_split_sharp_edges=ISO_SPLIT_SHARP_EDGES,
            iso_lighting=ISO_LIGHTING,
            iso_ambient=ISO_AMBIENT,
            iso_diffuse=ISO_DIFFUSE,
            iso_specular=ISO_SPECULAR,
            iso_specular_power=ISO_SPECULAR_POWER,
            default_iso_opacity=ISO_OPACITY,
            body_object=case.object_name,
            body_diameter=BODY_DIAMETER,
            body_center=BODY_CENTER,
            render_config=RENDER_CONFIG or None,
            camera_file=CAMERA_FILE or None,
            registered_camera_views=sorted(REGISTERED_CAMERA_VIEWS),
        )
        clean_snapshot_outputs(case)

        with log().timed("read_nek", source_file=str(case.field_path), bytes=source_stat.st_size):
            field = readnek(case.field_path)
        available_fields = available_field_names(field)
        renderable_fields = renderable_field_names(available_fields)
        log().info(
            "Loaded Nek snapshot",
            nel=int(field.nel),
            lr1=list(field.lr1),
            time=float(field.time),
            istep=int(field.istep),
            vars=list(field.var),
            available_fields=list(available_fields),
            renderable_fields=list(renderable_fields),
        )

        with log().timed("build_body_mesh", object=case.object_name):
            body = make_body_mesh(case.object_name)

        snapshot_time = float(field.time)
        snapshot_istep = int(field.istep)
        manifest = {
            "source_file": str(case.field_path),
            "source_file_size_bytes": source_stat.st_size,
            "source_file_mtime": source_stat.st_mtime,
            "case_output_dir": str(case.output_dir),
            "file_label": case.file_label,
            "object_name": case.object_name,
            "body_diameter": BODY_DIAMETER,
            "body_center": list(BODY_CENTER),
            "nek_time": snapshot_time,
            "nek_istep": snapshot_istep,
            "nel": int(field.nel),
            "lr1": list(field.lr1),
            "vars": list(field.var),
            "available_fields": list(available_fields),
            "renderable_fields": list(renderable_fields),
            "image_format": "jpg" if IMAGE_FORMAT == "jpeg" else IMAGE_FORMAT,
            "render_config": RENDER_CONFIG or None,
            "camera_file": CAMERA_FILE or None,
            "registered_camera_views": {
                name: camera_record(view_spec)
                for name, view_spec in sorted(REGISTERED_CAMERA_VIEWS.items())
            },
            "render_quality": {
                "anti_aliasing": ANTI_ALIASING or None,
                "anti_aliasing_samples": ANTI_ALIASING_SAMPLES if ANTI_ALIASING == "msaa" else None,
                "contour_method": CONTOUR_METHOD,
                "contour_compute_normals": CONTOUR_COMPUTE_NORMALS,
                "contour_compute_gradients": CONTOUR_COMPUTE_GRADIENTS,
                "contour_compute_scalars": CONTOUR_COMPUTE_SCALARS,
                "skip_missing_iso": SKIP_MISSING_ISO,
                "surface_clean": SURFACE_CLEAN,
                "surface_clean_tolerance": SURFACE_CLEAN_TOLERANCE,
                "default_surface_smooth_method": SURFACE_SMOOTH_METHOD,
                "surface_smooth_iterations": SURFACE_SMOOTH_ITERATIONS,
                "surface_smooth_relaxation": SURFACE_SMOOTH_RELAXATION,
                "surface_taubin_pass_band": SURFACE_TAUBIN_PASS_BAND,
                "surface_smooth_edge_angle": SURFACE_SMOOTH_EDGE_ANGLE,
                "surface_smooth_feature_angle": SURFACE_SMOOTH_FEATURE_ANGLE,
                "surface_smooth_boundary": SURFACE_SMOOTH_BOUNDARY,
                "surface_smooth_feature": SURFACE_SMOOTH_FEATURE,
                "iso_smooth_shading": ISO_SMOOTH_SHADING,
                "iso_split_sharp_edges": ISO_SPLIT_SHARP_EDGES,
                "iso_lighting": ISO_LIGHTING,
                "iso_ambient": ISO_AMBIENT,
                "iso_diffuse": ISO_DIFFUSE,
                "iso_specular": ISO_SPECULAR,
                "iso_specular_power": ISO_SPECULAR_POWER,
                "default_iso_opacity": ISO_OPACITY,
            },
            "log_path": str(log_path),
            "events_path": str(events_path),
            "scenes": [],
            "isocontours": [],
            "images": [],
            "timings": [],
        }

        for scene in scenes:
            with log().timed("scene_total", scene=scene.name):
                scene_specs = parse_iso_specs(
                    scene.iso_specs_text,
                    available_fields,
                    scene.iso_colors,
                    scene.iso_opacities,
                    allow_empty=bool(scene.compositions),
                )
                composition_specs = [
                    (
                        composition,
                        parse_iso_specs(
                            composition.iso_specs_text,
                            available_fields,
                            scene.iso_colors,
                            scene.iso_opacities,
                        ),
                    )
                    for composition in scene.compositions
                ]
                all_specs = unique_iso_specs(
                    [scene_specs] + [specs for _, specs in composition_specs]
                )
                if not all_specs:
                    log().warning(
                        "Skipping scene because no requested fields are renderable",
                        scene=scene.name,
                        available_fields=list(available_fields),
                        renderable_fields=list(renderable_fields),
                        iso_specs=scene.iso_specs_text,
                        compositions=[
                            composition_record(composition, specs, scene)
                            for composition, specs in composition_specs
                        ],
                    )
                    manifest["scenes"].append(
                        {
                            "name": scene.name,
                            "skipped": True,
                            "skip_reason": "no requested fields are renderable",
                            "roi_bounds": None if scene.roi_bounds is None else list(scene.roi_bounds),
                            "camera_zoom": scene.camera_zoom,
                            "show_bounds": scene.show_bounds,
                            "surface_smoothing": {
                                "method": scene.surface_smooth_method,
                                "iterations": scene.surface_smooth_iterations,
                                "relaxation": scene.surface_smooth_relaxation,
                                "taubin_pass_band": scene.surface_taubin_pass_band,
                                "edge_angle": scene.surface_smooth_edge_angle,
                                "feature_angle": scene.surface_smooth_feature_angle,
                                "boundary_smoothing": scene.surface_smooth_boundary,
                                "feature_smoothing": scene.surface_smooth_feature,
                            },
                            "views": list(scene.view_names),
                            "resolutions": [resolution_record(resolution) for resolution in scene.resolutions],
                            "iso_specs_text": scene.iso_specs_text,
                            "iso_colors": scene.iso_colors,
                            "iso_opacities": scene.iso_opacities,
                            "iso_specs": [iso_spec_record(spec) for spec in scene_specs],
                            "extracted_iso_specs": [],
                            "compositions": [
                                composition_record(composition, specs, scene)
                                for composition, specs in composition_specs
                            ],
                        }
                    )
                    continue
                validate_view_names(scene.view_names, f"scene {scene.name}")
                for composition, _ in composition_specs:
                    validate_view_names(
                        composition.view_names or scene.view_names,
                        f"composition {composition.name} in scene {scene.name}",
                    )
                log().info(
                    "Scene configuration",
                    scene=scene.name,
                    iso_specs=scene.iso_specs_text,
                    expanded_iso_specs=[iso_spec_record(spec) for spec in scene_specs],
                    all_extracted_iso_specs=[iso_spec_record(spec) for spec in all_specs],
                    compositions=[
                        composition_record(composition, specs, scene)
                        for composition, specs in composition_specs
                    ],
                    views=list(scene.view_names),
                    resolutions=[resolution.label for resolution in scene.resolutions],
                    roi_bounds=None if scene.roi_bounds is None else list(scene.roi_bounds),
                    surface_smooth_method=scene.surface_smooth_method,
                    surface_smooth_iterations=scene.surface_smooth_iterations,
                    surface_smooth_relaxation=scene.surface_smooth_relaxation,
                    surface_taubin_pass_band=scene.surface_taubin_pass_band,
                    iso_colors=scene.iso_colors,
                    iso_opacities=scene.iso_opacities,
                )
                manifest["scenes"].append(
                    {
                        "name": scene.name,
                        "roi_bounds": None if scene.roi_bounds is None else list(scene.roi_bounds),
                        "camera_zoom": scene.camera_zoom,
                        "show_bounds": scene.show_bounds,
                        "surface_smoothing": {
                            "method": scene.surface_smooth_method,
                            "iterations": scene.surface_smooth_iterations,
                            "relaxation": scene.surface_smooth_relaxation,
                            "taubin_pass_band": scene.surface_taubin_pass_band,
                            "edge_angle": scene.surface_smooth_edge_angle,
                            "feature_angle": scene.surface_smooth_feature_angle,
                            "boundary_smoothing": scene.surface_smooth_boundary,
                            "feature_smoothing": scene.surface_smooth_feature,
                        },
                        "views": list(scene.view_names),
                        "resolutions": [resolution_record(resolution) for resolution in scene.resolutions],
                        "iso_specs_text": scene.iso_specs_text,
                        "iso_colors": scene.iso_colors,
                        "iso_opacities": scene.iso_opacities,
                        "iso_specs": [iso_spec_record(spec) for spec in scene_specs],
                        "extracted_iso_specs": [iso_spec_record(spec) for spec in all_specs],
                        "compositions": [
                            composition_record(composition, specs, scene)
                            for composition, specs in composition_specs
                        ],
                    }
                )

                surfaces_by_key = {}
                for field_name, specs_for_field in group_iso_specs(all_specs).items():
                    with log().timed(
                        "extract_field_isosurfaces",
                        scene=scene.name,
                        field=field_name,
                        n_values=len(specs_for_field),
                    ):
                        surfaces, contour_stats = extract_isosurfaces_for_field(
                            field,
                            specs_for_field,
                            scene,
                        )
                    for spec in specs_for_field:
                        contour_record = dict(contour_stats[spec])
                        contour_record["scene"] = scene.name
                        manifest["isocontours"].append(contour_record)
                    for spec, surface in surfaces.items():
                        surfaces_by_key[(spec.field, spec.value)] = surface

                for spec in scene_specs:
                    surface = surfaces_by_key.get((spec.field, spec.value))
                    if surface is None:
                        continue
                    for view_label in scene.view_names:
                        manifest["images"].extend(
                            render_view(
                                ((spec, surface),),
                                body,
                                case,
                                scene,
                                spec.label,
                                f"{spec.field}={spec.value:g}",
                                view_label,
                                VIEWS[view_label],
                                scene.resolutions,
                                snapshot_time,
                                snapshot_istep,
                            )
                        )

                for composition, specs in composition_specs:
                    if not specs:
                        log().warning(
                            "Skipping composition because it has no renderable layers",
                            scene=scene.name,
                            composition=composition.name,
                        )
                        continue
                    missing_specs = [
                        spec
                        for spec in specs
                        if (spec.field, spec.value) not in surfaces_by_key
                    ]
                    if missing_specs:
                        log().warning(
                            "Skipping composition because one or more layers were not extracted",
                            scene=scene.name,
                            composition=composition.name,
                            missing=[iso_spec_record(spec) for spec in missing_specs],
                        )
                        continue

                    layers = tuple(
                        (spec, surfaces_by_key[(spec.field, spec.value)])
                        for spec in specs
                    )
                    composition_views = composition.view_names or scene.view_names
                    composition_resolutions = composition.resolutions or scene.resolutions
                    for view_label in composition_views:
                        manifest["images"].extend(
                            render_view(
                                layers,
                                body,
                                case,
                                scene,
                                composition.name,
                                iso_summary(specs),
                                view_label,
                                VIEWS[view_label],
                                composition_resolutions,
                                snapshot_time,
                                snapshot_istep,
                                image_kind="composition",
                                composition_name=composition.name,
                            )
                        )

        manifest["timings"] = log().timings
        manifest_path = case.output_dir / f"{case.file_label}_render_manifest.json"
        with log().timed("write_manifest", path=str(manifest_path)):
            with manifest_path.open("w", encoding="utf-8") as handle:
                json.dump(manifest, handle, indent=2)
                handle.write("\n")
        log().info(
            "Render job finished",
            images=len(manifest["images"]),
            contours=len(manifest["isocontours"]),
            manifest_path=str(manifest_path),
        )
    except Exception as exc:
        log().warning(
            "Render job failed",
            error=repr(exc),
            traceback=traceback.format_exc(),
        )
        raise
    finally:
        log().close()
        LOGGER = None


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: render_nek_isosurface_views.py /path/to/case0.f00001 [...]", file=sys.stderr)
        return 2

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    pv.OFF_SCREEN = True
    pv.global_theme.window_size = [parse_resolutions(RESOLUTION_PRESETS_TEXT)[0].width, parse_resolutions(RESOLUTION_PRESETS_TEXT)[0].height]
    pv.global_theme.font.family = "arial"

    if not RENDER_CONFIG:
        register_camera_views()
    scenes = load_scenes()
    for raw_path in argv:
        render_case(make_render_case(Path(raw_path)), scenes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
