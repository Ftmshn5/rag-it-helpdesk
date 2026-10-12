"""Dosyaları yerel diskte (varsayılan: data/uploads) saklayan implementasyon."""

import uuid
from pathlib import Path

from app.application.interfaces.file_storage import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def save(self, content: bytes, *, folder: str, extension: str) -> str:
        # Rastgele ad: istemcinin verdiği dosya adı hiç kullanılmaz; böylece
        # "../../app/main.py" gibi adlarla kök dışına yazmak mümkün olmaz.
        relative_path = Path(folder) / f"{uuid.uuid4().hex}.{extension}"
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return relative_path.as_posix()

    def delete(self, path: str) -> None:
        self._resolve(Path(path)).unlink(missing_ok=True)

    def _resolve(self, relative_path: Path) -> Path:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Depolama kökü dışına erişilemez.")
        return target
