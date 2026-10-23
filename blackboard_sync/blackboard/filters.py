from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from bwfilters import BWFilter

from .models import BBAttachment, BBMembership


@dataclass
class BBAttachmentFilter:
    mime_types: BWFilter[BBAttachment]

    def filter(self, items: Sequence[BBAttachment]) -> Iterable[BBAttachment]:
        return self.mime_types.filter_wc(lambda item: item.mimeType, items)


@dataclass
class BBMembershipFilter:
    data_sources: BWFilter[BBMembership]
    min_year: int | None = None

    def filter(self, items: Sequence[BBMembership]) -> Iterable[BBMembership]:
        if self.min_year is not None:
            items = [
                item
                for item in items
                if item.created is None or item.created.year >= self.min_year
            ]
        return self.data_sources.filter(lambda item: item.dataSourceId, items)
