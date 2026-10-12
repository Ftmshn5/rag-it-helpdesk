import pytest

from app.infrastructure.storage.local_file_storage import LocalFileStorage


def test_save_writes_file_with_generated_name_under_folder(tmp_path):
    storage = LocalFileStorage(tmp_path)

    path = storage.save(b"data", folder="tickets/7", extension="png")

    assert path.startswith("tickets/7/")
    assert path.endswith(".png")
    assert (tmp_path / path).read_bytes() == b"data"


def test_two_saves_never_overwrite_each_other(tmp_path):
    storage = LocalFileStorage(tmp_path)
    first = storage.save(b"1", folder="tickets/1", extension="png")
    second = storage.save(b"2", folder="tickets/1", extension="png")

    assert first != second


def test_delete_removes_file_and_ignores_missing(tmp_path):
    storage = LocalFileStorage(tmp_path)
    path = storage.save(b"data", folder="x", extension="jpg")

    storage.delete(path)
    storage.delete(path)  # ikinci kez: hata vermemeli

    assert not (tmp_path / path).exists()


def test_paths_outside_root_are_refused(tmp_path):
    storage = LocalFileStorage(tmp_path / "uploads")

    with pytest.raises(ValueError, match="kökü dışına"):
        storage.save(b"x", folder="../../outside", extension="png")
    with pytest.raises(ValueError, match="kökü dışına"):
        storage.delete("../secret.txt")
