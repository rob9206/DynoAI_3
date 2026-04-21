"""
Ingest package for DynoAI.

Provides content-based classification of uploaded files so the UI can stop
relying on filenames/folders.
"""

from api.services.ingest.sniffer import (
    Classification,
    FileType,
    classify_upload,
)

__all__ = ["FileType", "Classification", "classify_upload"]
