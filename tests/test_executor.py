import logging
import time

from blackboard_sync import executor as executor_module
from blackboard_sync.executor import SyncExecutor


def test_shutdown_logs_while_workers_are_pending(caplog, monkeypatch):
    monkeypatch.setattr(executor_module, "SHUTDOWN_LOG_INTERVAL", 0.005)
    executor = SyncExecutor(max_workers=1)
    executor.submit(time.sleep, 0.03)

    with caplog.at_level(logging.WARNING, logger="blackboard_sync.executor"):
        executor.shutdown()

    assert "Still waiting for 1 download worker(s)" in caplog.text