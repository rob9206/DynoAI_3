"""
MasterTune repository scraper.

Scrapes the public MasterTune tuning repository listing and downloads files with
robots-aware delay handling. This scraper is intentionally polite and
non-aggressive: one request every 10 seconds by default.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from dynoai.core.io_contracts import safe_path
from external_scrapers import get_stdout_logger
from external_scrapers.http_utils import RobotsAwareSession

logger = get_stdout_logger(__name__)

MASTER_TUNE_REPO_URL = "https://www.mastertune.net/repository.php"
MASTER_TUNE_ALLOWED_EXTENSIONS = {".mte", ".mt7", ".mt8", ".mt9"}
MASTER_TUNE_DEFAULT_DELAY_SECONDS = 10.0

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class MasterTuneFile:
    """Represents one downloadable tune file entry from the repository."""

    filename: str
    extension: str
    download_url: str
    category: str


@dataclass
class ScrapeSummary:
    """Aggregate result for a MasterTune scrape run."""

    total_links_found: int
    candidate_files: int
    selected_files: int
    downloaded_count: int
    skipped_existing_count: int
    failed_count: int
    output_dir: str
    index_csv: str
    downloaded_files: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "total_links_found": self.total_links_found,
            "candidate_files": self.candidate_files,
            "selected_files": self.selected_files,
            "downloaded_count": self.downloaded_count,
            "skipped_existing_count": self.skipped_existing_count,
            "failed_count": self.failed_count,
            "output_dir": self.output_dir,
            "index_csv": self.index_csv,
            "downloaded_files": self.downloaded_files,
        }


def _safe_local_filename(filename: str) -> str:
    """
    Convert remote filename into a safe local filename.
    """
    base = Path(filename).name
    base = _INVALID_FILENAME_CHARS.sub("_", base)
    base = base.strip().strip(".")
    return base or "unnamed_tune_file"


def _extract_extension(filename: str) -> str:
    lower = filename.lower()
    for ext in MASTER_TUNE_ALLOWED_EXTENSIONS:
        if lower.endswith(ext):
            return ext
    return ""


class MasterTuneScraper:
    """
    Scraper for the public MasterTune file repository page.
    """

    def __init__(
        self,
        repository_url: str = MASTER_TUNE_REPO_URL,
        delay_seconds: float = MASTER_TUNE_DEFAULT_DELAY_SECONDS,
    ):
        self.repository_url = repository_url
        self.delay_seconds = delay_seconds
        parsed = urlparse(repository_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"

    def scrape_repository_listing(self, session: RobotsAwareSession) -> List[MasterTuneFile]:
        """
        Parse repository HTML and return all candidate tune files.
        """
        response = session.get(self.repository_url)
        soup = BeautifulSoup(response.text, "html.parser")

        files: List[MasterTuneFile] = []
        seen_urls = set()

        all_links = soup.find_all("a")
        for anchor in all_links:
            href = anchor.get("href")
            if not href:
                continue
            if "public-uploaded-files/" not in href:
                continue

            full_url = urljoin(self.repository_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            path = urlparse(full_url).path
            filename = unquote(Path(path).name)
            if filename in {"", ".", ".."}:
                continue

            extension = _extract_extension(filename)
            if extension == "":
                continue

            category_tag = anchor.find_previous("h3")
            category = category_tag.get_text(" ", strip=True) if category_tag else "unknown"

            files.append(
                MasterTuneFile(
                    filename=filename,
                    extension=extension,
                    download_url=full_url,
                    category=category,
                )
            )

        logger.info(
            "MasterTune listing parsed: %d candidate files from %d links",
            len(files),
            len(all_links),
        )
        return files

    def download_file(
        self,
        session: RobotsAwareSession,
        file_info: MasterTuneFile,
        output_dir: Path,
        *,
        resume: bool = True,
    ) -> Path:
        """
        Download one file and return local path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        local_name = _safe_local_filename(file_info.filename)
        local_path = output_dir / local_name

        if resume and local_path.exists() and local_path.stat().st_size > 0:
            logger.info("Skipping existing file: %s", local_path)
            return local_path

        response = session.get(file_info.download_url)
        local_path.write_bytes(response.content)
        logger.info("Downloaded %s -> %s", file_info.filename, local_path)
        return local_path

    def run_mastertune_scrape(
        self,
        output_dir: str | Path,
        *,
        max_files: Optional[int] = None,
        resume: bool = True,
        write_index_csv: bool = True,
    ) -> ScrapeSummary:
        """
        Scrape listing and download files.
        """
        safe_output_dir = safe_path(str(output_dir))
        safe_output_dir.mkdir(parents=True, exist_ok=True)
        index_csv = safe_output_dir / "index.csv"

        downloaded_files: List[str] = []
        downloaded_count = 0
        skipped_existing = 0
        failed_count = 0

        with RobotsAwareSession(
            base_url=self.base_url,
            delay_seconds=self.delay_seconds,
        ) as session:
            files = self.scrape_repository_listing(session)
            selected = files if max_files is None else files[: max_files]

            index_rows: List[Dict[str, str]] = []

            for file_info in selected:
                local_name = _safe_local_filename(file_info.filename)
                local_path = safe_output_dir / local_name
                status = "downloaded"
                bytes_written = ""

                if resume and local_path.exists() and local_path.stat().st_size > 0:
                    skipped_existing += 1
                    status = "skipped_existing"
                    bytes_written = str(local_path.stat().st_size)
                else:
                    try:
                        path = self.download_file(
                            session,
                            file_info,
                            safe_output_dir,
                            resume=resume,
                        )
                        downloaded_count += 1
                        downloaded_files.append(str(path))
                        bytes_written = str(path.stat().st_size)
                    except Exception as exc:
                        failed_count += 1
                        status = f"failed: {exc}"
                        logger.warning(
                            "Failed to download %s: %s",
                            file_info.download_url,
                            exc,
                        )

                index_rows.append(
                    {
                        "filename": file_info.filename,
                        "extension": file_info.extension,
                        "category": file_info.category,
                        "download_url": file_info.download_url,
                        "local_path": str(local_path),
                        "status": status,
                        "bytes": bytes_written,
                    }
                )

            if write_index_csv:
                with index_csv.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=[
                            "filename",
                            "extension",
                            "category",
                            "download_url",
                            "local_path",
                            "status",
                            "bytes",
                        ],
                    )
                    writer.writeheader()
                    writer.writerows(index_rows)

        summary = ScrapeSummary(
            total_links_found=len(files),
            candidate_files=len(files),
            selected_files=len(selected),
            downloaded_count=downloaded_count,
            skipped_existing_count=skipped_existing,
            failed_count=failed_count,
            output_dir=str(safe_output_dir),
            index_csv=str(index_csv),
            downloaded_files=downloaded_files,
        )
        logger.info("MasterTune scrape summary: %s", summary.to_dict())
        return summary


def run_mastertune_scrape(
    output_dir: str | Path,
    *,
    max_files: Optional[int] = None,
    resume: bool = True,
    repository_url: str = MASTER_TUNE_REPO_URL,
    delay_seconds: float = MASTER_TUNE_DEFAULT_DELAY_SECONDS,
) -> ScrapeSummary:
    """
    Convenience wrapper for scripts/CLI.
    """
    scraper = MasterTuneScraper(
        repository_url=repository_url,
        delay_seconds=delay_seconds,
    )
    return scraper.run_mastertune_scrape(
        output_dir=output_dir,
        max_files=max_files,
        resume=resume,
    )


__all__ = [
    "MASTER_TUNE_REPO_URL",
    "MASTER_TUNE_ALLOWED_EXTENSIONS",
    "MASTER_TUNE_DEFAULT_DELAY_SECONDS",
    "MasterTuneFile",
    "ScrapeSummary",
    "MasterTuneScraper",
    "run_mastertune_scrape",
]
