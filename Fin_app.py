import os
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Financieel Toezicht Decentrale Overheid",
    layout="wide",
)

DATA_FILE = "financieel_toezicht_data.csv"
LOGO_PATH = "aftnext_logo.png"
VOLUMIA_FILE = "volumia_2026.csv"
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
        "naam": "Demo‑gebruiker",
    },
}

DEFAULT_AUTO_USER = "sl.schot@zeeland.nl"


@st.cache_data
def load_volumia(jaar: int):
    """Lees basisgegevens uit volumia_<jaar>.csv (CBS, inwoners, woonruimten)."""
    bestand = f"volumia_{jaar}.csv"
    if not os.path.exists(bestand):
        return None

    try:
        # Laat pandas zelf het scheidingsteken bepalen (komma, puntkomma, enz.)
        df_raw = pd.read_csv(bestand, sep=None, engine="python")
    except Exception:
        return None

    # Verwacht minimaal 52 kolommen
    if df_raw.shape[1] < 52:
        return None

    # Kolom 1: CBS-code, kolom 2: gemeentenaam, kolom 14: inwoners, kolom 51: woonruimten
    # Waarden in kolom 14 en 51 zijn geschreven met punten en komma's (bijv. 45.283,34),
    # daarom eerst tekst schoonmaken: alle punten eruit, komma vervangen door punt.
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
        email = st.text_input("E‑mailadres", key="login_email")
        wachtwoord = st.text_input("Wachtwoord", type="password", key="login_password")
        provincie = st.selectbox("Provincie", ["Zeeland", "Zuid‑Holland", "Noord‑Brabant"])
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
            st.error("Onjuiste combinatie van e‑mail en wachtwoord.")

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
    "en slaat de gegevens op in een CSV‑bestand dat je later kunt inzien."
)

tab_start, tab_invoer, tab_dashboard = st.tabs(
    ["Dashboard", "Invoer gegevens", "Database / overzicht"]
)

