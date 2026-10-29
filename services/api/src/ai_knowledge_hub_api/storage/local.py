from pathlib import Path


class UnsafeStorageKeyError(ValueError):
    """Raised when a storage key would escape the configured root."""


class LocalDocumentStorage:
    """Private local filesystem storage for development uploads."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def resolve_key_path(self, storage_key: str) -> Path:
        if not storage_key or storage_key.startswith("/") or ".." in storage_key:
            raise UnsafeStorageKeyError("Invalid storage key")
        path = (self._root / storage_key).resolve()
        if not path.is_relative_to(self._root):
            raise UnsafeStorageKeyError("Storage key escapes root")
        return path

    def write(self, storage_key: str, data: bytes) -> None:
        path = self.resolve_key_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, storage_key: str) -> bytes:
        path = self.resolve_key_path(storage_key)
        if not path.is_file():
            raise FileNotFoundError("Stored document object not found")
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        try:
            path = self.resolve_key_path(storage_key)
        except UnsafeStorageKeyError:
            return
        if path.is_file():
            path.unlink()
