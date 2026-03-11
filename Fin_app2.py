import os
import io
import base64
import re
import unicodedata
from typing import Optional
import pandas as pd
import streamlit as st
import pdfplumber

st.set_page_config(
    page_title="Financieel Toezicht Decentrale Overheid",
    layout="wide",
)

DATA_FILE = "financieel_toezicht_data.csv"
LOGO_PATH = "aftnext_logo.png"
AUTO_LOGIN = True  # zet op False voor 'echte' login

NAMEN_PER_TYPE = {
    "Gemeenten": [
        "Borsele",
        "Goes",
        "Hulst",
        "Kapelle",
        "Middelburg",
        "Noord-Beveland",
        "Reimerswaal",
        "Schouwen-Duiveland",
        "Sluis",
        "Terneuzen",
        "Tholen",
        "Veere",
        "Vlissingen",
    ],
    "Gemeenschappelijke regeling": [
        "BGTS aan-Z",
        "de Betho",
        "GR de Bevelanden",
        "Dethon",
        "GGD Zeeland",
        "Muziekschool Zeeland",
        "OLAZ",
        "Orionis",
        "SaBeWa",
        "Stadsgewestelijke Brandweer",
        "SWVO",
        "VRZ",
    ],
    "Waterschap": [
        "Scheldestromen",
    ],
}

USERS = {
    "sl.schot@zeeland.nl": {
        "wachtwoord": "demo123",
        "naam": "Simon Schot",
    },
    "demo@voorbeeld.nl": {
        "wachtwoord": "demo123",
        "naam": "Demo-gebruiker",
    },
}

DEFAULT_AUTO_USER = "sl.schot@zeeland.nl"


