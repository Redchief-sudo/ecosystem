import pathlib


def test_no_raw_asyncio_create_task_calls():
    """Fail if raw asyncio.create_task calls appear outside the approved whitelist."""
    repo_root = pathlib.Path(__file__).parent.parent
    pattern = "asyncio.create_task("
    whitelist = {
        "utils/task_manager.py",
    }

    offending = []
    for p in repo_root.rglob("*.py"):
        # Skip venv and third-party packages
        if "venv" in p.parts or "site-packages" in p.parts:
            continue
        rel = p.relative_to(repo_root).as_posix()
        # Skip tests and this test file itself
        if rel.startswith("tests/") or rel == "tests/test_no_direct_create_task.py":
            continue
        if rel in whitelist:
            continue
        try:
            text = p.read_text()
        except Exception:
            continue
        if pattern in text:
            offending.append(rel)

    assert not offending, f"Found raw asyncio.create_task calls in: {offending} - please register tasks via utils.task_manager"