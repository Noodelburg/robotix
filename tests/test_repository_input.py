import json
import tempfile
import unittest
from pathlib import Path

from repository_input import build_repository_input_document


class RepositoryInputTests(unittest.TestCase):
    def test_build_repository_input_document_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "repo"
            chunks_dir = root / "chunks"
            root.mkdir()
            chunks_dir.mkdir()
            source_file = root / "app.py"
            source_file.write_text("print('hi')\nprint('bye')\n", encoding="utf-8")
            manifest_path = chunks_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "root": str(root),
                        "chunk_count": 1,
                        "max_lines": 10,
                        "source_file_count": 1,
                        "chunks": [
                            {
                                "id": "chunk-0001",
                                "name": "app",
                                "reason": "single file",
                                "file": "chunk-0001.txt",
                                "total_lines": 2,
                                "files": ["app.py"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = build_repository_input_document(chunks_dir)

            self.assertEqual(payload["root"], str(root.resolve()))
            self.assertEqual(payload["source"]["chunk_count"], 1)
            self.assertEqual(payload["chunks"][0]["id"], "chunk-0001")
            self.assertEqual(payload["chunks"][0]["file_count"], 1)
            self.assertEqual(payload["chunks"][0]["total_lines"], 2)
            self.assertEqual(
                payload["chunks"][0]["files"],
                [{"path": "app.py", "lines": 2}],
            )


if __name__ == "__main__":
    unittest.main()
