import uuid
import mimetypes
import logging

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from ..blackboard import BBAttachment

from .base import BStream
from .api_path import BBContentPath
from .job import DownloadJob

logger = logging.getLogger(__name__)


class Attachment(BStream):
    """File attached to a content."""

    def __init__(self, attachment: BBAttachment, api_path: BBContentPath,
                 job: DownloadJob):
        self._attachment_id = attachment.id
        self._api_path = api_path
        self._job = job
        filename = attachment.fileName or str(uuid.uuid1())
        name_ext = '.' + filename.split('.')[-1]

        # Guess extension based on content
        mime = attachment.mimeType or 'text/plain'
        possible_ext = mimetypes.guess_all_extensions(mime, strict=False)

        if name_ext in possible_ext:
            self.filename = filename
        else:
            real_ext = possible_ext[0] if possible_ext else '.txt'
            self.filename = filename + real_ext

    def write(self, path: Path, executor: ThreadPoolExecutor) -> None:
        target = path / self.filename
        if target.is_file():
            logger.info("Skipping existing attachment %s", target)
            return

        target.parent.mkdir(exist_ok=True, parents=True)
        stream = self._job.session.download(
            attachment_id=self._attachment_id, **self._api_path
        )
        super().write_base(target, executor, stream)
