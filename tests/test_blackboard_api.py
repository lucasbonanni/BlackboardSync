from unittest.mock import Mock, patch

import pytest
import requests

from blackboard_sync.blackboard import (
    BBForbiddenError,
    BBStatusError,
    BlackboardSession,
    BBCourse,
)


def make_session(get_mock, cookies=None):
    if cookies is None:
        cookies = requests.cookies.RequestsCookieJar()
    with patch("blackboard_sync.blackboard.api.requests.Session") as session_factory:
        session_factory.return_value.get = get_mock
        session = BlackboardSession("https://learn.example.edu", cookies=cookies)
    return session, session_factory.return_value


def make_response(payload, status_code=200):
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.text = "request failed" if status_code >= 400 else ""
    response.json.return_value = payload
    return response


def test_fetch_user_uses_cookie_auth_and_documented_path():
    get_mock = Mock(return_value=make_response({"id": "user-1"}))
    cookies = requests.cookies.RequestsCookieJar()
    session, _ = make_session(get_mock, cookies)

    assert session.fetch_users(user_id="me") == {"id": "user-1"}

    get_mock.assert_called_once_with(
        "https://learn.example.edu/learn/api/public/v1/users/me",
        cookies=cookies,
        timeout=12,
        stream=False,
    )
    assert get_mock.call_args.kwargs["cookies"] is cookies


def test_collection_follows_documented_next_page_link():
    get_mock = Mock(
        side_effect=[
            make_response(
                {
                    "results": [{"courseId": "one"}],
                    "paging": {
                        "nextPage": "/learn/api/public/v1/users/me/courses?offset=1"
                    },
                }
            ),
            make_response({"results": [{"courseId": "two"}], "paging": {}}),
        ]
    )
    session, _ = make_session(get_mock)

    memberships = session.fetch_user_memberships(user_id="me")
    assert [membership.courseId for membership in memberships] == ["one", "two"]
    assert [call.args[0] for call in get_mock.call_args_list] == [
        "https://learn.example.edu/learn/api/public/v1/users/me/courses",
        "https://learn.example.edu/learn/api/public/v1/users/me/courses?offset=1",
    ]


def test_http_error_maps_to_blackboard_status_error():
    session, _ = make_session(Mock(return_value=make_response({}, status_code=500)))

    with pytest.raises(BBStatusError):
        session.fetch_users(user_id="me")


def test_webdav_returns_error_response_for_content_validation():
    response = make_response({}, status_code=404)
    session, _ = make_session(Mock(return_value=response))

    assert (
        session.download_webdav(webdav_url="https://learn.example.edu/webdav/file")
        is response
    )


def test_json_status_envelope_maps_to_blackboard_auth_error():
    session, _ = make_session(
        Mock(return_value=make_response({"status": 403, "message": "Forbidden"}))
    )

    with pytest.raises(BBForbiddenError):
        session.fetch_users(user_id="me")


def test_course_details_use_v3_endpoint_and_model():
    get_mock = Mock(return_value=make_response({"id": "course-1"}))
    session, _ = make_session(get_mock)

    assert session.fetch_courses(course_id="course-1") == BBCourse(id="course-1")
    assert get_mock.call_args.args[0] == (
        "https://learn.example.edu/learn/api/public/v3/courses/course-1"
    )
