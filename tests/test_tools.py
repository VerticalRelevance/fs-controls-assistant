import pytest

from controls_assistant.tools import ToolError, run_tool


def test_known_control_returns_record():
    result = run_tool("get_control_status", {"control_id": "CTL-003"})
    assert result["status"] == "deficient"


@pytest.mark.parametrize(
    "args",
    [
        {"control_id": "ctl-3"},
        {"control_id": 3},
        {},
        {"control_id": "CTL-001", "extra": "x"},
        "CTL-001",
    ],
)
def test_bad_arguments_are_rejected(args):
    with pytest.raises(ToolError):
        run_tool("get_control_status", args)


def test_missing_control_is_an_error():
    with pytest.raises(ToolError, match="No control found"):
        run_tool("get_control_status", {"control_id": "CTL-999"})


def test_unknown_tool_is_rejected():
    with pytest.raises(ToolError, match="Unknown tool"):
        run_tool("delete_control", {"control_id": "CTL-001"})
