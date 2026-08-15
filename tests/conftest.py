from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Automatically tag tests with markers based on directory location."""
    for item in items:
        path = Path(item.fspath)
        parts = path.parts
        if "e2e" in parts:
            item.add_marker(pytest.mark.selenium)
            item.add_marker(pytest.mark.e2e)
        elif "unit" in parts:
            item.add_marker(pytest.mark.unit)
        elif "golden" in parts:
            item.add_marker(pytest.mark.golden)
        elif "property" in parts:
            item.add_marker(pytest.mark.property)
