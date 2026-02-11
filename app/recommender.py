from __future__ import annotations

from pathlib import Path
import csv
import json
from collections import Counter
from itertools import product, combinations
from typing import Dict, List, Optional, Tuple, Set, Any

CATEGORIES = [
    "dps",
    "healing",
    "tanking",
    "pet_tanking",
    "solo",
    "sustain",
    "kite",
    "charm",
]

PORTERS = {"Wizard", "Druid"}
RUN_SPEED = {"Bard", "Druid", "Shaman", "Ranger"}
CHARMERS = {"Enchanter"}

PET_DPS = {"Magician", "Necromancer", "Beastlord"}
KITERS = {"Necromancer", "Druid", "Wizard", "Bard", "Ranger"}

SLOWERS = {"Shaman", "Enchanter"}
CCERS = {"Enchanter", "Bard"}
# Snare (root/snare for charm break safety): Wizard, Druid, Ranger
SNARERS = {"Wizard", "Druid", "Ranger"}

MELEE_DPS = {"Monk", "Rogue", "Ranger", "Berserker"}
CASTER_DPS = {"Wizard", "Magician", "Necromancer", "Enchanter", "Druid"}

TANKS = {"Warrior", "Shadowknight", "Paladin"}
HEALERS = {"Cleric", "Druid", "Shaman"}
PET_TANKERS = {"Magician", "Necromancer", "Beastlord"}


