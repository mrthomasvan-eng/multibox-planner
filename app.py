import base64
import json
import random
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

from app.recommender import (
    load_class_ratings,
    load_default_comps,
    load_rulesets,
    load_meta_builds,
    list_data_files,
    get_available_classes,
    filter_default_comps,
    generate_scored_recommendations,
    force_constraints_into_slots,
)

from app.templates import get_template

st.set_page_config(page_title="EverQuest Multibox Planner", layout="wide")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
# Fallback to cwd/assets so backgrounds load when run from project root
_assets = ASSETS_DIR if ASSETS_DIR.exists() else (Path.cwd() / "assets")


BANNER_LINK_URL = "https://www.redguides.com/amember/aff/go/vanman2099"
_WIDE_BANNER_FILES = ["frostreaverwide.png", "frostreaverwide1.png"]


@st.cache_data(show_spinner=False)
def _load_assets(_assets_path: Path):
    """Load and base64-encode images once; cached so constraint changes don't re-read files."""
    out = {"bg_tile": None, "sidebar": None, "header": None, "class_icons": {}, "wide_banners": []}
    try:
        p = _assets_path / "bg_tile.png"
        if p.exists():
            out["bg_tile"] = base64.b64encode(p.read_bytes()).decode()
        p = _assets_path / "sidebar.png"
        if p.exists():
            out["sidebar"] = base64.b64encode(p.read_bytes()).decode()
        p = _assets_path / "header.png"
        if p.exists():
            out["header"] = base64.b64encode(p.read_bytes()).decode()
    except Exception:
        pass
    icons_dir = _assets_path / "class_icons"
    if icons_dir.exists():
        for f in icons_dir.glob("*.png"):
            try:
                out["class_icons"][f.stem] = base64.b64encode(f.read_bytes()).decode()
            except Exception:
                pass
    banners_dir = _assets_path / "banners"
    if banners_dir.exists():
        for name in _WIDE_BANNER_FILES:
            p = banners_dir / name
            if p.exists():
                try:
                    out["wide_banners"].append(base64.b64encode(p.read_bytes()).decode())
                except Exception:
                    pass
    return out


_asset = _load_assets(_assets)
_bg_tile_b64 = _asset["bg_tile"]
_sidebar_b64 = _asset["sidebar"]
_header_b64 = _asset["header"]
_class_icons_b64 = _asset.get("class_icons", {})


def _class_icon_key(name: str) -> str:
    return "shadow_knight" if name == "Shadowknight" else name.lower().replace(" ", "_")


def _build_line(comp, medal_or_rank_html: str) -> str:
    """Build recommendation card line: medal/rank + class names (no icons)."""
    names = " · ".join(f'<span class="rec-class-name">{cls}</span>' for cls in comp)
    return medal_or_rank_html + '<span class="rec-label">' + names + "</span>"


def _build_line_with_icons(comp, medal_or_rank_html: str) -> str:
    """Build line with small class icons (for top result only)."""
    parts = []
    for cls in comp:
        key = _class_icon_key(cls)
        b64 = _class_icons_b64.get(key)
        if b64:
            parts.append(f'<span class="rec-class-chunk"><img class="rec-class-icon" src="data:image/png;base64,{b64}" alt="" /><span class="rec-class-name">{cls}</span></span>')
        else:
            parts.append(f'<span class="rec-class-chunk"><span class="rec-class-name">{cls}</span></span>')
    return medal_or_rank_html + '<span class="rec-label">' + " · ".join(parts) + "</span>"
_bg_tile_url = f"url(data:image/png;base64,{_bg_tile_b64})" if _bg_tile_b64 else "none"
_sidebar_url = f"url(data:image/png;base64,{_sidebar_b64})" if _sidebar_b64 else "none"
# Lighter overlay (0.5) so the tiled texture shows through; was 0.88/0.85 and looked almost solid
_main_bg = f"linear-gradient(rgba(15,23,42,0.5), rgba(15,23,42,0.5)), {_bg_tile_url}" if _bg_tile_b64 else "#0f172a"
_sidebar_bg = f"linear-gradient(rgba(15,23,42,0.5), rgba(15,23,42,0.5)), {_sidebar_url}" if _sidebar_b64 else "#0f172a"

