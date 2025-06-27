import json
from pathlib import Path
from typing import Dict, List, Tuple, Set

import pytest

from src.a2a_mcp.common.types import CustomAgentCard

# --------------------------------------------------------------------------------------
# Helper utilities (paths adjusted for unit_tests folder depth)
# --------------------------------------------------------------------------------------

# This file lives in project_root / unit_tests / test_agent_cards_validation /
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # move up two levels
AGENT_CARDS_DIR = PROJECT_ROOT / "agent_cards"


def _load_card_paths() -> List[Path]:
    """Return paths for all JSON agent cards."""
    return sorted(AGENT_CARDS_DIR.glob("*.json"))


def _load_card_json(card_path: Path) -> Dict:
    with card_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------------------------------

@pytest.fixture(scope="session")
def all_cards_data() -> List[Tuple[Path, Dict]]:
    return [(p, _load_card_json(p)) for p in _load_card_paths()]


@pytest.fixture(scope="session")
def all_cards(all_cards_data) -> List[Tuple[Path, CustomAgentCard]]:
    parsed = []
    for path, data in all_cards_data:
        card = CustomAgentCard(**data)
        parsed.append((path, card))
    return parsed


# -------------------------------------------------------------------------------------------------
# Test A – schema soundness
# -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("card_path", _load_card_paths())
def test_card_json_is_valid_and_parses(card_path: Path):
    data = _load_card_json(card_path)
    CustomAgentCard(**data)


# -------------------------------------------------------------------------------------------------
# Test B – field-level sanity checks per card
# -------------------------------------------------------------------------------------------------

def test_card_fields_sane(all_cards, all_cards_data):
    data_lookup = {path: data for path, data in all_cards_data}

    for path, card in all_cards:
        # Required string fields
        for field_name in ["name", "url", "description", "version", "modelName"]:
            value = getattr(card, field_name)
            assert isinstance(value, str) and value.strip(), f"{field_name} missing/empty in {path.name}"

        # Skill checks
        assert card.skills, f"No skills defined in {path.name}"
        skill_ids: Set[str] = set()
        for skill in card.skills:
            for attr in ["id", "name", "description"]:
                val = getattr(skill, attr)
                assert isinstance(val, str) and val.strip(), f"Skill {attr} missing in {path.name}"
            assert skill.id not in skill_ids, f"Duplicate skill id '{skill.id}' in {path.name}"
            skill_ids.add(skill.id)

        # Capabilities checks using raw dict to preserve types
        raw_caps = data_lookup[path].get("capabilities", {})
        for key in ["streaming", "pushNotifications", "stateTransitionHistory"]:
            assert key in raw_caps, f"Capability '{key}' missing in {path.name}"
            assert raw_caps[key] in {"True", "False"}, f"Capability '{key}' must be 'True'/'False' in {path.name}"

        # nextAgent type
        assert isinstance(card.nextAgent, list), f"nextAgent must be list in {path.name}"


# -------------------------------------------------------------------------------------------------
# Test C – cross-file integrity
# -------------------------------------------------------------------------------------------------

def test_cross_file_integrity(all_cards):
    urls = [card.url for _, card in all_cards]
    assert len(urls) == len(set(urls)), "Duplicate 'url' entries across agent cards"

    url_set = set(urls)
    for path, card in all_cards:
        for ref in card.nextAgent:
            assert ref in url_set, (
                f"nextAgent reference '{ref}' in {path.name} does not match any agent card 'url'"
            ) 