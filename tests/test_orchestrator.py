import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import orchestrator


class OrchestratorTests(unittest.TestCase):
    def test_main_runs_full_pipeline_with_updated_validator_imports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            repo.mkdir()

            with patch.object(orchestrator, "TARGET_DIRECTORY", str(repo)), patch.object(
                orchestrator, "run_chunking"
            ) as run_chunking, patch.object(
                orchestrator, "validate_chunks"
            ) as validate_chunks, patch.object(
                orchestrator, "write_repository_input"
            ) as write_repository_input, patch.object(
                orchestrator, "run_mapper"
            ) as run_mapper, patch.object(
                orchestrator, "validate_mapper"
            ) as validate_mapper, patch.object(
                orchestrator, "run_reviewer"
            ) as run_reviewer, patch.object(
                orchestrator, "validate_reviewer"
            ) as validate_reviewer:
                repository_input_path = repo / "chunks" / "repository-input.json"
                write_repository_input.return_value = repository_input_path

                orchestrator.main()

                run_chunking.assert_called_once()
                validate_chunks.assert_called_once_with(Path(orchestrator.DEFAULT_OUTPUT_DIR))
                write_repository_input.assert_called_once_with(Path(orchestrator.DEFAULT_OUTPUT_DIR))
                run_mapper.assert_called_once()
                validate_mapper.assert_called_once()
                run_reviewer.assert_called_once()
                validate_reviewer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
