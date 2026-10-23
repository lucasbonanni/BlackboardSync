from pathlib import Path
from unittest import mock

from hypothesis import given
from hypothesis import assume

from blackboard_sync.blackboard import (
    BBCourse,
    BBCourseContent,
    BBContentHandler,
    BBResourceType,
    BBAttachment,
    BBAvailability
)

from blackboard_sync.content import (
    BBContentPath,
    Course,
    Content,
    Folder,
    Document,
    Unhandled
)

from blackboard_sync.content.base import FStream
from blackboard_sync.content.attachment import Attachment
from blackboard_sync.content.webdav import ContentParser, validate_webdav_response


def assert_written(path, content):
    assert path.is_file()
    with path.open('r') as f:
        assert content == f.read()


def make_available(model):
    return model.model_copy(update={
        'availability': BBAvailability(available='Yes')
    })


def get_module(class_name):
    return 'blackboard_sync.content.content.' + class_name


def test_fstream_write(tmpdir):
    new_file_path = Path(tmpdir, 'my_new_file.txt')
    contents = 'whatever the file says\nincluding newlines'

    # Write a text file to disk
    assert not new_file_path.exists()

    content = FStream()
    content.write_base(new_file_path, mock.Mock(submit=lambda x: x()),
                       contents)

    assert new_file_path.is_file()

    with new_file_path.open('r') as f:
        assert contents == f.read()


@given(...)
def test_course_api_call(course: BBCourse):
    course = make_available(course)

    job = mock.Mock()
    job.session.fetch_contents.return_value = []

    Course(course, job)

    job.session.fetch_contents.assert_called_once_with(
        course_id=course.id
    )


@given(...)
def test_folder_api_call(api_path: BBContentPath):
    job = mock.Mock()
    job.session.fetch_content_children.return_value = []

    Folder(None, api_path, job)
    job.session.fetch_content_children.assert_called_once_with(**api_path)


@given(...)
def test_file_api_call(api_path: BBContentPath):
    job = mock.Mock()
    job.session.fetch_file_attachments.return_value = []

    Document(None, api_path, job)

    job.session.fetch_file_attachments.assert_called_once_with(
        **api_path
    )


@given(...)
def test_children_course(course: BBCourse, contents: list[BBCourseContent]):
    job = mock.Mock()
    job.session.fetch_contents.return_value = contents

    course = make_available(course)

    calls = []
    for content in contents:
        api_path = BBContentPath(course_id=course.id, content_id=content.id)
        calls.append(mock.call(content, api_path, job))

    with mock.patch('blackboard_sync.content.course.Content') as p:
        Course(course, job)
        p.assert_has_calls(calls)


@given(...)
def test_children_folder(api_path: BBContentPath,
                         children: list[BBCourseContent]):
    job = mock.Mock()
    job.session.fetch_content_children.return_value = children

    calls = []
    for child in children:
        api_path = BBContentPath(course_id=api_path.get('course_id'),
                                 content_id=child.id)
        calls.append(mock.call(child, api_path, job))

    with mock.patch('blackboard_sync.content.folder.content.Content') as p:
        Folder(None, api_path, job)
        p.assert_has_calls(calls)


@given(...)
def test_children_file(api_path: BBContentPath,
                       attachments: list[BBAttachment]):
    job = mock.Mock()
    job.session.fetch_file_attachments.return_value = attachments

    calls = []

    # Setup calls
    for att in attachments:
        if att.mimeType is not None:
            assume(not att.mimeType.startswith("video/"))
            assume(not att.mimeType == '*')

        calls.append(mock.call(att, api_path, job))

    with mock.patch('blackboard_sync.content.document.Attachment') as p:
        Document(None, api_path, job)
        p.assert_has_calls(calls)


@given(...)
def test_content_folder(api_path: BBContentPath):
    job = mock.Mock()
    job.has_changed.return_value = True

    content = mock.MagicMock()
    content.contentHandler = BBContentHandler(id=BBResourceType.Folder)
    content.availability = True
    content.id = api_path['content_id']
    content.body = False

    with mock.patch(get_module('folder.Folder')) as p:
        Content(content, api_path, job)
        p.assert_called_once_with(content, api_path, job)


