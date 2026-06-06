"""Landing-pad validity classification.

STUB MODULE. The competition organisers have NOT published the rule that
determines whether an ArUco-marked landing pad is "valid" or "invalid" for
the Reconnaissance challenge. The default placeholder treats even marker IDs
as valid and odd marker IDs as invalid; this is a guess to keep the pipeline
end-to-end testable.

When the organisers publish the real rule, the expected change is a one-line
edit to the lambda for `_RULES[_DEFAULT_RULE]` (currently the `'even'` entry),
or — if the rule needs lookup tables / external state — to the body of
`decide_landing_validity`.

Runtime override
----------------
The environment variable ``MAPPING_DRONE_VALIDITY`` selects an alternate rule
at startup without code changes. Accepted values:

    even          even IDs valid (DEFAULT)
    odd           odd IDs valid
    all_valid     every detected pad valid
    all_invalid   every detected pad invalid
    id_below_50   IDs with value < 50 valid

Any other value falls back to the default with a warning.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)

_ENV_VAR = "MAPPING_DRONE_VALIDITY"
_DEFAULT_RULE = "even"

_RULES: dict[str, Callable[[int], bool]] = {
    "even": lambda aid: (aid % 2) == 0,
    "odd": lambda aid: (aid % 2) == 1,
    "all_valid": lambda aid: True,
    "all_invalid": lambda aid: False,
    "id_below_50": lambda aid: aid < 50,
}

_RULE_DESCRIPTIONS: dict[str, str] = {
    "even": "even ArUco IDs valid, odd IDs invalid (PLACEHOLDER — org has not published the real rule)",
    "odd": "odd ArUco IDs valid, even IDs invalid",
    "all_valid": "every detected landing pad classified valid",
    "all_invalid": "every detected landing pad classified invalid",
    "id_below_50": "ArUco IDs < 50 valid, IDs >= 50 invalid",
}


def _active_rule_name() -> str:
    raw = os.environ.get(_ENV_VAR, "").strip().lower()
    if not raw:
        return _DEFAULT_RULE
    if raw not in _RULES:
        logger.warning(
            "%s=%r is not a known rule (choose from %s); falling back to %r",
            _ENV_VAR,
            raw,
            sorted(_RULES.keys()),
            _DEFAULT_RULE,
        )
        return _DEFAULT_RULE
    return raw


def decide_landing_validity(aruco_id: int) -> bool:
    """Classify a landing pad by its ArUco marker ID.

    STUB. Org has not published the rule. Default placeholder: even IDs valid.
    REPLACE this function body when org publishes the actual rule — typically
    a one-line change to ``_RULES[_DEFAULT_RULE]`` (currently the ``'even'``
    lambda) or this function.

    Honours the ``MAPPING_DRONE_VALIDITY`` env var; see module docstring.
    """
    rule_name = _active_rule_name()
    return _RULES[rule_name](int(aruco_id))


def describe_rule() -> str:
    """Human-readable description of the currently active validity rule.

    Intended for the controller to log at startup, e.g.:
        logger.info("current validity rule: %s", describe_rule())
    """
    rule_name = _active_rule_name()
    source = "env override" if os.environ.get(_ENV_VAR, "").strip().lower() in _RULES else "default"
    return f"{rule_name} ({source}) — {_RULE_DESCRIPTIONS[rule_name]}"


__all__ = ["decide_landing_validity", "describe_rule"]
