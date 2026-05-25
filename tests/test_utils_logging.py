import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import utils  # noqa: E402


class FakeHandler:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeQueueListener:
    instances = []

    def __init__(self, queue, handler):
        self.queue = queue
        self.handlers = [handler]
        self.started = False
        self.stopped = False
        FakeQueueListener.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class LoggingSetupTests(unittest.TestCase):
    def tearDown(self):
        utils.queue_listener = None
        utils._log_listener_started = False
        FakeQueueListener.instances.clear()

    def test_log_listener_is_created_lazily_and_closes_handler(self):
        handler = FakeHandler()

        with patch.object(utils, "setup_file_handler", return_value=handler), patch.object(
            utils.logging.handlers, "QueueListener", FakeQueueListener
        ):
            self.assertIsNone(utils.queue_listener)
            utils.StartLogListener()
            self.assertTrue(FakeQueueListener.instances[0].started)

            utils.StopLogListener()
            self.assertTrue(FakeQueueListener.instances[0].stopped)
            self.assertTrue(handler.closed)
            self.assertIsNone(utils.queue_listener)


if __name__ == "__main__":
    unittest.main()