_APP_CSS = f"""
<style id="eq-multibox-css">
[data-testid="stApp"] {{ --background-color: #0f172a !important; --secondary-background-color: #1e293b !important; background: {_main_bg} !important; background-repeat: no-repeat !important; background-size: cover !important; background-position: center !important; }}
body {{ background: {_main_bg} !important; background-repeat: no-repeat !important; background-size: cover !important; background-position: center !important; }}
[data-testid="stAppViewContainer"] {{ background: {_main_bg} !important; background-repeat: no-repeat !important; background-size: cover !important; background-position: center !important; box-shadow: inset 0 0 90px rgba(0,0,0,0.25) !important; }}
section.main {{ background: {_main_bg} !important; background-repeat: no-repeat !important; background-size: cover !important; background-position: center !important; min-height: 100vh !important; position: relative !important; }}
section.main::before {{ content: ""; position: absolute; inset: 0; background: rgba(15,23,42,0.18); pointer-events: none; z-index: 0; }}
section.main > div {{ position: relative; z-index: 1; }}
.block-container {{ background: transparent !important; max-width: 1360px !important; margin-left: auto !important; margin-right: auto !important; padding-left: 2rem !important; padding-right: 2rem !important; box-shadow: 0 0 50px rgba(0,0,0,0.2) !important; }}
.main .block-container {{ background: transparent !important; }}
.main .block-container {{ padding-top: 1rem; padding-bottom: 1rem; }}
.main .block-container > div {{ margin-bottom: 0.5rem; }}
.main p, .main span, .main label, .main li {{ color: #f1f5f9 !important; }}
.main div[data-testid="stMarkdown"] {{ color: #f1f5f9 !important; }}
.main a {{ color: #d4af37 !important; }}
h1 {{ color: #ffffff !important; font-weight: 700 !important; border-bottom: 2px solid #d4af37; padding-bottom: 0.4rem; }}
h2, h3 {{ color: #f1f5f9 !important; font-weight: 600 !important; }}
[data-testid="stSidebar"], [data-testid="stSidebar"] > div {{ background: {_sidebar_bg} !important; background-repeat: no-repeat !important; background-size: cover !important; background-position: center !important; position: relative !important; }}
[data-testid="stSidebar"] > div {{ position: relative !important; }}
[data-testid="stSidebar"] > div::after {{ content: ""; position: absolute; inset: 0; background: rgba(15,23,42,0.38); pointer-events: none; z-index: 0; }}
[data-testid="stSidebar"] > div > * {{ position: relative; z-index: 1; }}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{ color: #f1f5f9 !important; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {{ margin-bottom: 0 !important; padding-bottom: 0.04rem !important; }}
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stCheckbox, [data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stTextInput {{ margin-top: 0.15rem !important; margin-bottom: 0.15rem !important; }}
[data-testid="stSidebar"] hr {{ margin: 0.26rem 0 !important; border-color: rgba(212, 175, 55, 0.25); }}
[data-testid="stSidebar"] h3 {{ margin-top: 0.3rem !important; margin-bottom: 0.19rem !important; color: #a68b2b !important; font-weight: 600 !important; }}
[data-testid="stSidebar"] h3:first-of-type {{ margin-top: 0.15rem !important; }}
[data-baseweb="select"] {{ background: #1e293b !important; }}
[data-baseweb="select"] > div, [data-baseweb="select"] input {{ background: #1e293b !important; color: #f1f5f9 !important; border-color: rgba(212, 175, 55, 0.4) !important; }}
[data-baseweb="select"] span, [data-baseweb="select"] div {{ color: #f1f5f9 !important; }}
[data-testid="stSidebar"] [data-baseweb="select"] span, [data-testid="stSidebar"] [data-baseweb="select"] div {{ color: #f1f5f9 !important; }}
/* Dropdown menu (options list) – often in a portal so global selectors */
[data-baseweb="popover"], [data-baseweb="menu"], div[role="listbox"], ul[role="listbox"] {{ background: #1e293b !important; color: #f1f5f9 !important; border: 1px solid rgba(212, 175, 55, 0.3) !important; }}
li[role="option"], div[role="option"], [data-baseweb="menu"] li, [data-baseweb="menu"] div {{ background: #1e293b !important; color: #f1f5f9 !important; }}
li[role="option"]:hover, div[role="option"]:hover {{ background: #334155 !important; color: #ffffff !important; }}
/* Multiselect and any listbox in the app */
[data-baseweb="select"] [role="listbox"], [data-baseweb="select"] + div [role="listbox"] {{ background: #1e293b !important; }}
.stSelectbox > div > div {{ background: #1e293b !important; color: #f1f5f9 !important; }}
/* Dropdown arrow/chevron: gold and larger so it’s visible on dark background */
[data-baseweb="select"] svg, .stSelectbox svg {{ fill: #d4af37 !important; color: #d4af37 !important; width: 20px !important; height: 20px !important; min-width: 20px !important; min-height: 20px !important; }}
[data-baseweb="select"] [aria-label] svg, [data-baseweb="select"] div[style*="align"] svg {{ fill: #d4af37 !important; }}
[data-baseweb="select"] > div > div:last-child, [data-baseweb="select"] [data-id="dropdown-icon"] {{ color: #d4af37 !important; }}
.stSelectbox div[style*="flex"] > div:last-child {{ color: #d4af37 !important; }}
[data-testid="stSidebar"] button {{ background-color: #d4af37 !important; color: #0f172a !important; font-weight: 600 !important; }}
[data-testid="stSidebar"] button:hover {{ background-color: #e5c04a !important; color: #0f172a !important; }}
[data-testid="stSidebar"] {{ border-right: 1px solid rgba(212, 175, 55, 0.4); }}
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stCheckbox {{ margin-bottom: 0 !important; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0 !important; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {{ padding-top: 0.02rem !important; padding-bottom: 0.02rem !important; }}
[data-testid="stCaption"] {{ color: #cbd5e1 !important; }}
.streamlit-expanderHeader {{ color: #f1f5f9 !important; font-weight: 600 !important; }}
[data-testid="stExpander"] {{ background: rgba(30, 41, 59, 0.98) !important; border: 1px solid rgba(212, 175, 55, 0.35) !important; border-radius: 8px !important; }}
[data-testid="stExpander"] > div {{ background: rgba(30, 41, 59, 0.98) !important; color: #f1f5f9 !important; }}
[data-testid="stExpander"] p, [data-testid="stExpander"] span, [data-testid="stExpander"] li, [data-testid="stExpander"] label {{ color: #f1f5f9 !important; }}
[data-testid="stExpander"] [data-testid="stMarkdown"] {{ color: #f1f5f9 !important; }}
.eq-header-wrap {{ margin-top: -1.5rem !important; margin-bottom: 0 !important; }}
.main .block-container {{ padding-top: 0.25rem !important; padding-bottom: 1rem; }}
.eq-header-img {{ width: 100%; height: auto; display: block; margin-bottom: 0.5rem; }}
.ac-row {{ display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem; }}
.ac-box {{ display: inline-flex; align-items: center; gap: 0.35rem; background: rgba(30, 41, 59, 0.95); border: 1px solid rgba(148, 163, 184, 0.25); border-radius: 8px; padding: 0.4rem 0.75rem; font-size: 0.85rem; font-weight: 600; color: #f1f5f9; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
.ac-box .ac-box-icon {{ font-size: 0.9rem; color: #d4af37; line-height: 1; }}
.ac-msg {{ color: #94a3b8; font-size: 0.78rem; margin-top: 0.35rem; line-height: 1.4; }}
div.rec-card {{ margin-bottom: 0.35rem !important; padding: 0.5rem 0.75rem !important; border-radius: 12px !important; background: linear-gradient(180deg, #243548 0%, #1e293b 100%) !important; border: 1px solid rgba(212,175,55,0.25) !important; box-shadow: 0 4px 14px rgba(0,0,0,0.25) !important; color: #e2e8f0 !important; transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease !important; }}
div.rec-card:hover {{ transform: translateY(-2px) !important; border-color: rgba(212,175,55,0.45) !important; box-shadow: 0 6px 18px rgba(0,0,0,0.3) !important; }}
div.rec-card.rec-card--first {{ background: linear-gradient(180deg, #2a3d52 0%, #243547 100%) !important; border: 2px solid rgba(212,175,55,0.7) !important; box-shadow: 0 4px 20px rgba(0,0,0,0.3), 0 0 24px rgba(212,175,55,0.25), inset 0 0 20px rgba(212,175,55,0.04) !important; }}
div.rec-card.rec-card--first:hover {{ border-color: rgba(212,175,55,0.85) !important; box-shadow: 0 6px 24px rgba(0,0,0,0.35), 0 0 28px rgba(212,175,55,0.3), inset 0 0 20px rgba(212,175,55,0.06) !important; }}
.rec-card.rec-card--first .rec-bar-bg {{ box-shadow: 0 0 0 1px rgba(212,175,55,0.3); }}
.rec-card .rec-build-line {{ line-height: 1.4; margin-bottom: 0.15rem; display: flex; flex-wrap: wrap; align-items: center; gap: 0.2rem; }}
.rec-card .rec-class-chunk {{ display: inline-flex; align-items: center; gap: 0.25rem; }}
.rec-card .rec-class-icon {{ height: 1.1em; width: auto; vertical-align: middle; object-fit: contain; }}
.rec-card .rec-class-name {{ font-weight: 600; color: #f8fafc; }}
.rec-card .rec-medal {{ font-size: 1.4rem; line-height: 1; margin-right: 0.25rem; vertical-align: middle; }}
.rec-card .rec-medal.rec-meta-rank {{ font-size: 1.15rem; font-weight: 700; margin-right: 0.4rem; }}
.rec-card .rec-rank {{ font-size: 1rem; font-weight: 600; color: #cbd5e1; margin-right: 0.4rem; }}
.rec-card .rec-label {{ color: #f8fafc; font-size: 1.15rem; font-weight: 600; }}
.rec-card .rec-score-line {{ font-size: 0.9rem; font-weight: 600; color: #f1f5f9; margin: 0 0 0.25rem 0; }}
.rec-bar-wrap {{ display: flex; align-items: center; gap: 0.5rem; margin-top: 0.2rem; }}
.rec-bar-bg {{ flex: 1; height: 10px; border-radius: 5px; background: rgba(0,0,0,0.4); overflow: hidden; }}
.rec-bar-fill {{ height: 100%; border-radius: 5px; transition: width 0.2s ease; }}
.rec-pct {{ min-width: 2.5em; text-align: right; font-size: 0.75rem; color: #cbd5e1; }}
.rec-section-divider {{ height: 1px; background: rgba(212, 175, 55, 0.2); margin: 0.25rem 0 0.5rem 0; }}
[data-testid="stAlert"] {{ background: rgba(30, 41, 59, 0.95) !important; color: #f1f5f9 !important; border: 1px solid rgba(212, 175, 55, 0.3); }}
[data-testid="stAlert"] p, [data-testid="stAlert"] span {{ color: #f1f5f9 !important; }}
</style>
"""
# Inject CSS into document.head so it actually applies (Streamlit often ignores <style> in markdown)
_style_inner = _APP_CSS[_APP_CSS.index(">", _APP_CSS.find("<style")) + 1 : _APP_CSS.rfind("</style>")].strip()
_script = f'<script>(function(){{var d=window.parent.document;var old=d.getElementById("eq-multibox-css");if(old)old.remove();var s=d.createElement("style");s.id="eq-multibox-css";s.textContent={json.dumps(_style_inner)};d.head.appendChild(s);}})();</script>'
components.html(_script, height=0)
st.markdown(_APP_CSS, unsafe_allow_html=True)