@st.cache_data
def get_logo_data_uri(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None

BALANS_VELDEN = {
    "activa": {
        "immateriele_vaste_activa": [
            "immateriele vaste activa",
            "immateriële vaste activa",
        ],
        "materiele_vaste_activa": [
            "materiele vaste activa",
            "materiële vaste activa",
        ],
        "financiele_vaste_activa": [
            "financiele vaste activa",
            "financiële vaste activa",
        ],
        "subtotaal_vaste_activa": [
            "subtotaal vaste activa",
            "totaal vaste activa",
        ],
        "bouwgronden_in_exploitatie": [
            "bouwgronden in exploitatie",
            "bouwgrond in exploitatie",
        ],
        "overige_voorraden": [
            "overige voorraden",
        ],
        "totaal_voorraden": [
            "totaal voorraden",
        ],
        "uitzettingen": [
            "uitzettingen",
            "uitzettingen <1 jaar",
        ],
        "liquide_middelen": [
            "liquide middelen",
        ],
        "overlopende_activa": [
            "overlopende activa",
        ],
        "totaal_vlottende_activa": [
            "totaal vlottende activa",
        ],
        "totaal_activa": [
            "totaal activa",
        ],
    },
    "passiva": {
        "algemene_reserve": [
            "algemene reserve",
        ],
        "bestemmingsreserve": [
            "bestemmingsreserve",
            "bestemmingsreserves",
        ],
        "gerealiseerd_resultaat": [
            "gerealiseerd resultaat",
            "resultaat na bestemming",
            "nog te bestemmen resultaat",
        ],
        "totaal_eigen_vermogen": [
            "totaal eigen vermogen",
            "eigen vermogen",
        ],
        "voorzieningen": [
            "voorzieningen",
        ],
        "vaste_schuld": [
            "vaste schuld",
        ],
        "totaal_vaste_passiva": [
            "totaal vaste passiva",
        ],
        "vlottende_passiva": [
            "vlottende passiva",
        ],
        "totaal_passiva": [
            "totaal passiva",
        ],
    },
}

# Weergavelabels balans: zoveel mogelijk gelijk aan omschrijvingen in documenten/PDF
BALANS_LABELS = {
    "immateriele_vaste_activa": "Immateriële vaste activa",
    "materiele_vaste_activa": "Materiële vaste activa",
    "financiele_vaste_activa": "Financiële vaste activa",
    "subtotaal_vaste_activa": "Subtotaal vaste activa / Totaal vaste activa",
    "bouwgronden_in_exploitatie": "Bouwgronden in exploitatie",
    "overige_voorraden": "Overige voorraden",
    "totaal_voorraden": "Totaal voorraden",
    "uitzettingen": "Uitzettingen (<1 jaar)",
    "liquide_middelen": "Liquide middelen",
    "overlopende_activa": "Overlopende activa",
    "totaal_vlottende_activa": "Totaal vlottende activa",
    "totaal_activa": "Totaal activa",
    "algemene_reserve": "Algemene reserve",
    "bestemmingsreserve": "Bestemmingsreserve",
    "gerealiseerd_resultaat": "Gerealiseerd resultaat / Resultaat na bestemming",
    "totaal_eigen_vermogen": "Eigen vermogen / Totaal eigen vermogen",
    "voorzieningen": "Voorzieningen",
    "vaste_schuld": "Vaste schuld",
    "totaal_vaste_passiva": "Totaal vaste passiva",
    "vlottende_passiva": "Totaal vlottende passiva",
    "totaal_passiva": "Totaal passiva",
}

ACTIVA_VOLGORDE = [
    "immateriele_vaste_activa",
    "materiele_vaste_activa",
    "financiele_vaste_activa",
    "subtotaal_vaste_activa",
    "bouwgronden_in_exploitatie",
    "overige_voorraden",
    "totaal_voorraden",
    "uitzettingen",
    "liquide_middelen",
    "overlopende_activa",
    "totaal_vlottende_activa",
    "totaal_activa",
]

PASSIVA_VOLGORDE = [
    "algemene_reserve",
    "bestemmingsreserve",
    "gerealiseerd_resultaat",
    "totaal_eigen_vermogen",
    "voorzieningen",
    "vaste_schuld",
    "totaal_vaste_passiva",
    "vlottende_passiva",
    "totaal_passiva",
]


@st.cache_data
def load_volumia(jaar: int):
    """Lees basisgegevens uit volumia_<jaar>.csv (CBS, inwoners, woonruimten)."""
    bestand = f"volumia_{jaar}.csv"
    if not os.path.exists(bestand):
        return None

    try:
        df_raw = pd.read_csv(bestand, sep=None, engine="python")
    except Exception:
        return None

    if df_raw.shape[1] < 52:
        return None

    col_inwoners = (
        df_raw.iloc[:, 13]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    col_woonr = (
        df_raw.iloc[:, 50]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    df = pd.DataFrame(
        {
            "cbs_code": df_raw.iloc[:, 0].astype(str).str.strip(),
            "naam_gemeente": df_raw.iloc[:, 1].astype(str).str.strip(),
            "aantal_inwoners": pd.to_numeric(col_inwoners, errors="coerce"),
            "aantal_woonruimten": pd.to_numeric(col_woonr, errors="coerce"),
        }
    )
    return df


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value)
    return value


# Maximale absolute waarde voor balansbedragen (voorkomt e+167 door misparsing)
MAX_BALANS_BEDRAG = 1e12


def sanitize_balance_value(x: float) -> float:
    """Zet onrealistische balanswaarden (bijv. uit PDF-parsing) op 0."""
    if x is None:
        return 0.0
    try:
        v = float(x)
        if abs(v) > MAX_BALANS_BEDRAG or (v != 0 and (v != v)):  # NaN check
            return 0.0
        return v
    except (TypeError, ValueError):
        return 0.0


def parse_bedrag(value):
    if value is None:
        return None

    txt = str(value).strip()
    if not txt:
        return None

    txt = txt.replace("€", "").replace("EUR", "").replace("eur", "")
    txt = txt.replace("(", "-").replace(")", "")
    txt = txt.replace("−", "-").replace("–", "-").replace("—", "-")
    txt = txt.replace(" ", "")
    txt = re.sub(r"[^0-9,.\-]", "", txt)

    if not txt or txt in {"-", ".", ","}:
        return None

    # Nederlands formaat / duizendtallen
    # Voorbeelden:
    # - 72.252  -> 72252  (punt = duizend)
    # - 45.283,34 -> 45283.34 (punt = duizend, komma = decimaal)
    # - 72252.34 -> 72252.34 (punt = decimaal)
    if "," in txt:
        # Komma aanwezig -> komma is decimaal, punten zijn duizendtallen
        txt = txt.replace(".", "")
        txt = txt.replace(",", ".")
    else:
        # Geen komma: bepaal of punt duizendtallen of decimaal is
        if re.match(r"^-?\d{1,3}(\.\d{3})+$", txt):
            # Duidelijk duizendnotatie (bijv. 1.234 of 12.345.678)
            txt = txt.replace(".", "")
        # Anders: laat één punt staan als decimaal scheiding
        if txt.count(".") > 1:
            txt = txt.replace(".", "")
        if txt.count(",") > 1:
            txt = txt.replace(",", "")

    try:
        result = float(txt)
        if abs(result) > MAX_BALANS_BEDRAG:
            return None
        return round(result)
    except Exception:
        return None


def get_balance_years() -> list[int]:
    basisjaar = int(st.session_state.get("boekjaar", 2026))
    return [basisjaar + i for i in range(4)]


def regel_bevat_balans(text: str) -> bool:
    """Alleen pagina's waar expliciet 'Geprognotiseerde balans' op staat."""
    text_n = normalize_text(text)
    return "geprognotiseerde balans" in text_n


def zoek_balans_paginas(pdf_bytes: bytes):
    paginas = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if regel_bevat_balans(text):
                paginas.append(page_num)
    return paginas


@st.dialog("Balanspagina's in PDF")
def toon_balans_pagina_popup():
    """Toon de gevonden balanspagina's van de PDF als afbeelding in een pop-up."""
    pdf_bytes = st.session_state.get("uploaded_pdf", None)
    balans_paginas = st.session_state.get("balans_pdf_paginas", [])

    if not pdf_bytes:
        st.warning("Geen PDF geladen. Upload eerst een PDF op het Dashboard.")
        return
    if not balans_paginas:
        st.info(
            "Nog geen balanspagina's gevonden. Klik eerst op 'Zoek balans in PDF' "
            "of upload een PDF waar 'Geprognosticeerde balans' in staat."
        )

    col_sluit, col_hint = st.columns([1, 4])
    with col_sluit:
        if st.button("Sluit", key="balans_popup_sluit"):
            st.session_state["show_balans_popup"] = False
            return
    with col_hint:
        if balans_paginas:
            st.caption(f"Pagina's: {', '.join(str(p) for p in sorted(balans_paginas))}")

    if "balans_popup_zoom" not in st.session_state:
        st.session_state["balans_popup_zoom"] = 1.0

    col_min, col_zoom, col_plus = st.columns([1, 2, 1])
    with col_min:
        if st.button("–", key="balans_popup_zoom_min"):
            st.session_state["balans_popup_zoom"] = max(
                0.5, float(st.session_state["balans_popup_zoom"]) - 0.25
            )
            st.session_state["show_balans_popup"] = True
            st.rerun()
    with col_zoom:
        st.write(f"Zoom: {st.session_state['balans_popup_zoom']:.2f}×")
    with col_plus:
        if st.button("+", key="balans_popup_zoom_plus"):
            st.session_state["balans_popup_zoom"] = min(
                6.0, float(st.session_state["balans_popup_zoom"]) + 0.25
            )
            st.session_state["show_balans_popup"] = True
            st.rerun()

    if not balans_paginas:
        return

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num in sorted(balans_paginas):
                if page_num < 1 or page_num > len(pdf.pages):
                    continue
                page = pdf.pages[page_num - 1]
                try:
                    # Resolutie schalen met zoomfactor
                    zoom = float(st.session_state.get("balans_popup_zoom", 1.0))
                    resolution = int(540 * zoom)
                    page_img = page.to_image(resolution=resolution)
                    pil_image = page_img.original
                    # Echte vergroting: schaal de weergavebreedte mee met zoom
                    width_px = int(800 * zoom)
                    st.image(
                        pil_image,
                        caption=f"Pagina {page_num}",
                        width=width_px,
                    )
                except Exception:
                    st.caption(
                        f"Pagina {page_num} kon niet als afbeelding worden getoond."
                    )
    except Exception as e:
        st.error(f"PDF kon niet worden geopend: {e}")


def render_balans_pdf_viewer():
    """Toon balanspagina's naast de invoer (geen pop-up)."""
    pdf_bytes = st.session_state.get("uploaded_pdf", None)
    balans_paginas = st.session_state.get("balans_pdf_paginas", [])

    if not pdf_bytes:
        st.info("Upload eerst een PDF op het Dashboard.")
        return
    if not balans_paginas:
        st.info("Nog geen balanspagina's gevonden. Klik eerst op 'Zoek balans in PDF'.")
        return

    if "balans_viewer_zoom" not in st.session_state:
        st.session_state["balans_viewer_zoom"] = 2.0
    if "balans_viewer_pagina" not in st.session_state:
        st.session_state["balans_viewer_pagina"] = sorted(balans_paginas)[0]

    # Besturing
    st.markdown("#### Balans (PDF)")
    st.caption(f"Beschikbare pagina's: {', '.join(str(p) for p in sorted(balans_paginas))}")

    col_prev, col_sel, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("Vorige", key="balans_viewer_prev"):
            pages = sorted(balans_paginas)
            cur = int(st.session_state["balans_viewer_pagina"])
            idx = pages.index(cur) if cur in pages else 0
            st.session_state["balans_viewer_pagina"] = pages[max(0, idx - 1)]
            st.rerun()
    with col_sel:
        st.selectbox(
            "Pagina",
            options=sorted(balans_paginas),
            key="balans_viewer_pagina",
            label_visibility="collapsed",
        )
    with col_next:
        if st.button("Volgende", key="balans_viewer_next"):
            pages = sorted(balans_paginas)
            cur = int(st.session_state["balans_viewer_pagina"])
            idx = pages.index(cur) if cur in pages else 0
            st.session_state["balans_viewer_pagina"] = pages[min(len(pages) - 1, idx + 1)]
            st.rerun()

    st.slider(
        "Zoom",
        min_value=0.5,
        max_value=6.0,
        step=0.25,
        key="balans_viewer_zoom",
    )

    # Render 1 pagina (groot genoeg om af te lezen)
    page_num = int(st.session_state["balans_viewer_pagina"])
    zoom = float(st.session_state["balans_viewer_zoom"])
    resolution = int(180 * zoom)
    width_px = int(520 * zoom)

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if 1 <= page_num <= len(pdf.pages):
                page = pdf.pages[page_num - 1]
                page_img = page.to_image(resolution=resolution)
                st.image(
                    page_img.original,
                    caption=f"Pagina {page_num}",
                    width=width_px,
                )
            else:
                st.warning("Pagina valt buiten het bereik van de PDF.")
    except Exception as e:
        st.error(f"PDF kon niet worden geopend: {e}")


def detect_section(line_norm: str, current_section):
    if "activa" in line_norm and "passiva" not in line_norm:
        return "activa"
    if "passiva" in line_norm and "activa" not in line_norm:
        return "passiva"
    return current_section


def match_balance_field(line_norm: str, section):
    groepen = BALANS_VELDEN if section is None else {section: BALANS_VELDEN[section]}
    for groep_naam, groep in groepen.items():
        for veld, zoektermen in groep.items():
            if any(term in line_norm for term in zoektermen):
                return veld, groep_naam
    return None, None


def extract_bedragen_from_line(raw_line: str):
    matches = re.findall(r"-?\d[\d\.\,\s]*", raw_line)
    bedragen = []
    for match in matches:
        bedrag = parse_bedrag(match)
        if bedrag is not None:
            bedragen.append(bedrag)
    return bedragen


def detect_year_columns(cells: list[str], balance_years: list[int]):
    kolommap = {}
    for idx, cell in enumerate(cells):
        cell_norm = normalize_text(cell)
        for jaar in balance_years:
            if str(jaar) == cell_norm:
                kolommap[idx] = jaar
    return kolommap


def extract_balance_fields_from_pdf(pdf_bytes: bytes, balance_years: list[int]):
    gevonden = {}
    debug_regels = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        balans_paginas = zoek_balans_paginas(pdf_bytes)
        # Alleen zoeken op pagina's waar "Geprognosticeerde balans" staat; geen andere blz.

        for page_num in balans_paginas:
            page = pdf.pages[page_num - 1]

            text = page.extract_text() or ""
            current_section = None

            for raw_line in text.splitlines():
                line_norm = normalize_text(raw_line)
                if not line_norm:
                    continue

                current_section = detect_section(line_norm, current_section)
                veld, groep = match_balance_field(line_norm, current_section)

                if veld:
                    bedragen = extract_bedragen_from_line(raw_line)
                    if bedragen:
                        for i, bedrag in enumerate(bedragen[: len(balance_years)]):
                            sleutel = f"{veld}_{balance_years[i]}"
                            if sleutel not in gevonden:
                                gevonden[sleutel] = round(bedrag)
                        debug_regels.append(
                            f"Pagina {page_num} tekst | {groep} | {veld} -> {bedragen} | {raw_line}"
                        )

            tables = page.extract_tables()
            for table in tables or []:
                current_section_table = None
                year_column_map = {}

                for row in table:
                    if not row:
                        continue

                    row_clean = [str(cell).strip() if cell is not None else "" for cell in row]
                    row_text = " ".join(cell for cell in row_clean if cell)
                    row_norm = normalize_text(row_text)
                    if not row_norm:
                        continue

                    year_column_map_candidate = detect_year_columns(row_clean, balance_years)
                    if year_column_map_candidate:
                        year_column_map = year_column_map_candidate

                    current_section_table = detect_section(row_norm, current_section_table)
                    veld, groep = match_balance_field(row_norm, current_section_table)

                    if veld:
                        if year_column_map:
                            for idx, jaar in year_column_map.items():
                                if idx < len(row_clean):
                                    bedrag = parse_bedrag(row_clean[idx])
                                    if bedrag is not None:
                                        sleutel = f"{veld}_{jaar}"
                                        if sleutel not in gevonden:
                                            gevonden[sleutel] = round(bedrag)
                            debug_regels.append(
                                f"Pagina {page_num} tabel-kolommen | {groep} | {veld} | {row_text}"
                            )
                        else:
                            bedragen = []
                            for cell in row_clean:
                                bedrag = parse_bedrag(cell)
                                if bedrag is not None:
                                    bedragen.append(bedrag)

                            if bedragen:
                                for i, bedrag in enumerate(bedragen[: len(balance_years)]):
                                    sleutel = f"{veld}_{balance_years[i]}"
                                    if sleutel not in gevonden:
                                        gevonden[sleutel] = round(bedrag)
                                debug_regels.append(
                                    f"Pagina {page_num} tabel-rij | {groep} | {veld} -> {bedragen} | {row_text}"
                                )

    return gevonden, debug_regels


def render_balance_table(titel: str, velden: list[str], balance_years: list[int]):
    st.markdown(f"#### {titel}")
    kolommen = st.columns([2.8] + [1] * len(balance_years))

    with kolommen[0]:
        st.write("")

    for i, jaar in enumerate(balance_years):
        with kolommen[i + 1]:
            st.markdown(f"**{jaar}**")

    for veld in velden:
        with kolommen[0]:
            st.write(BALANS_LABELS[veld])

        for i, jaar in enumerate(balance_years):
            with kolommen[i + 1]:
                sleutel = f"{veld}_{jaar}"
                huidige = st.session_state.get(sleutel, 0.0)
                st.session_state[sleutel] = sanitize_balance_value(huidige)

                st.number_input(
                    label=sleutel,
                    min_value=None,
                    max_value=None,
                    step=1.0,
                    key=sleutel,
                    label_visibility="collapsed",
                    format="%.0f",
                )


def logout() -> None:
    st.session_state.pop("authenticated", None)
    st.session_state.pop("current_user", None)
    st.rerun()


def login() -> None:
    col_links, col_midden, col_rechts = st.columns([1, 2, 1])
    with col_midden:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
        st.markdown(
            "<h2 style='text-align:center;margin-top:1rem;'>Login Financieel Toezicht</h2>",
            unsafe_allow_html=True,
        )

    with st.form("login_form"):
        email = st.text_input("E-mailadres", key="login_email")
        wachtwoord = st.text_input("Wachtwoord", type="password", key="login_password")
        provincie = st.selectbox("Provincie", ["Zeeland", "Zuid-Holland", "Noord-Brabant"])
        ingelogd = st.form_submit_button("Login")

    if ingelogd:
        gebruiker = USERS.get(email)
        if gebruiker and wachtwoord == gebruiker["wachtwoord"]:
            st.session_state["authenticated"] = True
            st.session_state["current_user"] = {
                "email": email,
                "naam": gebruiker["naam"],
                "provincie": provincie,
            }
            st.rerun()
        else:
            st.error("Onjuiste combinatie van e-mail en wachtwoord.")

    st.stop()


if AUTO_LOGIN and not st.session_state.get("authenticated"):
    auto_user = USERS.get(DEFAULT_AUTO_USER)
    if auto_user:
        st.session_state["authenticated"] = True
        st.session_state["current_user"] = {
            "email": DEFAULT_AUTO_USER,
            "naam": auto_user["naam"],
            "provincie": "Zeeland",
        }

if not st.session_state.get("authenticated") and not AUTO_LOGIN:
    login()

gebruiker = st.session_state.get("current_user", {})

kol_links, kol_rechts = st.columns([3, 1])
with kol_links:
    st.title("Financieel toezicht decentrale overheid")
with kol_rechts:
    st.write(f"Ingelogd als **{gebruiker.get('naam', 'onbekend')}**")
    if st.button("Uitloggen"):
        logout()

st.write(
    "Vul kerncijfers uit de begroting of jaarrekening in. "
    "De applicatie berekent enkele basisindicatoren voor financieel toezicht "
    "en slaat de gegevens op in een CSV-bestand dat je later kunt inzien."
)

tab_start, tab_invoer, tab_database = st.tabs(
    ["Dashboard", "Invoer gegevens", "Database / overzicht"]
)

with tab_start:
    logo_uri = get_logo_data_uri(LOGO_PATH)
    if logo_uri:
        st.markdown(
            f"""
            <style>
              .aftnext-floating-logo {{
                position: fixed;
                top: 0.75rem;
                right: 1rem;
                z-index: 9999;
                background: rgba(255,255,255,0.0);
              }}
            </style>
            <div class="aftnext-floating-logo">
              <img src="{logo_uri}" width="280" />
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader(f"Welkom {gebruiker.get('naam', '')}")

    kol_zoek, kol_detail = st.columns([1, 3])

    with kol_zoek:
        st.markdown("#### Upload document")
        uploaded_pdf_global = st.file_uploader(
            "Upload begroting / jaarrekening (PDF)",
            type="pdf",
            key="global_pdf_upload",
        )

        if uploaded_pdf_global is not None:
            st.session_state["uploaded_pdf"] = uploaded_pdf_global.read()
            st.success("PDF succesvol geladen. Deze wordt gebruikt in andere tabbladen.")

    with kol_detail:
        gekozen_type = st.session_state.get("type_overheid")
        gekozen_naam = st.session_state.get("naam_overheid")
        dash_documenttype = st.session_state.get("documenttype")
        dash_boekjaar = st.session_state.get("boekjaar")

        if not gekozen_type or not gekozen_naam:
            st.markdown("### Geen organisatie geselecteerd")
            st.info(
                "Selecteer je gemeente/GR/waterschap in tab **Invoer gegevens → 1. Algemeen**."
            )
        else:
            titel_type = (
                gekozen_type[:-1] if str(gekozen_type).endswith("n") else gekozen_type
            )
            st.markdown(f"### {titel_type} {gekozen_naam}")

            if dash_documenttype and dash_boekjaar:
                st.caption(f"{dash_documenttype} • {dash_boekjaar}")

            st.markdown("#### Algemene info")
            col_info_links, col_info_rechts = st.columns(2)
            with col_info_links:
                st.write("**Provincie**")
            with col_info_rechts:
                st.write(gebruiker.get("provincie", "Onbekend"))

            st.write("---")
            st.markdown("#### Documenten")

            if os.path.exists(DATA_FILE):
                df_dashboard = pd.read_csv(
                    DATA_FILE,
                    engine="python",
                    on_bad_lines="skip",
                )
                mask = (df_dashboard["type_overheid"] == gekozen_type) & (
                    df_dashboard["naam_overheid"] == gekozen_naam
                )
                resultaten = df_dashboard[mask]

                if resultaten.empty:
                    st.info("Geen resultaten aanwezig in de tabel.")
                else:
                    bestaande_kolommen = [
                        kol
                        for kol in [
                            "documenttype",
                            "boekjaar",
                            "begrotingssaldo",
                            "ingelogde_gebruiker",
                        ]
                        if kol in resultaten.columns
                    ]
                    tabel = resultaten[bestaande_kolommen].sort_values(
                        ["boekjaar", "documenttype"]
                    )
                    st.dataframe(tabel)
            else:
                st.info("Er zijn nog geen gegevens opgeslagen in de database.")

with tab_invoer:
    (
        sub_algemeen,
        sub_resultaat,
        sub_balans,
        sub_kengetallen,
        sub_weerstand,
        sub_onderhoud,
        sub_verbonden,
        sub_lokale_heffingen,
    ) = st.tabs(
        [
            "1. Algemeen",
            "3. Resultaatbepaling",
            "4. Geprognosticeerde balans",
            "5. Kengetallen",
            "6. Weerstandsvermogen",
            "7. Onderhoud kapitaalgoederen",
            "8. Verbonden partijen",
            "11. Lokale heffingen",
        ]
    )

    with sub_algemeen:
        st.subheader("1. Algemeen – basisgegevens")

        opties_type_overheid = [
            "Gemeenten",
            "Waterschap",
            "Gemeenschappelijke regeling",
        ]
        type_overheid = st.selectbox(
            "Type overheid",
            opties_type_overheid,
            key="type_overheid",
        )

        opties_naam_overheid = NAMEN_PER_TYPE.get(
            type_overheid,
            ["(Nog geen namen ingevuld voor dit type)"],
        )

        naam_overheid = st.selectbox(
            "Naam overheid",
            opties_naam_overheid,
            key="naam_overheid",
        )

        jaren = list(range(2023, 2031))
        if "boekjaar" not in st.session_state:
            st.session_state["boekjaar"] = jaren[-4]
        boekjaar = st.selectbox(
            "Boekjaar",
            jaren,
            key="boekjaar",
        )

        documenttype = st.selectbox(
            "Type document",
            ["Begroting", "Jaarrekening", "Kadernota"],
            key="documenttype",
        )

        prev_type = st.session_state.get("_prev_type_overheid")
        prev_naam = st.session_state.get("_prev_naam_overheid")
        prev_boekjaar = st.session_state.get("_prev_boekjaar")
        organisatie_gewijzigd = (
            prev_type != type_overheid
            or prev_naam != naam_overheid
            or prev_boekjaar != boekjaar
        )

        volumia_info = ""
        if organisatie_gewijzigd:
            if type_overheid == "Gemeenten":
                df_volumia = load_volumia(boekjaar)
                if df_volumia is None:
                    volumia_info = (
                        f"volumia_{boekjaar}.csv niet gevonden of niet leesbaar; "
                        "automatische vulling alleen voor beschikbare jaren."
                    )
                else:
                    match = df_volumia.loc[
                        df_volumia["naam_gemeente"] == str(naam_overheid).strip()
                    ]
                    if not match.empty:
                        row = match.iloc[0]
                        st.session_state["cbs_code"] = str(row["cbs_code"])
                        try:
                            if pd.notna(row["aantal_inwoners"]):
                                st.session_state["aantal_inwoners"] = int(
                                    row["aantal_inwoners"]
                                )
                        except Exception:
                            st.session_state["aantal_inwoners"] = 0
                        try:
                            if pd.notna(row["aantal_woonruimten"]):
                                st.session_state["aantal_woonruimten"] = int(
                                    row["aantal_woonruimten"]
                                )
                        except Exception:
                            st.session_state["aantal_woonruimten"] = 0
                    else:
                        volumia_info = (
                            "Geen match gevonden in volumia-bestand voor deze gemeente."
                        )
            else:
                st.session_state["cbs_code"] = ""
                st.session_state["aantal_inwoners"] = 0
                st.session_state["aantal_woonruimten"] = 0

            st.session_state["_prev_type_overheid"] = type_overheid
            st.session_state["_prev_naam_overheid"] = naam_overheid
            st.session_state["_prev_boekjaar"] = boekjaar

        if volumia_info:
            st.caption(volumia_info)

        st.markdown("---")
        st.markdown("#### Kengetallen")

        st.text_input(
            "Behandeld ambtenaar",
            value=st.session_state.get(
                "behandeld_ambtenaar", gebruiker.get("naam", "")
            ),
            key="behandeld_ambtenaar",
        )

        st.radio(
            "Invoer gereed?",
            ["Nee", "Ja"],
            index=0,
            key="invoer_gereed",
        )

        st.text_input("Dossiernummer", key="dossiernummer")
        st.text_input("CBS-code", key="cbs_code")

        st.number_input(
            "Aantal inwoners (peildatum: 1 januari – begrotingsjaar)",
            min_value=0,
            step=1,
            key="aantal_inwoners",
        )
        st.number_input(
            "Aantal woonruimten (peildatum: 1 januari – begrotingsjaar)",
            min_value=0,
            step=1,
            key="aantal_woonruimten",
        )

        st.date_input(
            "Datum vaststelling begroting",
            key="datum_vaststelling_begroting",
        )
        st.date_input(
            "Datum verzending begroting",
            key="datum_verzending_begroting",
        )

        st.selectbox(
            "Is er sprake van AHRI-toezicht?",
            ["Nee", "Ja"],
            key="alert_toezicht",
        )

        st.text_area(
            "Wat komt er in de brief?",
            key="brief_toelichting",
        )

    with sub_resultaat:
        st.subheader("3. Resultaatbepaling – exploitatie")

        st.markdown("#### Vragen")
        st.radio(
            "Is er een eerste begrotingswijziging vastgesteld die bij het financieel toezicht dient te worden betrokken?",
            ["Nee", "Ja"],
            key="result_eerste_begrotingswijziging",
        )
        st.radio(
            "Zijn er amendementen met financiële consequenties vastgesteld?",
            ["Nee", "Ja"],
            key="result_amendementen",
        )

        st.markdown("#### Exploitatie en resultaat per jaar (x 1.000)")

        basisjaar = int(st.session_state.get("boekjaar", 2026))
        jaren_reeks = [basisjaar + i for i in range(4)]

        kol_gewichten = [2] + [1] * len(jaren_reeks)
        kolommen = st.columns(kol_gewichten)

        with kolommen[0]:
            st.write("")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                st.markdown(f"**{jaar}**")

        lasten_excl = {}
        baten_excl = {}

        with kolommen[0]:
            st.write("Lasten exclusief reservemutaties")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                lasten_excl[jaar] = st.number_input(
                    f"lasten_excl_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"lasten_excl_{jaar}",
                    label_visibility="collapsed",
                )

        with kolommen[0]:
            st.write("Baten exclusief reservemutaties")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                baten_excl[jaar] = st.number_input(
                    f"baten_excl_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"baten_excl_{jaar}",
                    label_visibility="collapsed",
                )

        saldo_baten_lasten = {}
        with kolommen[0]:
            st.write("**Saldo van baten en lasten**")
        for i, jaar in enumerate(jaren_reeks):
            saldo = baten_excl[jaar] - lasten_excl[jaar]
            saldo_baten_lasten[jaar] = saldo
            st.session_state[f"saldo_baten_lasten_{jaar}"] = saldo
            with kolommen[i + 1]:
                st.write(f"{saldo:,.0f}")

        toevoeg_res = {}
        onttrekk_res = {}

        with kolommen[0]:
            st.write("Toevoegingen reserves (last)")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                toevoeg_res[jaar] = st.number_input(
                    f"toevoeg_reserves_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"toevoeg_reserves_{jaar}",
                    label_visibility="collapsed",
                )

        with kolommen[0]:
            st.write("Onttrekkingen reserves (baat)")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                onttrekk_res[jaar] = st.number_input(
                    f"onttrekk_reserves_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"onttrekk_reserves_{jaar}",
                    label_visibility="collapsed",
                )

        saldo_mut_reserves = {}
        with kolommen[0]:
            st.write("**Saldo mutatie reserves**")
        for i, jaar in enumerate(jaren_reeks):
            saldo = onttrekk_res[jaar] - toevoeg_res[jaar]
            saldo_mut_reserves[jaar] = saldo
            st.session_state[f"saldo_mut_reserves_{jaar}"] = saldo
            with kolommen[i + 1]:
                st.write(f"{saldo:,.0f}")

        geraamd_resultaat = {}
        with kolommen[0]:
            st.write("**Geraamd resultaat**")
        for i, jaar in enumerate(jaren_reeks):
            res = saldo_baten_lasten[jaar] + saldo_mut_reserves[jaar]
            geraamd_resultaat[jaar] = res
            st.session_state[f"geraamd_resultaat_{jaar}"] = res
            with kolommen[i + 1]:
                st.write(f"{res:,.0f}")

        inc_lasten = {}
        inc_baten = {}

        with kolommen[0]:
            st.write("Incidentele lasten (incl. reservemutaties)")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                inc_lasten[jaar] = st.number_input(
                    f"incidentele_lasten_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"incidentele_lasten_{jaar}",
                    label_visibility="collapsed",
                )

        with kolommen[0]:
            st.write("Incidentele baten (incl. reservemutaties)")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                inc_baten[jaar] = st.number_input(
                    f"incidentele_baten_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"incidentele_baten_{jaar}",
                    label_visibility="collapsed",
                )

        saldo_incidenteel = {}
        with kolommen[0]:
            st.write("**Saldo incidentele baten en lasten**")
        for i, jaar in enumerate(jaren_reeks):
            saldo = inc_baten[jaar] - inc_lasten[jaar]
            saldo_incidenteel[jaar] = saldo
            st.session_state[f"saldo_incidenteel_{jaar}"] = saldo
            with kolommen[i + 1]:
                st.write(f"{saldo:,.0f}")

        structureel_resultaat = {}
        with kolommen[0]:
            st.write("**Structureel resultaat**")
        for i, jaar in enumerate(jaren_reeks):
            res = geraamd_resultaat[jaar] - saldo_incidenteel[jaar]
            structureel_resultaat[jaar] = res
            st.session_state[f"structureel_resultaat_{jaar}"] = res
            with kolommen[i + 1]:
                st.write(f"{res:,.0f}")

    with sub_balans:
        st.subheader("4. Geprognosticeerde balans")
        balance_years = get_balance_years()

        pdf_bytes = st.session_state.get("uploaded_pdf", None)

        if "show_pdf_panel" not in st.session_state:
            st.session_state["show_pdf_panel"] = False

        # Links invullen, rechts PDF
        col_invoer, col_viewer = st.columns([1.85, 1.15], gap="large")

        with col_invoer:
            st.markdown("#### PDF inlezen")

            col_btns = st.columns([1, 1, 2])
            with col_btns[0]:
                if st.button("Zoek balans in PDF", key="zoek_balans_pdf"):
                    if pdf_bytes is None:
                        st.warning("Upload eerst een PDF-bestand op het Dashboard.")
                    else:
                        balans_paginas = zoek_balans_paginas(pdf_bytes)
                        st.session_state["balans_pdf_paginas"] = balans_paginas

                        gevonden, debug_regels = extract_balance_fields_from_pdf(
                            pdf_bytes, balance_years
                        )
                        st.session_state["balans_pdf_resultaten"] = gevonden
                        st.session_state["balans_pdf_debug"] = debug_regels

                        if gevonden:
                            for veld, waarde in gevonden.items():
                                st.session_state[veld] = sanitize_balance_value(waarde)
                            st.success(
                                f"{len(gevonden)} balanswaarden gevonden en ingevuld."
                            )
                        else:
                            st.warning(
                                "Geen balansposten herkend. Controleer of de PDF een leesbare tekstlaag bevat."
                            )
            with col_btns[1]:
                if st.button("Toon PDF", key="toon_pdf_panel"):
                    st.session_state["show_pdf_panel"] = True
            with col_btns[2]:
                if st.session_state.get("show_pdf_panel"):
                    if st.button("Verberg PDF", key="verberg_pdf_panel"):
                        st.session_state["show_pdf_panel"] = False

            if pdf_bytes is None:
                st.info("Upload eerst een PDF op het Dashboard.")

            st.markdown("---")
            render_balance_table("Activa", ACTIVA_VOLGORDE, balance_years)

            st.markdown("---")
            render_balance_table("Passiva", PASSIVA_VOLGORDE, balance_years)

            st.markdown("---")
            st.markdown("#### Samenvatting voor kengetallen")

        with col_viewer:
            if st.session_state.get("show_pdf_panel"):
                render_balans_pdf_viewer()
            else:
                st.info("Klik op **Toon PDF** om de balanspagina te bekijken.")

        basisjaar_kengetallen = balance_years[0]

        if "uitstaande_schuld" not in st.session_state:
            st.session_state["uitstaande_schuld"] = sanitize_balance_value(
                st.session_state.get(f"vaste_schuld_{basisjaar_kengetallen}", 0.0)
            )
        st.number_input(
            "Uitstaande schuld (leningen, lang + kort)",
            min_value=None,
            max_value=None,
            step=1.0,
            key="uitstaande_schuld",
            format="%.0f",
        )
        if "vlottende_middelen" not in st.session_state:
            st.session_state["vlottende_middelen"] = sanitize_balance_value(
                st.session_state.get(f"liquide_middelen_{basisjaar_kengetallen}", 0.0)
            )
        st.number_input(
            "Vlottende middelen (kas, bank, kortlopend)",
            min_value=None,
            max_value=None,
            step=1.0,
            key="vlottende_middelen",
            format="%.0f",
        )
        if "reserves_eigen_vermogen" not in st.session_state:
            st.session_state["reserves_eigen_vermogen"] = sanitize_balance_value(
                st.session_state.get(f"totaal_eigen_vermogen_{basisjaar_kengetallen}", 0.0)
            )
        st.number_input(
            "Reserves / eigen vermogen",
            min_value=None,
            max_value=None,
            step=1.0,
            key="reserves_eigen_vermogen",
            format="%.0f",
        )

    with sub_kengetallen:
        st.subheader("Kengetallen (plaatshouder)")
        st.info("Hier komen later de kengetallen zoals schuldquote, solvabiliteit enz.")

    with sub_weerstand:
        st.subheader("Weerstandsvermogen (plaatshouder)")
        st.info(
            "Hier komen later de velden voor beschikbare en benodigde "
            "weerstandscapaciteit en risicoanalyse."
        )

    with sub_onderhoud:
        st.subheader("Onderhoud kapitaalgoederen (plaatshouder)")
        st.info(
            "Hier kun je later een tabel met kapitaalgoederen en onderhoudsgegevens invoeren."
        )

    with sub_verbonden:
        st.subheader("Verbonden partijen (plaatshouder)")
        st.info(
            "Hier kun je later per GR / deelneming de financiële gegevens en toelichting vastleggen."
        )

    with sub_lokale_heffingen:
        st.subheader("Lokale heffingen (plaatshouder)")
        st.info(
            "Hier komen later de velden voor OZB, rioolheffing, afvalstoffenheffing e.d."
        )

    verzonden = st.button("Indicatoren berekenen en opslaan")

    if verzonden:
        type_overheid_val = st.session_state.get("type_overheid")
        naam_overheid_val = st.session_state.get("naam_overheid")
        boekjaar_val = st.session_state.get("boekjaar")
        documenttype_val = st.session_state.get("documenttype")

        behandeld_ambtenaar_val = st.session_state.get("behandeld_ambtenaar", "")
        invoer_gereed_val = st.session_state.get("invoer_gereed", "")
        dossiernummer_val = st.session_state.get("dossiernummer", "")
        cbs_code_val = st.session_state.get("cbs_code", "")
        aantal_inwoners_val = st.session_state.get("aantal_inwoners", 0)
        aantal_woonruimten_val = st.session_state.get("aantal_woonruimten", 0)
        datum_vaststelling_val = st.session_state.get(
            "datum_vaststelling_begroting", None
        )
        datum_verzending_val = st.session_state.get(
            "datum_verzending_begroting", None
        )
        alert_toezicht_val = st.session_state.get("alert_toezicht", "")
        brief_toelichting_val = st.session_state.get("brief_toelichting", "")

        basisjaar_val = int(boekjaar_val)
        baten_exploitatie_val = st.session_state.get(
            f"baten_excl_{basisjaar_val}", 0.0
        )
        lasten_exploitatie_val = st.session_state.get(
            f"lasten_excl_{basisjaar_val}", 0.0
        )
        baten_financieel_val = 0.0
        lasten_financieel_val = 0.0

        uitstaande_schuld_val = st.session_state.get("uitstaande_schuld", 0.0)
        vlottende_middelen_val = st.session_state.get("vlottende_middelen", 0.0)
        reserves_eigen_vermogen_val = st.session_state.get(
            "reserves_eigen_vermogen", 0.0
        )

        totale_baten = baten_exploitatie_val
        totale_lasten = lasten_exploitatie_val
        saldo = st.session_state.get(
            f"geraamd_resultaat_{basisjaar_val}",
            totale_baten - totale_lasten,
        )

        exploitatieresultaat_marge = saldo / totale_baten if totale_baten > 0 else 0.0
        schuldquote = (
            uitstaande_schuld_val / totale_baten if totale_baten > 0 else 0.0
        )
        liquiditeitsratio = (
            vlottende_middelen_val / uitstaande_schuld_val
            if uitstaande_schuld_val > 0
            else 0.0
        )
        solvabiliteitsratio = (
            reserves_eigen_vermogen_val
            / (reserves_eigen_vermogen_val + uitstaande_schuld_val)
            if (reserves_eigen_vermogen_val + uitstaande_schuld_val) > 0
            else 0.0
        )

        st.markdown("---")
        st.subheader(
            f"Resultaten voor {type_overheid_val} – {naam_overheid_val} – "
            f"{boekjaar_val} ({documenttype_val})"
        )

        if saldo >= 0:
            st.success(f"Begrotingssaldo: **{saldo:,.0f}** (overschot)")
        else:
            st.error(f"Begrotingssaldo: **{saldo:,.0f}** (tekort)")

        st.write(
            f"**Exploitatieresultaat (marge)**: {exploitatieresultaat_marge * 100:.1f}%"
        )
        if exploitatieresultaat_marge < 0:
            st.error("Negatieve exploitatieresultaatmarge – structureel risico.")
        elif exploitatieresultaat_marge < 0.02:
            st.warning("Exploitatieresultaatmarge onder 2% – beperkte buffer.")
        else:
            st.success("Exploitatieresultaatmarge boven 2% – lijkt acceptabel.")

        st.write(f"**Schuldquote (schuld / baten)**: {schuldquote * 100:.1f}%")
        if schuldquote > 2.0:
            st.error("Zeer hoge schuldenlast ten opzichte van de baten.")
        elif schuldquote > 1.0:
            st.warning("Relatief hoge schuldenlast ten opzichte van de baten.")
        else:
            st.success("Schuldenlast lijkt relatief gematigd.")

        st.write(
            f"**Liquiditeitsratio (vlottende middelen / schuld)**: {liquiditeitsratio * 100:.1f}%"
        )
        if liquiditeitsratio < 0.1:
            st.warning("Zeer beperkte liquiditeit ten opzichte van de schuld.")
        else:
            st.info("Liquiditeitsratio boven 10%.")

        st.write(
            f"**Solvabiliteitsratio (reserves / reserves + schuld)**: {solvabiliteitsratio * 100:.1f}%"
        )
        if solvabiliteitsratio < 0.1:
            st.error("Zeer lage solvabiliteit (<10%).")
        elif solvabiliteitsratio < 0.25:
            st.warning("Solvabiliteit tussen 10–25% – verhoogd risico.")
        else:
            st.success("Solvabiliteit boven 25% – over het algemeen gezondere positie.")

        nieuwe_rij = {
            "type_overheid": type_overheid_val,
            "naam_overheid": naam_overheid_val,
            "boekjaar": int(boekjaar_val),
            "documenttype": documenttype_val,
            "behandeld_ambtenaar": behandeld_ambtenaar_val,
            "invoer_gereed": invoer_gereed_val,
            "dossiernummer": dossiernummer_val,
            "cbs_code": cbs_code_val,
            "aantal_inwoners": int(aantal_inwoners_val),
            "aantal_woonruimten": int(aantal_woonruimten_val),
            "datum_vaststelling_begroting": str(datum_vaststelling_val)
            if datum_vaststelling_val
            else "",
            "datum_verzending_begroting": str(datum_verzending_val)
            if datum_verzending_val
            else "",
            "alert_toezicht": alert_toezicht_val,
            "brief_toelichting": brief_toelichting_val,
            "baten_exploitatie": baten_exploitatie_val,
            "lasten_exploitatie": lasten_exploitatie_val,
            "baten_financieel": baten_financieel_val,
            "lasten_financieel": lasten_financieel_val,
            "uitstaande_schuld": uitstaande_schuld_val,
            "vlottende_middelen": vlottende_middelen_val,
            "reserves_eigen_vermogen": reserves_eigen_vermogen_val,
            "begrotingssaldo": saldo,
            "exploitatieresultaat_marge": exploitatieresultaat_marge,
            "schuldquote": schuldquote,
            "liquiditeitsratio": liquiditeitsratio,
            "solvabiliteitsratio": solvabiliteitsratio,
            "ingelogde_gebruiker": gebruiker.get("email"),
            "provincie": gebruiker.get("provincie"),
        }

        balance_years = get_balance_years()
        for veld in ACTIVA_VOLGORDE + PASSIVA_VOLGORDE:
            for jaar in balance_years:
                nieuwe_rij[f"{veld}_{jaar}"] = st.session_state.get(f"{veld}_{jaar}", 0.0)

        df_nieuw = pd.DataFrame([nieuwe_rij])

        if os.path.exists(DATA_FILE):
            df_nieuw.to_csv(
                DATA_FILE,
                mode="a",
                header=False,
                index=False,
                encoding="utf-8",
            )
        else:
            df_nieuw.to_csv(DATA_FILE, index=False, encoding="utf-8")

        st.success("Gegevens zijn opgeslagen in de database (CSV-bestand).")

with tab_database:
    st.subheader("Database en eenvoudig dashboard")

    if os.path.exists(DATA_FILE):
        df = pd.read_csv(
            DATA_FILE,
            engine="python",
            on_bad_lines="skip",
        )

        st.write("**Ruwe gegevens (alle ingevoerde cases):**")
        st.dataframe(df)

        st.write("**Ontwikkeling begrotingssaldo per jaar (totaal):**")
        if "boekjaar" in df.columns and "begrotingssaldo" in df.columns:
            df_jaar = df.groupby("boekjaar", as_index=True)["begrotingssaldo"].sum()
            st.bar_chart(df_jaar)

        st.caption(
            "Je kunt dit tabblad later uitbreiden met meer grafieken, "
            "filters per type overheid of documenttype, en andere kengetallen."
        )
    else:
        st.info(
            "Er zijn nog geen gegevens opgeslagen. "
            "Vul eerst een case in op het tabblad 'Invoer gegevens'."
        )