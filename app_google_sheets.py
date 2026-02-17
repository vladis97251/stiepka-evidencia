import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
import io

# ══════════════════════════════════════════════════════
# NASTAVENIA - uprav len toto!
# ══════════════════════════════════════════════════════

SHEET_ID = "1MB041dTwz-zfGg6u3wM1XpmrS_ynDe1J"

# GID pre každý mesiac (1=január … 12=december)
SHEET_GIDS = {
    1:  "2041175941",
    2:  "996148749",
    3:  "1052948469",
    4:  "1742234642",
    5:  "1522704266",
    6:  "318756165",
    7:  "174620779",
    8:  "1714534272",
    9:  "2141494448",
    10: "953926717",
    11: "1911464342",
    12: "33776211",
}

NAZVY_MESIACOV = {
    1: "Január", 2: "Február", 3: "Marec", 4: "Apríl",
    5: "Máj", 6: "Jún", 7: "Júl", 8: "August",
    9: "September", 10: "Október", 11: "November", 12: "December"
}

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

# CSS štýly — kompatibilné s light aj dark režimom
st.markdown("""
<style>
    .main { padding-top: 1rem; }

    /* Metric karty — respektujú tému */
    .stMetric {
        border: 1px solid rgba(128,128,128,0.2);
        border-radius: 12px;
        padding: 16px !important;
    }
    .stMetric:hover {
        border-color: #2E86AB;
        box-shadow: 0 4px 12px rgba(46,134,171,0.15);
        transition: all 0.2s;
    }

    /* Veľký zostatok box — vždy biely text na modrom pozadí */
    .metric-big {
        background: linear-gradient(135deg, #2E86AB 0%, #1a5f7a 100%);
        color: white !important;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 8px 24px rgba(46,134,171,0.3);
    }
    .metric-big h1 { color: white !important; margin: 0; font-size: 2.5rem; }
    .metric-big p  { color: rgba(255,255,255,0.85) !important; margin: 0; font-size: 0.9rem; }

    /* Status farby — fungujú v oboch režimoch */
    .status-ok  { color: #06A77D; font-weight: bold; }
    .status-warn{ color: #F7A600; font-weight: bold; }
    .status-err { color: #E53E3E; font-weight: bold; }

    /* Info box — adaptívne farby */
    .info-box {
        background: rgba(46,134,171,0.08);
        border-left: 4px solid #2E86AB;
        border-radius: 4px;
        padding: 12px 16px;
        margin: 8px 0;
    }
    .month-box {
        background: rgba(46,134,171,0.05);
        border: 1px solid rgba(128,128,128,0.2);
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        font-size: 0.9rem;
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
        d.drop(d[d['Datum'] == 'Spolu'].index, inplace=True, errors='ignore')
        d['Datum'] = pd.to_datetime(d['Datum'], format='%m/%d/%Y', errors='coerce')
        d.dropna(subset=['Datum'], inplace=True)
        for col in ['Bodos', 'z Dreva HBP', 'Recyklácia', 'Jankula', 'Spotreba']:
            d[col] = pd.to_numeric(
                d[col].astype(str).str.replace(',', '.').str.strip(),
                errors='coerce'
            ).fillna(0)
        d['Prijem_celkom'] = d[['Bodos', 'z Dreva HBP', 'Recyklácia', 'Jankula']].sum(axis=1)

    return bc.reset_index(drop=True), bh.reset_index(drop=True)


def nacitaj_mesiace(od_mesiaca: int, do_mesiaca: int):
    """
    Načíta a spracuje dáta pre rozsah mesiacov (vrátane oboch krajných).
    Vráti spojené DataFramy pre BC a BH.
    """
    bc_all = []
    bh_all = []
    chyby = []

    for mesiac in range(od_mesiaca, do_mesiaca + 1):
        gid = SHEET_GIDS.get(mesiac)
        if not gid:
            continue

        df_raw, chyba = nacitaj_z_google_sheets(SHEET_ID, gid)
        if chyba:
            chyby.append(f"{NAZVY_MESIACOV[mesiac]}: {chyba}")
            continue

        bc_m, bh_m = spracuj_data(df_raw)
        if not bc_m.empty:
            bc_all.append(bc_m)
        if not bh_m.empty:
            bh_all.append(bh_m)

    bc_final = pd.concat(bc_all, ignore_index=True) if bc_all else pd.DataFrame()
    bh_final = pd.concat(bh_all, ignore_index=True) if bh_all else pd.DataFrame()

    return bc_final, bh_final, chyby


def vypocitaj(data, lokalita, datum):
    """
    Vypočíta stav skladu k danému dátumu.
    Rozdeľuje na:
      - predchádzajúce mesiace → tvoria "počiatočný stav mesiaca"
      - aktuálny mesiac (do vybraného dátumu) → príjem a spotreba mesiaca
    """
    filt = data[data['Datum'] <= pd.Timestamp(datum)]
    if filt.empty:
        return None

    mesiac = datum.month
    poc_orig = POCIATOCNY_STAV[lokalita]

    # Dáta za predchádzajúce mesiace (< aktuálny mesiac)
    predch = filt[filt['Datum'].dt.month < mesiac]
    prijem_predch = predch['Prijem_celkom'].sum() if not predch.empty else 0
    spotreba_predch = predch['Spotreba'].sum() if not predch.empty else 0

    # Počiatočný stav aktuálneho mesiaca = pôvodný + predchádzajúce mesiace
    poc_mesiac = poc_orig + prijem_predch - spotreba_predch

    # Dáta za aktuálny mesiac (do vybraného dátumu vrátane)
    aktualny = filt[filt['Datum'].dt.month == mesiac]
    prijem_mesiac = aktualny['Prijem_celkom'].sum() if not aktualny.empty else 0
    spotreba_mesiac = aktualny['Spotreba'].sum() if not aktualny.empty else 0

    zostatok = poc_mesiac + prijem_mesiac - spotreba_mesiac

    return {
        'pociatocny_orig':  poc_orig,
        'pociatocny':       poc_mesiac,
        'prijem_celkom':    prijem_mesiac,
        'prijem_bodos':     aktualny['Bodos'].sum() if not aktualny.empty else 0,
        'prijem_dreva':     aktualny['z Dreva HBP'].sum() if not aktualny.empty else 0,
        'prijem_recyklacia':aktualny['Recyklácia'].sum() if not aktualny.empty else 0,
        'prijem_jankula':   aktualny['Jankula'].sum() if not aktualny.empty else 0,
        'spotreba_celkom':  spotreba_mesiac,
        'zostatok':         zostatok,
        'mesiac':           mesiac,
        'data_filtered':    filt
    }


def vypocitaj_mesacne_sumare(data, lokalita, do_datumu):
    """
    Vypočíta súhrn pre každý mesiac (príjem, spotreba, zostatok na konci mesiaca).
    Vracia list slovníkov.
    """
    poc = POCIATOCNY_STAV[lokalita]
    filt = data[data['Datum'] <= pd.Timestamp(do_datumu)].copy()
    if filt.empty:
        return []

    filt['Mesiac'] = filt['Datum'].dt.month
    mesiace = sorted(filt['Mesiac'].unique())

    sumare = []
    kumulativny_zostatok = poc

    for m in mesiace:
        m_data = filt[filt['Mesiac'] == m]
        prijem = m_data['Prijem_celkom'].sum()
        spotreba = m_data['Spotreba'].sum()
        kumulativny_zostatok += prijem - spotreba
        sumare.append({
            'mesiac': m,
            'nazov': NAZVY_MESIACOV[m],
            'prijem': prijem,
            'spotreba': spotreba,
            'zmena': prijem - spotreba,
            'zostatok': kumulativny_zostatok,
            'dni': len(m_data)
        })

    return sumare


def dashboard(stav, lokalita, datum, mesacne_sumare):
    nazov = "Baňa Cigeľ" if lokalita == 'BC' else "Baňa Handlová"
    zostatok = stav['zostatok']
    mesiac_nazov = NAZVY_MESIACOV[stav['mesiac']]

    # Farebné upozornenie podľa zostatku — rôzne limity pre BC a BH
    if lokalita == 'BC':
        # BC: väčšia spotreba
        if zostatok > 300:
            stav_ikona, stav_text = "🟢", "Zásoby v poriadku"
        elif zostatok > 100:
            stav_ikona, stav_text = "🟡", "Zásoby nízke – sleduj"
        else:
            stav_ikona, stav_text = "🔴", "⚠️ KRITICKY NÍZKE ZÁSOBY"
    else:
        # BH: nižšia spotreba
        if zostatok > 100:
            stav_ikona, stav_text = "🟢", "Zásoby v poriadku"
        elif zostatok >= 50:
            stav_ikona, stav_text = "🟡", "Zásoby nízke – sleduj"
        else:
            stav_ikona, stav_text = "🔴", "⚠️ KRITICKY NÍZKE ZÁSOBY"

    st.markdown(f"## 📊 {nazov} ({lokalita}) — {datum.strftime('%d.%m.%Y')}")
    st.markdown(f"**Stav zásob:** {stav_ikona} {stav_text}")
    st.divider()

    # Zostatok veľký
    pct = (zostatok / stav['pociatocny_orig'] * 100) if stav['pociatocny_orig'] else 0
    st.markdown(f"""
    <div class="metric-big">
        <p>🎯 AKTUÁLNY ZOSTATOK NA SKLADE</p>
        <h1>{zostatok:,.2f} t</h1>
        <p>{pct:.1f} % z počiatočného stavu (1.1.2026)</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # Popis odkiaľ sa berie počiatočný stav
    if stav['mesiac'] == 1:
        poc_label = "📦 Počiatočný stav (1.1.2026)"
    else:
        predch_mesiac = NAZVY_MESIACOV[stav['mesiac'] - 1]
        poc_label = f"📦 Poč. stav ({mesiac_nazov}) = koniec {predch_mesiac}"

    # 4 metriky — za aktuálny mesiac
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(poc_label,
                  f"{stav['pociatocny']:,.2f} t")
    with c2:
        st.metric(f"➕ Príjem ({mesiac_nazov})",
                  f"{stav['prijem_celkom']:,.2f} t",
                  delta=f"+{stav['prijem_celkom']:,.2f} t")
    with c3:
        st.metric(f"➖ Spotreba ({mesiac_nazov})",
                  f"{stav['spotreba_celkom']:,.2f} t",
                  delta=f"-{stav['spotreba_celkom']:,.2f} t",
                  delta_color="inverse")
    with c4:
        zmena = zostatok - stav['pociatocny']
        zmena_str = f"+{zmena:,.2f} t" if zmena >= 0 else f"{zmena:,.2f} t"
        st.metric("🏁 Konečný stav",
                  f"{zostatok:,.2f} t",
                  delta=zmena_str,
                  delta_color="normal")

    st.divider()

    # Dodávatelia — aktuálny mesiac
    st.markdown(f"### 📥 Príjem podľa dodávateľov ({mesiac_nazov})")
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

    # Mesačný prehľad
    if mesacne_sumare and len(mesacne_sumare) > 1:
        st.divider()
        st.markdown("### 📅 Prehľad po mesiacoch")

        cols_header = st.columns([2, 2, 2, 2, 2])
        with cols_header[0]:
            st.markdown("**Mesiac**")
        with cols_header[1]:
            st.markdown("**Príjem [t]**")
        with cols_header[2]:
            st.markdown("**Spotreba [t]**")
        with cols_header[3]:
            st.markdown("**Zmena [t]**")
        with cols_header[4]:
            st.markdown("**Zostatok [t]**")

        for s in mesacne_sumare:
            cols_row = st.columns([2, 2, 2, 2, 2])
            zmena_prefix = "+" if s['zmena'] >= 0 else ""
            with cols_row[0]:
                st.markdown(f"**{s['nazov']}** ({s['dni']} dní)")
            with cols_row[1]:
                st.markdown(f"📦 {s['prijem']:,.2f}")
            with cols_row[2]:
                st.markdown(f"🔥 {s['spotreba']:,.2f}")
            with cols_row[3]:
                color = "#06A77D" if s['zmena'] >= 0 else "#D62246"
                st.markdown(f"<span style='color:{color};font-weight:bold'>{zmena_prefix}{s['zmena']:,.2f}</span>",
                           unsafe_allow_html=True)
            with cols_row[4]:
                st.markdown(f"**{s['zostatok']:,.2f}**")


def grafy(data, lokalita, datum):
    filt = data[data['Datum'] <= pd.Timestamp(datum)].copy()
    poc = POCIATOCNY_STAV[lokalita]
    filt = filt.sort_values('Datum').reset_index(drop=True)
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
        marker=dict(size=5, color='#2E86AB'),
        fillcolor='rgba(46,134,171,0.1)'
    ))
    fig1.add_hline(y=poc, line_dash='dash', line_color='#888',
                   annotation_text=f'Počiatočný stav ({poc:,.2f} t)',
                   annotation_position='top right')
    fig1.update_layout(
        title='📈 Vývoj zostatku na sklade (celé obdobie)',
        xaxis_title='Dátum', yaxis_title='Tony [t]',
        hovermode='x unified', height=420,
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

    # Graf 4 – Mesačný prehľad (ak viac mesiacov)
    if filt['Datum'].dt.month.nunique() > 1:
        st.divider()
        monthly = filt.copy()
        monthly['Mesiac'] = monthly['Datum'].dt.month
        monthly_agg = monthly.groupby('Mesiac').agg(
            Prijem=('Prijem_celkom', 'sum'),
            Spotreba=('Spotreba', 'sum')
        ).reset_index()
        monthly_agg['Nazov'] = monthly_agg['Mesiac'].map(NAZVY_MESIACOV)

        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            x=monthly_agg['Nazov'], y=monthly_agg['Prijem'],
            name='Príjem', marker_color='#06A77D'
        ))
        fig4.add_trace(go.Bar(
            x=monthly_agg['Nazov'], y=monthly_agg['Spotreba'],
            name='Spotreba', marker_color='#D62246'
        ))
        fig4.update_layout(
            title='📊 Mesačný príjem vs. spotreba',
            barmode='group', height=380,
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(showgrid=False, title=''),
            yaxis=dict(showgrid=True, gridcolor='#f0f0f0', title='Tony [t]')
        )
        st.plotly_chart(fig4, use_container_width=True)


