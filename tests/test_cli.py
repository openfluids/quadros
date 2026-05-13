from __future__ import annotations

from neksnap.cli import build_parser


def test_parser_exposes_expected_commands() -> None:
    parser = build_parser()
    actions = [action for action in parser._actions if action.dest == "command"]
    choices = set(actions[0].choices)
    assert {"doctor", "render", "render-many", "inspect", "encode", "extract-camera"} <= choices