@given(...)
def test_content_file(api_path: BBContentPath):
    job = mock.Mock()
    job.has_changed.return_value = True

    content = mock.MagicMock()
    content.contentHandler = BBContentHandler(id=BBResourceType.Document)
    content.availability = True
    content.id = api_path['content_id']
    content.body = False

    with mock.patch(get_module('document.Document')) as p:
        Content(content, api_path, job)
        p.assert_called_once_with(content, api_path, job)


def test_old_content_is_processed():
    api_path = BBContentPath(course_id="course-id", content_id="content-id")
    job = mock.Mock()
    job.has_changed.return_value = False
    content = BBCourseContent(
        id=api_path['content_id'],
        title="Old document",
        modified="2000-01-01T00:00:00Z",
        availability=BBAvailability(available='Yes'),
        contentHandler=BBContentHandler(id=BBResourceType.Document),
    )

    with mock.patch(get_module('document.Document')) as handler:
        Content(content, api_path, job)

    handler.assert_called_once_with(content, api_path, job)
    job.has_changed.assert_not_called()


def test_attachment_write_skips_existing_file(tmp_path):
    api_path = BBContentPath(course_id="course-id", content_id="content-id")
    job = mock.Mock()
    executor = mock.Mock()
    attachment = Attachment(
        BBAttachment(
            id="attachment-id", fileName="exam.pdf", mimeType="application/pdf"
        ),
        api_path,
        job,
    )
    (tmp_path / "exam.pdf").write_bytes(b"already downloaded")

    attachment.write(tmp_path, executor)

    job.session.download.assert_not_called()
    executor.submit.assert_not_called()


def test_attachment_write_downloads_missing_file(tmp_path):
    api_path = BBContentPath(course_id="course-id", content_id="content-id")
    job = mock.Mock()
    executor = mock.Mock()
    attachment = Attachment(
        BBAttachment(
            id="attachment-id", fileName="exam.pdf", mimeType="application/pdf"
        ),
        api_path,
        job,
    )
    target_dir = tmp_path / "new-folder"

    attachment.write(target_dir, executor)

    job.session.download.assert_called_once_with(
        attachment_id="attachment-id", **api_path
    )
    executor.submit.assert_called_once()
    assert target_dir.is_dir()


def test_content_parser_finds_embedded_video_webdav_link():
    base_url = "https://learn.example.edu"
    href = f"{base_url}/bbcswebdav/pid-1-dt-content-rid-2/xid-2"
    second_href = f"{base_url}/bbcswebdav/pid-1-dt-content-rid-3/xid-3"
    body = (
        '<a data-bbtype="attachment" '
        'data-bbfile="{&quot;displayName&quot;:&quot;lecture.mp4&quot;}" '
        f'href="{href}"><video src="{href}"></video></a>'
        f'<video aria-label="seminar.mp4" src="{second_href}"></video>'
    )

    parser = ContentParser(body, base_url)

    assert parser.links == [
        (href, "lecture.mp4"),
        (second_href, "seminar.mp4"),
    ]
    assert 'href="lecture.mp4"' in parser.body
    assert 'src="lecture.mp4"' in parser.body
    assert 'src="seminar.mp4"' in parser.body


def test_webdav_accepts_large_video_response():
    response = mock.Mock(
        status_code=200,
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": "109368442",
        },
    )

    assert validate_webdav_response(
        response,
        "https://learn.example.edu/bbcswebdav/video.mp4",
        "https://learn.example.edu",
    )


@given(...)
def test_content_link(api_path: BBContentPath):
    job = mock.Mock()
    job.has_changed.return_value = True

    content = mock.MagicMock()
    content.contentHandler = BBContentHandler(id=BBResourceType.ExternalLink)
    content.availability = True
    content.id = api_path['content_id']
    content.body = False

    with mock.patch(get_module('externallink.ExternalLink')) as p:
        Content(content, api_path, job)
        p.assert_called_once_with(content, api_path, job)


@given(...)
def test_content_unhandled(api_path: BBContentPath):
    job = mock.Mock()
    job.has_changed.return_value = True

    content = mock.MagicMock()
    content.contentHandler = BBContentHandler(id=BBResourceType.Blankpage)
    content.availability = True
    content.id = api_path['content_id']
    content.body = False

    with mock.patch(get_module('unhandled.Unhandled')) as p:
        Content(content, api_path, job)
        p.assert_called_once_with(content, api_path, job)


def test_unhandled():
    executor = mock.Mock()

    content = Unhandled(mock.Mock(title="Content title"), None, mock.Mock())
    content.write(None, executor)
    executor.submit.assert_not_called()
