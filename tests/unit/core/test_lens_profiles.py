from pathlib import Path

from chemigram.core.exif import ExifData
from chemigram.core.lens_profiles import find_lens_profile


def _database(tmp_path: Path, mount: str, lens_name: str) -> Path:
    directory = tmp_path / "lensfun"
    directory.mkdir()
    (directory / "sample.xml").write_text(
        f"""<lensdatabase version="1">
        <camera><maker>Sony</maker><model>ILCE-6700</model>
        <mount>{mount}</mount><cropfactor>1.534</cropfactor></camera>
        <lens><maker>Sony</maker><model>{lens_name}</model>
        <mount>{mount}</mount><cropfactor>1.534</cropfactor>
        <calibration><distortion model="poly3" focal="35" k1="0.01"/>
        <tca model="linear" focal="35" kr="1" kb="1"/></calibration></lens>
        </lensdatabase>""",
        encoding="utf-8",
    )
    return directory


def test_profile_matches_exif_aperture_spelling_and_mount(tmp_path: Path, monkeypatch) -> None:
    directory = _database(tmp_path, "Sony E", "E 70-350mm f/4.5-6.3 G OSS")
    monkeypatch.setenv("CHEMIGRAM_LENSFUN_DB_DIR", str(directory))
    exif = ExifData("SONY", "ILCE-6700", "E 70-350mm F4.5-6.3 G OSS", 350, 6.3)
    profile = find_lens_profile(exif)
    assert profile is not None
    assert profile.lens == "E 70-350mm f/4.5-6.3 G OSS"
    assert profile.corrections == ("distortion", "tca")
    assert profile.crop_factor == 1.534


def test_missing_lens_identity_only_uses_fixed_mount(tmp_path: Path, monkeypatch) -> None:
    directory = _database(tmp_path, "Sony E", "E 70-350mm f/4.5-6.3 G OSS")
    monkeypatch.setenv("CHEMIGRAM_LENSFUN_DB_DIR", str(directory))
    exif = ExifData("SONY", "ILCE-6700", "", 350, 6.3)
    assert find_lens_profile(exif) is None
    (directory / "sample.xml").write_text(
        (directory / "sample.xml").read_text().replace("Sony E", "sonyFixed")
    )
    assert find_lens_profile(exif) is not None


def test_common_camera_and_lens_maker_variants(tmp_path: Path, monkeypatch) -> None:
    directory = _database(tmp_path, "Nikon Z", "NIKKOR Z 24-70mm f/4 S")
    file = directory / "sample.xml"
    file.write_text(file.read_text().replace("Sony", "Nikon").replace("ILCE-6700", "Z 6II"))
    monkeypatch.setenv("CHEMIGRAM_LENSFUN_DB_DIR", str(directory))
    exif = ExifData("NIKON CORPORATION", "NIKON Z 6II", "Nikon NIKKOR Z 24-70mm F4 S", 50, 4.0)
    assert find_lens_profile(exif) is not None
