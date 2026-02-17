import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
import io

# ══════════════════════════════════════════════════════
# NASTAVENIA - uprav len toto!
# ══════════════════════════════════════════════════════

SHEET_ID = "1MB041dTwz-zfGg6u3wM1XpmrS_ynDe1J"
SHEET_GID = "2041175941"

# Počiatočné stavy skladu k 1.1.2026 (tony)
POCIATOCNY_STAV = {
    'BC': 955.94,
    'BH': 222.42
}

# ══════════════════════════════════════════════════════

st.set_page_config(
    page_title="Evidencia štiepky | HE",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS štýly
st.markdown("""
<style>
    .main { padding-top: 1rem; }
    .stMetric {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 12px;
        padding: 16px !important;
    }
    .stMetric:hover {
        border-color: #2E86AB;
        box-shadow: 0 4px 12px rgba(46,134,171,0.15);
        transition: all 0.2s;
    }
    .metric-big {
        background: linear-gradient(135deg, #2E86AB 0%, #1a5f7a 100%);
        color: white !important;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 8px 24px rgba(46,134,171,0.3);
    }
    .metric-big h1 { color: white !important; margin: 0; font-size: 2.5rem; }
    .metric-big p  { color: rgba(255,255,255,0.8) !important; margin: 0; font-size: 0.9rem; }
    div[data-testid="stSidebar"] { background-color: #1a1a2e; }
    div[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    div[data-testid="stSidebar"] .stRadio label { color: #e0e0e0 !important; }
    div[data-testid="stSidebar"] hr { border-color: #333 !important; }
    .status-ok  { color: #06A77D; font-weight: bold; }
    .status-warn{ color: #F77F00; font-weight: bold; }
    .status-err { color: #D62246; font-weight: bold; }
    .info-box {
        background: #e8f4f8;
        border-left: 4px solid #2E86AB;
        border-radius: 4px;
        padding: 12px 16px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)   # cache 5 minút
def nacitaj_z_google_sheets(sheet_id: str, gid: str):
    """Stiahne dáta priamo z Google Sheets (verejný link)"""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    try:
        df = pd.read_csv(url)
        return df, None
    except Exception as e:
        return None, str(e)


def spracuj_data(df):
    """Rozdelí a vyčistí dáta pre BC a BH"""
    bc_cols = ['BC', 'Bodos', 'z Dreva HBP', 'Recyklácia', 'Jankula', 'Spotreba']
    bh_cols = ['BH', 'Bodos.1', 'z Dreva HBP.1', 'Recyklácia.1', 'Jankula.1', 'Spotreba.1']

    bc = df[bc_cols].copy()
    bh = df[bh_cols].copy()
    bc.columns = bh.columns = ['Datum', 'Bodos', 'z Dreva HBP', 'Recyklácia', 'Jankula', 'Spotreba']

    for d in [bc, bh]:
        d.drop(d[d['Datum'] == 'Spolu'].index, inplace=True)
        d['Datum'] = pd.to_datetime(d['Datum'], format='%m/%d/%Y', errors='coerce')
        d.dropna(subset=['Datum'], inplace=True)
        for col in ['Bodos', 'z Dreva HBP', 'Recyklácia', 'Jankula', 'Spotreba']:
            d[col] = pd.to_numeric(
                d[col].astype(str).str.replace(',', '.').str.strip(),
                errors='coerce'
            ).fillna(0)
        d['Prijem_celkom'] = d[['Bodos', 'z Dreva HBP', 'Recyklácia', 'Jankula']].sum(axis=1)

    return bc.reset_index(drop=True), bh.reset_index(drop=True)


def vypocitaj(data, lokalita, datum):
    """Vypočíta stav skladu k danému dátumu"""
    filt = data[data['Datum'] <= pd.Timestamp(datum)]
    if filt.empty:
        return None

    poc = POCIATOCNY_STAV[lokalita]
    prijem = filt['Prijem_celkom'].sum()
    spotreba = filt['Spotreba'].sum()

    return {
        'pociatocny':       poc,
        'prijem_celkom':    prijem,
        'prijem_bodos':     filt['Bodos'].sum(),
        'prijem_dreva':     filt['z Dreva HBP'].sum(),
        'prijem_recyklacia':filt['Recyklácia'].sum(),
        'prijem_jankula':   filt['Jankula'].sum(),
        'spotreba_celkom':  spotreba,
        'zostatok':         poc + prijem - spotreba,
        'data_filtered':    filt
    }


def dashboard(stav, lokalita, datum):
    nazov = "Baňa Cigeľ" if lokalita == 'BC' else "Baňa Handlová"
    zostatok = stav['zostatok']

    # Farebné upozornenie podľa zostatku
    if zostatok > 300:
        stav_ikona = "🟢"
        stav_text  = "Zásoby v poriadku"
    elif zostatok > 100:
        stav_ikona = "🟡"
        stav_text  = "Zásoby nízke – sleduj"
    else:
        stav_ikona = "🔴"
        stav_text  = "⚠️ KRITICKY NÍZKE ZÁSOBY"

    st.markdown(f"## 📊 {nazov} ({lokalita}) — {datum.strftime('%d.%m.%Y')}")
    st.markdown(f"**Stav zásob:** {stav_ikona} {stav_text}")
    st.divider()

    # Zostatok veľký
    pct = (zostatok / stav['pociatocny'] * 100) if stav['pociatocny'] else 0
    st.markdown(f"""
    <div class="metric-big">
        <p>🎯 AKTUÁLNY ZOSTATOK NA SKLADE</p>
        <h1>{zostatok:,.2f} t</h1>
        <p>{pct:.1f} % z počiatočného stavu</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # 3 metriky
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📦 Počiatočný stav (1.1.2026)",
                  f"{stav['pociatocny']:,.2f} t")
    with c2:
        st.metric("➕ Príjem spolu",
                  f"{stav['prijem_celkom']:,.2f} t",
                  delta=f"+{stav['prijem_celkom']:,.2f} t")
    with c3:
        st.metric("➖ Spotreba spolu",
                  f"{stav['spotreba_celkom']:,.2f} t",
                  delta=f"-{stav['spotreba_celkom']:,.2f} t",
                  delta_color="inverse")

    st.divider()

    # Dodávatelia
    st.markdown("### 📥 Príjem podľa dodávateľov")
    d1, d2, d3, d4 = st.columns(4)
    celk = stav['prijem_celkom'] or 1
    with d1:
        pct_b = stav['prijem_bodos']/celk*100
        st.metric("Bodos", f"{stav['prijem_bodos']:,.2f} t",
                  delta=f"{pct_b:.1f} %")
    with d2:
        pct_d = stav['prijem_dreva']/celk*100
        st.metric("z Dreva HBP", f"{stav['prijem_dreva']:,.2f} t",
                  delta=f"{pct_d:.1f} %")
    with d3:
        pct_r = stav['prijem_recyklacia']/celk*100
        st.metric("Recyklácia", f"{stav['prijem_recyklacia']:,.2f} t",
                  delta=f"{pct_r:.1f} %")
    with d4:
        pct_j = stav['prijem_jankula']/celk*100
        st.metric("Jankula", f"{stav['prijem_jankula']:,.2f} t",
                  delta=f"{pct_j:.1f} %")


def grafy(data, lokalita, datum):
    filt = data[data['Datum'] <= pd.Timestamp(datum)].copy()
    poc = POCIATOCNY_STAV[lokalita]
    filt['Kum_prijem']   = filt['Prijem_celkom'].cumsum()
    filt['Kum_spotreba'] = filt['Spotreba'].cumsum()
    filt['Zostatok']     = poc + filt['Kum_prijem'] - filt['Kum_spotreba']

    farby = {'Bodos':'#F77F00','z Dreva HBP':'#06A77D','Recyklácia':'#2E86AB','Jankula':'#A23B72'}

    # Graf 1 – Vývoj zostatku
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=filt['Datum'], y=filt['Zostatok'],
        mode='lines+markers',
        name='Zostatok', fill='tozeroy',
        line=dict(color='#2E86AB', width=3),
        marker=dict(size=6, color='#2E86AB'),
        fillcolor='rgba(46,134,171,0.1)'
    ))
    fig1.add_hline(y=poc, line_dash='dash', line_color='#888',
                   annotation_text=f'Počiatočný stav ({poc:,.2f} t)',
                   annotation_position='top right')
    fig1.update_layout(
        title='📈 Vývoj zostatku na sklade',
        xaxis_title='Dátum', yaxis_title='Tony [t]',
        hovermode='x unified', height=380,
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
        yaxis=dict(showgrid=True, gridcolor='#f0f0f0')
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Grafy 2 a 3 vedľa seba
    col1, col2 = st.columns(2)

    with col1:
        # Graf 2 – Príjem vs Spotreba
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=filt['Datum'], y=filt['Prijem_celkom'],
                              name='Príjem', marker_color='#06A77D'))
        fig2.add_trace(go.Bar(x=filt['Datum'], y=-filt['Spotreba'],
                              name='Spotreba', marker_color='#D62246'))
        fig2.update_layout(
            title='📊 Denný príjem vs. spotreba',
            barmode='relative', height=360,
            hovermode='x unified',
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
            yaxis=dict(showgrid=True, gridcolor='#f0f0f0', title='Tony [t]')
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        # Graf 3 – Koláč dodávateľov
        labely  = list(farby.keys())
        hodnoty = [filt[l].sum() for l in labely]
        fig3 = go.Figure(data=[go.Pie(
            labels=labely, values=hodnoty, hole=0.45,
            marker=dict(colors=list(farby.values())),
            textinfo='label+percent',
            hovertemplate='%{label}: %{value:.2f} t<extra></extra>'
        )])
        fig3.update_layout(
            title='🥧 Podiel dodávateľov',
            height=360, paper_bgcolor='white',
            showlegend=True,
            legend=dict(orientation='h', y=-0.15)
        )
        st.plotly_chart(fig3, use_container_width=True)


def tabulka(data, datum):
    filt = data[data['Datum'] <= pd.Timestamp(datum)].copy()
    filt['Datum'] = filt['Datum'].dt.strftime('%d.%m.%Y')
    filt = filt.rename(columns={'Prijem_celkom': 'Príjem spolu'})
    cols = ['Datum','Bodos','z Dreva HBP','Recyklácia','Jankula','Príjem spolu','Spotreba']
    for c in cols[1:]:
        filt[c] = filt[c].apply(lambda x: f"{x:,.2f}" if x != 0 else "—")
    st.dataframe(filt[cols], use_container_width=True, hide_index=True, height=400)


# ══════════════════════════════════════════════════════
# HLAVNÁ LOGIKA
# ══════════════════════════════════════════════════════

# Hlavička
st.title("🌲 Evidencia skladu štiepky")
st.caption("Handlovská energetika · BC (Baňa Cigeľ) · BH (Baňa Handlová)")

# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ Nastavenia")
    st.divider()

    lokalita = st.radio(
        "🏭 Lokalita:",
        ['BC', 'BH'],
        format_func=lambda x: f"{'Baňa Cigeľ' if x=='BC' else 'Baňa Handlová'} ({x})"
    )
    st.divider()

    # Refresh tlačidlo
    if st.button("🔄 Obnoviť dáta z Google Sheets", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("**📊 Počiatočné stavy (1.1.2026)**")
    st.markdown(f"- **BC:** {POCIATOCNY_STAV['BC']:,.2f} t")
    st.markdown(f"- **BH:** {POCIATOCNY_STAV['BH']:,.2f} t")
    st.divider()
    st.caption("Dáta sa automaticky obnovujú každých 5 minút.")

# Načítanie dát z Google Sheets
with st.spinner("📡 Načítavam dáta z Google Sheets..."):
    df_raw, chyba = nacitaj_z_google_sheets(SHEET_ID, SHEET_GID)

if chyba:
    st.error(f"""
    ❌ **Nepodarilo sa načítať dáta z Google Sheets.**

    **Chyba:** `{chyba}`

    **Riešenie:**
    1. Otvor Google Sheets
    2. Klikni **Zdieľať** (vpravo hore)
    3. Zmeň na **"Ktokoľvek s odkazom"** → Zobrazovateľ
    4. Klikni **Obnoviť dáta** v ľavom paneli
    """)
    st.stop()

# Spracovanie dát
bc_data, bh_data = spracuj_data(df_raw)
data = bc_data if lokalita == 'BC' else bh_data

if data.empty:
    st.warning("⚠️ Žiadne dáta v Google Sheets.")
    st.stop()

# Výber dátumu
min_d = data['Datum'].min().date()
max_d = data['Datum'].max().date()

col_d, col_info = st.columns([1, 2])
with col_d:
    vybrany_datum = st.date_input(
        "📅 Zobraziť stav ku dňu:",
        value=max_d, min_value=min_d, max_value=max_d,
        format="DD.MM.YYYY"
    )
with col_info:
    st.markdown(f"""
    <div class="info-box">
        ✅ Dáta načítané z Google Sheets · 
        Rozsah: <b>{min_d.strftime('%d.%m.%Y')}</b> – <b>{max_d.strftime('%d.%m.%Y')}</b> · 
        Záznamy: <b>{len(data)} dní</b>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Výpočet a zobrazenie
stav = vypocitaj(data, lokalita, vybrany_datum)

if stav:
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📈 Grafy", "📋 Detail"])
    with tab1:
        dashboard(stav, lokalita, vybrany_datum)
    with tab2:
        grafy(data, lokalita, vybrany_datum)
    with tab3:
        st.markdown("### 📋 Detailný prehľad pohybov")
        tabulka(data, vybrany_datum)
else:
    st.warning("⚠️ Pre vybraný dátum nie sú dáta.")