def tabulka(data, datum):
    filt = data[data['Datum'] <= pd.Timestamp(datum)].copy()
    filt = filt.sort_values('Datum').reset_index(drop=True)
    filt['Datum'] = filt['Datum'].dt.strftime('%d.%m.%Y')
    filt = filt.rename(columns={'Prijem_celkom': 'Príjem spolu'})
    cols = ['Datum','Bodos','z Dreva HBP','Recyklácia','Jankula','Príjem spolu','Spotreba']
    for c in cols[1:]:
        filt[c] = filt[c].apply(lambda x: f"{x:,.2f}" if x != 0 else "—")
    st.dataframe(filt[cols], use_container_width=True, hide_index=True, height=500)


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

# Výber dátumu — ešte pred načítaním, aby sme vedeli aký rozsah mesiacov treba
st.markdown("### 📅 Výber dátumu")

col_d, col_info = st.columns([1, 2])
with col_d:
    # Dnešný dátum orezaný na platný rozsah
    dnes = date.today()
    default_datum = max(date(2026, 1, 1), min(dnes, date(2026, 12, 31)))

    vybrany_datum = st.date_input(
        "📅 Zobraziť stav ku dňu:",
        value=default_datum,
        min_value=date(2026, 1, 1),
        max_value=date(2026, 12, 31),
        format="DD.MM.YYYY"
    )

