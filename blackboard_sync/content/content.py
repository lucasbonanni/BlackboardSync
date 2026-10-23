import logging
from pathlib import Path
from json import JSONDecodeError
from pydantic import ValidationError
from requests import RequestException
from concurrent.futures import ThreadPoolExecutor

from ..blackboard import (
    BBCourseContent,
    BBResourceType,
    BBContentHandler
)
from ..blackboard import BBBadRequestError, BBForbiddenError

from . import folder, document, externallink, body, unhandled

from .api_path import BBContentPath
from .job import DownloadJob

logger = logging.getLogger(__name__)


class Content:
    """Content factory for all types."""

    def __init__(self, content: BBCourseContent, api_path: BBContentPath,
                 job: DownloadJob) -> None:

        self.body = None
        self.handler = None

        self.ignore = not Content.should_download(content)

        if self.ignore:
            return

        Handler = Content.get_handler(content.contentHandler)
        self.title = content.title_path_safe.replace('.', '_')
        logger.info("Processing content '%s' (id=%s, handler=%s)",
                    content.title, content.id, content.contentHandler)

        try:
            logger.debug("Starting handler for %s", content.title)
            self.handler = Handler(content, api_path, job)
            logger.debug("Finished handler for %s", content.title)
        except (ValidationError, JSONDecodeError,
                BBBadRequestError, BBForbiddenError):
            logger.exception(f"Error fetching {content.title}")

        try:
            if content.body:
                logger.info("Processing body for %s", content.title)
                self.body = body.ContentBody(content, None, job)
                logger.info("Finished processing body for %s", content.title)
        except (ValidationError, JSONDecodeError,
                BBBadRequestError, BBForbiddenError, RequestException):
            logger.exception("Error processing body of %s", content.title)

    def write(self, path: Path, executor: ThreadPoolExecutor) -> None:
        if self.ignore:
            return

        # Build nested path with content title
        path = path / self.title

        if self.handler is not None:
            if self.handler.create_dir:
                path.mkdir(exist_ok=True, parents=True)

            self.handler.write(path, executor)

        if self.body is not None:
            path.mkdir(exist_ok=True, parents=True)
            self.body.write(path, executor)

    @staticmethod
    def should_download(content: BBCourseContent) -> bool:
        available = bool(content.availability)

        if not available:
            logger.info("Skipping content '%s' (id=%s): unavailable",
                        content.title, content.id)

        return available

    @staticmethod
    def get_handler(content_handler: BBContentHandler | None):
        match content_handler:
            case BBResourceType.Folder | BBResourceType.Lesson:
                return folder.Folder
            case BBResourceType.File | BBResourceType.Document:
                return document.Document
            case BBResourceType.Assignment:
                return document.Document
            case BBResourceType.ExternalLink:
                return externallink.ExternalLink
            case _:
                return unhandled.Unhandled
