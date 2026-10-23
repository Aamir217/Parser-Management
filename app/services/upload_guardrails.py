import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import Any

from app.core.config import settings


ALLOWED_EXTENSIONS = {
    ".xlsx",
}


REQUIRED_XLSX_MEMBERS = {
    "[Content_Types].xml",
    "xl/workbook.xml",
}


class UploadGuardrailError(ValueError):
    def __init__(
        self,
        message: str,
        guardrail_name: str,
    ):
        super().__init__(message)

        self.message = message
        self.guardrail_name = guardrail_name


def sanitize_filename(filename: str) -> str:
    basename = Path(filename).name

    sanitized = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        basename,
    )

    sanitized = sanitized.strip("._")

    if not sanitized:
        raise UploadGuardrailError(
            message="The filename is empty after sanitization.",
            guardrail_name="SAFE_FILENAME",
        )

    return sanitized[:255]


def validate_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise UploadGuardrailError(
            message=(
                "Only .xlsx files are permitted "
                "in the current prototype."
            ),
            guardrail_name="ALLOWED_EXTENSION",
        )

    return extension


def validate_file_size(content: bytes) -> int:
    size_bytes = len(content)

    if size_bytes == 0:
        raise UploadGuardrailError(
            message="The uploaded file is empty.",
            guardrail_name="NON_EMPTY_FILE",
        )

    maximum_bytes = (
        settings.max_file_size_mb
        * 1024
        * 1024
    )

    if size_bytes > maximum_bytes:
        raise UploadGuardrailError(
            message=(
                f"The file exceeds the "
                f"{settings.max_file_size_mb} MB limit."
            ),
            guardrail_name="MAXIMUM_FILE_SIZE",
        )

    return size_bytes


def validate_xlsx_structure(content: bytes) -> None:
    memory_file = io.BytesIO(content)

    if not zipfile.is_zipfile(memory_file):
        raise UploadGuardrailError(
            message=(
                "The uploaded file is not a valid "
                "ZIP-based XLSX workbook."
            ),
            guardrail_name="XLSX_ZIP_STRUCTURE",
        )

    memory_file.seek(0)

    try:
        with zipfile.ZipFile(memory_file) as archive:
            archive_members = set(
                archive.namelist()
            )

            missing_members = (
                REQUIRED_XLSX_MEMBERS
                - archive_members
            )

            if missing_members:
                raise UploadGuardrailError(
                    message=(
                        "The workbook is missing "
                        "required XLSX components."
                    ),
                    guardrail_name=(
                        "XLSX_REQUIRED_COMPONENTS"
                    ),
                )

            for member in archive.infolist():
                if member.file_size <= 0:
                    continue

                compressed_size = max(
                    member.compress_size,
                    1,
                )

                compression_ratio = (
                    member.file_size
                    / compressed_size
                )

                if compression_ratio > 100:
                    raise UploadGuardrailError(
                        message=(
                            "The workbook contains "
                            "a suspicious compression ratio."
                        ),
                        guardrail_name=(
                            "ZIP_COMPRESSION_RATIO"
                        ),
                    )

    except zipfile.BadZipFile as exception:
        raise UploadGuardrailError(
            message="The XLSX ZIP structure is invalid.",
            guardrail_name="XLSX_ZIP_STRUCTURE",
        ) from exception


def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_upload(
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    sanitized_filename = sanitize_filename(
        filename
    )

    extension = validate_extension(
        sanitized_filename
    )

    size_bytes = validate_file_size(
        content
    )

    validate_xlsx_structure(
        content
    )

    checksum = calculate_sha256(
        content
    )

    return {
        "sanitized_filename": sanitized_filename,
        "extension": extension,
        "size_bytes": size_bytes,
        "checksum_sha256": checksum,
        "guardrails": [
            {
                "name": "SAFE_FILENAME",
                "status": "PASSED",
            },
            {
                "name": "ALLOWED_EXTENSION",
                "status": "PASSED",
            },
            {
                "name": "NON_EMPTY_FILE",
                "status": "PASSED",
            },
            {
                "name": "MAXIMUM_FILE_SIZE",
                "status": "PASSED",
            },
            {
                "name": "XLSX_ZIP_STRUCTURE",
                "status": "PASSED",
            },
            {
                "name": "XLSX_REQUIRED_COMPONENTS",
                "status": "PASSED",
            },
            {
                "name": "ZIP_COMPRESSION_RATIO",
                "status": "PASSED",
            },
            {
                "name": "SHA256_CHECKSUM",
                "status": "PASSED",
            },
        ],
    }