RATINGS_FILE = DATA_DIR / "class_ratings.csv"
DEFAULTS_FILE = DATA_DIR / "synergies_and_defaults.csv"
RULESETS_FILE = DATA_DIR / "rulesets.json"
META_BUILDS_FILE = DATA_DIR / "meta_builds.csv"

ERA_ORDER = ["ckv", "luclin", "pop", "god", "oow"]
ERA_LABELS = {
    "ckv": "Classic (Classic + Kunark + Velious)",
    "luclin": "Shadows of Luclin",
    "pop": "Planes of Power (LoY + LDoN)",
    "god": "Gates of Discord",
    "oow": "Omens of War",
}

TWO_BOX_MODE_LABELS = {
    "traditional": "Traditional (Tank + Healer)",
    "pet_tank": "Pet tank (Pet tanks, partner is caster/support)",
    "ench_charm_tank": "Enchanter Pet Charm/Tank",
    "kiting": "Kiting (choose style below)",
}

KITE_STYLE_LABELS = {
    "swarm": "Swarm kiting (Bard AoE)",
    "fear_snare": "Fear/Snare/Quad (Necro/Druid/Wizard/Ranger)",
}

DEFAULT_STATE = {
    "era": "ckv",
    "box_size": 2,
    "two_box_mode": "traditional",
    "kiting_style": "swarm",
    "ruleset_key": "frostreaver",
    "boxing_mode": "manual",
    "focus": "balanced",
    "start": "fresh",
    "require_ports": False,
    "require_run_speed": False,
    "require_charm": False,
    "require_pet_heavy": False,  # preference only
    "must_include": [],
    "exclude": [],
    "show_debug": False,
    "show_explain": False,
    "use_meta_builds": False,
}