with tab_start:
    st.subheader(f"Welkom {gebruiker.get('naam', '')}")

    kol_zoek, kol_detail = st.columns([1, 3])

    with kol_zoek:
        st.markdown("#### Zoeken")

        type_opties = list(NAMEN_PER_TYPE.keys())
        gekozen_type = st.selectbox(
            "Type organisatie",
            type_opties,
            key="dash_type_overheid",
        )

        opties_namen = NAMEN_PER_TYPE.get(
            gekozen_type,
            ["(Nog geen namen ingevuld voor dit type)"],
        )

        gekozen_naam = st.selectbox(
            "Naam",
            opties_namen,
            key="dash_naam_overheid",
        )

        st.markdown("#### Documentselectie")
        doc_opties = ["Begroting", "Jaarrekening", "Kadernota"]
        dash_documenttype = st.selectbox(
            "Kies een document",
            doc_opties,
            key="dash_documenttype",
        )

        jaren_dash = list(range(2015, 2031))
        dash_boekjaar = st.selectbox(
            "Kies een jaartal",
            jaren_dash,
            index=len(jaren_dash) - 2,
            key="dash_boekjaar",
        )

        if st.button("Gebruik in invoerscherm"):
            st.session_state["type_overheid"] = gekozen_type
            st.session_state["naam_overheid"] = gekozen_naam
            st.session_state["documenttype"] = dash_documenttype
            st.session_state["boekjaar"] = dash_boekjaar
            st.success(
                "Selectie staat klaar op tab 'Invoer gegevens'. "
                "Klik daarboven op het tabblad om de gegevens in te vullen."
            )

    with kol_detail:
        titel_type = gekozen_type[:-1] if gekozen_type.endswith("n") else gekozen_type
        st.markdown(f"### {titel_type} {gekozen_naam}")

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
                tabel = resultaten[
                    [
                        "documenttype",
                        "boekjaar",
                        "begrotingssaldo",
                        "ingelogde_gebruiker",
                    ]
                ].sort_values(["boekjaar", "documenttype"])
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

        jaren = list(range(2015, 2031))  # 2015 t/m 2030
        if "boekjaar" not in st.session_state:
            # standaard op het 4e jaar vóór het laatste jaar (2030 -> 2027)
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

        # Bepaal of de geselecteerde organisatie/jaar is gewijzigd t.o.v. vorige run
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
                # Voor niet-gemeenten standaard leeg/0
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

        behandeld_ambtenaar = st.text_input(
            "Behandeld ambtenaar",
            value=st.session_state.get(
                "behandeld_ambtenaar", gebruiker.get("naam", "")
            ),
            key="behandeld_ambtenaar",
        )

        invoer_gereed = st.radio(
            "Invoer gereed?",
            ["Nee", "Ja"],
            index=0,
            key="invoer_gereed",
        )

        dossiernummer = st.text_input("Dossiernummer", key="dossiernummer")
        cbs_code = st.text_input("CBS-code", key="cbs_code")

        aantal_inwoners = st.number_input(
            "Aantal inwoners (peildatum: 1 januari – begrotingsjaar)",
            min_value=0,
            step=1,
            key="aantal_inwoners",
        )
        aantal_woonruimten = st.number_input(
            "Aantal woonruimten (peildatum: 1 januari – begrotingsjaar)",
            min_value=0,
            step=1,
            key="aantal_woonruimten",
        )

        datum_vaststelling_begroting = st.date_input(
            "Datum vaststelling begroting",
            key="datum_vaststelling_begroting",
        )
        datum_verzending_begroting = st.date_input(
            "Datum verzending begroting",
            key="datum_verzending_begroting",
        )

        alert_toezicht = st.selectbox(
            "Is er sprake van AHRI-toezicht?",
            ["Nee", "Ja"],
            key="alert_toezicht",
        )

        brief_toelichting = st.text_area(
            "Wat komt er in de brief?",
            key="brief_toelichting",
        )

    with sub_resultaat:
        st.subheader("3. Resultaatbepaling – exploitatie")

        st.markdown("#### Vragen")
        eerste_begrotingswijziging = st.radio(
            "Is er een eerste begrotingswijziging vastgesteld die bij het financieel toezicht dient te worden betrokken?",
            ["Nee", "Ja"],
            key="result_eerste_begrotingswijziging",
        )
        amendementen = st.radio(
            "Zijn er amendementen met financiële consequenties vastgesteld?",
            ["Nee", "Ja"],
            key="result_amendementen",
        )

        st.markdown("#### Exploitatie en resultaat per jaar (x 1.000)")

        basisjaar = int(st.session_state.get("boekjaar", 2026))
        jaren_reeks = [basisjaar + i for i in range(4)]

        # Iets bredere eerste kolom voor de omschrijvingen
        kol_gewichten = [2] + [1] * len(jaren_reeks)
        kolommen = st.columns(kol_gewichten)

        # Kopregel met jaartallen
        with kolommen[0]:
            st.write("")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                st.markdown(f"**{jaar}**")

        # 1. Lasten / baten excl. reservemutaties
        lasten_excl = {}
        baten_excl = {}

        with kolommen[0]:
            st.write("Lasten exclusief reservemutaties")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                v = st.number_input(
                    f"lasten_excl_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"lasten_excl_{jaar}",
                    label_visibility="collapsed",
                )
                lasten_excl[jaar] = v

        with kolommen[0]:
            st.write("Baten exclusief reservemutaties")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                v = st.number_input(
                    f"baten_excl_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"baten_excl_{jaar}",
                    label_visibility="collapsed",
                )
                baten_excl[jaar] = v

        saldo_baten_lasten = {}
        with kolommen[0]:
            st.write("**Saldo van baten en lasten**")
        for i, jaar in enumerate(jaren_reeks):
            saldo = baten_excl[jaar] - lasten_excl[jaar]
            saldo_baten_lasten[jaar] = saldo
            st.session_state[f"saldo_baten_lasten_{jaar}"] = saldo
            with kolommen[i + 1]:
                st.write(f"{saldo:,.0f}")

        # 2. Mutatie reserves
        toevoeg_res = {}
        onttrekk_res = {}

        with kolommen[0]:
            st.write("Toevoegingen reserves (last)")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                v = st.number_input(
                    f"toevoeg_reserves_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"toevoeg_reserves_{jaar}",
                    label_visibility="collapsed",
                )
                toevoeg_res[jaar] = v

        with kolommen[0]:
            st.write("Onttrekkingen reserves (baat)")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                v = st.number_input(
                    f"onttrekk_reserves_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"onttrekk_reserves_{jaar}",
                    label_visibility="collapsed",
                )
                onttrekk_res[jaar] = v

        saldo_mut_reserves = {}
        with kolommen[0]:
            st.write("**Saldo mutatie reserves**")
        for i, jaar in enumerate(jaren_reeks):
            saldo = onttrekk_res[jaar] - toevoeg_res[jaar]
            saldo_mut_reserves[jaar] = saldo
            st.session_state[f"saldo_mut_reserves_{jaar}"] = saldo
            with kolommen[i + 1]:
                st.write(f"{saldo:,.0f}")

        # 3. Geraamd resultaat
        geraamd_resultaat = {}
        with kolommen[0]:
            st.write("**Geraamd resultaat**")
        for i, jaar in enumerate(jaren_reeks):
            res = saldo_baten_lasten[jaar] + saldo_mut_reserves[jaar]
            geraamd_resultaat[jaar] = res
            st.session_state[f"geraamd_resultaat_{jaar}"] = res
            with kolommen[i + 1]:
                st.write(f"{res:,.0f}")

        # 4. Incidentele baten en lasten
        inc_lasten = {}
        inc_baten = {}

        with kolommen[0]:
            st.write("Incidentele lasten (incl. reservemutaties)")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                v = st.number_input(
                    f"incidentele_lasten_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"incidentele_lasten_{jaar}",
                    label_visibility="collapsed",
                )
                inc_lasten[jaar] = v

        with kolommen[0]:
            st.write("Incidentele baten (incl. reservemutaties)")
        for i, jaar in enumerate(jaren_reeks):
            with kolommen[i + 1]:
                v = st.number_input(
                    f"incidentele_baten_{jaar}",
                    min_value=0.0,
                    step=1000.0,
                    key=f"incidentele_baten_{jaar}",
                    label_visibility="collapsed",
                )
                inc_baten[jaar] = v

        saldo_incidenteel = {}
        with kolommen[0]:
            st.write("**Saldo incidentele baten en lasten**")
        for i, jaar in enumerate(jaren_reeks):
            saldo = inc_baten[jaar] - inc_lasten[jaar]
            saldo_incidenteel[jaar] = saldo
            st.session_state[f"saldo_incidenteel_{jaar}"] = saldo
            with kolommen[i + 1]:
                st.write(f"{saldo:,.0f}")

        # 5. Structureel resultaat
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
        st.subheader("Geprognosticeerde balans – kerncijfers")

        uitstaande_schuld = st.number_input(
            "Uitstaande schuld (leningen, lang + kort)",
            min_value=0.0,
            step=1000.0,
            key="uitstaande_schuld",
        )
        vlottende_middelen = st.number_input(
            "Vlottende middelen (kas, bank, kortlopend)",
            min_value=0.0,
            step=1000.0,
            key="vlottende_middelen",
        )
        reserves_eigen_vermogen = st.number_input(
            "Reserves / eigen vermogen (algemeen + bestemmingsreserves)",
            min_value=0.0,
            step=1000.0,
            key="reserves_eigen_vermogen",
        )

        st.markdown("**Uitbreiding (optioneel, ter analyse):**")
        voorzieningen = st.number_input(
            "Voorzieningen (totaal)",
            min_value=0.0,
            step=1000.0,
            key="voorzieningen",
        )
        vaste_activa = st.number_input(
            "Vaste activa (boekwaarde)",
            min_value=0.0,
            step=1000.0,
            key="vaste_activa",
        )
        vlottende_activa = st.number_input(
            "Vlottende activa (excl. vlottende middelen)",
            min_value=0.0,
            step=1000.0,
            key="vlottende_activa",
        )

    with sub_kengetallen:
        st.subheader("Kengetallen (plaats­houder)")
        st.info("Hier komen later de kengetallen zoals schuldquote, solvabiliteit enz.")

    with sub_weerstand:
        st.subheader("Weerstandsvermogen (plaats­houder)")
        st.info(
            "Hier komen later de velden voor beschikbare en benodigde "
            "weerstandscapaciteit en risicoanalyse."
        )

    with sub_onderhoud:
        st.subheader("Onderhoud kapitaalgoederen (plaats­houder)")
        st.info(
            "Hier kun je later een tabel met kapitaalgoederen en onderhoudsgegevens invoeren."
        )

    with sub_verbonden:
        st.subheader("Verbonden partijen (plaats­houder)")
        st.info(
            "Hier kun je later per GR / deelneming de financiële gegevens en toelichting vastleggen."
        )

    with sub_lokale_heffingen:
        st.subheader("Lokale heffingen (plaats­houder)")
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
        # Gebruik voor het begrotingssaldo het geraamde resultaat van het basisjaar
        saldo = st.session_state.get(
            f"geraamd_resultaat_{basisjaar_val}",
            totale_baten - totale_lasten,
        )

        if totale_baten > 0:
            exploitatieresultaat_marge = saldo / totale_baten
        else:
            exploitatieresultaat_marge = 0.0

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

        st.success("Gegevens zijn opgeslagen in de database (CSV‑bestand).")

with tab_dashboard:
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