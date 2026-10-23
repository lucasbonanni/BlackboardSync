from datetime import datetime
from enum import Enum
from typing import Any

from pathvalidate import sanitize_filename
from pydantic import BaseModel, ConfigDict, field_validator


class ImmutableModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class BBDurationType(str, Enum):
    Continuous = "Continuous"
    DateRange = "DateRange"
    FixedNumDays = "FixedNumDays"
    Term = "Term"
    Other = "__bblearn_other"

    @classmethod
    def _missing_(cls, value: Any) -> "BBDurationType":
        return cls.Other


class BBDuration(ImmutableModel):
    type: BBDurationType | None = None


class BBLocale(ImmutableModel):
    force: bool = False


class BBEnrollment(ImmutableModel):
    type: str | None = None


class BBProctoring(ImmutableModel):
    secureBrowserRequiredToTake: bool = False
    secureBrowserRequiredToReview: bool = False
    webcamRequired: bool = False


class BBFile(ImmutableModel):
    fileName: str | None = None


class BBAttachment(ImmutableModel):
    id: str
    fileName: str | None = None
    mimeType: str | None = None


class BBLink(ImmutableModel):
    href: str | None = None
    rel: str | None = None
    title: str | None = None
    type: str | None = None


class BBAvailable(str, Enum):
    Yes = "Yes"
    Term = "Term"
    No = "No"
    Disabled = "Disabled"
    PartiallyVisible = "PartiallyVisible"
    Other = "__bblearn_other"

    @classmethod
    def _missing_(cls, value: Any) -> "BBAvailable":
        return cls.Other

    def __bool__(self) -> bool:
        return self not in (BBAvailable.No, BBAvailable.Disabled)


class BBAvailability(ImmutableModel):
    available: BBAvailable | None = None
    allowGuests: bool = False
    adaptiveRelease: dict[str, str] = {}
    duration: BBDuration | None = None

    def __bool__(self) -> bool:
        return bool(self.available)


class BBMembership(ImmutableModel):
    id: str | None = None
    userId: str | None = None
    courseId: str
    dataSourceId: str | None = None
    created: datetime | None = None
    modified: datetime | None = None
    availability: BBAvailability | None = None
    courseRoleId: str | None = None
    lastAccessed: datetime | None = None
    childCourseId: str | None = None


class BBResourceType(str, Enum):
    Folder = "x-bb-folder"
    File = "x-bb-file"
    Document = "x-bb-document"
    ExternalLink = "x-bb-externallink"
    ToolLink = "x-bb-toollink"
    Turnitin_Assignment = "x-turnitin-assignment"
    BLTIPlacement_Portal = "x-bb-bltiplacement-Portal"
    Assignment = "x-bb-assignment"
    Asmt_Test_Link = "x-bb-asmt-test-link"
    Syllabus = "x-bb-syllabus"
    CourseLink = "x-bb-courselink"
    Blankpage = "x-bb-blankpage"
    Lesson = "x-bb-lesson"
    Other = "__bblearn_other"

    @classmethod
    def _missing_(cls, value: Any) -> "BBResourceType":
        return cls.Other


class BBContentHandler(ImmutableModel):
    id: BBResourceType | None = None
    url: str | None = None
    file: BBFile | None = None
    gradeColumnId: str | None = None
    groupContent: bool | None = None
    targetId: str | None = None
    targetType: str | None = None
    placementHandle: str | None = None
    assessmentId: str | None = None
    proctoring: BBProctoring | None = None

    @field_validator("id", mode="before")
    @classmethod
    def normalize_resource_type(cls, value: Any) -> Any:
        if value is None:
            return BBResourceType.Other
        if isinstance(value, str):
            return value.removeprefix("resource/")
        return value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BBResourceType):
            return self.id == other
        if isinstance(other, Enum):
            return False
        if isinstance(other, str):
            try:
                return self.id == BBResourceType(other.removeprefix("resource/"))
            except ValueError:
                return False
        if isinstance(other, BBContentHandler):
            return super().__eq__(other)
        return False

    def __str__(self) -> str:
        return str(self.id)


class BBCourseContent(ImmutableModel):
    id: str
    title: str | None = None
    body: str | None = None
    created: datetime | None = None
    modified: datetime | None = None
    position: int = 0
    hasChildren: bool = False
    parentId: str | None = None
    launchInNewWindow: bool = False
    reviewable: bool = False
    availability: BBAvailability | None = None
    contentHandler: BBContentHandler | None = None
    links: list[BBLink] = []
    hasGradebookColumns: bool = False
    hasAssociatedGroups: bool = False

    def __str__(self) -> str:
        return self.title or "Untitled"

    @property
    def title_path_safe(self) -> str:
        return (
            sanitize_filename(self.title or "Untitled", replacement_text="_")
            or "Untitled"
        )


class BBCourse(ImmutableModel):
    id: str
    courseId: str | None = None
    name: str | None = None
    description: str | None = None
    created: datetime | None = None
    modified: datetime | None = None
    organization: bool = False
    ultraStatus: str | None = None
    closedComplete: bool = False
    availability: BBAvailability | None = None
    enrollment: BBEnrollment | None = None
    locale: BBLocale | None = None
    externalAccessUrl: str | None = None

    @property
    def code(self) -> str | None:
        return self.name.split(" : ", 1)[0] if self.name else None

    @property
    def title(self) -> str | None:
        if not self.name:
            return None
        title = self.name.split(" : ", 1)[-1].split(",")[0]
        return sanitize_filename(title, replacement_text="_")
