from __future__ import annotations

import json

import pytest

from backtest.logical_groups import groups_as_mapping, parse_logical_groups
from src.ui_services import build_trade_markers, load_chart_groups, load_chart_symbols


def test_missing_groups_falls_back_to_singletons() -> None:
    groups = parse_logical_groups({}, ["local:TA0001.ZCE", "RB_MAIN"])
    assert [group.as_dict() for group in groups] == [
        {
            "logical_symbol": "TA0001.ZCE",
            "display_name": "TA0001.ZCE",
            "codes": ["TA0001.ZCE"],
            "chart_code": "TA0001.ZCE",
        },
        {
            "logical_symbol": "RB_MAIN",
            "display_name": "RB_MAIN",
            "codes": ["RB_MAIN"],
            "chart_code": "RB_MAIN",
        },
    ]


def test_multiple_logical_groups_are_independent() -> None:
    groups = parse_logical_groups(
        {
            "codes": ["local:TA1", "local:TA2", "local:RB1"],
            "logical_groups": [
                {"logical_symbol": "TA", "display_name": "TA主连", "codes": ["local:TA1", "local:TA2"]},
                {"logical_symbol": "RB", "display_name": "RB主连", "codes": ["local:RB1"]},
            ],
        }
    )
    assert groups_as_mapping(groups) == {"TA": ["TA1", "TA2"], "RB": ["RB1"]}
    assert groups[0].chart_code == "TA1"
    assert groups[1].display_name == "RB主连"


@pytest.mark.parametrize(
    "config, message",
    [
        ({"codes": ["A", "B"], "logical_groups": [{"logical_symbol": "G", "codes": ["A", "B"]}, {"logical_symbol": "H", "codes": ["B"]}]}, "multiple"),
        ({"codes": ["A"], "logical_groups": [{"logical_symbol": "G", "codes": ["B"]}]}, "not present"),
        ({"codes": ["A"], "logical_groups": [{"logical_symbol": "G", "codes": ["A"], "chart_code": "B"}]}, "chart_code"),
    ],
)
def test_invalid_group_config_fails_closed(config: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_logical_groups(config)


def test_group_member_trade_markers_are_mapped_to_chart_code() -> None:
    markers = build_trade_markers(
        [
            {"code": "TA0002.ZCE", "side": "BUY", "timestamp": "2024-01-01", "price": "10", "qty": "1"},
        ],
        symbols={"TA0001.ZCE"},
        code_aliases={"TA0002.ZCE": "TA0001.ZCE"},
    )
    assert len(markers) == 1
    assert markers[0]["code"] == "TA0001.ZCE"


def test_chart_groups_keep_multiple_logical_instruments_separate(tmp_path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "codes": ["TA0001.ZCE", "TA0002.ZCE", "RB0001.ZCE"],
                "logical_groups": [
                    {"logical_symbol": "TA", "display_name": "TA主连", "codes": ["TA0001.ZCE", "TA0002.ZCE"]},
                    {"logical_symbol": "RB", "display_name": "RB主连", "codes": ["RB0001.ZCE"]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for code in ("TA0001.ZCE", "TA0002.ZCE", "RB0001.ZCE"):
        (artifacts / f"ohlcv_{code}.csv").write_text(
            "timestamp,open,high,low,close,volume,trade_date\n"
            "2024-01-01 09:00:00,1,1,1,1,1,2024-01-01\n",
            encoding="utf-8",
        )

    assert load_chart_symbols(run_dir) == ["TA0001.ZCE", "RB0001.ZCE"]
    assert [group["display_name"] for group in load_chart_groups(run_dir)] == ["TA主连", "RB主连"]
