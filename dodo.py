"""DoIt Script. Run all tasks with `poetry run doit` or single task with `poetry run doit run update_cl`."""

from pathlib import Path

from dash_dev.doit_base import DIG, task_check_req, task_export_req  # noqa: F401
from dash_dev.doit_doc import (task_create_tag, task_document, task_open_docs, task_remove_tag,  # noqa: F401
                               task_update_cl)
from dash_dev.doit_lint import task_lint  # noqa: F401
from dash_dev.doit_test import (task_coverage, task_open_test_docs, task_test, task_test_keyword,  # noqa: F401
                                task_test_marker)

# Configure Dash paths
DIG.set_paths(Path(__file__).parent)

# Create list of all tasks run with `poetry run doit`
DOIT_CONFIG = {
    'action_string_formatting': 'old',  # Required for keyword-based tasks
    'default_tasks': [
        'export_req', 'check_req', 'update_cl',  # Comment on/off as needed
        # 'lint',  # Comment on/off as needed
        'coverage',  # Comment on/off as needed
        'open_test_docs',  # Comment on/off as needed
        'document',  # Comment on/off as needed
        'open_docs',  # Comment on/off as needed
    ],
}
"""DoIt Configuration Settings. Run with `poetry run doit`."""
