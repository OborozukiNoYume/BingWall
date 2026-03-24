from pathlib import Path
import shutil


class FileStorage:
    def __init__(self, *, tmp_dir: Path, public_dir: Path, failed_dir: Path) -> None:
        self.tmp_dir = tmp_dir
        self.public_dir = public_dir
        self.failed_dir = failed_dir

    def ensure_directories(self) -> None:
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

    def tmp_path_for(self, relative_path: str) -> Path:
        path = self.tmp_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def public_path_for(self, relative_path: str) -> Path:
        path = self.public_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def failed_path_for(self, relative_path: str) -> Path:
        path = self.failed_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def move_to_public(self, *, tmp_path: Path, relative_path: str) -> Path:
        public_path = self.public_path_for(relative_path)
        shutil.move(str(tmp_path), str(public_path))
        return public_path

    def move_to_failed(self, *, tmp_path: Path, relative_path: str) -> Path:
        failed_path = self.failed_path_for(relative_path)
        shutil.move(str(tmp_path), str(failed_path))
        return failed_path
