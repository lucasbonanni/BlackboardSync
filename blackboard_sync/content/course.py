import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from ..blackboard import BBCourse

from .api_path import BBContentPath
from .job import DownloadJob
from .content import Content

logger = logging.getLogger(__name__)


class Course:
    def __init__(self, course: BBCourse, job: DownloadJob):
        logger.info("Starting course %s (%s, id=%s)",
                course.title, course.code, course.id)

        self.ignore = not course.availability

        if self.ignore:
            return

        self.year = self.get_year(course.created)
        self.title = course.title or 'Untitled Course'

        contents = job.session.fetch_contents(course_id=course.id)
        logger.info("Found %d top-level content items in course %s",
                len(contents), course.title)
        self.children = []

        for content in contents:
            api_path = BBContentPath(course_id=course.id,
                                     content_id=content.id)
            self.children.append(Content(content, api_path, job))

    def write(self, path: Path, executor: ThreadPoolExecutor) -> None:
        if self.ignore:
            return

        path = path / self.year / self.title

        for child in self.children:
            child.write(path, executor)

    @staticmethod
    def get_year(created: datetime | None) -> str:
        return str(created.year) if created is not None else 'No Date'
