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
    lookup        load valid/invalid ID sets from a JSON file (see below)

Any other value falls back to the default with a warning.

Lookup rule
-----------
``lookup`` reads a JSON file with schema::

    {"valid_ids": [int, ...], "invalid_ids": [int, ...]}

Path resolution order:
    1. ``MAPPING_DRONE_VALIDITY_LOOKUP`` env var (absolute or relative path)
    2. ``configs/valid_ids_unknown.json`` resolved against CWD

For the lookup rule, ``decide_landing_validity`` returns ``True`` if the ID
is in ``valid_ids``, ``False`` if it is in ``invalid_ids``, and ``None``
when neither set contains the ID — letting the caller fall back to its own
default policy.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_ENV_VAR = "MAPPING_DRONE_VALIDITY"
_ENV_VAR_LOOKUP = "MAPPING_DRONE_VALIDITY_LOOKUP"
_DEFAULT_RULE = "even"
_DEFAULT_LOOKUP_RELPATH = "configs/valid_ids_unknown.json"

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
    "lookup": "lookup ArUco ID against JSON-defined valid/invalid ID sets (None if unknown)",
}

# Sentinel rule names that don't fit into _RULES (because their signature
# returns Optional[bool] rather than bool). Handled inline in
# decide_landing_validity.
_SPECIAL_RULES = {"lookup"}

# Lookup-rule cache: maps resolved-path -> {"valid": set[int], "invalid": set[int]}.
# Populated lazily on first call; survives process lifetime.
_LOOKUP_CACHE: dict[str, dict[str, set[int]]] = {}


def _resolve_lookup_path() -> Path:
    """Resolve the JSON file path used by the lookup rule.

    Priority: env-var override → CWD-relative default.
    """
    raw = os.environ.get(_ENV_VAR_LOOKUP, "").strip()
    if raw:
        return Path(raw)
    return Path(_DEFAULT_LOOKUP_RELPATH)


def _load_lookup(path: Path) -> dict[str, set[int]]:
    """Load (and cache) the valid/invalid ID sets from a JSON file."""
    key = str(path.resolve()) if path.exists() else str(path)
    cached = _LOOKUP_CACHE.get(key)
    if cached is not None:
        return cached
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    valid = {int(x) for x in data.get("valid_ids", [])}
    invalid = {int(x) for x in data.get("invalid_ids", [])}
    overlap = valid & invalid
    if overlap:
        logger.warning(
            "lookup file %s lists %d IDs in both valid_ids and invalid_ids: %s",
            path,
            len(overlap),
            sorted(overlap),
        )
    bundle = {"valid": valid, "invalid": invalid}
    _LOOKUP_CACHE[key] = bundle
    return bundle


def _active_rule_name() -> str:
    raw = os.environ.get(_ENV_VAR, "").strip().lower()
    if not raw:
        return _DEFAULT_RULE
    if raw not in _RULES and raw not in _SPECIAL_RULES:
        logger.warning(
            "%s=%r is not a known rule (choose from %s); falling back to %r",
            _ENV_VAR,
            raw,
            sorted(set(_RULES.keys()) | _SPECIAL_RULES),
            _DEFAULT_RULE,
        )
        return _DEFAULT_RULE
    return raw


def decide_landing_validity(aruco_id: int) -> Optional[bool]:
    """Classify a landing pad by its ArUco marker ID.

    STUB. Org has not published the rule. Default placeholder: even IDs valid.
    REPLACE this function body when org publishes the actual rule — typically
    a one-line change to ``_RULES[_DEFAULT_RULE]`` (currently the ``'even'``
    lambda) or this function.

    Honours the ``MAPPING_DRONE_VALIDITY`` env var; see module docstring.

    Returns ``True`` / ``False`` for all built-in rules. For the ``lookup``
    rule, may also return ``None`` when the queried ID appears in neither
    the valid nor invalid set.
    """
    rule_name = _active_rule_name()
    aid = int(aruco_id)
    if rule_name == "lookup":
        path = _resolve_lookup_path()
        bundle = _load_lookup(path)
        if aid in bundle["valid"]:
            return True
        if aid in bundle["invalid"]:
            return False
        return None
    return _RULES[rule_name](aid)


def describe_rule() -> str:
    """Human-readable description of the currently active validity rule.

    Intended for the controller to log at startup, e.g.:
        logger.info("current validity rule: %s", describe_rule())
    """
    rule_name = _active_rule_name()
    raw_env = os.environ.get(_ENV_VAR, "").strip().lower()
    source = "env override" if raw_env in _RULES or raw_env in _SPECIAL_RULES else "default"
    desc = _RULE_DESCRIPTIONS[rule_name]
    if rule_name == "lookup":
        path = _resolve_lookup_path()
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        return f"{rule_name} ({source}) — {desc} [file: {resolved}]"
    return f"{rule_name} ({source}) — {desc}"


__all__ = ["decide_landing_validity", "describe_rule"]


# ---------------------------------------------------------------------------
# Module-bottom smoke check.
#
# Loads the default lookup config (if present) and verifies the round-trip:
# every id listed in valid_ids resolves to True, every id in invalid_ids
# resolves to False, and an obviously-absent id resolves to None.
# Skips silently when the default config is missing — production runs that
# never use the lookup rule must not be tripped up by this check.
# ---------------------------------------------------------------------------
def _smoke_check_lookup() -> bool:
    cfg_path = Path(os.environ.get(_ENV_VAR_LOOKUP, "") or _DEFAULT_LOOKUP_RELPATH)
    if not cfg_path.exists():
        logger.debug("validity smoke check: %s missing, skipping", cfg_path)
        return True
    prev_rule = os.environ.get(_ENV_VAR)
    os.environ[_ENV_VAR] = "lookup"
    try:
        bundle = _load_lookup(cfg_path)
        for vid in bundle["valid"]:
            if decide_landing_validity(vid) is not True:
                logger.error("validity smoke check FAILED: valid id %d did not resolve True", vid)
                return False
        for iid in bundle["invalid"]:
            if decide_landing_validity(iid) is not False:
                logger.error("validity smoke check FAILED: invalid id %d did not resolve False", iid)
                return False
        # Pick an ID that is in neither set.
        sentinel = max((bundle["valid"] | bundle["invalid"]), default=0) + 9_999_983
        if decide_landing_validity(sentinel) is not None:
            logger.error("validity smoke check FAILED: sentinel id %d did not resolve None", sentinel)
            return False
        logger.debug(
            "validity smoke check OK: %d valid / %d invalid loaded from %s",
            len(bundle["valid"]),
            len(bundle["invalid"]),
            cfg_path,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — smoke check must never crash import
        logger.warning("validity smoke check raised %s: %s", type(exc).__name__, exc)
        return False
    finally:
        if prev_rule is None:
            os.environ.pop(_ENV_VAR, None)
        else:
            os.environ[_ENV_VAR] = prev_rule


_smoke_check_lookup()