def init_state():
    for k, v in DEFAULT_STATE.items():
        st.session_state.setdefault(k, v)


def reset_state():
    for k, v in DEFAULT_STATE.items():
        st.session_state[k] = v


init_state()

# ----------------------------
# Load data
# ----------------------------
missing = []
if not DATA_DIR.exists():
    missing.append("data folder")
if not RATINGS_FILE.exists():
    missing.append("data/class_ratings.csv")
if not DEFAULTS_FILE.exists():
    missing.append("data/synergies_and_defaults.csv")
if not RULESETS_FILE.exists():
    missing.append("data/rulesets.json")

if missing:
    st.error("Missing required project files:\n- " + "\n- ".join(missing))
    st.stop()


@st.cache_data(show_spinner=False)
def _load_app_data(_data_dir: Path):
    """Load CSV/JSON data once so constraint changes don't re-read files."""
    ratings = load_class_ratings(_data_dir / "class_ratings.csv")
    defaults = load_default_comps(_data_dir / "synergies_and_defaults.csv")
    rulesets = load_rulesets(_data_dir / "rulesets.json")
    meta_path = _data_dir / "meta_builds.csv"
    meta_builds_data = load_meta_builds(meta_path) if meta_path.exists() else {}
    return ratings, defaults, rulesets, meta_builds_data


ratings, defaults, rulesets, meta_builds_data = _load_app_data(DATA_DIR)


