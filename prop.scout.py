import streamlit as st
import anthropic
import re
from datetime import datetime

st.set_page_config(
    page_title="PropFinder — Sports & Esports Research",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.grade-A{background:#EAF3DE;color:#3B6D11;padding:3px 10px;border-radius:6px;font-weight:700;font-size:13px;}
.grade-B{background:#E6F1FB;color:#185FA5;padding:3px 10px;border-radius:6px;font-weight:700;font-size:13px;}
.grade-C{background:#FAEEDA;color:#854F0B;padding:3px 10px;border-radius:6px;font-weight:700;font-size:13px;}
.grade-D{background:#FCEBEB;color:#A32D2D;padding:3px 10px;border-radius:6px;font-weight:700;font-size:13px;}
.hit{background:#EAF3DE;color:#3B6D11;padding:2px 8px;border-radius:4px;font-size:12px;}
.miss{background:#FCEBEB;color:#A32D2D;padding:2px 8px;border-radius:4px;font-size:12px;}
div[data-testid="stMetricValue"]{font-size:1.5rem!important;}
</style>
""", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────────
SPORTS = {
    "🏈 NFL":              ["Passing yards","Rushing yards","Receiving yards","Touchdowns","Receptions","Interceptions","Sacks","Fantasy points"],
    "🏀 NBA":              ["Points","Rebounds","Assists","3-pointers made","Steals","Blocks","Points+Rebounds+Assists","Fantasy points"],
    "⚾ MLB":              ["Strikeouts","Hits","Total bases","RBIs","Home runs","Walks allowed","Earned runs","Outs recorded"],
    "🏒 NHL":              ["Goals","Assists","Points","Shots on goal","Saves","Save %","Power play points"],
    "⚽ MLS":              ["Shots on target","Total shots","Goals","Assists","Goal+assist","Goalkeeper saves","Tackles"],
    "⚽ EPL":              ["Shots on target","Total shots","Goals","Assists","Goal+assist","Goalkeeper saves","Tackles"],
    "⚽ Liga MX":          ["Shots on target","Total shots","Goals","Assists","Goal+assist","Goalkeeper saves"],
    "⚽ Champions League": ["Shots on target","Goals","Assists","Goal+assist","Goalkeeper saves"],
    "🎾 Tennis":           ["Aces","Double faults","Games won","Sets won","First serve %","Break points won"],
    "🎮 League of Legends":["Kills","Deaths","Assists","CS","KDA","Gold earned","Vision score","Damage dealt"],
    "🎮 CS2":              ["Kills","Deaths","Assists","ADR","HLTV rating","Headshot %","Entry kills","Maps played"],
    "🎮 Valorant":         ["Kills","Deaths","Assists","ACS","ADR","First bloods","Clutches","Headshot %"],
    "🎮 Dota 2":           ["Kills","Deaths","Assists","GPM","XPM","Last hits","Hero damage","Tower damage"],
    "🎮 Rocket League":    ["Goals","Assists","Saves","Shots","Demos","Boost stolen","Score"],
}

PLATFORMS  = ["PrizePicks","Underdog Fantasy","DraftKings","FanDuel","BetMGM","Caesars","ESPNBet","Bet365","PointsBet","BetRivers"]
ALL_BOOKS  = ["PrizePicks","Underdog Fantasy","DraftKings","FanDuel","BetMGM","Caesars","ESPNBet","Bet365",
              "PointsBet","BetRivers","SuperDraft","Chalkboard","OwnersBox","Betr","Fliff","Sleeper","PropSwap"]
GRADE_ORDER= {"A":0,"B":1,"C":2,"D":3}

# ── Session state ────────────────────────────────────────────────────────────
for key,default in [("props",[]),("slip",[]),("results",[]),("api_key",""),("page","🏠 Dashboard")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── API helpers ──────────────────────────────────────────────────────────────
def get_api_key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return st.session_state.get("api_key","")

def get_client():
    key = get_api_key()
    if not key:
        st.error("Enter your Anthropic API key in the sidebar.")
        st.stop()
    return anthropic.Anthropic(api_key=key)

def ai_call(prompt, max_tokens=1200):
    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        tools=[{"type":"web_search_20250305","name":"web_search"}],
        messages=[{"role":"user","content":prompt}],
    )
    return " ".join(b.text for b in response.content if hasattr(b,"text"))

def conf_bar(conf):
    filled = int(conf/10)
    return "█"*filled + "░"*(10-filled) + f"  {conf}%"

def parse_block(text):
    grade_m = re.search(r"GRADE:\s*([ABCD])",text,re.I)
    conf_m  = re.search(r"CONFIDENCE:\s*(\d+)",text,re.I)
    key_m   = re.search(r"KEY STAT:\s*(.+)",text,re.I)
    sum_m   = re.search(r"SUMMARY:\s*([\s\S]+?)(?:\n[A-Z ]+:|$)",text,re.I)
    return {
        "grade":      grade_m.group(1).upper() if grade_m else "C",
        "confidence": int(conf_m.group(1))      if conf_m  else 50,
        "key_stat":   key_m.group(1).strip()    if key_m   else None,
        "summary":    sum_m.group(1).strip()    if sum_m   else text[:400],
    }

def get_section(text, label):
    m = re.search(rf"{label}:\s*([\s\S]+?)(?:\n[A-Z][A-Z ]+:|$)", text, re.I)
    return m.group(1).strip() if m else None

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎯 PropFinder")
    st.caption("Sports & Esports Research Platform")
    if not get_api_key():
        k = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
        if k:
            st.session_state.api_key = k
    else:
        st.success("API key loaded ✓", icon="🔑")

    st.divider()
    pages = ["🏠 Dashboard","🔍 Prop Analyzer","👤 Player Deep Dive",
             "📊 Market Scanner","📈 Trend & Hit Rate","📋 My Slip"]
    st.session_state.page = st.radio("Navigation", pages, label_visibility="collapsed")

    st.divider()
    slip_count = len(st.session_state.slip)
    total_res  = len(st.session_state.results)
    hits_res   = sum(1 for r in st.session_state.results if r.get("result")=="hit")
    st.metric("Slip legs", slip_count)
    st.metric("Hit rate", f"{round(hits_res/total_res*100)}%" if total_res else "—")

    st.divider()
    st.caption("**Grade legend**")
    st.markdown("""<span class='grade-A'>A</span> Strong edge<br>
<span class='grade-B'>B</span> Lean / value<br>
<span class='grade-C'>C</span> Neutral / skip<br>
<span class='grade-D'>D</span> Fade strongly""", unsafe_allow_html=True)

    st.divider()
    st.caption("**Sports covered**")
    for s in SPORTS:
        st.caption(s)

page = st.session_state.page

# ════════════════════════════════════════════════════════════════════════════
# 🏠 DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("🏠 Dashboard")
    st.caption(f"{datetime.now().strftime('%A, %B %d, %Y')}")

    col_main, col_side = st.columns([2,1])

    with col_main:
        st.subheader("Top Plays Today")
        c1,c2 = st.columns(2)
        sport_filter = c1.selectbox("Sport filter", ["All sports"]+list(SPORTS.keys()), key="d_sport")
        plat_filter  = c2.selectbox("Platform", ["All platforms"]+PLATFORMS, key="d_plat")

        if st.button("⚡ Generate today's top plays", type="primary", use_container_width=True):
            sport_clause = f"Focus exclusively on {sport_filter.split(' ',1)[-1]}." if sport_filter!="All sports" else "Cover a mix of NFL, NBA, MLB, MLS, and esports (LoL, CS2, Valorant)."
            plat_clause  = f"Lines are from {plat_filter}." if plat_filter!="All platforms" else "Reference PrizePicks and Underdog Fantasy."
            prompt = f"""You are a sharp DFS and player prop analyst. Today: {datetime.now().strftime('%B %d, %Y')}.
{sport_clause} {plat_clause}

Search for today's games, injury news, and current prop lines. Find 5 high-value props with strong statistical backing.

For EACH prop use this EXACT format followed by ---:

PROP: [Player Name] — [OVER/UNDER] [line] [stat] ([League])
GRADE: [A/B/C/D]
CONFIDENCE: [0-100]
KEY STAT: [one compelling data point]
SUMMARY: [2 sentences max with data]
---

Only include Grade A and B props. Be selective."""

            with st.spinner("Scanning today's best props..."):
                try:
                    raw    = ai_call(prompt, max_tokens=2000)
                    blocks = [b.strip() for b in raw.split("---") if "PROP:" in b]
                    if not blocks:
                        st.write(raw)
                    else:
                        for block in blocks:
                            prop_m  = re.search(r"PROP:\s*(.+)", block, re.I)
                            grade_m = re.search(r"GRADE:\s*([ABCD])", block, re.I)
                            conf_m  = re.search(r"CONFIDENCE:\s*(\d+)", block, re.I)
                            key_m   = re.search(r"KEY STAT:\s*(.+)", block, re.I)
                            sum_m   = re.search(r"SUMMARY:\s*([\s\S]+?)$", block, re.I)
                            grade = grade_m.group(1).upper() if grade_m else "B"
                            conf  = int(conf_m.group(1)) if conf_m else 65
                            label = prop_m.group(1).strip() if prop_m else "Prop"
                            with st.container(border=True):
                                hc,gc = st.columns([4,1])
                                with hc:
                                    st.markdown(f"**{label}**")
                                    if key_m: st.caption(f"📊 {key_m.group(1).strip()}")
                                with gc:
                                    st.markdown(f"<span class='grade-{grade}'>{grade}</span>", unsafe_allow_html=True)
                                st.caption(conf_bar(conf))
                                if sum_m: st.write(sum_m.group(1).strip())
                                if st.button("＋ Add to slip", key=f"d_add_{label[:25]}"):
                                    player_name = label.split("—")[0].strip()
                                    st.session_state.slip.append({
                                        "id":datetime.now().timestamp(),"player":player_name,
                                        "team":"","league":"Various","stat":label,"line":0,
                                        "direction":"over","platform":plat_filter if plat_filter!="All platforms" else "PrizePicks",
                                        "grade":grade,"confidence":conf,
                                        "summary":sum_m.group(1).strip() if sum_m else "","status":"done"
                                    })
                                    st.success("Added!")
                except Exception as e:
                    st.error(f"Error: {e}")

    with col_side:
        st.subheader("📊 Stats")
        total = len(st.session_state.results)
        hits  = sum(1 for r in st.session_state.results if r.get("result")=="hit")
        st.metric("Props tracked", total)
        st.metric("Hits", hits)
        st.metric("Hit rate", f"{round(hits/total*100)}%" if total else "—")
        st.metric("Slip legs", len(st.session_state.slip))

        if st.session_state.slip:
            st.divider()
            st.subheader("Current slip")
            for p in st.session_state.slip[:5]:
                g = p.get("grade","?")
                st.caption(f"**{p['player']}** · {p.get('direction','').upper()} {p.get('line','')} {p.get('stat','')} " +
                           (f"<span class='grade-{g}'>{g}</span>" if g in "ABCD" else ""), unsafe_allow_html=True)
            if len(st.session_state.slip) > 5:
                st.caption(f"...and {len(st.session_state.slip)-5} more")

# ════════════════════════════════════════════════════════════════════════════
# 🔍 PROP ANALYZER
# ════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Prop Analyzer":
    st.title("🔍 Prop Analyzer")
    st.caption("Deep-dive analysis on individual props with live stat research.")

    with st.form("prop_form"):
        c1,c2 = st.columns(2)
        player   = c1.text_input("Player name *", placeholder="e.g. Cristian Arango")
        team     = c2.text_input("Team", placeholder="e.g. LAFC")
        c3,c4 = st.columns(2)
        sport_key = c3.selectbox("Sport / League", list(SPORTS.keys()))
        platform  = c4.selectbox("Platform", PLATFORMS)
        stat_opts = SPORTS[sport_key] + ["Custom..."]
        c5,c6,c7  = st.columns(3)
        stat_choice = c5.selectbox("Stat type", stat_opts)
        line        = c6.number_input("Line", min_value=0.0, step=0.5, value=1.5, format="%.1f")
        direction   = c7.selectbox("Direction", ["Over","Under"])
        custom_stat = ""
        if stat_choice == "Custom...":
            custom_stat = st.text_input("Custom stat name")
        stat_label = custom_stat if stat_choice=="Custom..." else stat_choice
        c8,c9 = st.columns(2)
        context = c8.text_input("Match context", placeholder="e.g. vs Portland, home, Week 14")
        filters = c9.multiselect("Advanced filters", [
            "Opponent injured starter","Home game","Away game","Back-to-back",
            "Primetime game","vs weak defense","vs strong defense","Favorable H2H history"
        ])
        submitted = st.form_submit_button("⚡ Analyze prop", type="primary", use_container_width=True)

    if submitted:
        if not player:
            st.error("Enter a player name.")
        elif stat_choice=="Custom..." and not custom_stat:
            st.error("Enter a custom stat name.")
        else:
            filter_str = f"\nExtra context: {', '.join(filters)}." if filters else ""
            prompt = f"""You are a sharp sports betting analyst. Analyze this prop:

Player: {player}{' (' + team + ')' if team else ''}
League: {sport_key.split(' ',1)[-1]}
Prop: {direction.upper()} {line} {stat_label}
Platform: {platform}
{('Match context: ' + context) if context else ''}{filter_str}

Search for:
1. Last 5-8 game log for {stat_label}
2. Season average and home/away splits
3. Head-to-head vs this opponent if mentioned
4. Injury/lineup news
5. How this line compares to other books

Respond in this EXACT format:
GRADE: [A/B/C/D]
CONFIDENCE: [0-100]
KEY STAT: [single most compelling data point]
L5 AVERAGE: [average last 5 games]
HIT RATE: [e.g. 4/5 last 5 games hit over 1.5]
LINE VALUE: [sharp, fair, or inflated?]
SUMMARY: [3 sentences max — data-driven edge or fade reasoning]
RISK FLAGS: [any concerns]

Grade: A=strong edge, B=lean, C=neutral, D=fade."""

            with st.spinner(f"Scouting {player}..."):
                try:
                    raw    = ai_call(prompt, max_tokens=1200)
                    result = parse_block(raw)
                    l5_m   = re.search(r"L5 AVERAGE:\s*(.+)", raw, re.I)
                    hr_m   = re.search(r"HIT RATE:\s*(.+)", raw, re.I)
                    lv_m   = re.search(r"LINE VALUE:\s*(.+)", raw, re.I)
                    risk_m = re.search(r"RISK FLAGS:\s*([\s\S]+?)(?:\n[A-Z ]+:|$)", raw, re.I)
                    grade  = result["grade"]
                    conf   = result["confidence"]

                    with st.container(border=True):
                        hc,gc = st.columns([4,1])
                        with hc:
                            st.markdown(f"### {player}")
                            st.caption(f"{platform} · {sport_key.split(' ',1)[-1]} · **{direction.upper()} {line} {stat_label}**")
                        with gc:
                            st.markdown(f"<span class='grade-{grade}'>{grade}</span>", unsafe_allow_html=True)
                        st.caption(conf_bar(conf))

                        m1,m2,m3,m4 = st.columns(4)
                        m1.metric("Grade", grade)
                        m2.metric("Confidence", f"{conf}%")
                        if l5_m: m3.metric("L5 Avg", l5_m.group(1).strip()[:20])
                        if hr_m: m4.metric("Hit Rate", hr_m.group(1).strip()[:20])

                        st.divider()
                        if result.get("key_stat"): st.markdown(f"**📊 Key stat:** {result['key_stat']}")
                        if lv_m: st.markdown(f"**📉 Line value:** {lv_m.group(1).strip()}")
                        if result.get("summary"): st.write(result["summary"])
                        if risk_m: st.warning(f"⚠️ **Risk flags:** {risk_m.group(1).strip()}")

                        b1,b2 = st.columns(2)
                        with b1:
                            if st.button("＋ Add to slip", type="primary", key="add_slip"):
                                entry = {"id":datetime.now().timestamp(),"player":player,"team":team,
                                         "league":sport_key.split(' ',1)[-1],"stat":stat_label,"line":line,
                                         "direction":direction.lower(),"platform":platform,"context":context,
                                         **result,"status":"done"}
                                st.session_state.props.append(entry)
                                st.session_state.slip.append(entry)
                                st.success("Added to slip!")
                        with b2:
                            if st.button("Save to queue", key="save_q"):
                                entry = {"id":datetime.now().timestamp(),"player":player,"team":team,
                                         "league":sport_key.split(' ',1)[-1],"stat":stat_label,"line":line,
                                         "direction":direction.lower(),"platform":platform,"context":context,
                                         **result,"status":"done"}
                                st.session_state.props.append(entry)
                                st.success("Saved to queue!")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

    if st.session_state.props:
        st.divider()
        st.subheader("Prop Queue")
        for p in reversed(st.session_state.props[-10:]):
            g = p.get("grade","?")
            c1,c2 = st.columns([4,1])
            c1.caption(f"**{p['player']}** · {p.get('direction','').upper()} {p.get('line','')} {p.get('stat','')} · {p.get('league','')} · {p.get('platform','')}")
            if g in "ABCD":
                c2.markdown(f"<span class='grade-{g}'>{g}</span>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# 👤 PLAYER DEEP DIVE
# ════════════════════════════════════════════════════════════════════════════
elif page == "👤 Player Deep Dive":
    st.title("👤 Player Deep Dive")
    st.caption("Full statistical profile, splits, DFS value, and prop projections.")

    c1,c2,c3 = st.columns(3)
    player = c1.text_input("Player name", placeholder="e.g. LeBron James")
    sport  = c2.selectbox("Sport", list(SPORTS.keys()), key="pd_sport")
    team   = c3.text_input("Team (optional)")

    if st.button("🔎 Full player analysis", type="primary"):
        if not player:
            st.error("Enter a player name.")
        else:
            league = sport.split(' ',1)[-1]
            stats_str = ", ".join(SPORTS[sport][:6])
            prompt = f"""Comprehensive DFS and prop research profile for:
Player: {player}{' (' + team + ')' if team else ''}
Sport: {league}
Today: {datetime.now().strftime('%B %d, %Y')}

Search thoroughly and provide ALL sections:

OVERVIEW: [current role, form, importance to team — 2 sentences]
RECENT FORM: [last 5 games with key stats — {stats_str}]
SEASON AVERAGES: [key per-game averages this season]
HOME VS AWAY: [notable splits with numbers]
VS TOP DEFENSE: [stats vs top-10 defenses]
VS WEAK DEFENSE: [stats vs bottom-10 defenses]
INJURY STATUS: [current health status and any recent concerns]
UPCOMING MATCHUP: [next opponent, their defensive ranking vs this player's key stats]
DFS VALUE: [underpriced, fairly priced, or overpriced for DFS right now and why]
BEST PROP BET: [the single best prop line to target this week and why]
PROPS TO AVOID: [any prop lines to fade this week and why]
PROJECTION: [statistical projection for next game]"""

            with st.spinner(f"Building full profile for {player}..."):
                try:
                    raw = ai_call(prompt, max_tokens=2000)
                    st.markdown(f"## {player}")
                    st.caption(f"{league}{' · ' + team if team else ''}")

                    overview = get_section(raw, "OVERVIEW")
                    if overview: st.info(overview)

                    tab1,tab2,tab3,tab4 = st.tabs(["📊 Stats & Form","🏟 Splits","💰 DFS & Props","⚕️ Status"])

                    with tab1:
                        form = get_section(raw, "RECENT FORM")
                        avgs = get_section(raw, "SEASON AVERAGES")
                        if form: st.subheader("Recent form (L5)"); st.write(form)
                        if avgs: st.subheader("Season averages"); st.write(avgs)

                    with tab2:
                        ha   = get_section(raw, "HOME VS AWAY")
                        top  = get_section(raw, "VS TOP DEFENSE")
                        weak = get_section(raw, "VS WEAK DEFENSE")
                        if ha:   st.subheader("Home vs Away"); st.write(ha)
                        if top:  st.subheader("vs Top defenses"); st.write(top)
                        if weak: st.subheader("vs Weak defenses"); st.write(weak)

                    with tab3:
                        dfs  = get_section(raw, "DFS VALUE")
                        best = get_section(raw, "BEST PROP BET")
                        avoid= get_section(raw, "PROPS TO AVOID")
                        proj = get_section(raw, "PROJECTION")
                        if dfs:  st.subheader("DFS value"); st.write(dfs)
                        if best: st.subheader("✅ Best prop to target"); st.success(best)
                        if avoid:st.subheader("❌ Props to avoid"); st.error(avoid)
                        if proj: st.subheader("Next game projection"); st.info(proj)

                    with tab4:
                        inj  = get_section(raw, "INJURY STATUS")
                        mu   = get_section(raw, "UPCOMING MATCHUP")
                        if inj:
                            if any(w in inj.lower() for w in ["out","doubtful","questionable","injured","limited"]):
                                st.error(f"⚕️ {inj}")
                            else:
                                st.success(f"✅ {inj}")
                        if mu: st.subheader("Upcoming matchup"); st.write(mu)

                except Exception as e:
                    st.error(f"Error: {e}")

# ════════════════════════════════════════════════════════════════════════════
# 📊 MARKET SCANNER
# ════════════════════════════════════════════════════════════════════════════
elif page == "📊 Market Scanner":
    st.title("📊 Market Scanner")
    st.caption("Line shopping across 17 books + line movement tracking.")

    tab_shop, tab_move = st.tabs(["🏦 Line shopping","📉 Line movement"])

    with tab_shop:
        st.subheader("Compare a prop across books")
        c1,c2,c3 = st.columns(3)
        player = c1.text_input("Player", key="ms_p")
        stat   = c2.text_input("Stat type", placeholder="e.g. Points", key="ms_s")
        sport  = c3.selectbox("Sport", list(SPORTS.keys()), key="ms_sp")
        books  = st.multiselect("Books to compare", ALL_BOOKS,
                                default=["PrizePicks","Underdog Fantasy","DraftKings","FanDuel","BetMGM"])

        if st.button("🔎 Scan lines", type="primary", key="scan"):
            if not player or not stat:
                st.error("Enter player and stat.")
            else:
                prompt = f"""Sports betting odds analyst. Today: {datetime.now().strftime('%B %d, %Y')}.

Find current player prop lines for:
Player: {player} | Sport: {sport.split(' ',1)[-1]} | Stat: {stat}
Check these books: {', '.join(books)}

Respond EXACTLY:
LINE SUMMARY: [consensus / most common line]
BEST OVER: [book with best over line and why]
BEST UNDER: [book with best under line and why]
LINE DISCREPANCY: [any notable differences between books]
SHARP ACTION: [signs of sharp money or movement]
RECOMMENDATION: [best book + direction for value]

BOOK LINES:
[Book]: [line] ([over odds] / [under odds])
[repeat for each book found]"""

                with st.spinner("Scanning books..."):
                    try:
                        raw = ai_call(prompt, max_tokens=1200)
                        ls  = get_section(raw, "LINE SUMMARY")
                        bo  = get_section(raw, "BEST OVER")
                        bu  = get_section(raw, "BEST UNDER")
                        ld  = get_section(raw, "LINE DISCREPANCY")
                        sa  = get_section(raw, "SHARP ACTION")
                        rec = get_section(raw, "RECOMMENDATION")
                        bl_m= re.search(r"BOOK LINES:\s*([\s\S]+?)$", raw, re.I)

                        st.markdown(f"### {player} — {stat}")
                        if ls: st.info(f"**Consensus line:** {ls}")
                        cc1,cc2 = st.columns(2)
                        if bo: cc1.success(f"**Best over:** {bo}")
                        if bu: cc2.info(f"**Best under:** {bu}")
                        if ld: st.warning(f"⚠️ **Line discrepancy:** {ld}")
                        if sa: st.write(f"**📌 Sharp action:** {sa}")
                        if rec: st.success(f"✅ **Recommendation:** {rec}")
                        if bl_m:
                            st.divider()
                            st.subheader("Book-by-book lines")
                            st.write(bl_m.group(1).strip())
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab_move:
        st.subheader("Line movement tracker")
        c1,c2,c3 = st.columns(3)
        player2 = c1.text_input("Player", key="lm_p")
        stat2   = c2.text_input("Stat", key="lm_s")
        sport2  = c3.selectbox("Sport", list(SPORTS.keys()), key="lm_sp")

        if st.button("📉 Track line movement", type="primary", key="lm"):
            if not player2 or not stat2:
                st.error("Enter player and stat.")
            else:
                prompt = f"""Line movement analyst. Today: {datetime.now().strftime('%B %d, %Y')}.

Research line movement for:
Player: {player2} | Sport: {sport2.split(' ',1)[-1]} | Stat: {stat2}

OPENING LINE: [what did the line open at?]
CURRENT LINE: [current line]
MOVEMENT: [direction and magnitude of movement]
WHY IT MOVED: [injury news, sharp action, public betting, or other reason]
STEAM MOVES: [any steam moves or syndicate betting?]
FADE OR FOLLOW: [should you follow the line or fade it — explain with reasoning]"""

                with st.spinner("Checking line movement..."):
                    try:
                        raw = ai_call(prompt, max_tokens=800)
                        om  = re.search(r"OPENING LINE:\s*(.+)", raw, re.I)
                        cm  = re.search(r"CURRENT LINE:\s*(.+)", raw, re.I)
                        mm  = re.search(r"MOVEMENT:\s*(.+)", raw, re.I)
                        why = get_section(raw, "WHY IT MOVED")
                        fof = get_section(raw, "FADE OR FOLLOW")
                        if om or cm:
                            mc1,mc2,mc3 = st.columns(3)
                            if om: mc1.metric("Opening line", om.group(1).strip()[:15])
                            if cm: mc2.metric("Current line", cm.group(1).strip()[:15])
                            if mm: mc3.metric("Movement", mm.group(1).strip()[:15])
                        if why: st.write(f"**Why it moved:** {why}")
                        if fof: st.info(f"**Fade or follow:** {fof}")
                        if not any([om,cm,why,fof]): st.write(raw)
                    except Exception as e:
                        st.error(f"Error: {e}")

# ════════════════════════════════════════════════════════════════════════════
# 📈 TREND & HIT RATE
# ════════════════════════════════════════════════════════════════════════════
elif page == "📈 Trend & Hit Rate":
    st.title("📈 Trend & Hit Rate Research")
    st.caption("Historical hit rates, H2H data, and defense vs. position rankings.")

    tab1,tab2,tab3,tab4 = st.tabs(["📊 Prop trends","⚔️ Head-to-head","🛡 Def vs Position","📋 My results"])

    with tab1:
        st.subheader("Historical hit rate for a prop line")
        c1,c2,c3 = st.columns(3)
        player = c1.text_input("Player", key="tr_p")
        stat   = c2.text_input("Stat type", key="tr_s")
        line   = c3.number_input("Line", min_value=0.0, step=0.5, value=20.0, key="tr_l")
        c4,c5  = st.columns(2)
        direction = c4.selectbox("Direction", ["Over","Under"], key="tr_d")
        span      = c5.selectbox("Sample", ["Last 5 games","Last 10 games","Last 20 games","This season"])

        if st.button("📊 Get hit rate", type="primary", key="hr"):
            if not player or not stat:
                st.error("Enter player and stat.")
            else:
                prompt = f"""Sports data analyst. Today: {datetime.now().strftime('%B %d, %Y')}.

Research: {player} | Stat: {stat} | Line: {direction} {line} | Period: {span}

HIT RATE: [X/Y games hit]
HIT RATE %: [percentage]
AVERAGE: [average {stat} in this period]
HIGH: [highest single game]
LOW: [lowest single game]
STREAK: [current over/under streak]
HOME HIT RATE: [hit rate in home games]
AWAY HIT RATE: [hit rate in away games]
TREND: [trending up, down, or flat recently]
BEST SPOT: [game situations that produce the best results]
WORST SPOT: [game situations that produce the worst results]"""

                with st.spinner(f"Researching {player} trends..."):
                    try:
                        raw  = ai_call(prompt, max_tokens=1200)
                        hrm  = re.search(r"HIT RATE:\s*(.+)",raw,re.I)
                        hrpm = re.search(r"HIT RATE %:\s*(.+)",raw,re.I)
                        avm  = re.search(r"AVERAGE:\s*(.+)",raw,re.I)
                        him  = re.search(r"HIGH:\s*(.+)",raw,re.I)
                        lom  = re.search(r"LOW:\s*(.+)",raw,re.I)
                        strm = re.search(r"STREAK:\s*(.+)",raw,re.I)
                        trm  = get_section(raw,"TREND")
                        bsm  = get_section(raw,"BEST SPOT")
                        wsm  = get_section(raw,"WORST SPOT")

                        st.markdown(f"### {player} — {direction} {line} {stat} ({span})")
                        m1,m2,m3,m4,m5 = st.columns(5)
                        if hrm:  m1.metric("Hit rate", hrm.group(1).strip()[:15])
                        if hrpm: m2.metric("Hit %", hrpm.group(1).strip()[:10])
                        if avm:  m3.metric("Average", avm.group(1).strip()[:10])
                        if him:  m4.metric("High", him.group(1).strip()[:10])
                        if lom:  m5.metric("Low", lom.group(1).strip()[:10])
                        if strm: st.info(f"**Streak:** {strm.group(1).strip()}")
                        if trm:  st.write(f"**Trend:** {trm}")
                        if bsm:  st.success(f"✅ **Best spot:** {bsm}")
                        if wsm:  st.warning(f"⚠️ **Worst spot:** {wsm}")
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab2:
        st.subheader("Head-to-head history")
        c1,c2,c3 = st.columns(3)
        player = c1.text_input("Player", key="h2h_p")
        stat   = c2.text_input("Stat (optional)", key="h2h_s")
        opp    = c3.text_input("Opponent / team", placeholder="e.g. Boston Celtics", key="h2h_o")

        if st.button("⚔️ Get H2H data", type="primary", key="h2h"):
            if not player or not opp:
                st.error("Enter player and opponent.")
            else:
                prompt = f"""Research H2H history:
Player: {player} | Stat: {stat if stat else 'all major stats'} | Opponent: {opp}
Today: {datetime.now().strftime('%B %d, %Y')}

Search historical game logs vs {opp} and provide:
- Last 5 meetings: stats for each game
- Career average vs {opp}
- Notable trends or patterns in this matchup
- Prop hit rates vs {opp} if possible
- Verdict: favorable or unfavorable matchup for props?"""

                with st.spinner("Searching H2H history..."):
                    try:
                        st.write(ai_call(prompt, max_tokens=1000))
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab3:
        st.subheader("Defense vs Position")
        c1,c2,c3 = st.columns(3)
        sport_dvp = c1.selectbox("Sport", list(SPORTS.keys()), key="dvp_sp")
        opp_dvp   = c2.text_input("Opponent team", placeholder="e.g. LA Rams", key="dvp_o")
        pos_dvp   = c3.text_input("Position", placeholder="e.g. WR, PG, ST, ADC", key="dvp_p")

        if st.button("🛡 Get defensive rankings", type="primary", key="dvp"):
            if not opp_dvp:
                st.error("Enter an opponent team.")
            else:
                prompt = f"""DFS and prop analyst. Today: {datetime.now().strftime('%B %d, %Y')}.

How does {opp_dvp} defend {pos_dvp if pos_dvp else 'each position'} in {sport_dvp.split(' ',1)[-1]}?

- Current ranking vs {pos_dvp if pos_dvp else 'each position'}
- Key stats allowed per game
- Any recent defensive injuries affecting this matchup
- Which stats are most exploitable vs {opp_dvp}
- Top 3 players to target in props or DFS vs {opp_dvp} this week"""

                with st.spinner("Pulling defensive data..."):
                    try:
                        st.write(ai_call(prompt, max_tokens=1000))
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab4:
        st.subheader("My prop results")
        if not st.session_state.results:
            st.caption("No results yet. Mark props hit/miss from the Slip page.")
        else:
            hits  = sum(1 for r in st.session_state.results if r.get("result")=="hit")
            total = len(st.session_state.results)
            c1,c2,c3 = st.columns(3)
            c1.metric("Total tracked", total)
            c2.metric("Hits", hits)
            c3.metric("Hit rate", f"{round(hits/total*100)}%")
            st.divider()
            for r in reversed(st.session_state.results):
                rc = "hit" if r.get("result")=="hit" else "miss"
                rl = "✅ HIT" if rc=="hit" else "❌ MISS"
                st.caption(f"**{r['player']}** · {r.get('direction','').upper()} {r.get('line','')} {r.get('stat','')} · <span class='{rc}'>{rl}</span>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# 📋 MY SLIP
# ════════════════════════════════════════════════════════════════════════════
elif page == "📋 My Slip":
    st.title("📋 My Slip")
    st.caption("Build your parlay, get AI review, and log results.")

    if not st.session_state.slip:
        st.info("Slip is empty. Analyze props and add them here.")
    else:
        confs  = [p["confidence"] for p in st.session_state.slip if p.get("confidence")]
        grades = [p["grade"] for p in st.session_state.slip if p.get("grade") in "ABCD"]
        m1,m2,m3 = st.columns(3)
        m1.metric("Legs", len(st.session_state.slip))
        m2.metric("Avg confidence", f"{round(sum(confs)/len(confs))}%" if confs else "—")
        m3.metric("Best grade", sorted(grades, key=lambda g: GRADE_ORDER.get(g,9))[0] if grades else "—")
        st.divider()

        for i, prop in enumerate(st.session_state.slip):
            g = prop.get("grade","?")
            with st.container(border=True):
                c1,c2,c3 = st.columns([3,1,1])
                with c1:
                    st.markdown(f"**{prop['player']}**")
                    st.caption(f"{prop.get('direction','').upper()} {prop.get('line','')} {prop.get('stat','')} · {prop.get('league','')} · {prop.get('platform','')}")
                    if prop.get("key_stat"): st.caption(f"📊 {prop['key_stat']}")
                with c2:
                    if g in "ABCD":
                        st.markdown(f"<span class='grade-{g}'>{g}</span>", unsafe_allow_html=True)
                    if prop.get("confidence"): st.caption(f"{prop['confidence']}%")
                with c3:
                    r1,r2 = st.columns(2)
                    if r1.button("✅", key=f"hit_{i}", help="Mark hit"):
                        r = dict(prop); r["result"]="hit"; r["logged_at"]=str(datetime.now())
                        st.session_state.results.append(r)
                        st.session_state.slip.pop(i); st.rerun()
                    if r2.button("❌", key=f"miss_{i}", help="Mark miss"):
                        r = dict(prop); r["result"]="miss"; r["logged_at"]=str(datetime.now())
                        st.session_state.results.append(r)
                        st.session_state.slip.pop(i); st.rerun()
                    if st.button("🗑", key=f"del_{i}", help="Remove"):
                        st.session_state.slip.pop(i); st.rerun()

        st.divider()
        bc1,bc2 = st.columns(2)
        with bc1:
            if st.button("🤖 AI slip review", type="primary", use_container_width=True):
                lines = "\n".join(
                    f"• {p['player']} ({p.get('league','?')}) — {p.get('direction','over').upper()} "
                    f"{p.get('line','')} {p.get('stat','')} on {p.get('platform','?')}"
                    f"{' [Grade: '+p.get('grade','?')+', Conf: '+str(p.get('confidence','?'))+'%]' if p.get('grade') else ''}"
                    for p in st.session_state.slip
                )
                prompt = f"""Review this parlay slip:
{lines}
Today: {datetime.now().strftime('%B %d, %Y')}

For each leg: keep or drop + one-line reason.
Overall: play/fade recommendation. Identify the single weakest leg. Note if this is better as power play (2-3) or flex (4+).
Be direct."""
                with st.spinner("Reviewing slip..."):
                    try:
                        st.markdown("### AI Verdict")
                        st.markdown(ai_call(prompt, max_tokens=800))
                    except Exception as e:
                        st.error(f"Error: {e}")
        with bc2:
            if st.button("🗑 Clear slip", use_container_width=True):
                st.session_state.slip = []; st.rerun()

        st.divider()
        st.markdown("""**Grade legend** &nbsp; <span class='grade-A'>A</span> Strong edge &nbsp; <span class='grade-B'>B</span> Lean &nbsp; <span class='grade-C'>C</span> Neutral &nbsp; <span class='grade-D'>D</span> Fade""", unsafe_allow_html=True)
