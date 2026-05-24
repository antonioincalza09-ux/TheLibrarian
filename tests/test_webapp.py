from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from src.config import RuntimeConfig
from src.webapp import create_server


class WebAppTests(unittest.TestCase):
    def test_server_exposes_inventory_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                inventory = json.loads(urlopen(f"http://{host}:{port}/api/inventory", timeout=5).read())
                plan = json.loads(urlopen(f"http://{host}:{port}/api/plan", timeout=5).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(inventory["summary"]["total_files"], 1)
            self.assertEqual(plan["entries"][0]["destination"], "Documents/report.pdf")

    def test_apply_endpoint_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            server = create_server(root, host="127.0.0.1", port=0, config=RuntimeConfig())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                with self.assertRaises(HTTPError) as error:
                    urlopen(f"http://{host}:{port}/api/apply", data=b"{}", timeout=5).read()
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
