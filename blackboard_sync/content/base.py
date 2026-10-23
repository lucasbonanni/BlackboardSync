import logging
from pathlib import Path
from requests import Response

from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)


class BStream:
    """Base class for content that can be downloaded as a byte stream."""
    CHUNK_SIZE = 1024

    def write_base(self, path: Path, executor: ThreadPoolExecutor,
                   stream: Response) -> None:
        """Schedule the write operation."""

        def _write() -> None:
            logger.info("Starting download write to %s", path)
            try:
                with path.open("wb") as f:
                    for chunk in stream.iter_content(
                            chunk_size=self.CHUNK_SIZE):
                        f.write(chunk)
            except Exception:
                logger.exception("Download write failed for %s", path)
                raise
            logger.info("Finished download write to %s", path)

        executor.submit(_write)


class FStream:
    """Base class for content that can be written as text."""

    def write_base(self, path: Path, executor: ThreadPoolExecutor,
                   body: str) -> None:
        """Schedule the write operation."""

        def _write() -> None:
            logger.info("Starting content write to %s", path)
            try:
                with path.open('w', encoding='utf-8') as f:
                    f.write(body)
            except Exception:
                logger.exception("Content write failed for %s", path)
                raise
            logger.info("Finished content write to %s", path)

        executor.submit(_write)
