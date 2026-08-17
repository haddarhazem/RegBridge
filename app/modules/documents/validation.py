import zipfile
from dataclasses import dataclass
from pathlib import Path


SUPPORTED = {
    ".pdf": ("application/pdf",),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"),
    ".txt": ("text/plain", "application/octet-stream"),
}


@dataclass(frozen=True)
class ValidatedFile:
    extension: str
    mime_type: str


def validate_file(path: Path, filename: str, declared_mime: str | None) -> ValidatedFile:
    extension = Path(filename).suffix.lower()
    allowed_mimes = SUPPORTED.get(extension)
    if allowed_mimes is None:
        raise ValueError("Unsupported document format")
    if declared_mime and declared_mime not in allowed_mimes:
        raise ValueError("Declared MIME type does not match the file format")
    with path.open("rb") as file:
        prefix = file.read(8)
    if extension == ".pdf" and not prefix.startswith(b"%PDF-"):
        raise ValueError("File is not a valid PDF")
    if extension == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise ValueError("File is not a valid DOCX")
        except zipfile.BadZipFile as exc:
            raise ValueError("File is not a valid DOCX") from exc
    if extension == ".txt":
        try:
            with path.open("rb") as file:
                file.read().decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("TXT file is not valid UTF-8") from exc
    return ValidatedFile(extension=extension, mime_type="text/plain" if extension == ".txt" else "application/pdf" if extension == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