# -----------------------------
# Loaders
# -----------------------------
def load_class_ratings(path: Path) -> Dict[str, Dict[str, Dict[str, int]]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing class ratings file: {path}")

    ratings: Dict[str, Dict[str, Dict[str, int]]] = {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("class_ratings.csv has no header row.")

        required = {"era", "class"} | set(CATEGORIES)
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"class_ratings.csv missing columns: {sorted(missing)}")

        for line_no, row in enumerate(reader, start=2):
            era = (row.get("era") or "").strip()
            cls = (row.get("class") or "").strip()
            if not era or not cls:
                raise ValueError(f"Line {line_no}: era/class cannot be blank.")

            scores: Dict[str, int] = {}
            for cat in CATEGORIES:
                raw = (row.get(cat) or "").strip()
                val = int(raw)
                if not 0 <= val <= 100:
                    raise ValueError(f"Line {line_no}: {cat} must be 0-100, got {val}.")
                scores[cat] = val

            ratings.setdefault(era, {})[cls] = scores

    return ratings


def load_default_comps(path: Path) -> Dict[str, Dict[int, List[Tuple[int, List[str]]]]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing defaults file: {path}")

    defaults: Dict[str, Dict[int, List[Tuple[int, List[str]]]]] = {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("synergies_and_defaults.csv has no header row.")

        required = {"era", "box_size", "rank", "classes"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(
                "synergies_and_defaults.csv missing columns: "
                f"{sorted(missing)}. Expected: era,box_size,rank,classes"
            )

        for line_no, row in enumerate(reader, start=2):
            era = (row.get("era") or "").strip()
            box_size = int((row.get("box_size") or "").strip())
            rank = int((row.get("rank") or "").strip())
            classes_raw = (row.get("classes") or "").strip()

            classes = [c.strip() for c in classes_raw.split("|") if c.strip()]
            if len(classes) != box_size:
                raise ValueError(
                    f"Line {line_no}: classes count ({len(classes)}) must equal box_size ({box_size}). "
                    f"Got: '{classes_raw}'"
                )

            defaults.setdefault(era, {}).setdefault(box_size, []).append((rank, classes))

    for era, by_size in defaults.items():
        for size, items in by_size.items():
            items.sort(key=lambda x: x[0])

    return defaults


def load_rulesets(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing rulesets file: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError("rulesets.json must be a non-empty JSON object at the top level.")

    for key, rs in data.items():
        if not isinstance(rs, dict):
            raise ValueError(f"Ruleset '{key}' must map to an object.")
        for required in ["label", "add_classes_by_era", "remove_classes_by_era", "weight_modifiers"]:
            if required not in rs:
                raise ValueError(f"Ruleset '{key}' missing required field '{required}'.")

    return data


def list_data_files(data_dir: Path) -> Dict[str, str]:
    found = {}
    for name in ["class_ratings.csv", "synergies_and_defaults.csv", "rulesets.json"]:
        found[name] = "FOUND" if (data_dir / name).exists() else "MISSING"
    return found


def load_meta_builds(path: Path) -> Dict[str, Dict[int, List[Tuple[int, List[str]]]]]:
    """Load data/meta_builds.csv. Skips comment lines (#) and blanks. Returns {era: {box_size: [(rank, classes), ...]}}."""
    if not path.exists():
        return {}
    out: Dict[str, Dict[int, List[Tuple[int, List[str]]]]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",", 3)
            if len(parts) < 4:
                continue
            era = (parts[0] or "").strip()
            try:
                box_size = int((parts[1] or "").strip())
                rank = int((parts[2] or "").strip())
            except ValueError:
                continue
            classes_raw = (parts[3] or "").strip()
            classes = [c.strip() for c in classes_raw.split("|") if c.strip()]
            if len(classes) != box_size:
                continue
            out.setdefault(era, {}).setdefault(box_size, []).append((rank, classes))
    for era, by_size in out.items():
        for size in by_size:
            by_size[size].sort(key=lambda x: x[0])
    return out


# -----------------------------
# Availability + Filtering
# -----------------------------
def get_available_classes(
    ratings: Dict[str, Dict[str, Dict[str, int]]],
    era: str,
    ruleset: Dict[str, Any],
) -> List[str]:
    base = set(ratings.get(era, {}).keys())
    add_map = ruleset.get("add_classes_by_era", {}) or {}
    remove_map = ruleset.get("remove_classes_by_era", {}) or {}
    additions = set(add_map.get(era, []) or [])
    removals = set(remove_map.get(era, []) or [])
    final = (base | additions) - removals
    return sorted(final)


def comp_matches_filters(comp: List[str], must_include: Set[str], exclude: Set[str]) -> bool:
    comp_set = set(comp)
    if comp_set & exclude:
        return False
    if not must_include.issubset(comp_set):
        return False
    return True


def comp_matches_constraints(
    comp: List[str],
    require_ports: bool,
    require_run_speed: bool,
    require_charm: bool,
    require_pet_heavy: bool,
    require_kiting: bool,
) -> bool:
    # require_kiting is deprecated in UI; kept for compatibility.
    comp_set = set(comp)

    if require_ports and not (PORTERS & comp_set):
        return False
    if require_run_speed and not (RUN_SPEED & comp_set):
        return False
    if require_charm and "Enchanter" not in comp_set:
        return False
    if require_pet_heavy and not (PET_DPS & comp_set):
        return False
    if require_kiting and not (KITERS & comp_set):
        return False

    return True


def filter_default_comps(
    defaults_for_era_and_size: List[Tuple[int, List[str]]],
    must_include: Set[str],
    exclude: Set[str],
    require_ports: bool,
    require_run_speed: bool,
    require_charm: bool,
    require_pet_heavy: bool,
    require_kiting: bool,
) -> List[Tuple[int, List[str]]]:
    out: List[Tuple[int, List[str]]] = []
    for rank, comp in defaults_for_era_and_size:
        if not comp_matches_filters(comp, must_include, exclude):
            continue
        if not comp_matches_constraints(
            comp,
            require_ports=require_ports,
            require_run_speed=require_run_speed,
            require_charm=require_charm,
            require_pet_heavy=require_pet_heavy,
            require_kiting=require_kiting,
        ):
            continue
        out.append((rank, comp))
    return out


# -----------------------------
# Scoring helpers
# -----------------------------
def get_score(ratings: Dict[str, Dict[str, Dict[str, int]]], era: str, cls: str, cat: str) -> int:
    return ratings.get(era, {}).get(cls, {}).get(cat, 0)


def melee_penalty(boxing_mode: str, cls: str, era: str = "") -> int:
    """Manual boxing: melee DPS is harder to play; apply penalty so they rank below equivalent casters. Ranger in Luclin/PoP uses bow so no penalty."""
    if boxing_mode != "manual":
        return 0
    if cls not in MELEE_DPS:
        return 0
    if cls == "Ranger" and era in ("luclin", "pop"):
        return 0
    return 15


def start_condition_bonus(start: str, cls: str) -> int:
    if start != "fresh":
        return 0
    if cls in PET_DPS:
        return 10
    if cls == "Monk":
        return 6
    return 0


def synergy_bonus(comp: List[str]) -> int:
    bonus = 0
    comp_set = set(comp)

    if "Shadowknight" in comp_set and "Shaman" in comp_set:
        bonus += 18

    melee_count = sum(1 for c in comp if c in MELEE_DPS)
    caster_count = sum(1 for c in comp if c in CASTER_DPS)

    if "Bard" in comp_set and melee_count >= 2:
        bonus += 10

    if "Enchanter" in comp_set and caster_count >= 2:
        bonus += 8

    # Classic 6-box double-melee synergy: Warrior or SK, Shaman, Bard, Cleric, 2x melee DPS (e.g. Monk Monk)
    if len(comp) == 6:
        comp_set = set(comp)
        has_tank_sk_war = bool(comp_set & {"Warrior", "Shadowknight"})
        has_shaman_bard_cleric = "Shaman" in comp_set and "Bard" in comp_set and "Cleric" in comp_set
        melee_dps_in_comp = [c for c in comp if c in MELEE_DPS]
        if has_tank_sk_war and has_shaman_bard_cleric and len(melee_dps_in_comp) >= 2:
            bonus += 28

    return bonus


def _charm_synergy_bonus(comp: List[str]) -> int:
    """When Enchanter is charm-tanking, caster and caster-pet classes get a synergy bonus (no melee when charm pet tanks).
    Magician/Necromancer: high; Beastlord: some; Wizard/Druid (casters): bonus."""
    if "Enchanter" not in comp:
        return 0
    bonus = 0
    for c in comp:
        if c == "Enchanter":
            continue
        if c in {"Magician", "Necromancer"}:
            bonus += 14
        elif c == "Beastlord":
            bonus += 6
        elif c in {"Wizard", "Druid"}:
            bonus += 8
    return bonus


def _manual_partner_allowed(cls: str) -> bool:
    if cls in TANKS:
        return False
    if cls in MELEE_DPS:
        return False
    return True


# -----------------------------
# Role pools
# -----------------------------
def role_candidates(
    available: List[str],
    ratings: Dict[str, Dict[str, Dict[str, int]]],
    era: str,
    role: str,
    boxing_mode: str,
    start: str,
    require_charm: bool,
) -> List[str]:
    avail = list(available)

    def top_by(cat: str, n: int) -> List[str]:
        scored = []
        for c in avail:
            base = get_score(ratings, era, c, cat)
            base += start_condition_bonus(start, c)

            if cat == "dps":
                base -= melee_penalty(boxing_mode, c, era)
                if require_charm and c == "Enchanter":
                    base += 30

            scored.append((base, c))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:n]]

    if role == "tank":
        tank_avail = [c for c in avail if c in TANKS]
        scored = [(get_score(ratings, era, c, "tanking"), c) for c in tank_avail]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:6]]

    if role == "healer":
        healer_avail = [c for c in avail if c in HEALERS]
        scored = [(get_score(ratings, era, c, "healing"), c) for c in healer_avail]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:6]]

    if role == "slow":
        pool = [c for c in avail if c in SLOWERS]
        return pool if pool else top_by("solo", 5)

    if role == "cc":
        pool = [c for c in avail if c in CCERS]
        return pool if pool else top_by("solo", 5)

    if role == "pet_tank":
        pool = [c for c in avail if c in PET_TANKERS]
        scored = [(get_score(ratings, era, c, "pet_tanking"), c) for c in pool]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:6]]

    if role == "charm_tank":
        if "Enchanter" not in avail:
            return []
        return ["Enchanter"]

    if role == "charm_partner":
        # Partner must not be Enchanter (slot 1 is always Enchanter in this mode)
        use = [c for c in avail if c != "Enchanter"]
        if boxing_mode == "manual":
            use = [c for c in use if _manual_partner_allowed(c)]
        scored = []
        for c in use:
            dps = get_score(ratings, era, c, "dps") - melee_penalty(boxing_mode, c, era)
            healing = get_score(ratings, era, c, "healing")
            base = int(dps * 0.85 + healing * 0.15)
            if c in SNARERS:
                base += 15  # snare for charm-break safety
            if c in RUN_SPEED:
                base += 6
            if c in PORTERS:
                base += 5
            base += int(start_condition_bonus(start, c) * 0.5)
            scored.append((base, c))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:10]]

    if role == "pet_partner":
        use = avail
        if boxing_mode == "manual":
            use = [c for c in avail if _manual_partner_allowed(c)]
        scored = []
        for c in use:
            dps = get_score(ratings, era, c, "dps") - melee_penalty(boxing_mode, c, era)
            healing = get_score(ratings, era, c, "healing")
            base = int(dps * 0.85 + healing * 0.15)
            if c in SLOWERS:
                base += 12
            if c in PORTERS:
                base += 5
            if c in RUN_SPEED:
                base += 6
            if c in CCERS:
                base += 5
            if c in PET_DPS:
                base += 8
            base += int(start_condition_bonus(start, c) * 0.5)
            scored.append((base, c))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:10]]

    if role == "kiter":
        pool = [c for c in avail if c in KITERS]
        scored = [(get_score(ratings, era, c, "kite"), c) for c in pool]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:8]]

    if role == "kiter_swarm":
        if "Bard" not in avail:
            return []
        return ["Bard"]

    if role == "kiter_fear_snare":
        pool = [c for c in avail if c in {"Necromancer", "Druid", "Wizard", "Ranger"}]
        scored = [(get_score(ratings, era, c, "kite"), c) for c in pool]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:6]]

    if role == "kite_partner_swarm":
        use = avail
        if boxing_mode == "manual":
            use = [c for c in avail if _manual_partner_allowed(c)]
        scored = []
        for c in use:
            dps = get_score(ratings, era, c, "dps") - melee_penalty(boxing_mode, c, era)
            healing = get_score(ratings, era, c, "healing")
            base = int(healing * 0.60 + dps * 0.40)

            if c in RUN_SPEED:
                base += 10
            if c in SLOWERS:
                base += 6
            if c in PORTERS:
                base += 4

            base += int(start_condition_bonus(start, c) * 0.4)
            scored.append((base, c))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:10]]

    if role == "kite_partner_fear_snare":
        use = avail
        if boxing_mode == "manual":
            use = [c for c in avail if _manual_partner_allowed(c)]
        scored = []
        for c in use:
            dps = get_score(ratings, era, c, "dps") - melee_penalty(boxing_mode, c, era)
            healing = get_score(ratings, era, c, "healing")
            base = int(dps * 0.85 + healing * 0.15)

            if c in RUN_SPEED:
                base += 8
            if c in PORTERS:
                base += 6
            if c in PET_DPS:
                base += 8
            if c in SLOWERS:
                base += 6

            base += int(start_condition_bonus(start, c) * 0.4)
            scored.append((base, c))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:10]]

    if role == "support":
        scored = []
        for c in avail:
            healing = get_score(ratings, era, c, "healing")
            sustain = get_score(ratings, era, c, "sustain")
            solo = get_score(ratings, era, c, "solo")
            kite = get_score(ratings, era, c, "kite")
            charm = get_score(ratings, era, c, "charm")

            base = int(healing * 0.65 + sustain * 0.45 + solo * 0.35 + kite * 0.20 + charm * 0.15)

            if c in SLOWERS:
                base += 14
            if c in CCERS:
                base += 8
            if c in PORTERS:
                base += 6
            if c in RUN_SPEED:
                base += 6

            base += int(start_condition_bonus(start, c) * 0.5)

            if require_charm and c == "Enchanter":
                base += 18

            if boxing_mode == "manual" and c in MELEE_DPS:
                base -= 6

            scored.append((base, c))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for _, c in scored[:10]]

    if role == "dps":
        # Manual boxing: melee is still considered but scores 15 points lower so casters rank above equivalent melee
        return top_by("dps", 10)

    return top_by("solo", 6)


