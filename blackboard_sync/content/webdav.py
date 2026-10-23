"""
Parse an html to look for links
"""

# Copyright (C) 2021, Jacob Sánchez Pérez

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.


import logging
import json
import mimetypes
import time
from pathlib import Path
from requests import Response
from bs4 import BeautifulSoup
from urllib.parse import unquote
from typing import List, NamedTuple
from pathvalidate import sanitize_filename
from concurrent.futures import ThreadPoolExecutor

from .base import BStream
from .job import DownloadJob


logger = logging.getLogger(__name__)


class Link(NamedTuple):
    href: str
    text: str


class ContentParser:
    def __init__(self, body: str, base_url: str,
                 *, find_links: bool = True) -> None:
        soup = BeautifulSoup(body, 'html.parser')
        self._links = []

        if find_links:
            a = self._find_replace(soup, 'a', 'href', base_url)
            img = self._find_replace(soup, 'img', 'src', base_url)
            video = self._find_replace(soup, 'video', 'src', base_url)
            links_by_url = {}
            for link in [*a, *img, *video]:
                previous = links_by_url.get(link.href)
                fallback_title = unquote(link.href.rsplit('/', 1)[-1])
                if (previous is None or
                        (previous.text == fallback_title
                         and link.text != fallback_title)):
                    links_by_url[link.href] = link
            self._links = list(links_by_url.values())

        self._body = str(soup)
        self._text = soup.text

    def _find_replace(self, soup: BeautifulSoup,
                      tag: str, attr: str, base_url: str) -> list[Link]:
        links = []

        for el in soup.find_all(tag):
            # Add link for later download
            uri = el.get(attr)

            if uri:
                # Handle url-encoding
                filename = unquote(uri.split('/')[-1])
                title = el.get('aria-label') or filename
                bbfile = el.get('data-bbfile')
                if not bbfile and el.name == 'video':
                    parent = el.find_parent('a')
                    if parent is not None:
                        bbfile = parent.get('data-bbfile')
                        title = parent.get('aria-label') or title
                if bbfile:
                    try:
                        metadata = json.loads(bbfile)
                    except json.JSONDecodeError:
                        metadata = {}
                    title = (metadata.get('displayName')
                             or metadata.get('fileName')
                             or title)
                links.append(Link(href=uri, text=title))

                # Replace for local instance
                if uri.startswith(base_url):
                    el[attr] = title
        return links

    @property
    def links(self) -> List[Link]:
        return self._links

    @property
    def body(self) -> str:
        return self._body

    @property
    def text(self) -> str:
        return self._text


def validate_webdav_response(response: Response,
                             link: str, base_url: str) -> bool:
    return response.status_code == 200 and link.startswith(base_url)


class WebDavFile(BStream):
    """A Blackboard WebDav file which can be downloaded directly"""
    def __init__(self, link: Link, job: DownloadJob) -> None:
        self.title = sanitize_filename(link.text, replacement_text="_")
        started_at = time.monotonic()
        logger.info("Starting WebDAV request for %s", self.title)
        try:
            self.stream = job.session.download_webdav(webdav_url=link.href)
        except Exception:
            logger.exception(
                "WebDAV request failed for %s after %.1f seconds",
                self.title,
                time.monotonic() - started_at
            )
            raise

        logger.info(
            "Received WebDAV response for %s (status %s, %.1f seconds)",
            self.title,
            self.stream.status_code,
            time.monotonic() - started_at
        )
        content_type = self.stream.headers.get('Content-Type', 'text/plain')
        self.extension = mimetypes.guess_extension(content_type)
        self.valid = validate_webdav_response(self.stream, link.href,
                                              job.session.instance_url)
        if not self.valid:
            logger.warning(
                "Skipping WebDAV file '%s' (status=%s, content_type=%s, "
                "content_length=%s, same_instance=%s)",
                self.title,
                self.stream.status_code,
                self.stream.headers.get('Content-Type', ''),
                self.stream.headers.get('Content-Length', 'unknown'),
                link.href.startswith(job.session.instance_url)
            )

    def write(self, path: Path, executor: ThreadPoolExecutor) -> None:
        if self.valid:
            path = Path(path, self.title)

            if self.extension:
                path = path.with_suffix(self.extension)

            super().write_base(path, executor, self.stream)
