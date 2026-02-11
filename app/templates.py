from typing import Dict, List

# Slot names are semantic, not classes
# These are requirements, not suggestions

TEMPLATES: Dict[int, List[str]] = {
    2: ["tank", "healer"],
    3: ["tank", "healer", "dps"],
    4: ["tank", "healer", "slow", "dps"],
    5: ["tank", "healer", "slow", "dps", "dps"],
    6: ["tank", "healer", "slow", "cc", "dps", "dps"],
}

LEVELING_6BOX_TEMPLATE = ["tank", "healer", "cc", "dps", "dps", "dps"]

# Hardcore (solo_raid): mandatory tank, Shaman, Bard, Cleric; 4-box = those 4 only, 5-box +1 dps, 6-box +2 dps
HARDCORE_TEMPLATES: Dict[int, List[str]] = {
    4: ["tank", "healer", "slow", "cc"],  # tank, cleric, shaman, bard
    5: ["tank", "healer", "slow", "cc", "dps"],
    6: ["tank", "healer", "slow", "cc", "dps", "dps"],
}


def get_template(box_size: int, focus: str) -> List[str]:
    """
    focus:
      - leveling
      - balanced
      - solo_raid (Hardcore: tank + Shaman + Bard + Cleric required; 5-box +1 dps, 6-box +2 dps)
    """
    if focus == "solo_raid" and box_size >= 4 and box_size in HARDCORE_TEMPLATES:
        return HARDCORE_TEMPLATES[box_size]
    if box_size != 6:
        return TEMPLATES[box_size]
    if focus == "leveling":
        return LEVELING_6BOX_TEMPLATE
    return TEMPLATES[6]
