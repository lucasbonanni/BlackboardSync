import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from ..blackboard import BBCourseContent
from ..blackboard.filters import BBAttachmentFilter
from bwfilters import BWFilter

from .attachment import Attachment
from .api_path import BBContentPath
from .job import DownloadJob

logger = logging.getLogger(__name__)


class Document:
    """Represents a file with attachments in the Blackboard API"""
    def __init__(self, content: BBCourseContent, api_path: BBContentPath,
                 job: DownloadJob):
        content_title = (content.title if content is not None
                 else api_path['content_id'])
        attachments = job.session.fetch_file_attachments(**api_path)
        assert isinstance(attachments, list)

        att_filter = BBAttachmentFilter(mime_types=BWFilter(['video/*']))
        filtered_attachments = list(att_filter.filter(attachments))
        logger.info(
            "Content '%s' (id=%s): found %d attachment(s), "
            "%d non-video attachment(s)",
            content_title, api_path['content_id'], len(attachments),
            len(filtered_attachments)
        )

        self.attachments = []

        for i, attachment in enumerate(filtered_attachments):
            logger.info("Content '%s': downloading attachment '%s' (%s)",
                        content_title, attachment.fileName,
                        attachment.mimeType)
            self.attachments.append(
                Attachment(attachment, api_path, job)
            )

    def write(self, path: Path, executor: ThreadPoolExecutor) -> None:
        # If only attachment, just use parent
        if len(self.attachments) > 1:
            path.mkdir(exist_ok=True, parents=True)
        else:
            path = path.parent

        for attachment in self.attachments:
            attachment.write(path, executor)

    @property
    def create_dir(self) -> bool:
        return False
