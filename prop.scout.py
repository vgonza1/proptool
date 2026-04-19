import streamlit as st
import anthropic
import re
from datetime import datetime

st.set_page_config(
    page_title="Prop Scout",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .grade-A { background:#EAF3DE; color:#3B6D11; padding:3px 10px; border-radius:6px; font-weight:600; font-size:13px; }
    .grade-B { background:#E6F1FB; color:#185FA5; padding:3px 10px; border-radius:6px; font-weight:600; font-size:13px; }
    .grade-C { background:#FAEEDA; color:#854F0B; padding:3px 10px; border-radius:6px; font-weight:600; font-size:13px; }
    .grade-D { background:#FCEBEB; color:#A32D2D; padding:3px 10px; border-radius:6px; font-weight:600; font-size:13px; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────────────────
if "props" not in st.session_state:
    st.session_state.props = []
if "slip" not in st.session_state:
    st.session_state.slip = []

# ── API key: Streamlit secrets first, then sidebar input ────────────────────
def get_api_key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return st.session_state.get("api_key", "")

# ── Helpers ──────────────────────────────────────────────────────────────────
GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}

def conf_bar(conf):
    filled = int(conf / 10)
    return "█" * filled + "░" * (10 - filled) + f"  {conf}%"

def analyze_prop(client, prop):
    prompt = f"""You are a sharp sports betting analyst. Analyze this player prop for {prop['platform']}:

Player: {prop['player']}{' (' + prop['team'] + ')' if prop['team'] else ''}
League: {prop['league']}
Prop: {prop['direction'].upper()} {prop['line']} {prop['stat']}
{('Context: ' + prop['context']) if prop.get('context') else ''}

Use web search to find:
1. {prop['player']}'s recent stats for {prop['stat']} over the last 5-8 games
2. Season averages for {prop['stat']}
3. Current team form and any injuries or suspensions
4. Matchup context if provided

Respond in this EXACT format (each field on its own line):
GRADE: [A/B/C/D]
CONFIDENCE: [0-100]
KEY STAT: [most relevant recent number, e.g. "3.2 avg shots/game L5"]
SUMMARY: [2-3 concise sentences citing the numbers you found]

Grade key: A=strong edge, B=lean, C=neutral/skip, D=fade."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    text = " ".join(b.text for b in response.content if hasattr(b, "text"))
    grade_m = re.search(r"GRADE:\s*([ABCD])", text, re.I)
    conf_m  = re.search(r"CONFIDENCE:\s*(\d+)", text, re.I)
    key_m   = re.search(r"KEY STAT:\s*(.+)", text, re.I)
    sum_m   = re.search(r"SUMMARY:\s*([\s\S]+?)(?:\n[A-Z ]+:|$)", text, re.I)

    return {
        "grade":      grade_m.group(1).upper() if grade_m else "C",
        "confidence": int(conf_m.group(1))      if conf_m  else 50,
        "key_stat":   key_m.group(1).strip()    if key_m   else None,
        "summary":    sum_m.group(1).strip()    if sum_m   else text[:300],
    }

def review_slip(client, slip):
    lines = "\n".join(
        f"• {p['player']} ({p['league']}) — {p['direction'].upper()} {p['line']} {p['stat']} "
        f"on {p['platform']}{' [Grade: ' + p.get('grade','?') + ']' if p.get('grade') else ''}"
        for p in slip
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content":
            f"Review this parlay slip and give a final verdict. For each leg briefly note keep or drop, "
            f"then give an overall play/fade recommendation.\n\n{lines}\n\nBe direct. Flag the weakest leg."
        }],
    )
    return " ".join(b.text for b in response.content if hasattr(b, "text"))

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎯 Prop Scout")
    st.caption("AI-powered player prop analyzer")

    if not get_api_key():
        key_input = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
        if key_input:
            st.session_state.api_key = key_input
    else:
        st.success("API key loaded ✓", icon="🔑")

    st.divider()
    st.subheader("Build a prop")

    player  = st.text_input("Player name", placeholder="e.g. Cristian Arango")
    team    = st.text_input("Team", placeholder="e.g. LAFC")
    league  = st.selectbox("League", [
        "MLS", "Liga MX", "NBA", "MLB", "NHL", "NFL",
        "EPL", "Champions League", "La Liga", "Serie A", "Other"
    ])

    STATS = [
        "Shots on target", "Total shots", "Goals", "Assists",
        "Goal + assist", "Goalkeeper saves", "Points", "Rebounds",
        "Strikeouts", "Hits", "Rushing yards", "Receiving yards",
        "Passing yards", "Saves (hockey)", "Custom..."
    ]
    stat_choice = st.selectbox("Stat type", STATS)
    stat_label  = (
        st.text_input("Custom stat", placeholder="e.g. corner kicks")
        if stat_choice == "Custom..."
        else stat_choice.lower()
    )

    c1, c2    = st.columns(2)
    line      = c1.number_input("Line", min_value=0.0, step=0.5, value=1.5, format="%.1f")
    direction = c2.selectbox("Direction", ["Over", "Under"])

    platform = st.selectbox("Platform", [
        "PrizePicks", "Underdog Fantasy", "DraftKings",
        "FanDuel", "BetMGM", "Caesars"
    ])
    context = st.text_input("Match context (optional)", placeholder="e.g. vs Portland, home")

    analyze_clicked = st.button("⚡ Analyze prop", use_container_width=True, type="primary")

    if analyze_clicked:
        api_key = get_api_key()
        if not api_key:
            st.error("Enter your Anthropic API key.")
        elif not player:
            st.error("Enter a player name.")
        elif stat_choice == "Custom..." and not stat_label:
            st.error("Enter a custom stat name.")
        else:
            prop = {
                "id": datetime.now().timestamp(),
                "player": player, "team": team, "league": league,
                "stat": stat_label, "line": line, "direction": direction.lower(),
                "platform": platform, "context": context,
                "grade": None, "confidence": None, "key_stat": None, "summary": None,
                "status": "analyzing",
            }
            st.session_state.props.insert(0, prop)

            with st.spinner(f"Scouting {player}..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    prop.update(analyze_prop(client, prop))
                    prop["status"] = "done"
                except Exception as e:
                    prop["status"] = "error"
                    prop["summary"] = f"Analysis failed: {e}"
            st.rerun()

# ── Main ─────────────────────────────────────────────────────────────────────
st.title("Prop Queue")

if not st.session_state.props:
    st.info("Add a prop in the sidebar. The AI Scout searches live stats and grades each line A–D.")
else:
    col_queue, col_slip = st.columns([2, 1])

    with col_queue:
        for prop in st.session_state.props:
            grade = prop.get("grade") or "?"
            conf  = prop.get("confidence")

            with st.container(border=True):
                hcol, gcol = st.columns([4, 1])
                with hcol:
                    st.markdown(f"**{prop['player']}**" + (f" · {prop['team']}" if prop['team'] else ""))
                    st.caption(f"{prop['platform']} · {prop['league']} · {prop['direction'].upper()} {prop['line']} {prop['stat']}")
                    if prop.get("context"):
                        st.caption(f"📍 {prop['context']}")
                with gcol:
                    if grade in "ABCD":
                        st.markdown(f"<span class='grade-{grade}'>{grade}</span>", unsafe_allow_html=True)

                if prop["status"] == "analyzing":
                    st.info("Searching for stats...", icon="🔍")
                elif prop["status"] == "error":
                    st.error(prop.get("summary", "Analysis error."))
                else:
                    if conf is not None:
                        st.caption(conf_bar(conf))
                    if prop.get("key_stat"):
                        st.markdown(f"**📊 {prop['key_stat']}**")
                    if prop.get("summary"):
                        st.write(prop["summary"])

                b1, b2    = st.columns([1, 1])
                in_slip   = any(s["id"] == prop["id"] for s in st.session_state.slip)
                with b1:
                    if not in_slip:
                        if st.button("＋ Add to slip", key=f"add_{prop['id']}"):
                            st.session_state.slip.append(prop)
                            st.rerun()
                    else:
                        st.caption("✓ In slip")
                with b2:
                    if st.button("Remove", key=f"rm_{prop['id']}"):
                        st.session_state.props = [p for p in st.session_state.props if p["id"] != prop["id"]]
                        st.session_state.slip  = [s for s in st.session_state.slip  if s["id"] != prop["id"]]
                        st.rerun()

    with col_slip:
        st.subheader("Parlay Slip")

        if not st.session_state.slip:
            st.caption("Add analyzed props here to build your parlay.")
        else:
            for prop in st.session_state.slip:
                g = prop.get("grade", "?")
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{prop['player']}**")
                    st.caption(f"{prop['direction'].upper()} {prop['line']} {prop['stat']}")
                    st.caption(f"{prop['league']} · {prop['platform']}")
                with c2:
                    if g in "ABCD":
                        st.markdown(f"<span class='grade-{g}'>{g}</span>", unsafe_allow_html=True)
                    if st.button("×", key=f"slip_rm_{prop['id']}"):
                        st.session_state.slip = [s for s in st.session_state.slip if s["id"] != prop["id"]]
                        st.rerun()
                st.divider()

            confs  = [p["confidence"] for p in st.session_state.slip if p.get("confidence") is not None]
            grades = [p["grade"] for p in st.session_state.slip if p.get("grade") in "ABCD"]

            m1, m2 = st.columns(2)
            m1.metric("Legs", len(st.session_state.slip))
            m2.metric("Avg conf", f"{round(sum(confs)/len(confs))}%" if confs else "—")
            if grades:
                best = sorted(grades, key=lambda g: GRADE_ORDER.get(g, 9))[0]
                st.metric("Best grade", best)

            st.divider()

            if st.button("🤖 Review slip with AI", use_container_width=True, type="primary"):
                api_key = get_api_key()
                if not api_key:
                    st.error("Enter your API key.")
                else:
                    with st.spinner("AI reviewing your slip..."):
                        client = anthropic.Anthropic(api_key=api_key)
                        verdict = review_slip(client, st.session_state.slip)
                    st.markdown("### AI Verdict")
                    st.markdown(verdict)

            if st.button("Clear slip", use_container_width=True):
                st.session_state.slip = []
                st.rerun()

        st.divider()
        st.markdown("""
**Grade legend**

<span class='grade-A'>A</span> Strong edge — play it<br><br>
<span class='grade-B'>B</span> Lean — worth including<br><br>
<span class='grade-C'>C</span> Neutral — use caution<br><br>
<span class='grade-D'>D</span> Fade — avoid
""", unsafe_allow_html=True)