# Zistíme, koľko mesiacov treba načítať
mesiac_vybrany = vybrany_datum.month
mesiace_na_nacitanie = list(range(1, mesiac_vybrany + 1))

with col_info:
    mesiace_text = ", ".join([NAZVY_MESIACOV[m] for m in mesiace_na_nacitanie])
    st.markdown(f"""
    <div class="info-box">
        📡 Načítavam dáta za: <b>{mesiace_text}</b><br>
        (od 1.1.2026 do {vybrany_datum.strftime('%d.%m.%Y')} = <b>{len(mesiace_na_nacitanie)}</b> mesiac{'ov' if len(mesiace_na_nacitanie) > 1 else ''})
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Načítanie dát z Google Sheets — všetky potrebné mesiace
with st.spinner(f"📡 Načítavam dáta z Google Sheets ({len(mesiace_na_nacitanie)} mesiac{'ov' if len(mesiace_na_nacitanie) > 1 else ''})..."):
    bc_data, bh_data, chyby = nacitaj_mesiace(1, mesiac_vybrany)

if chyby:
    for ch in chyby:
        st.warning(f"⚠️ Problém s načítaním: {ch}")

if bc_data.empty and bh_data.empty:
    st.error("""
    ❌ **Nepodarilo sa načítať žiadne dáta z Google Sheets.**

    **Riešenie:**
    1. Otvor Google Sheets
    2. Klikni **Zdieľať** (vpravo hore)
    3. Zmeň na **"Ktokoľvek s odkazom"** → Zobrazovateľ
    4. Klikni **Obnoviť dáta** v ľavom paneli
    """)
    st.stop()

# Vyber dáta podľa lokality
data = bc_data if lokalita == 'BC' else bh_data

if data.empty:
    st.warning("⚠️ Žiadne dáta pre vybranú lokalitu.")
    st.stop()

# Zoradíme podľa dátumu
data = data.sort_values('Datum').reset_index(drop=True)

# Obmedzenie na skutočne dostupné dáta
min_d = data['Datum'].min().date()
max_d = data['Datum'].max().date()

# Ak vybraný dátum presahuje dostupné dáta
if vybrany_datum > max_d:
    st.info(f"ℹ️ Posledný dostupný záznam je z **{max_d.strftime('%d.%m.%Y')}**. Zobrazujem stav k tomuto dátumu.")
    vybrany_datum = max_d

if vybrany_datum < min_d:
    st.warning(f"⚠️ Prvý dostupný záznam je z {min_d.strftime('%d.%m.%Y')}.")
    st.stop()

# Info o načítaných dátach
st.markdown(f"""
<div class="info-box">
    ✅ Dáta úspešne načítané · 
    Rozsah: <b>{min_d.strftime('%d.%m.%Y')}</b> – <b>{max_d.strftime('%d.%m.%Y')}</b> · 
    Záznamy: <b>{len(data)} dní</b> ·
    Mesiacov: <b>{data['Datum'].dt.month.nunique()}</b>
</div>
""", unsafe_allow_html=True)

st.divider()

# Výpočet a zobrazenie
stav = vypocitaj(data, lokalita, vybrany_datum)
mesacne_sumare = vypocitaj_mesacne_sumare(data, lokalita, vybrany_datum)

if stav:
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📈 Grafy", "📋 Detail"])
    with tab1:
        dashboard(stav, lokalita, vybrany_datum, mesacne_sumare)
    with tab2:
        grafy(data, lokalita, vybrany_datum)
    with tab3:
        st.markdown("### 📋 Detailný prehľad pohybov")
        # Filter pre detail
        detail_mesiac = st.selectbox(
            "Filtrovať mesiac:",
            ["Všetky"] + [NAZVY_MESIACOV[m] for m in sorted(data[data['Datum'] <= pd.Timestamp(vybrany_datum)]['Datum'].dt.month.unique())]
        )
        if detail_mesiac != "Všetky":
            mesiac_num = [k for k, v in NAZVY_MESIACOV.items() if v == detail_mesiac][0]
            filtered_data = data[data['Datum'].dt.month == mesiac_num]
            tabulka(filtered_data, vybrany_datum)
        else:
            tabulka(data, vybrany_datum)
else:
    st.warning("⚠️ Pre vybraný dátum nie sú dáta.")