# -----------------------------
# Must-include: best slot for a class when we need to guarantee it appears in some comp
# -----------------------------
def _best_slot_index_for_must_include(
    cls: str,
    template_slots: List[str],
    exclude_indices: Set[int] | None = None,
) -> int:
    """Return slot index where this class should be added so must_include is satisfied. Prefer dps, then tank (for 2-box), then other roles. Skips slots in exclude_indices (e.g. hardcore core)."""
    excluded = exclude_indices or set()
    slot_types_for_class: List[str] = []
    if cls in TANKS:
        slot_types_for_class = ["tank"]
    elif cls in HEALERS:
        slot_types_for_class = ["healer"]
    elif cls in PET_TANKERS:
        slot_types_for_class = ["pet_tank", "pet_partner", "dps"]
    elif cls in SLOWERS:
        slot_types_for_class = ["slow", "cc", "dps"]
    elif cls in CCERS:
        slot_types_for_class = ["cc", "dps"]
    elif cls in CHARMERS:
        slot_types_for_class = ["charm_tank", "cc", "dps"]
    elif cls in KITERS:
        slot_types_for_class = ["kiter_swarm", "kiter_fear_snare", "kiter", "kite_partner_swarm", "kite_partner_fear_snare", "dps"]
    else:
        # DPS/flex (Ranger, Wizard, Monk, Rogue, etc.): prefer dps; then tank (2-box tank/healer); then partner slots (pet/kite); then slow, cc, healer
        slot_types_for_class = [
            "dps", "tank",
            "pet_partner", "charm_partner", "kite_partner_swarm", "kite_partner_fear_snare", "kite_partner",
            "support", "slow", "cc", "healer",
        ]

    for slot_type in slot_types_for_class:
        for i, s in enumerate(template_slots):
            if s == slot_type and i not in excluded:
                return i
    for i in range(len(template_slots)):
        if i not in excluded:
            return i
    return 0


