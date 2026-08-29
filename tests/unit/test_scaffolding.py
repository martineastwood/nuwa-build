"""Tests for project scaffolding helpers."""

from nuwa_build.scaffolding import create_github_actions


def test_create_github_actions_tests_installed_module(tmp_path):
    """Generated wheel jobs smoke-test the project's import name."""
    create_github_actions(tmp_path, "example_module")

    workflow = (tmp_path / ".github" / "workflows" / "publish.yml").read_text()

    assert "CIBW_TEST_COMMAND: 'python -c \"import example_module\"'" in workflow
    assert 'nim-version: "2.2.10"' in workflow
    assert 'cibw-version: "4.2.0"' in workflow
