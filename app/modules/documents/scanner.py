import asyncio
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class ScanResult:
    status: str
    detail: str | None = None


class MalwareScanner:
    async def scan(self, path: Path) -> ScanResult:  # pragma: no cover - protocol shape
        raise NotImplementedError


class ClamAVScanner(MalwareScanner):
    """Small ClamAV INSTREAM adapter. Scanner errors are deliberately propagated."""

    def __init__(self, settings: Settings) -> None:
        self.host = settings.clamav_host
        self.port = settings.clamav_port

    async def scan(self, path: Path) -> ScanResult:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            writer.write(b"zINSTREAM\0")
            with path.open("rb") as file:
                while chunk := file.read(1024 * 1024):
                    writer.write(len(chunk).to_bytes(4, "big") + chunk)
                    await writer.drain()
            writer.write((0).to_bytes(4, "big"))
            await writer.drain()
            result = await reader.readline()
        finally:
            writer.close()
            await writer.wait_closed()
        message = result.decode("utf-8", errors="replace").strip()
        if message.endswith("OK"):
            return ScanResult("clean")
        if "FOUND" in message:
            return ScanResult("infected", message)
        return ScanResult("error", message or "ClamAV returned no result")


@lru_cache(maxsize=1)
def get_malware_scanner() -> MalwareScanner:
    return ClamAVScanner(get_settings())