# -----------------------------
# Slot forcing
# -----------------------------
# Slots that can receive constraint forcing (ports, run speed, etc.). Never tank; in hardcore only dps.
def _flex_slot_indices(template_slots: List[str], hardcore_required: bool) -> List[int]:
    """Indices of slots that can be forced to satisfy a constraint. Tank is never flexed; in hardcore only dps slots are."""
    if hardcore_required:
        # Hardcore: only dps slots are flex; tank, healer, slow, cc are core and must not be replaced
        return [i for i, s in enumerate(template_slots) if s == "dps"]
    # 3-box charm: Enchanter is tank (charm_tank); flex is dps first, then healer (e.g. meet SOW with Druid in slot 2, or force healer if needed)
    if template_slots == ["charm_tank", "healer", "dps"]:
        return [2, 1]  # dps slot first, then healer
    # Not hardcore: healer (e.g. Druid for ports), slow, cc, dps can flex; never tank
    order = ["healer", "slow", "cc", "dps", "pet_partner", "charm_partner", "kite_partner_swarm", "kite_partner_fear_snare", "kite_partner", "support"]
    non_flex = {"tank", "charm_tank"}  # charm_tank is filled by Enchanter when require_charm; don't force other constraints into it
    indices: List[int] = []
    for slot_name in order:
        indices.extend([i for i, s in enumerate(template_slots) if s == slot_name])
    indices.extend([i for i, s in enumerate(template_slots) if s not in order and s not in non_flex])
    return indices


