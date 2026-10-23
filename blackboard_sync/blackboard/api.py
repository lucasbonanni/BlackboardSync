import logging
from urllib.parse import urljoin, urlsplit
from typing import Any

import requests
from requests.cookies import RequestsCookieJar

from .exceptions import (
    BBBadRequestError,
    BBForbiddenError,
    BBStatusError,
    BBUnauthorizedError,
)
from .filters import BBMembershipFilter
from .models import BBAttachment, BBMembership, BBCourse, BBCourseContent

logger = logging.getLogger(__name__)


class BlackboardSession:
    def __init__(self, url: str, *, cookies: RequestsCookieJar):
        self._instance_url = url.rstrip("/")
        self._url = self._instance_url + "/learn/api/public/v{version}"
        self._cookies = cookies
        self._client_session = requests.Session()
        self._user_id: str | None = None

    @property
    def instance_url(self) -> str:
        return self._instance_url

    @property
    def user_id(self) -> str:
        if self._user_id is None:
            self._user_id = self.fetch_users(user_id="me")["id"]
        return self._user_id

    def _raise_status(self, status_code: int, error: object) -> None:
        error_type = {
            400: BBBadRequestError,
            401: BBUnauthorizedError,
            403: BBForbiddenError,
        }.get(status_code, BBStatusError)
        raise error_type(error)

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.status_code >= 400:
            self._raise_status(response.status_code, response)

    def _raise_for_payload_status(self, payload: Any) -> None:
        if isinstance(payload, dict) and "status" in payload:
            try:
                status_code = int(payload["status"])
            except (TypeError, ValueError):
                return
            self._raise_status(status_code, payload)

    def _request(
        self, url: str, *, stream: bool = False, check_status: bool = True
    ) -> requests.Response:
        response = self._client_session.get(
            url,
            cookies=self._cookies,
            timeout=12,
            stream=stream,
        )
        if check_status:
            self._raise_for_status(response)
        return response

    def _api_url(self, path: str, version: int) -> str:
        return self._url.format(version=version) + path

    def _get_json(self, path: str, *, version: int = 1) -> Any:
        response = self._request(self._api_url(path, version))
        payload = response.json()
        self._raise_for_payload_status(payload)
        return payload

    def _get_collection(self, path: str) -> list[dict[str, Any]]:
        url = self._api_url(path, 1)
        base = urlsplit(self._instance_url)
        results: list[dict[str, Any]] = []
        visited: set[str] = set()

        while url:
            if url in visited:
                raise ValueError("Blackboard pagination link cycle detected")
            visited.add(url)
            response = self._request(url)
            payload = response.json()
            self._raise_for_payload_status(payload)
            if isinstance(payload, list):
                results.extend(payload)
                break
            if not isinstance(payload, dict) or not isinstance(
                payload.get("results"), list
            ):
                raise ValueError("Blackboard collection response has no results list")

            results.extend(payload["results"])
            next_page = payload.get("paging", {}).get("nextPage")
            if not next_page:
                break

            next_url = urljoin(url, next_page)
            parsed_next = urlsplit(next_url)
            if parsed_next.scheme != base.scheme or parsed_next.netloc != base.netloc:
                raise ValueError("Blackboard pagination link points to another host")
            url = next_url

        return results

    def download_webdav(self, *, webdav_url: str) -> requests.Response:
        return self._request(webdav_url, stream=True, check_status=False)

    def fetch_users(self, *, user_id: str) -> dict[str, Any]:
        return self._get_json(f"/users/{user_id}")

    def fetch_user_memberships(self, *, user_id: str) -> list[BBMembership]:
        memberships = self._get_collection(f"/users/{user_id}/courses")
        return [BBMembership.model_validate(item) for item in memberships]

    def fetch_courses(self, *, course_id: str) -> BBCourse | list[BBCourse]:
        payload = self._get_json(f"/courses/{course_id}", version=3)
        if isinstance(payload, list):
            return [BBCourse.model_validate(item) for item in payload]
        return BBCourse.model_validate(payload)

    def fetch_contents(self, *, course_id: str) -> list[BBCourseContent]:
        return [
            BBCourseContent.model_validate(item)
            for item in self._get_collection(f"/courses/{course_id}/contents")
        ]

    def fetch_content_children(
        self, *, course_id: str, content_id: str
    ) -> list[BBCourseContent]:
        path = f"/courses/{course_id}/contents/{content_id}/children"
        return [
            BBCourseContent.model_validate(item) for item in self._get_collection(path)
        ]

    def fetch_file_attachments(
        self,
        *,
        course_id: str,
        content_id: str,
        attachment_id: str | None = None,
    ) -> list[BBAttachment] | BBAttachment:
        path = f"/courses/{course_id}/contents/{content_id}/attachments"
        if attachment_id is not None:
            payload = self._get_json(f"{path}/{attachment_id}")
            return BBAttachment.model_validate(payload)
        return [
            BBAttachment.model_validate(item) for item in self._get_collection(path)
        ]

    def download(
        self, *, course_id: str, content_id: str, attachment_id: str
    ) -> requests.Response:
        path = (
            f"/courses/{course_id}/contents/{content_id}/attachments/"
            f"{attachment_id}/download"
        )
        return self._request(self._api_url(path, 1), stream=True)


class BlackboardExtended(BlackboardSession):
    def ex_fetch_courses(
        self,
        *,
        result_filter: BBMembershipFilter | None = None,
        **kwargs: Any,
    ) -> list[BBCourse]:
        memberships = self.fetch_user_memberships(**kwargs)
        if result_filter is not None:
            memberships = list(result_filter.filter(memberships))

        courses = []
        for membership in memberships:
            if not membership.availability:
                continue
            try:
                course = self.fetch_courses(course_id=membership.courseId)
            except BBForbiddenError:
                logger.warning("Course %s is not available", membership.courseId)
                continue
            assert isinstance(course, BBCourse)
            courses.append(course.model_copy(update={"created": membership.created}))
        return courses
