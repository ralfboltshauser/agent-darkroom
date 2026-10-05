"""Find an unambiguous Lensfun camera/lens profile in the installed database."""

from __future__ import annotations

import ctypes as ct
import math
import os
import re
from ctypes.util import find_library
from dataclasses import dataclass
from pathlib import Path

from defusedxml import ElementTree

from chemigram.core.exif import ExifData


@dataclass(frozen=True)
class LensProfile:
    camera: str
    lens: str
    corrections: tuple[str, ...]
    database: str
    crop_factor: float


def _key(value: str) -> str:
    # EXIF commonly writes "F4.5" where Lensfun writes "f/4.5".
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _matches_model(exif_name: str, maker: str, model: str) -> bool:
    observed, brand, catalog = _key(exif_name), _key(maker), _key(model)
    return observed in {catalog, brand + catalog} or (
        bool(brand) and catalog.startswith(brand) and observed == catalog[len(brand) :]
    )


def _database_dirs() -> list[Path]:
    override = os.environ.get("CHEMIGRAM_LENSFUN_DB_DIR")
    if override:
        path = Path(override).expanduser()
        return [path] if path.is_dir() else []
    for path in (
        Path.home() / ".local/share/lensfun/updates/version_1",
        Path("/var/lib/lensfun-updates/version_1"),
        Path.home() / ".local/share/lensfun/version_1",
        Path("/usr/share/lensfun/version_1"),
        Path("/usr/local/share/lensfun/version_1"),
        Path("/opt/homebrew/share/lensfun/version_1"),
    ):
        if path.is_dir() and any(path.glob("*.xml")):
            return [path]
    return []


def find_lens_profile(exif: ExifData) -> LensProfile | None:
    """Return one compatible profile, or None when identity/DB is uncertain."""
    directories = _database_dirs()
    if not directories or not (exif.make and exif.model):
        return None
    cameras: list[tuple[str, str, float]] = []
    lenses: list[tuple[str, str, tuple[str, ...]]] = []
    for file in (file for directory in directories for file in sorted(directory.glob("*.xml"))):
        root = ElementTree.parse(file).getroot()
        for camera in root.findall("camera"):
            maker = camera.findtext("maker") or ""
            model = camera.findtext("model") or ""
            catalog_maker, observed_maker = _key(maker), _key(exif.make)
            maker_matches = catalog_maker == observed_maker or (
                min(len(catalog_maker), len(observed_maker)) >= 4
                and (
                    catalog_maker.startswith(observed_maker)
                    or observed_maker.startswith(catalog_maker)
                )
            )
            if maker_matches and _matches_model(exif.model, maker, model):
                mount = camera.findtext("mount") or ""
                cameras.append((model, mount, float(camera.findtext("cropfactor") or 1.0)))
        for lens in root.findall("lens"):
            model = lens.findtext("model") or ""
            maker = lens.findtext("maker") or ""
            if exif.lens_model and not _matches_model(exif.lens_model, maker, model):
                continue
            mounts = [m.text or "" for m in lens.findall("mount")]
            calibration = lens.find("calibration")
            corrections = tuple(
                name
                for name in ("distortion", "tca", "vignetting")
                if calibration is not None and calibration.find(name) is not None
            )
            for mount in mounts:
                lenses.append((model, mount, corrections))
    matches = {
        (camera_model, lens_model, corrections, crop)
        for camera_model, camera_mount, crop in cameras
        for lens_model, lens_mount, corrections in lenses
        if camera_mount == lens_mount
        and corrections
        and (exif.lens_model or camera_mount[:1].islower())
    }
    if len(matches) != 1:
        return None
    camera, lens, corrections, crop = matches.pop()
    return LensProfile(camera, lens, corrections, ", ".join(map(str, directories)), crop)


def lens_auto_scale(profile: LensProfile, exif: ExifData, raw_path: Path) -> float:
    """Use Lensfun's own geometry solver to crop away invalid corrected borders."""
    import rawpy

    library_name = find_library("lensfun")
    if library_name is None:
        raise RuntimeError("Lensfun shared library unavailable")
    lib = ct.CDLL(library_name)
    pointer = ct.c_void_p
    lib.lf_db_new.restype = pointer
    lib.lf_db_load.argtypes = [pointer]
    lib.lf_db_load.restype = ct.c_int
    lib.lf_db_find_cameras_ext.argtypes = [pointer, ct.c_char_p, ct.c_char_p, ct.c_int]
    lib.lf_db_find_cameras_ext.restype = ct.POINTER(pointer)
    lib.lf_db_find_lenses_hd.argtypes = [pointer, pointer, ct.c_char_p, ct.c_char_p, ct.c_int]
    lib.lf_db_find_lenses_hd.restype = ct.POINTER(pointer)
    lib.lf_modifier_new.argtypes = [pointer, ct.c_float, ct.c_int, ct.c_int]
    lib.lf_modifier_new.restype = pointer
    lib.lf_modifier_initialize.argtypes = [
        pointer,
        pointer,
        ct.c_int,
        ct.c_float,
        ct.c_float,
        ct.c_float,
        ct.c_float,
        ct.c_int,
        ct.c_int,
        ct.c_int,
    ]
    lib.lf_modifier_initialize.restype = ct.c_int
    lib.lf_modifier_get_auto_scale.argtypes = [pointer, ct.c_int]
    lib.lf_modifier_get_auto_scale.restype = ct.c_float
    lib.lf_modifier_destroy.argtypes = [pointer]
    lib.lf_db_destroy.argtypes = [pointer]

    with rawpy.imread(str(raw_path)) as raw:
        height, width = raw.raw_image_visible.shape
    distance = exif.focus_distance_m
    if distance is None or not math.isfinite(distance) or distance <= 0:
        distance = 1000.0
    db = lib.lf_db_new()
    if not db:
        raise RuntimeError("Lensfun database allocation failed")
    try:
        if lib.lf_db_load(db) != 0:
            raise RuntimeError("Lensfun database failed to load")
        cameras = lib.lf_db_find_cameras_ext(db, None, profile.camera.encode(), 0)
        if not cameras or not cameras[0]:
            raise RuntimeError("Lensfun could not resolve the matched camera")
        lenses = lib.lf_db_find_lenses_hd(db, cameras[0], None, profile.lens.encode(), 0)
        if not lenses or not lenses[0]:
            raise RuntimeError("Lensfun could not resolve the matched lens")
        modifier = lib.lf_modifier_new(lenses[0], profile.crop_factor, width, height)
        if not modifier:
            raise RuntimeError("Lensfun modifier allocation failed")
        try:
            flags = lib.lf_modifier_initialize(
                modifier,
                lenses[0],
                3,
                exif.focal_length_mm,
                exif.aperture,
                distance,
                1.0,
                1,
                0xFFFF,
                0,
            )
            if flags == 0:
                raise RuntimeError("Lensfun found no correction at this focal length")
            scale = float(lib.lf_modifier_get_auto_scale(modifier, 0))
            if not (0.5 <= scale <= 2.0):
                raise RuntimeError(f"Lensfun returned invalid auto scale {scale}")
            return max(1.0, scale * 1.005)
        finally:
            lib.lf_modifier_destroy(modifier)
    finally:
        lib.lf_db_destroy(db)