def _slot_priority_indices(template_slots: List[str]) -> List[int]:
    order = [
        "kiter_swarm",
        "kiter_fear_snare",
        "kiter",
        "pet_tank",
        "charm_tank",
        "tank",
        "healer",
        "slow",
        "cc",
        "dps",
        "pet_partner",
        "charm_partner",
        "kite_partner_swarm",
        "kite_partner_fear_snare",
        "kite_partner",
        "support",
    ]
    indices: List[int] = []
    for slot_name in order:
        indices.extend([i for i, s in enumerate(template_slots) if s == slot_name])
    indices.extend([i for i, s in enumerate(template_slots) if s not in order])
    return indices


def _build_requirement_sets(
    available_set: Set[str],
    require_ports: bool,
    require_run_speed: bool,
    require_charm: bool,
    require_pet_heavy: bool,
    require_kiting: bool,
    already_satisfied: Set[str],
) -> List[Set[str]]:
    """Build requirement sets for slot forcing. Ports and run speed are never forced (only filtered) so we don't replace tank/healer when Shaman/Bard/Druid already provide them."""
    reqs: List[Set[str]] = []
    # Never force ports or run speed into a slot - only comp_matches_constraints filters; avoids dropping Cleric for Druid or tank for ports
    if require_charm and not (CHARMERS & already_satisfied):
        reqs.append(set(CHARMERS) & available_set)
    if require_pet_heavy and not (PET_DPS & already_satisfied):
        reqs.append(set(PET_DPS) & available_set)
    if require_kiting and not (KITERS & already_satisfied):
        reqs.append(set(KITERS) & available_set)
    return [r for r in reqs if r]


def _best_intersection_group(reqs: List[Set[str]]) -> Tuple[Set[str], List[int]]:
    best_pool: Set[str] = set()
    best_idxs: List[int] = []
    n = len(reqs)

    for k in [3, 2, 1]:
        for idxs in combinations(range(n), k):
            inter = set(reqs[idxs[0]])
            for j in idxs[1:]:
                inter &= reqs[j]
            if not inter:
                continue

            if len(idxs) > len(best_idxs):
                best_pool = inter
                best_idxs = list(idxs)
            elif len(idxs) == len(best_idxs) and best_idxs:
                if len(inter) < len(best_pool):
                    best_pool = inter
                    best_idxs = list(idxs)

        if best_idxs:
            return best_pool, best_idxs

    return best_pool, best_idxs


def force_constraints_into_slots(
    template_slots: List[str],
    available: List[str],
    require_ports: bool,
    require_run_speed: bool,
    require_charm: bool,
    require_pet_heavy: bool,
    require_kiting: bool,
    already_satisfied: Set[str] | None = None,
    hardcore_required: bool = False,
) -> Dict[int, Set[str]]:
    available_set = set(available)
    satisfied = already_satisfied or set()
    reqs = _build_requirement_sets(
        available_set,
        require_ports=require_ports,
        require_run_speed=require_run_speed,
        require_charm=require_charm,
        require_pet_heavy=require_pet_heavy,
        require_kiting=require_kiting,
        already_satisfied=satisfied,
    )
    forced: Dict[int, Set[str]] = {}
    if not reqs:
        return forced

    # Only assign constraints to flex slots (never tank; in hardcore only dps)
    slot_order = _flex_slot_indices(template_slots, hardcore_required)
    if not slot_order:
        return forced
    slot_cursor = 0

    while reqs and slot_cursor < len(slot_order):
        pool, idxs = _best_intersection_group(reqs)
        if not idxs or not pool:
            break

        slot_idx = slot_order[slot_cursor]
        slot_cursor += 1
        forced[slot_idx] = pool

        for i in sorted(idxs, reverse=True):
            del reqs[i]

    return forced