@st.cache_data(show_spinner=False)
def _cached_recommendations(
    _data_dir_str: str,
    era: str,
    available_tuple: tuple,
    template_slots_tuple: tuple,
    boxing_mode: str,
    start: str,
    must_tuple: tuple,
    exclude_tuple: tuple,
    require_ports: bool,
    require_run_speed: bool,
    require_charm: bool,
    require_pet_heavy: bool,
    hardcore_required: bool,
):
    """Cache recommendation results so same selections return instantly."""
    ratings_in, _, _, _ = _load_app_data(Path(_data_dir_str))
    return generate_scored_recommendations(
        ratings=ratings_in,
        era=era,
        available=list(available_tuple),
        template_slots=list(template_slots_tuple),
        boxing_mode=boxing_mode,
        start=start,
        must_include=set(must_tuple),
        exclude=set(exclude_tuple),
        require_ports=require_ports,
        require_run_speed=require_run_speed,
        require_charm=require_charm,
        require_pet_heavy=require_pet_heavy,
        require_kiting=False,
        hardcore_required=hardcore_required,
        limit=15,
        return_explain=True,
    )


present_eras = set(ratings.keys()) | set(defaults.keys())
era_options = [e for e in ERA_ORDER if e in present_eras]
if not era_options:
    st.error("No eras found in class_ratings.csv / synergies_and_defaults.csv.")
    st.stop()

ruleset_keys = list(rulesets.keys())
if not ruleset_keys:
    st.error("rulesets.json has no rulesets.")
    st.stop()

# sanitize invalid values BEFORE rendering widgets (prevents double-click rerun fights)
if st.session_state["era"] not in era_options:
    st.session_state["era"] = era_options[0]
if st.session_state["ruleset_key"] not in ruleset_keys:
    st.session_state["ruleset_key"] = "frostreaver" if "frostreaver" in ruleset_keys else ruleset_keys[0]
if st.session_state["box_size"] not in [2, 3, 4, 5, 6]:
    st.session_state["box_size"] = 2
if st.session_state["two_box_mode"] not in ["traditional", "pet_tank", "ench_charm_tank", "kiting"]:
    st.session_state["two_box_mode"] = "traditional"
if st.session_state["kiting_style"] not in ["swarm", "fear_snare"]:
    st.session_state["kiting_style"] = "swarm"
if st.session_state["boxing_mode"] not in ["manual", "assisted", "macroquest"]:
    st.session_state["boxing_mode"] = "manual"
if st.session_state["focus"] not in ["leveling", "balanced", "solo_raid"]:
    st.session_state["focus"] = "balanced"
if st.session_state["start"] not in ["fresh", "assisted"]:
    st.session_state["start"] = "fresh"

# ----------------------------
# Sidebar
# ----------------------------
if st.sidebar.button("Reset all settings", key="reset_btn"):
    reset_state()
    st.rerun()

st.sidebar.subheader("Environment")
st.sidebar.selectbox(
    "Era",
    options=era_options,
    index=era_options.index(st.session_state["era"]),
    format_func=lambda e: ERA_LABELS.get(e, e),
    key="era",
)
ruleset_labels = {k: rulesets[k].get("label", k) for k in ruleset_keys}
st.sidebar.selectbox(
    "Server Ruleset",
    options=ruleset_keys,
    index=ruleset_keys.index(st.session_state["ruleset_key"]),
    format_func=lambda k: ruleset_labels.get(k, k),
    key="ruleset_key",
)

st.sidebar.markdown("---")
st.sidebar.subheader("Group Setup")
st.sidebar.selectbox(
    "How many are you boxing?",
    options=[2, 3, 4, 5, 6],
    index=[2, 3, 4, 5, 6].index(st.session_state["box_size"]),
    key="box_size",
)
if st.session_state["box_size"] == 2:
    two_box_opts = ["traditional", "pet_tank", "ench_charm_tank", "kiting"]
    st.sidebar.selectbox(
        "2-box mode",
        options=two_box_opts,
        index=two_box_opts.index(st.session_state["two_box_mode"]) if st.session_state["two_box_mode"] in two_box_opts else 0,
        format_func=lambda k: TWO_BOX_MODE_LABELS.get(k, k),
        key="two_box_mode",
    )
    if st.session_state["two_box_mode"] == "kiting":
        st.sidebar.selectbox(
            "Kiting style",
            options=["swarm", "fear_snare"],
            index=["swarm", "fear_snare"].index(st.session_state["kiting_style"]),
            format_func=lambda k: KITE_STYLE_LABELS.get(k, k),
            help="Swarm: Bard AoE swarm kiting.\n\nFear/Snare/Quad: Necro fear kite, Druid/Wiz quad kite, etc.",
            key="kiting_style",
        )

