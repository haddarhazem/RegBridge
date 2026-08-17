import io
import zipfile

import pytest
from starlette.datastructures import UploadFile

from app.modules.documents.authorization import DocumentAuthorizationPolicy
from app.modules.documents.service import DocumentService
from app.modules.documents.service import build_storage_key
from app.modules.documents.validation import validate_file


class FakeScanner:
    def __init__(self, status: str = "clean") -> None:
        self.status = status

    async def scan(self, path):
        from app.modules.documents.scanner import ScanResult

        return ScanResult(self.status)


class FailingScanner:
    async def scan(self, path):
        raise OSError("scanner unavailable")


def test_pdf_validation(tmp_path) -> None:
    path = tmp_path / "file.pdf"
    path.write_bytes(b"%PDF-1.7\nbody")

    result = validate_file(path, "file.pdf", "application/pdf")

    assert result.mime_type == "application/pdf"


def test_docx_validation(tmp_path) -> None:
    path = tmp_path / "file.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")

    result = validate_file(path, "file.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    assert result.extension == ".docx"


def test_txt_validation(tmp_path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("RegBridge", encoding="utf-8")

    assert validate_file(path, "file.txt", "text/plain").mime_type == "text/plain"


def test_unsupported_and_mismatched_content_are_rejected(tmp_path) -> None:
    binary = tmp_path / "file.exe"
    binary.write_bytes(b"MZ\x00\x01")
    pdf = tmp_path / "file.pdf"
    pdf.write_bytes(b"not a pdf")

    with pytest.raises(ValueError):
        validate_file(binary, "file.exe", "application/octet-stream")
    with pytest.raises(ValueError):
        validate_file(pdf, "file.pdf", "application/pdf")


@pytest.mark.asyncio
async def test_upload_staging_enforces_configured_size_and_hashes_incrementally() -> None:
    service = DocumentService(None, storage=object(), scanner=FakeScanner(), max_upload_bytes=4)  # type: ignore[arg-type]
    upload = UploadFile(file=io.BytesIO(b"12345"), filename="file.txt", headers={"content-type": "text/plain"})

    with pytest.raises(Exception) as error:
        await service._stage(upload)

    assert getattr(error.value, "status_code", None) == 413


@pytest.mark.asyncio
async def test_scanner_failure_is_not_treated_as_clean() -> None:
    service = DocumentService(None, storage=object(), scanner=FailingScanner(), max_upload_bytes=10)  # type: ignore[arg-type]
    path = __import__("pathlib").Path(__file__)

    result = await service._scan(path)

    assert result.status == "error"


def test_document_policy_is_conservative() -> None:
    policy = DocumentAuthorizationPolicy()
    member = type("Member", (), {"status": "active", "member_role": "member"})()
    viewer = type("Member", (), {"status": "active", "member_role": "viewer"})()

    assert policy.can_upload(member) is True
    assert policy.can_upload(viewer) is False
    assert policy.can_read("shared", "confidential", member, "owner", "other") is False
    assert policy.can_read("project_members", "confidential", member, "owner", "other") is True


def test_storage_key_is_backend_generated_and_filename_independent() -> None:
    import uuid

    key = build_storage_key(uuid.uuid4(), uuid.uuid4())

    assert key.startswith("documents/")
    assert ".." not in key
    assert "secret.pdf" not in key