# -----------------------------
# Slot-aware scoring
# -----------------------------
def _slot_value(
    ratings: Dict[str, Dict[str, Dict[str, int]]],
    era: str,
    cls: str,
    slot: str,
    boxing_mode: str,
    comp: Optional[List[str]] = None,
    template_slots: Optional[List[str]] = None,
) -> Tuple[float, Dict[str, float]]:
    if slot in {"kiter_swarm", "kiter_fear_snare"}:
        slot = "kiter"
    if slot in {"kite_partner_swarm", "kite_partner_fear_snare"}:
        slot = "kite_partner"

    dps = float(get_score(ratings, era, cls, "dps") - melee_penalty(boxing_mode, cls, era))
    healing = float(get_score(ratings, era, cls, "healing"))
    tanking = float(get_score(ratings, era, cls, "tanking"))
    pet_tanking = float(get_score(ratings, era, cls, "pet_tanking"))
    sustain = float(get_score(ratings, era, cls, "sustain"))
    kite = float(get_score(ratings, era, cls, "kite"))
    charm = float(get_score(ratings, era, cls, "charm"))

    # Secondary healer: not in healer slot, but is a healer class and comp has a main healer → full DPS + small healing bonus (10–20%)
    if comp is not None and template_slots is not None:
        main_healer = next((comp[i] for i, s in enumerate(template_slots) if s == "healer"), None)
        if (
            slot != "healer"
            and cls in HEALERS
            and main_healer is not None
            and cls != main_healer
        ):
            sec_heal = healing * 0.15
            return (dps + sec_heal, {"dps": dps, "healing": healing, "healing_secondary_bonus": sec_heal})

    # 2-box tank: tanking + sustain + tank DPS all matter
    if slot == "tank":
        val = tanking * 0.45 + sustain * 0.30 + dps * 0.25
        return val, {"tanking": tanking, "sustain": sustain, "dps": dps}

    if slot == "pet_tank":
        val = pet_tanking * 1.00 + sustain * 0.15
        return val, {"pet_tanking": pet_tanking, "sustain": sustain}

    if slot == "kiter":
        val = kite * 1.00 + sustain * 0.25
        return val, {"kite": kite, "sustain": sustain}

    if slot == "charm_tank":
        val = charm * 1.00 + sustain * 0.20
        return val, {"charm": charm, "sustain": sustain}

    # healer: sustain does not matter here (slow handled separately in comp logic)
    if slot == "healer":
        val = healing * 1.00
        return val, {"healing": healing}

    # 2-box partner slots: charm and sustain don't matter; score on dps + healing only
    if slot in {"kite_partner", "pet_partner", "charm_partner"}:
        val = healing * 0.50 + dps * 0.50
        return val, {"healing": healing, "dps": dps}

    if slot in {"slow", "cc", "support"}:
        val = healing * 0.35 + dps * 0.35 + charm * 0.20 + sustain * 0.15
        return val, {"healing": healing, "dps": dps, "charm": charm, "sustain": sustain}

    val = dps * 1.00
    return val, {"dps": dps}