st.sidebar.markdown("---")
st.sidebar.subheader("Playstyle")
st.sidebar.selectbox(
    "Boxing Method",
    options=["manual", "assisted", "macroquest"],
    index=["manual", "assisted", "macroquest"].index(st.session_state["boxing_mode"]),
    key="boxing_mode",
    help="Manual: prefer caster DPS with one-click macros.\n\nAssisted: you're autofiring macros, equally considers melee and casters.\n\nMacroQuest: automated, considers all.",
)
FOCUS_LABELS = {
    "leveling": "Leveling",
    "balanced": "Balanced",
    "solo_raid": "Hardcore",
}
st.sidebar.selectbox(
    "Group Focus",
    options=["leveling", "balanced", "solo_raid"],
    index=["leveling", "balanced", "solo_raid"].index(st.session_state["focus"]),
    format_func=lambda k: FOCUS_LABELS.get(k, k),
    key="focus",
    help="Leveling: grinding and occasional named.\n\nBalanced: harder missions and farming group named camps.\n\nHardcore: prep for one-group raid boss content (PoFire Minis).",
)
START_LABELS = {
    "fresh": "Fresh",
    "assisted": "Assisted / Krono",
}
st.sidebar.selectbox(
    "Start Condition",
    options=["fresh", "assisted"],
    index=["fresh", "assisted"].index(st.session_state["start"]),
    format_func=lambda k: START_LABELS.get(k, k),
    key="start",
    help="Fresh: will give preference to casters because there will be no money for gear or melee weapons; rusty swords don't work well.\n\nAssisted / Krono: equally considers all options.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("Constraints")
st.sidebar.checkbox("Ports (Wizard or Druid)", value=st.session_state["require_ports"], key="require_ports")
st.sidebar.checkbox("Run speed (SoW/Selo)", value=st.session_state["require_run_speed"], key="require_run_speed")
if st.session_state["box_size"] >= 3:
    st.sidebar.checkbox(
        "Pet-heavy DPS (prefer Mage/Necro/Beastlord as DPS)",
        value=st.session_state["require_pet_heavy"],
        help="Nudges DPS picks toward pet classes in 3–6 box groups.\n\nNot for 2-box (use 2-box mode for pet tanking).",
        key="require_pet_heavy",
    )
    st.sidebar.checkbox(
        "Charm group (Enchanter)",
        value=st.session_state["require_charm"],
        key="require_charm",
        help="Only applies to 3+ box.\n\nFor 2-box use 'Enchanter Pet Charm/Tank' mode instead.",
    )

# ----------------------------
# Available classes + filters
# ----------------------------
era = st.session_state["era"]
ruleset_key = st.session_state["ruleset_key"]
ruleset = rulesets[ruleset_key]

available = get_available_classes(ratings, era, ruleset)
available_set = set(available)

st.sidebar.subheader("Class Filters")
# sanitize selected lists to only available classes
st.session_state["must_include"] = [c for c in st.session_state["must_include"] if c in available_set]
st.session_state["exclude"] = [c for c in st.session_state["exclude"] if c in available_set]

st.sidebar.multiselect("Must include", options=available, default=st.session_state["must_include"], key="must_include")
st.sidebar.multiselect("Exclude", options=available, default=st.session_state["exclude"], key="exclude")

must_set = set(st.session_state["must_include"])
exclude_set = set(st.session_state["exclude"])

st.sidebar.subheader("Options")
st.sidebar.checkbox("Meta Builds", value=st.session_state["use_meta_builds"], key="use_meta_builds", help="Show top 5 curated meta builds for this era and box size.\n\nNo scoring or include/exclude.")
st.sidebar.checkbox("Explain scoring under results", value=st.session_state["show_explain"], key="show_explain")

# ----------------------------
# Template slots
# ----------------------------
box_size = st.session_state["box_size"]
focus = st.session_state["focus"]

template_slots = get_template(box_size, focus)

if box_size == 2:
    mode = st.session_state["two_box_mode"]
    if mode == "traditional":
        template_slots = ["tank", "healer"]
    elif mode == "pet_tank":
        template_slots = ["pet_tank", "pet_partner"]
    elif mode == "ench_charm_tank":
        template_slots = ["charm_tank", "charm_partner"]
    elif mode == "kiting":
        if st.session_state["kiting_style"] == "swarm":
            template_slots = ["kiter_swarm", "kite_partner_swarm"]
        else:
            template_slots = ["kiter_fear_snare", "kite_partner_fear_snare"]
elif box_size == 3 and st.session_state["require_charm"]:
    # 3-box charm: Enchanter is the tank (charm tank), mandatory healer, 3rd slot is flex (dps/buffs; constraints can force healer e.g. Druid SOW)
    template_slots = ["charm_tank", "healer", "dps"]

# ----------------------------
# Debug panels
# ----------------------------
if False:  # Debug panels removed from UI (admin-only)
    st.subheader("Data status")
    st.write(f"Project folder: `{BASE_DIR}`")
    st.write(f"Data folder: `{DATA_DIR}`")
    st.json(list_data_files(DATA_DIR))
    st.success("All data loaded successfully.")

    st.subheader("Available classes (era + ruleset)")
    st.write(f"{len(available)} classes available for **{ERA_LABELS.get(era, era)}** under ruleset **{ruleset_key}**.")
    st.write(available)

    st.subheader("Template slots")
    st.write(template_slots)

    require_charm_effective = box_size >= 3 and st.session_state["require_charm"]
    _hardcore = focus == "solo_raid" and box_size >= 4
    _already = {c for c in ["Cleric", "Shaman", "Bard"] if c in available_set} if _hardcore else set()
    forced = force_constraints_into_slots(
        template_slots=template_slots,
        available=available,
        require_ports=st.session_state["require_ports"],
        require_run_speed=st.session_state["require_run_speed"],
        require_charm=require_charm_effective,
        require_pet_heavy=st.session_state["require_pet_heavy"],
        require_kiting=False,
        already_satisfied=_already,
        hardcore_required=_hardcore,
    )
    st.subheader("Slot forcing debug")
    if not forced:
        st.write("No slots forced by constraints.")
    else:
        for slot_idx in sorted(forced.keys()):
            slot_name = template_slots[slot_idx]
            pool = sorted(forced[slot_idx])
            st.write(f"Slot {slot_idx + 1} ({slot_name}) forced to: {', '.join(pool)}")

# ----------------------------
# Key settings summary (what’s affecting recommendations)
# ----------------------------
boxing_mode = st.session_state["boxing_mode"]
start = st.session_state["start"]
era_label = ERA_LABELS.get(era, era)
ruleset_label = rulesets.get(ruleset_key, {}).get("label", ruleset_key)
summary_parts = [
    f"Era: {era_label}",
    f"Box: {box_size}",
    f"Ruleset: {ruleset_label}",
    f"Method: {boxing_mode.capitalize()}",
    f"Focus: {FOCUS_LABELS.get(focus, focus)}",
    f"Start: {START_LABELS.get(start, start)}",
]
if box_size == 2:
    summary_parts.append(f"2-box: {TWO_BOX_MODE_LABELS.get(st.session_state['two_box_mode'], st.session_state['two_box_mode'])}")
constraint_count = sum([
    st.session_state["require_ports"],
    st.session_state["require_run_speed"],
    st.session_state["require_pet_heavy"],
    st.session_state["require_charm"] if box_size >= 3 else False,
])
constraint_msg = f"⚠ {constraint_count} constraint(s) active. Results are restricted." if constraint_count > 0 else "No special constraints applied."
# Build constraint boxes: first gets gold icon, rest are plain (Era: Luclin, Box: 4, Ruleset: Frostreaver, etc.)
ac_boxes = []
for i, part in enumerate(summary_parts):
    icon = '<span class="ac-box-icon">◆</span>' if i == 0 else ''
    ac_boxes.append(f'<span class="ac-box">{icon}{part}</span>')
ac_html = '<div class="ac-row">' + ''.join(ac_boxes) + '</div><div class="ac-msg">' + constraint_msg + '</div>'
st.markdown(ac_html, unsafe_allow_html=True)

if _header_b64:
    st.markdown(f'<div class="eq-header-wrap"><img src="data:image/png;base64,{_header_b64}" alt="EverQuest Multibox Planner" class="eq-header-img" /></div>', unsafe_allow_html=True)
else:
    st.title("EverQuest Multibox Recommendation Tool")

# ----------------------------
# Recommendations (with optional banners)
# ----------------------------
_wide_banner_b64_list = _asset.get("wide_banners", [])
if _wide_banner_b64_list:
    _banner_b64 = random.choice(_wide_banner_b64_list)
    st.markdown(
        f'<a href="{BANNER_LINK_URL}" target="_blank" rel="noopener noreferrer">'
        f'<img src="data:image/png;base64,{_banner_b64}" alt="Banner" style="width:100%; display:block;" /></a>',
        unsafe_allow_html=True,
    )

col_main, = st.columns([1])
with col_main:
    st.subheader("Recommendations")
    st.markdown('<div class="rec-section-divider"></div>', unsafe_allow_html=True)

    require_charm_effective = box_size >= 3 and st.session_state["require_charm"]
    hardcore_required = focus == "solo_raid" and box_size >= 4

    _meta_rank_display = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4", 5: "5"}
    if st.session_state["use_meta_builds"]:
        # Meta Builds: top 5 for era + box_size only; same card style as recommendations (no bar)
        builds_for_era = meta_builds_data.get(era, {}).get(box_size, [])
        meta_top5 = builds_for_era[:5]
        if meta_top5:
            st.caption("Curated meta builds for this era and box size.")
            for rank, comp in meta_top5:
                rank_show = _meta_rank_display.get(rank, str(rank))
                build_line = _build_line(comp, f'<span class="rec-medal rec-meta-rank">{rank_show}</span>')
                card_html = f"""
            <div class="rec-card">
                <div class="rec-build-line">{build_line}</div>
            </div>
            """
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.warning("No meta builds for this era/box size.")
    else:
        scored = _cached_recommendations(
            str(DATA_DIR),
            era,
            tuple(sorted(available)),
            tuple(template_slots),
            st.session_state["boxing_mode"],
            st.session_state["start"],
            tuple(sorted(must_set)),
            tuple(sorted(exclude_set)),
            st.session_state["require_ports"],
            st.session_state["require_run_speed"],
            require_charm_effective,
            st.session_state["require_pet_heavy"],
            hardcore_required,
        )

    if not st.session_state["use_meta_builds"] and scored:
        top_score = float(scored[0][0])
        # Color gradient: best = green, then softer as % drops (still works, not best)
        def _bar_color(ratio: float) -> str:
            # Emerald (top) to arcane blue (lower)
            if ratio >= 0.95:
                return "#10b981"
            if ratio >= 0.75:
                return "#14b8a6"
            if ratio >= 0.55:
                return "#06b6d4"
            if ratio >= 0.35:
                return "#0ea5e9"
            if ratio >= 0.15:
                return "#3b82f6"
            return "#3b82f6"

        _medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for rank_one_index, (score, comp, detail) in enumerate(scored, start=1):
            ratio = min(1.0, max(0.0, score / top_score if top_score else 0))
            pct = int(round(ratio * 100))
            bar_color = _bar_color(ratio)
            is_first = rank_one_index == 1
            card_class = "rec-card rec-card--first" if is_first else "rec-card"
            if rank_one_index in _medals:
                medal_html = f'<span class="rec-medal">{_medals[rank_one_index]}</span>'
            else:
                medal_html = f'<span class="rec-rank">#{rank_one_index}</span>'
            build_line = _build_line_with_icons(comp, medal_html) if is_first else _build_line(comp, medal_html)
            bar_html = f"""
        <div class="{card_class}">
            <div class="rec-build-line">{build_line}</div>
            <div class="rec-score-line">Score: {score}</div>
            <div class="rec-bar-wrap">
                <div class="rec-bar-bg"><div class="rec-bar-fill" style="width:{pct}%; background:{bar_color};"></div></div>
                <span class="rec-pct">{pct}%</span>
            </div>
        </div>
        """
            st.markdown(bar_html, unsafe_allow_html=True)

            if st.session_state["show_explain"]:
                with st.expander("Why this scored high"):
                    if "slot_breakdowns" in detail:
                        for row in detail["slot_breakdowns"]:
                            slot = row["slot"]
                            cls = row["class"]
                            val = row["value"]
                            st.write(f"**{slot}**: {cls} (slot score {val:.1f})")
                            bd = row.get("breakdown", {})
                            if bd:
                                st.write(", ".join([f"{k}={v:.1f}" for k, v in bd.items()]))
                        for line in detail.get("summary_lines", []):
                            st.write(line)
                    else:
                        for line in detail.get("summary_lines", []):
                            st.write(line)
    elif not st.session_state["use_meta_builds"]:
        if box_size == 2 and st.session_state["two_box_mode"] == "ench_charm_tank" and "Enchanter" not in available_set:
            st.warning("Enchanter is not available for this era/ruleset. Enchanter Pet Charm/Tank requires Enchanter; switch ruleset/era or pick another 2-box mode.")
        st.error("No scored comps found. Showing defaults fallback (filtered).")

        if era not in defaults or box_size not in defaults[era]:
            st.warning(f"No default comps found for era '{era}' and {box_size}-box.")
        else:
            all_defaults = defaults[era][box_size]
            ruleset_filtered_defaults = [(rank, comp) for (rank, comp) in all_defaults if set(comp).issubset(available_set)]

            filtered_defaults = filter_default_comps(
                ruleset_filtered_defaults,
                must_include=must_set,
                exclude=exclude_set,
                require_ports=st.session_state["require_ports"],
                require_run_speed=st.session_state["require_run_speed"],
                require_charm=require_charm_effective,
                require_pet_heavy=st.session_state["require_pet_heavy"],
                require_kiting=False,
            )

            if not filtered_defaults:
                st.error("No defaults match either.")
            else:
                for rank, comp in filtered_defaults:
                    st.write(f"Default #{rank}: " + " | ".join(comp))

# Re-inject CSS so it appears last in DOM and overrides Streamlit defaults
st.markdown(_APP_CSS, unsafe_allow_html=True)
