"""Offline GitHub issue-form shape/privacy checks, including sanitized exports."""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / ".github/ISSUE_TEMPLATE"
FORMS = ("bug_report.yml", "feature_request.yml", "compatibility_report.yml")


class UniqueKeysLoader(yaml.SafeLoader):
    pass


def mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise ValueError("Duplicate YAML key: " + str(key))
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueKeysLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def load(path):
    return yaml.load(path.read_text(), Loader=UniqueKeysLoader)


@pytest.mark.parametrize("name", FORMS)
def test_issue_forms_have_supported_fields_unique_ids_and_public_privacy_warning(name):
    form = load(DIRECTORY / name)
    assert set(form) == {"name", "description", "title", "body"}
    assert all(isinstance(form[k], str) and form[k].strip() for k in ("name", "description", "title"))
    assert len(form["name"]) <= 64
    assert isinstance(form["body"], list) and len(form["body"]) >= 3
    assert form["body"][0]["type"] == "markdown"
    notice = form["body"][0]["attributes"]["value"].lower()
    assert "public" in notice and "private" in notice and "game files" in notice
    ids = []
    required = 0
    for field in form["body"]:
        kind = field["type"]
        assert kind in {"markdown", "input", "textarea", "dropdown", "checkboxes"}
        attributes = field["attributes"]
        if kind == "markdown":
            assert set(field) == {"type", "attributes"} and isinstance(attributes["value"], str)
            continue
        assert set(field) <= {"type", "id", "attributes", "validations"}
        assert re.fullmatch(r"[a-z][a-z0-9_-]*", field["id"])
        ids.append(field["id"])
        assert isinstance(attributes["label"], str) and attributes["label"].strip()
        if "validations" in field:
            assert set(field["validations"]) == {"required"}
            assert isinstance(field["validations"]["required"], bool)
            required += field["validations"]["required"]
        if kind == "dropdown":
            assert len(attributes["options"]) >= 2
            assert all(isinstance(x, str) and x.strip() for x in attributes["options"])
        if kind == "checkboxes":
            for option in attributes["options"]:
                assert isinstance(option["label"], str) and isinstance(option["required"], bool)
    assert len(ids) == len(set(ids)) and required >= 2
    # Labels/assignees are deliberately omitted: no dependency on remotely
    # pre-created labels, usernames, or any repository mutation in these tests.


def test_issue_chooser_uses_existing_documentation_not_unconfigured_discussions():
    config = load(DIRECTORY / "config.yml")
    assert config["blank_issues_enabled"] is False
    assert len(config["contact_links"]) == 2
    for link in config["contact_links"]:
        assert set(link) == {"name", "url", "about"}
        prefix = "https://github.com/Wkrotik/OrBeats/blob/main/"
        assert link["url"].startswith(prefix)
        assert (ROOT / link["url"].removeprefix(prefix)).is_file()


def test_reports_distinguish_recovery_and_observed_capacity_from_hardware_limits():
    bug = (DIRECTORY / "bug_report.yml").read_text()
    capacity = (DIRECTORY / "compatibility_report.yml").read_text()
    assert "rollback/recovery" in bug and "fully closed" in bug
    assert "not a measured PS4 maximum" in capacity
    assert "Do not disable guards" in capacity
    assert "untested steps explicitly" in capacity
    assert "not proof of successful gameplay" in capacity
    pr = (ROOT / ".github/pull_request_template.md").read_text()
    assert "tests not run" in pr and "No game files" in pr


def test_template_regressions_are_in_source_only_ci():
    inventory = json.loads((ROOT / "desktop/development/source-ci-tests.json").read_text())
    assert "tests/test_github_templates.py" in inventory["tests"]


def test_yaml_duplicate_keys_are_refused():
    with pytest.raises(ValueError, match="Duplicate YAML key"):
        yaml.load("name: first\nname: second\n", Loader=UniqueKeysLoader)