def score_comp_explain(
    comp: List[str],
    ratings: Dict[str, Dict[str, Dict[str, int]]],
    era: str,
    boxing_mode: str,
    start: str,
    require_charm: bool,
    template_slots: List[str],
    hardcore_required: bool = False,
    require_run_speed: bool = False,
    require_ports: bool = False,
) -> Tuple[int, Dict[str, Any]]:
    slot_breakdowns = []
    slot_total = 0.0
    start_bonus_total = 0
    charm_bonus_applied = 0
    hardcore_warrior_bonus = 0
    constraint_already_met_bonus = 0

    best_tank_metric_name = "tanking"
    best_tank_value = 0.0
    best_heal_value = 0.0

    tank_count = sum(1 for c in comp if c in TANKS)

    for slot, cls in zip(template_slots, comp):
        base_val, breakdown = _slot_value(ratings, era, cls, slot, boxing_mode, comp=comp, template_slots=template_slots)

        if require_charm and cls == "Enchanter":
            base_val += 30
            charm_bonus_applied = 30

        # Hardcore: Warrior defensives matter; bonus applied to total below so Warrior at least matches SK
        if hardcore_required and slot == "tank" and cls == "Warrior":
            hardcore_warrior_bonus = 18

        sb = start_condition_bonus(start, cls)
        start_bonus_total += sb

        slot_total += base_val
        slot_breakdowns.append(
            {"slot": slot, "class": cls, "value": base_val, "breakdown": breakdown, "start_bonus": sb}
        )

        if slot == "healer":
            best_heal_value = max(best_heal_value, float(get_score(ratings, era, cls, "healing")))

        if slot == "tank":
            best_tank_metric_name = "tanking"
            best_tank_value = max(best_tank_value, float(get_score(ratings, era, cls, "tanking")))
        if slot == "pet_tank":
            best_tank_metric_name = "pet_tanking"
            best_tank_value = max(best_tank_value, float(get_score(ratings, era, cls, "pet_tanking")))

    syn_bonus = synergy_bonus(comp)
    charm_synergy = _charm_synergy_bonus(comp)

    # Run speed / ports checked: prefer comps that already have them (Bard/Shaman, Wizard/Druid) so we don't swap Cleric for Druid or drop Bard for Enchanter
    comp_set = set(comp)
    if require_run_speed and (comp_set & {"Bard", "Shaman"}):
        constraint_already_met_bonus += 28
    if require_ports and (comp_set & PORTERS):
        constraint_already_met_bonus += 15

    # 6-box assisted/macroquest non-fresh: bonus for classic double-melee comp (no Enchanter) so it ranks at top
    classic_double_melee_bonus = 0
    if (
        len(comp) == 6
        and boxing_mode in ("assisted", "macroquest")
        and start != "fresh"
    ):
        has_tank = bool(comp_set & {"Warrior", "Shadowknight"})
        has_shaman_bard_cleric = "Shaman" in comp_set and "Bard" in comp_set and "Cleric" in comp_set
        melee_dps_count = sum(1 for c in comp if c in MELEE_DPS)
        no_ench = "Enchanter" not in comp_set
        if has_tank and has_shaman_bard_cleric and melee_dps_count >= 2 and no_ench:
            classic_double_melee_bonus = 22

    # Charm + snare: 2/3-box with Enchanter gets bonus if group has snare (Wiz/Druid/Ranger) for charm-break safety
    charm_snare_bonus = 0
    if len(comp) in (2, 3) and ("Enchanter" in comp or require_charm) and (set(comp) & SNARERS):
        charm_snare_bonus = 18

    slow_logic = {"applied": False, "has_slow": False, "bonus_or_penalty": 0, "note": ""}
    has_slow = any(c in SLOWERS for c in comp)

    # Traditional 2-box only: slow should heavily influence outcomes
    if len(comp) == 2 and template_slots == ["tank", "healer"]:
        slow_logic["applied"] = True
        slow_logic["has_slow"] = has_slow
        if has_slow:
            slow_logic["bonus_or_penalty"] = 20
            slow_logic["note"] = "2-box tank+healer: slow is core, bonus applied."
        else:
            slow_logic["bonus_or_penalty"] = -25
            slow_logic["note"] = "2-box tank+healer: no slow, penalty applied."

    tank_stack_penalty = 0
    if tank_count >= 2:
        tank_stack_penalty = -40 * (tank_count - 1)

    total = int(
        slot_total
        + syn_bonus
        + charm_synergy
        + classic_double_melee_bonus
        + hardcore_warrior_bonus
        + constraint_already_met_bonus
        + start_bonus_total * 0.4
        + slow_logic["bonus_or_penalty"]
        + tank_stack_penalty
        + charm_snare_bonus
    )

    summary_lines = []
    summary_lines.append(f"Tank metric used: {best_tank_metric_name} | Best tank value: {int(best_tank_value)}")
    if "healer" in template_slots:
        summary_lines.append(f"Best healer value: {int(best_heal_value)}")
    summary_lines.append(f"Slot score sum: {slot_total:.1f}")
    if slow_logic["applied"]:
        summary_lines.append(f"Slow check: {'YES' if has_slow else 'NO'} ({slow_logic['bonus_or_penalty']:+d})")
    if syn_bonus:
        summary_lines.append(f"Synergy bonus: +{syn_bonus}")
    if charm_synergy:
        summary_lines.append(f"Charm caster/pet synergy: +{charm_synergy} (casters and pet classes, no melee when charm tanks)")
    if start_bonus_total:
        summary_lines.append(f"Start bonuses: +{start_bonus_total} (fresh start)")
    if tank_stack_penalty:
        summary_lines.append(f"Tank stacking penalty: {tank_stack_penalty}")
    if charm_snare_bonus:
        summary_lines.append(f"Charm + snare bonus: +{charm_snare_bonus} (snare for charm-break safety)")
    if classic_double_melee_bonus:
        summary_lines.append(f"Classic 6-box double-melee bonus: +{classic_double_melee_bonus} (Warrior/SK, Shaman, Bard, Cleric, 2x melee)")
    if hardcore_warrior_bonus:
        summary_lines.append(f"Hardcore Warrior bonus: +{hardcore_warrior_bonus} (defensives)")
    if constraint_already_met_bonus:
        summary_lines.append(f"Constraint already in group: +{constraint_already_met_bonus} (run speed/ports from Bard/Shaman/porter)")

    detail = {
        "summary_lines": summary_lines,
        "era": era,
        "boxing_mode": boxing_mode,
        "start": start,
        "require_charm": require_charm,
        "charm_bonus_applied": charm_bonus_applied,
        "charm_synergy": charm_synergy,
        "template_slots": template_slots,
        "slot_breakdowns": slot_breakdowns,
        "slow_logic": slow_logic,
        "synergy_bonus": syn_bonus,
        "start_bonus_total": start_bonus_total,
        "tank_count": tank_count,
        "tank_stack_penalty": tank_stack_penalty,
        "charm_snare_bonus": charm_snare_bonus,
        "classic_double_melee_bonus": classic_double_melee_bonus,
        "hardcore_warrior_bonus": hardcore_warrior_bonus,
        "constraint_already_met_bonus": constraint_already_met_bonus,
        "total": total,
    }
    return total, detail


