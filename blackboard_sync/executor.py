# Copyright (C) 2024, Jacob Sánchez Pérez

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

from typing import Any
from collections.abc import Callable
import logging

from concurrent.futures import ThreadPoolExecutor, Future
from concurrent.futures import wait as wait_futures


logger = logging.getLogger(__name__)
SHUTDOWN_LOG_INTERVAL = 30


class SyncExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers: int | None = None) -> None:
        super().__init__(max_workers)
        self.futures: list[Future[Any]] = []

    def submit(self, fn: Callable[..., Any], /,
               *args: Any, **kwargs: Any) -> Future[Any]:
        future = super().submit(fn, *args, **kwargs)
        self.futures.append(future)
        return future

    def shutdown(self, wait: bool = True, *,
                 cancel_futures: bool = False) -> None:
        pending = [future for future in self.futures if not future.done()]
        logger.info("Shutting down download workers (%d pending)", len(pending))

        super().shutdown(wait=False, cancel_futures=cancel_futures)

        if not wait:
            return

        while pending:
            _, pending_set = wait_futures(
                pending, timeout=SHUTDOWN_LOG_INTERVAL
            )
            if pending_set:
                logger.warning(
                    "Still waiting for %d download worker(s)",
                    len(pending_set)
                )
            pending = list(pending_set)

        super().shutdown(wait=True)
        logger.info("Download workers shut down")

    def raise_exceptions(self, timeout: int | None = None) -> None:
        done, _ = wait_futures(self.futures, timeout)

        for future in done:
            future.result()
