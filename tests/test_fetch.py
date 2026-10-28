import hashlib
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tests import _util  # noqa: F401
from harmonia_components import fetch
from harmonia_components.config import Source

BODY = b"tarball bytes"


def source() -> Source:
    s = mock.Mock(spec=Source)
    s.url = "https://example.invalid/x-1.0.tar.gz"
    s.filename = "x-1.0.tar.gz"
    s.sha256 = hashlib.sha256(BODY).hexdigest()
    return s


class FetchRetryTest(unittest.TestCase):
    def setUp(self):
        self.cache = Path(tempfile.mkdtemp())
        patcher = mock.patch.object(fetch.time, "sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def test_connection_reset_is_retried(self):
        calls = [ConnectionResetError(104, "Connection reset by peer"), io.BytesIO(BODY)]
        def urlopen(req, timeout):
            r = calls.pop(0)
            if isinstance(r, Exception):
                raise urllib.error.URLError(r)
            return r
        with mock.patch.object(fetch.urllib.request, "urlopen", urlopen):
            path = fetch.fetch(source(), self.cache)
        self.assertEqual(path.read_bytes(), BODY)
        self.assertEqual(self.sleep.call_count, 1)

    def test_gives_up_after_the_last_attempt(self):
        err = urllib.error.URLError(ConnectionResetError(104, "reset"))
        with mock.patch.object(fetch.urllib.request, "urlopen", side_effect=err) as m:
            with self.assertRaises(urllib.error.URLError):
                fetch.fetch(source(), self.cache)
        self.assertEqual(m.call_count, fetch.ATTEMPTS)

    def test_client_error_is_not_retried(self):
        err = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        with mock.patch.object(fetch.urllib.request, "urlopen", side_effect=err) as m:
            with self.assertRaises(urllib.error.HTTPError):
                fetch.fetch(source(), self.cache)
        self.assertEqual(m.call_count, 1)


if __name__ == "__main__":
    unittest.main()