def generate_scored_recommendations(
    *,
    ratings: Dict[str, Dict[str, Dict[str, int]]],
    era: str,
    available: List[str],
    template_slots: List[str],
    boxing_mode: str,
    start: str,
    must_include: Set[str],
    exclude: Set[str],
    require_ports: bool,
    require_run_speed: bool,
    require_charm: bool,
    require_pet_heavy: bool,
    require_kiting: bool,
    hardcore_required: bool = False,
    limit: int = 15,
    return_explain: bool = False,
) -> List[Any]:
    available_set = set(available)
    # Classes already in every comp for this template (e.g. Hardcore forces Cleric, Shaman, Bard) – don't force slots for those
    already_satisfied: Set[str] = set()
    if hardcore_required:
        already_satisfied = {c for c in ["Cleric", "Shaman", "Bard"] if c in available_set}
    # 3-box charm: charm_tank slot is Enchanter; don't force Enchanter into healer slot
    if "charm_tank" in template_slots and require_charm:
        already_satisfied = already_satisfied | (CHARMERS & available_set)

    forced_slots = force_constraints_into_slots(
        template_slots=template_slots,
        available=available,
        require_ports=require_ports,
        require_run_speed=require_run_speed,
        require_charm=require_charm,
        require_pet_heavy=require_pet_heavy,
        require_kiting=require_kiting,
        already_satisfied=already_satisfied,
        hardcore_required=hardcore_required,
    )

    # Hardcore (4+ box): mandatory Cleric (healer), Shaman (slow), Bard (cc); tank and dps slots unchanged
    hardcore_forced: Dict[int, List[str]] = {}
    if hardcore_required:
        if "healer" in template_slots and "Cleric" in available_set:
            for i, s in enumerate(template_slots):
                if s == "healer":
                    hardcore_forced[i] = ["Cleric"]
                    break
        if "slow" in template_slots and "Shaman" in available_set:
            for i, s in enumerate(template_slots):
                if s == "slow":
                    hardcore_forced[i] = ["Shaman"]
                    break
        if "cc" in template_slots and "Bard" in available_set:
            for i, s in enumerate(template_slots):
                if s == "cc":
                    hardcore_forced[i] = ["Bard"]
                    break

    slot_pools: List[List[str]] = []
    for i, slot in enumerate(template_slots):
        if i in hardcore_forced:
            pool = list(hardcore_forced[i])
        elif i in forced_slots:
            pool = sorted(forced_slots[i])
        else:
            pool = role_candidates(available, ratings, era, slot, boxing_mode, start, require_charm)
        slot_pools.append(pool)

    # Must-include: ensure every required class can appear in some comp by adding it to the best slot pool (never into hardcore core slots)
    hardcore_slot_indices = set(hardcore_forced.keys())
    for cls in must_include:
        if cls not in available_set or cls in exclude:
            continue
        if any(cls in pool for pool in slot_pools):
            continue
        idx = _best_slot_index_for_must_include(cls, template_slots, exclude_indices=hardcore_slot_indices)
        if idx < len(slot_pools):
            slot_pools[idx] = list(slot_pools[idx])
            if cls not in slot_pools[idx]:
                slot_pools[idx].append(cls)

    results: List[Any] = []
    seen: Set[Tuple[str, ...]] = set()

    # When there are 2+ DPS slots (5-box or 6-box), allow duplicating a class for DPS (e.g. Monk Monk, Wizard Wizard)
    allow_duplicate_dps = template_slots.count("dps") >= 2

    for picks in product(*slot_pools):
        comp = list(picks)
        # No duplicate classes, except allow one duplicated class in DPS when we have 2+ dps slots (never 2x Enchanter).
        # Manual: duplicate must be caster or Ranger (Luclin/PoP). Assisted/macro: melee duplicate OK too.
        if len(comp) != len(set(comp)):
            if not allow_duplicate_dps:
                continue
            counts = Counter(comp)
            if any(n > 1 for cls, n in counts.items() if cls == "Enchanter"):
                continue  # never allow 2x Enchanter
            if boxing_mode == "manual":
                if any(
                    n > 1 and (cls in MELEE_DPS and not (cls == "Ranger" and era in ("luclin", "pop")))
                    for cls, n in counts.items()
                ):
                    continue  # manual: only caster or Ranger (luclin/pop) can duplicate
        key = tuple(comp)
        if key in seen:
            continue
        seen.add(key)

        if not comp_matches_filters(comp, must_include, exclude):
            continue

        if not comp_matches_constraints(
            comp,
            require_ports=require_ports,
            require_run_speed=require_run_speed,
            require_charm=require_charm,
            require_pet_heavy=require_pet_heavy,
            require_kiting=require_kiting,
        ):
            continue

        score, detail = score_comp_explain(
            comp, ratings, era, boxing_mode, start, require_charm, template_slots,
            hardcore_required=hardcore_required,
            require_run_speed=require_run_speed,
            require_ports=require_ports,
        )

        if return_explain:
            results.append((score, comp, detail))
        else:
            results.append((score, comp))

    results.sort(reverse=True, key=lambda x: x[0])
    return results[:limit]
