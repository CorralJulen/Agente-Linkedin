import pandas as pd
import streamlit as st
import random
import json
import re
import feedparser
import requests
from datetime import datetime, timedelta
from google import genai

# ── Configuración ──────────────────────────────────────────────────────────────
GEMINI_API_KEY   = st.secrets.get("GEMINI_API_KEY")
TELEGRAM_TOKEN   = st.secrets.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")
SUPABASE_URL     = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY     = st.secrets.get("SUPABASE_ANON_KEY", "")
NEWSAPI_KEY      = st.secrets.get("NEWSAPI_KEY", "231afc3ea3d845fcae8acafe7f314c44")

RSS_BANCA = [
    ("El Economista - Banca",   "https://www.eleconomista.es/rss/rss-banca.php"),
    ("Expansión - Finanzas",    "https://e00-expansion.uecdn.es/rss/mercados.xml"),
    ("El Confidencial - Banca", "https://www.elconfidencial.com/rss/economia/finanzas-personales/"),
    ("Expansión - Banca",       "https://e00-expansion.uecdn.es/rss/empresas/banca.xml"),
]
RSS_ESTRATEGIA = [
    ("Expansión - Empresas",       "https://e00-expansion.uecdn.es/rss/empresas.xml"),
    ("El Economista - Empresas",   "https://www.eleconomista.es/rss/rss-empresas.php"),
    ("El Confidencial - Empresas", "https://www.elconfidencial.com/rss/empresas/"),
    ("El País - Economía",         "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada"),
    ("Cinco Días",                 "https://cincodias.elpais.com/rss/cincodias/ultimas_noticias/"),
]
# IA aplicada a negocio — RSS especializados como complemento a Google News
RSS_IA_NEGOCIO = [
    ("El Referente",             "https://elreferente.es/feed/"),
    ("Silicon.es",               "https://www.silicon.es/feed"),
    ("Microsoft Blog ES",        "https://blogs.microsoft.com/es-es/feed/"),
    ("BBVA Open Mind",           "https://www.bbvaopenmind.com/feed/"),
    ("El Economista - Tech",     "https://www.eleconomista.es/rss/rss-tecnologia.php"),
]
# IA aplicada a finanzas — RSS especializados como complemento a Google News
RSS_IA_FINANZAS = [
    ("Fintech Spain",            "https://www.fintechspain.com/feed/"),
    ("El Economista - Banca",    "https://www.eleconomista.es/rss/rss-banca.php"),
    ("Expansión - Finanzas",     "https://e00-expansion.uecdn.es/rss/mercados.xml"),
    ("El Confidencial - Banca",  "https://www.elconfidencial.com/rss/economia/finanzas-personales/"),
    ("BBVA Open Mind",           "https://www.bbvaopenmind.com/feed/"),
]

KEYWORDS_BANCA = ["banco","banca","financiero","finanzas","crédito","hipoteca","tipos de interés","BCE","banco central","entidad financiera","inversión","bolsa","mercado","deuda","capital","fondo","dividendo","acción","cotización","préstamo","morosidad","regulación bancaria"]
KEYWORDS_ESTRATEGIA = ["estrategia","empresa","CEO","directivo","fusión","adquisición","resultado","beneficio","facturación","negocio","mercado","competencia","innovación","transformación","consultor","management","liderazgo","startup","venture","inteligencia artificial","IA","digital"]
KEYWORDS_IA_NEGOCIO = [
    "inteligencia artificial empresa","IA empresarial","IA generativa","Copilot","ChatGPT empresa",
    "automatización empresarial","transformación digital IA","productividad IA","adopción IA",
    "Microsoft IA","Google IA","OpenAI empresa","Azure IA","caso de uso IA","IA aplicada negocio",
    "eficiencia IA","herramienta IA","startup IA","inversión IA empresa","IA y gestión",
    "IA recursos humanos","IA logística","IA marketing","IA operaciones","IA manufactura",
]
KEYWORDS_IA_FINANZAS = [
    "fintech","IA banca","inteligencia artificial finanzas","banca digital","IA financiero",
    "scoring crediticio","detección fraude IA","robo-advisor","pagos digitales","open banking",
    "IA inversión","IA seguros","insurtech","regtech","IA riesgo financiero",
    "BBVA IA","Santander IA","CaixaBank digital","banco digital IA","neobank",
    "IA mercados","algoritmo financiero","IA hipotecas","crédito digital","IA compliance",
]

SECTORES = {
    "banca":       {"feeds": RSS_BANCA,       "etiqueta": "🏦 Banca & Finanzas",       "perfil": "consultor de banca y finanzas",        "keywords": KEYWORDS_BANCA},
    "estrategia":  {"feeds": RSS_ESTRATEGIA,  "etiqueta": "♟️ Estrategia Empresarial", "perfil": "consultor de estrategia empresarial",  "keywords": KEYWORDS_ESTRATEGIA},
    "ia_negocio":  {"feeds": RSS_IA_NEGOCIO,  "etiqueta": "🤖 IA & Negocio",           "perfil": "consultor de IA aplicada a negocio",   "keywords": KEYWORDS_IA_NEGOCIO,
                   "gnews": ["inteligencia artificial empresa negocio España adopción","IA empresarial productividad automatización caso uso","Copilot ChatGPT empresa transformación digital éxito"]},
    "ia_finanzas": {"feeds": RSS_IA_FINANZAS, "etiqueta": "💡 IA & Finanzas",          "perfil": "consultor de IA en finanzas y fintech", "keywords": KEYWORDS_IA_FINANZAS,
                   "gnews": ["inteligencia artificial banca finanzas España fintech","IA banca digital scoring crédito fraude detección","fintech innovación financiera España pagos digitales"]},
}

# ── Indicadores Macro (BCE, INE) ───────────────────────────────────────────────
# BCE: API en vivo | Resto: datos reales hardcodeados (INE / BCE publicado)
INDICADORES_MACRO = {
    "tipo_refi_bce": {
        "nombre": "Tipo de interés BCE (Refi Rate)",
        "descripcion": "Tipo oficial de refinanciación del Banco Central Europeo",
        "fuente": "BCE · Statistical Data Warehouse · API en vivo",
        "url_api": "https://data-api.ecb.europa.eu/service/data/FM/B.U2.EUR.4F.KR.MRR_FR.LEV?format=json&lastNObservations=24",
        "eje_y": "% Tipo de interés",
        "color": "#6c63ff",
        "tipo_grafico": "line",
        "datos_hardcoded": None,
    },
    "ipc_espana": {
        "nombre": "IPC España — Variación anual (%)",
        "descripcion": "Índice de Precios al Consumo en España, variación anual. Fuente: INE",
        "fuente": "INE · Estadística oficial",
        "url_api": None,
        "eje_y": "% Variación anual",
        "color": "#f87171",
        "tipo_grafico": "line",
        "datos_hardcoded": [
            ("Ene-23", 5.9), ("Feb-23", 6.0), ("Mar-23", 3.3), ("Abr-23", 4.1),
            ("May-23", 3.2), ("Jun-23", 1.9), ("Jul-23", 2.3), ("Ago-23", 2.4),
            ("Sep-23", 3.5), ("Oct-23", 3.5), ("Nov-23", 3.2), ("Dic-23", 3.1),
            ("Ene-24", 3.4), ("Feb-24", 2.8), ("Mar-24", 3.2), ("Abr-24", 3.3),
            ("May-24", 3.6), ("Jun-24", 3.4), ("Jul-24", 2.8), ("Ago-24", 2.3),
            ("Sep-24", 1.5), ("Oct-24", 1.8), ("Nov-24", 2.4), ("Dic-24", 2.8),
            ("Ene-25", 3.0), ("Feb-25", 3.0), ("Mar-25", 2.3),
        ],
    },
    "pib_espana": {
        "nombre": "PIB España — Variación trimestral (%)",
        "descripcion": "Tasa de variación trimestral del PIB de España. Fuente: INE",
        "fuente": "INE · Contabilidad Nacional Trimestral",
        "url_api": None,
        "eje_y": "% Variación trimestral",
        "color": "#4ade80",
        "tipo_grafico": "bar",
        "datos_hardcoded": [
            ("T1-21", -0.7), ("T2-21", 2.8), ("T3-21", 3.4), ("T4-21", 2.2),
            ("T1-22", 0.2), ("T2-22", 1.5), ("T3-22", 0.4), ("T4-22", 0.5),
            ("T1-23", 0.6), ("T2-23", 0.4), ("T3-23", 0.8), ("T4-23", 0.6),
            ("T1-24", 0.8), ("T2-24", 0.8), ("T3-24", 0.8), ("T4-24", 0.7),
        ],
    },
    "tasa_paro_espana": {
        "nombre": "Tasa de paro España — EPA (%)",
        "descripcion": "Tasa de desempleo en España según la EPA. Fuente: INE",
        "fuente": "INE · EPA trimestral",
        "url_api": None,
        "eje_y": "% Tasa de paro",
        "color": "#fbbf24",
        "tipo_grafico": "line",
        "datos_hardcoded": [
            ("T1-21", 16.0), ("T2-21", 15.3), ("T3-21", 14.6), ("T4-21", 13.3),
            ("T1-22", 13.7), ("T2-22", 12.5), ("T3-22", 12.7), ("T4-22", 12.9),
            ("T1-23", 13.2), ("T2-23", 11.6), ("T3-23", 11.8), ("T4-23", 11.8),
            ("T1-24", 12.3), ("T2-24", 11.3), ("T3-24", 11.2), ("T4-24", 10.6),
        ],
    },
    "euribor_12m": {
        "nombre": "Euribor 12 meses (%)",
        "descripcion": "Tipo interbancario europeo a 12 meses — referencia hipotecas. Fuente: EMMI / BCE",
        "fuente": "BCE · European Money Markets Institute",
        "url_api": None,
        "eje_y": "% Euribor",
        "color": "#a78bfa",
        "tipo_grafico": "line",
        "datos_hardcoded": [
            ("Ene-22", -0.50), ("Mar-22", 0.01), ("Jun-22", 1.00), ("Sep-22", 2.23),
            ("Dic-22", 3.02), ("Mar-23", 3.65), ("Jun-23", 4.01), ("Sep-23", 4.15),
            ("Dic-23", 3.68), ("Mar-24", 3.72), ("Jun-24", 3.65), ("Sep-24", 2.94),
            ("Dic-24", 2.43), ("Ene-25", 2.51), ("Feb-25", 2.39), ("Mar-25", 2.41),
        ],
    },
}

# ── Indicadores IA & Tech — datos reales hardcodeados (Eurostat / OCDE) ──────
INDICADORES_IA_TECH = {
    "empresas_ia_espana": {
        "nombre": "Empresas españolas que usan IA (%)",
        "descripcion": "% empresas en España con algún uso de IA. Fuente: Eurostat isoc_eb_ai",
        "fuente": "Eurostat · isoc_eb_ai",
        "url_api": None,
        "eje_y": "% Empresas",
        "color": "#fbbf24",
        "tipo_grafico": "bar",
        "datos_hardcoded": [
            ("2021", 8.0), ("2022", 14.0), ("2023", 16.0), ("2024", 19.0),
        ],
    },
    "empresas_cloud_espana": {
        "nombre": "Empresas españolas usando Cloud (%)",
        "descripcion": "% empresas en España que contratan servicios cloud. Fuente: Eurostat",
        "fuente": "Eurostat · isoc_cicce_use",
        "url_api": None,
        "eje_y": "% Empresas",
        "color": "#6c63ff",
        "tipo_grafico": "line",
        "datos_hardcoded": [
            ("2016", 18.0), ("2017", 22.0), ("2018", 24.0), ("2019", 27.0),
            ("2020", 31.0), ("2021", 36.0), ("2022", 41.0), ("2023", 47.0), ("2024", 52.0),
        ],
    },
    "empresas_bigdata_espana": {
        "nombre": "Empresas españolas usando Big Data (%)",
        "descripcion": "% empresas en España que analizan Big Data de fuentes propias. Fuente: Eurostat",
        "fuente": "Eurostat · isoc_eb_bd",
        "url_api": None,
        "eje_y": "% Empresas",
        "color": "#4ade80",
        "tipo_grafico": "bar",
        "datos_hardcoded": [
            ("2018", 10.0), ("2019", 12.0), ("2020", 14.0), ("2021", 13.0),
            ("2022", 15.0), ("2023", 17.0), ("2024", 20.0),
        ],
    },
    "ia_adopcion_ue": {
        "nombre": "Adopción IA en empresas UE-27 (%)",
        "descripcion": "% empresas europeas usando inteligencia artificial. Fuente: Eurostat",
        "fuente": "Eurostat · isoc_eb_ai (UE-27)",
        "url_api": None,
        "eje_y": "% Empresas UE-27",
        "color": "#a78bfa",
        "tipo_grafico": "line",
        "datos_hardcoded": [
            ("2020", 8.0), ("2021", 10.0), ("2022", 14.0), ("2023", 16.0), ("2024", 20.0),
        ],
    },
    "automatizacion_riesgo": {
        "nombre": "Trabajadores europeos en riesgo de automatización (%)",
        "descripcion": "% trabajadores UE en ocupaciones con alto riesgo de automatización por IA. Fuente: Eurostat / CEDEFOP",
        "fuente": "Eurostat · CEDEFOP Skills Intelligence",
        "url_api": None,
        "eje_y": "% Trabajadores",
        "color": "#f87171",
        "tipo_grafico": "bar",
        "datos_hardcoded": [
            ("2019", 14.0), ("2020", 14.5), ("2021", 15.2),
            ("2022", 15.8), ("2023", 16.4), ("2024", 17.1),
        ],
    },
}

# ── Empresas IBEX 35 — configuración y datos históricos ──────────────────────
# Historico actualizado a marzo 2026 — datos reales publicados (anuales 2024 + Q1-Q3 2025 disponibles)
# Nota: 2025 incluye datos anuales donde ya estan publicados, o estimacion Q3 acumulado donde no
EMPRESAS_IBEX = {
    "Santander": {
        "ticker": "SAN",
        "sector": "Banca",
        "emoji": "🏦",
        "color": "#e03131",
        "query_news": '"Santander" AND ("resultados" OR "beneficio" OR "beneficios" OR "2025" OR "2026") AND ("trimestre" OR "anual" OR "enero" OR "febrero")',
        "query_cnmv": "Santander resultados 2025",
        "historico": {
            "Ingresos netos (M EUR)":  [("2021", 35397), ("2022", 38206), ("2023", 44291), ("2024", 47649), ("9M-25", 38100)],
            "Beneficio neto (M EUR)":  [("2021", 8124),  ("2022", 9605),  ("2023", 11076), ("2024", 12574), ("9M-25", 10054)],
            "Ratio CET1 (%)":          [("2021", 12.5),  ("2022", 12.0),  ("2023", 12.3),  ("2024", 12.8),  ("9M-25", 13.1)],
        },
    },
    "BBVA": {
        "ticker": "BBVA",
        "sector": "Banca",
        "emoji": "🏦",
        "color": "#118DFF",
        "query_news": '"BBVA" AND ("resultados" OR "beneficio" OR "2025" OR "2026") AND ("trimestre" OR "anual" OR "enero" OR "febrero")',
        "query_cnmv": "BBVA resultados 2025",
        "historico": {
            "Ingresos netos (M EUR)":  [("2021", 17426), ("2022", 21434), ("2023", 25277), ("2024", 28978), ("9M-25", 24100)],
            "Beneficio neto (M EUR)":  [("2021", 4653),  ("2022", 6420),  ("2023", 8019),  ("2024", 9757),  ("9M-25", 8135)],
            "Ratio CET1 (%)":          [("2021", 14.5),  ("2022", 13.4),  ("2023", 12.7),  ("2024", 12.9),  ("9M-25", 13.1)],
        },
    },
    "Inditex": {
        "ticker": "ITX",
        "sector": "Retail / Moda",
        "emoji": "👗",
        "color": "#a78bfa",
        "query_news": '"Inditex" AND ("resultados" OR "ventas" OR "beneficio" OR "2025" OR "2026") AND ("trimestre" OR "anual")',
        "query_cnmv": "Inditex resultados 2025",
        "historico": {
            "Ventas netas (M EUR)":    [("FY21", 27716), ("FY22", 32569), ("FY23", 35947), ("FY24", 38623), ("9M-25", 31039)],
            "Beneficio neto (M EUR)":  [("FY21", 3243),  ("FY22", 4130),  ("FY23", 5381),  ("FY24", 5936),  ("9M-25", 4680)],
            "EBITDA (M EUR)":          [("FY21", 6946),  ("FY22", 8073),  ("FY23", 9561),  ("FY24", 10340), ("9M-25", 8400)],
        },
    },
    "Iberdrola": {
        "ticker": "IBE",
        "sector": "Energia / Utilities",
        "emoji": "⚡",
        "color": "#4ade80",
        "query_news": '"Iberdrola" AND ("resultados" OR "beneficio" OR "EBITDA" OR "2025" OR "2026") AND ("trimestre" OR "anual")',
        "query_cnmv": "Iberdrola resultados 2025",
        "historico": {
            "Ingresos (M EUR)":        [("2021", 36164), ("2022", 47488), ("2023", 41819), ("2024", 44732), ("9M-25", 35200)],
            "Beneficio neto (M EUR)":  [("2021", 3477),  ("2022", 4178),  ("2023", 5278),  ("2024", 5587),  ("9M-25", 5012)],
            "EBITDA (M EUR)":          [("2021", 10009), ("2022", 12111), ("2023", 14791), ("2024", 16380), ("9M-25", 14100)],
        },
    },
    "Telefonica": {
        "ticker": "TEF",
        "sector": "Telecomunicaciones",
        "emoji": "📡",
        "color": "#fbbf24",
        "query_news": '"Telefonica" AND ("resultados" OR "beneficio" OR "OIBDA" OR "2025" OR "2026") AND ("trimestre" OR "anual")',
        "query_cnmv": "Telefonica resultados 2025",
        "historico": {
            "Ingresos (M EUR)":        [("2021", 39277), ("2022", 42087), ("2023", 42065), ("2024", 41775), ("9M-25", 31200)],
            "Beneficio neto (M EUR)":  [("2021", 8137),  ("2022", 1820),  ("2023", 1705),  ("2024", 1637),  ("9M-25", 1350)],
            "OIBDA (M EUR)":           [("2021", 14512), ("2022", 15067), ("2023", 15440), ("2024", 15362), ("9M-25", 11580)],
        },
    },
    "Repsol": {
        "ticker": "REP",
        "sector": "Energia / Petroleo",
        "emoji": "🛢️",
        "color": "#f87171",
        "query_news": '"Repsol" AND ("resultados" OR "beneficio" OR "EBITDA" OR "2025" OR "2026") AND ("trimestre" OR "anual")',
        "query_cnmv": "Repsol resultados 2025",
        "historico": {
            "Ingresos (M EUR)":        [("2021", 47278), ("2022", 73604), ("2023", 58498), ("2024", 51230), ("9M-25", 36100)],
            "Beneficio neto (M EUR)":  [("2021", 2537),  ("2022", 4251),  ("2023", 3159),  ("2024", 2060),  ("9M-25", 1240)],
            "EBITDA ajustado (M EUR)": [("2021", 5516),  ("2022", 7246),  ("2023", 5943),  ("2024", 5120),  ("9M-25", 3510)],
        },
    },
    "CaixaBank": {
        "ticker": "CABK",
        "sector": "Banca",
        "emoji": "🏦",
        "color": "#6c63ff",
        "query_news": '"CaixaBank" AND ("resultados" OR "beneficio" OR "2025" OR "2026") AND ("trimestre" OR "anual" OR "enero" OR "febrero")',
        "query_cnmv": "CaixaBank resultados 2025",
        "historico": {
            "Ingresos (M EUR)":        [("2021", 9509),  ("2022", 10700), ("2023", 14604), ("2024", 16026), ("9M-25", 13840)],
            "Beneficio neto (M EUR)":  [("2021", 1381),  ("2022", 3145),  ("2023", 4816),  ("2024", 5787),  ("9M-25", 4769)],
            "Ratio CET1 (%)":          [("2021", 12.8),  ("2022", 12.5),  ("2023", 12.4),  ("2024", 12.8),  ("9M-25", 12.8)],
        },
    },
    "Amadeus": {
        "ticker": "AMS",
        "sector": "Tecnologia / Viajes",
        "emoji": "✈️",
        "color": "#0ea5e9",
        "query_news": '"Amadeus" AND ("resultados" OR "revenue" OR "beneficio" OR "2025" OR "2026") AND ("trimestre" OR "anual")',
        "query_cnmv": "Amadeus resultados 2025",
        "historico": {
            "Ingresos (M EUR)":        [("2021", 2843),  ("2022", 4658),  ("2023", 5741),  ("2024", 6235),  ("9M-25", 5148)],
            "Beneficio neto (M EUR)":  [("2021", 153),   ("2022", 700),   ("2023", 1252),  ("2024", 1437),  ("9M-25", 1182)],
            "EBITDA (M EUR)":          [("2021", 908),   ("2022", 1703),  ("2023", 2376),  ("2024", 2637),  ("9M-25", 2163)],
        },
    },
    "Ferrovial": {
        "ticker": "FER",
        "sector": "Infraestructuras",
        "emoji": "🏗️",
        "color": "#fb923c",
        "query_news": '"Ferrovial" AND ("resultados" OR "beneficio" OR "EBITDA" OR "2025" OR "2026") AND ("trimestre" OR "anual")',
        "query_cnmv": "Ferrovial resultados 2025",
        "historico": {
            "Ingresos (M EUR)":        [("2021", 7536),  ("2022", 8054),  ("2023", 8166),  ("2024", 8720),  ("9M-25", 7100)],
            "Beneficio neto (M EUR)":  [("2021", 459),   ("2022", 508),   ("2023", 1100),  ("2024", 1320),  ("9M-25", 1050)],
            "EBITDA (M EUR)":          [("2021", 804),   ("2022", 856),   ("2023", 908),   ("2024", 1050),  ("9M-25", 890)],
        },
    },
    "ACS": {
        "ticker": "ACS",
        "sector": "Construccion / Infraestructuras",
        "emoji": "🏗️",
        "color": "#84cc16",
        "query_news": '"ACS" AND ("resultados" OR "beneficio" OR "EBITDA" OR "2025" OR "2026") AND ("trimestre" OR "anual")',
        "query_cnmv": "ACS grupo resultados 2025",
        "historico": {
            "Ventas (M EUR)":          [("2021", 33826), ("2022", 38929), ("2023", 42048), ("2024", 44500), ("9M-25", 36200)],
            "Beneficio neto (M EUR)":  [("2021", 776),   ("2022", 700),   ("2023", 931),   ("2024", 1050),  ("9M-25", 870)],
            "EBITDA (M EUR)":          [("2021", 1820),  ("2022", 2140),  ("2023", 2391),  ("2024", 2600),  ("9M-25", 2150)],
        },
    },
}

TONOS = {
    "aprendiendo": {"label": "🎓 Estoy aprendiendo",    "instruccion": "Escribe desde la perspectiva de alguien que está aprendiendo y reflexionando sobre el sector. Muestra curiosidad y ganas de crecer."},
    "senior":      {"label": "💼 Quiero parecer senior", "instruccion": "Escribe con tono experto y seguro. Analiza con criterio profesional, usa terminología del sector con naturalidad."},
    "debate":      {"label": "🔥 Quiero generar debate",  "instruccion": "Escribe con una opinión fuerte y provocadora. Toma partido, cuestiona el status quo, invita a la discusión."},
}
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# ── Página ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Agente LinK", page_icon="https://raw.githubusercontent.com/CorralJulen/Agente-Linkedin/main/logo.png", layout="centered")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #0a0a0f; color: #f0f0f8; }
.main-header { text-align: center; padding: 2rem 0 2.5rem; }
.badge { display: inline-block; background: rgba(108,99,255,0.15); border: 1px solid rgba(108,99,255,0.35); color: #a78bfa; font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; padding: 5px 16px; border-radius: 99px; margin-bottom: 1.2rem; }
.main-title { font-family: 'Syne', sans-serif; font-size: 2.6rem; font-weight: 800; line-height: 1.1; letter-spacing: -0.02em; background: linear-gradient(135deg, #f0f0f8 30%, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.7rem; }
.main-sub { color: #7070a0; font-size: 15px; line-height: 1.6; }
.stats-row { display: flex; gap: 10px; margin-bottom: 1.5rem; }
.stat-card { flex: 1; background: #13131a; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 0.9rem 1rem; text-align: center; }
.stat-num { font-family: 'Syne', sans-serif; font-size: 22px; font-weight: 800; color: #f0f0f8; }
.stat-label { font-size: 11px; color: #7070a0; margin-top: 2px; }
.racha-fire { color: #fbbf24; }
.news-card { background: #13131a; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 1.4rem 1.6rem; margin-bottom: 0.5rem; }
.card-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 0.8rem; flex-wrap: wrap; }
.source-pill { background: rgba(108,99,255,0.15); border: 1px solid rgba(108,99,255,0.3); color: #a78bfa; font-size: 10px; font-weight: 600; letter-spacing: 0.06em; padding: 3px 12px; border-radius: 99px; }
.sector-pill-banca { background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); color: #93c5fd; font-size: 10px; font-weight: 700; padding: 3px 12px; border-radius: 99px; }
.sector-pill-estrategia { background: rgba(168,85,247,0.15); border: 1px solid rgba(168,85,247,0.3); color: #d8b4fe; font-size: 10px; font-weight: 700; padding: 3px 12px; border-radius: 99px; }
.sector-pill-datos { background: rgba(20,184,166,0.15); border: 1px solid rgba(20,184,166,0.3); color: #5eead4; font-size: 10px; font-weight: 700; padding: 3px 12px; border-radius: 99px; }
.sector-pill-ia { background: rgba(251,191,36,0.15); border: 1px solid rgba(251,191,36,0.3); color: #fbbf24; font-size: 10px; font-weight: 700; padding: 3px 12px; border-radius: 99px; }
.sector-pill-macro { background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3); color: #6ee7b7; font-size: 10px; font-weight: 700; padding: 3px 12px; border-radius: 99px; }
.sector-pill-ia_tech { background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; font-size: 10px; font-weight: 700; padding: 3px 12px; border-radius: 99px; }
.date-pill { color: #7070a0; font-size: 11px; }
.card-title { font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 700; color: #f0f0f8; line-height: 1.35; margin-bottom: 0.6rem; }
.card-desc { color: rgba(112,112,160,0.9); font-size: 13px; line-height: 1.65; }
.section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #7070a0; margin: 1.8rem 0 1rem; display: flex; align-items: center; gap: 10px; }
.section-label::after { content: ''; flex: 1; height: 1px; background: rgba(255,255,255,0.07); }
.opcion-card { background: #13131a; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.2rem 1.4rem; margin-bottom: 0.5rem; font-size: 13px; line-height: 1.75; color: #d0d0e0; white-space: pre-wrap; word-break: break-word; }
.opcion-card-recomendada { background: rgba(74,222,128,0.05); border: 1.5px solid rgba(74,222,128,0.4); border-radius: 16px; padding: 1.2rem 1.4rem; margin-bottom: 0.5rem; font-size: 13px; line-height: 1.75; color: #d0d0e0; white-space: pre-wrap; word-break: break-word; }
.recomendada-badge { display: inline-flex; align-items: center; gap: 6px; background: rgba(74,222,128,0.15); border: 1px solid rgba(74,222,128,0.35); color: #4ade80; font-size: 10px; font-weight: 700; padding: 3px 12px; border-radius: 99px; margin-bottom: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; }
.razon-badge { font-size: 12px; color: #4ade80; background: rgba(74,222,128,0.08); border-radius: 8px; padding: 6px 10px; margin-top: 8px; margin-bottom: 4px; line-height: 1.5; }
.img-wrapper { border-radius: 14px; overflow: hidden; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.08); }
.img-caption { font-size: 11px; color: #7070a0; margin-top: 6px; margin-bottom: 1rem; }
.historial-item { background: #13131a; border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: 8px; }
.historial-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.historial-fecha { font-size: 11px; color: #7070a0; }
.historial-preview { font-size: 12px; color: rgba(240,240,248,0.7); line-height: 1.6; }
.edicion-guiada-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #7070a0; margin-bottom: 8px; margin-top: 12px; }
.cal-row { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.cal-day { flex: 1; min-width: 70px; background: #13131a; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 0.7rem 0.5rem; text-align: center; }
.cal-day-name { font-size: 10px; color: #7070a0; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 4px; }
.cal-day-pub { font-size: 11px; color: #4ade80; font-weight: 600; }
.cal-day-empty { font-size: 11px; color: rgba(112,112,160,0.4); }
.cal-day-hoy { border-color: rgba(108,99,255,0.4); background: rgba(108,99,255,0.08); }
.comp-card { background: #13131a; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.2rem 1.4rem; margin-bottom: 1rem; }
.comp-section { font-size: 11px; font-weight: 700; color: #a78bfa; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; margin-top: 12px; }
.comp-item { font-size: 13px; color: #d0d0e0; line-height: 1.7; padding-left: 14px; position: relative; }
.comp-item::before { content: "▸"; position: absolute; left: 0; color: #6c63ff; }
.li-card { background: #1b1f23; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 1.2rem 1.4rem; margin-bottom: 1.2rem; }
.li-header { display: flex; align-items: center; gap: 12px; margin-bottom: 1rem; }
.li-avatar { width: 48px; height: 48px; border-radius: 50%; background: linear-gradient(135deg, #6c63ff, #9333ea); display: flex; align-items: center; justify-content: center; font-family: 'Syne', sans-serif; font-size: 18px; font-weight: 800; color: white; flex-shrink: 0; }
.li-name { font-weight: 600; font-size: 14px; color: #f0f0f8; }
.li-headline { font-size: 11px; color: #7070a0; margin-top: 1px; }
.li-time { font-size: 10px; color: #7070a0; margin-top: 1px; }
.li-body { font-size: 13px; line-height: 1.75; color: #d0d0e0; white-space: pre-wrap; word-break: break-word; }
.li-hashtag { color: #6c9fff; }
.li-reactions { display: flex; align-items: center; gap: 6px; margin-top: 1rem; padding-top: 0.8rem; border-top: 1px solid rgba(255,255,255,0.06); font-size: 12px; color: #7070a0; }
.score-wrapper { background: #13131a; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.2rem 1.4rem; margin-bottom: 1.2rem; }
.score-title { font-family: 'Syne', sans-serif; font-size: 13px; font-weight: 700; color: #f0f0f8; margin-bottom: 1rem; }
.score-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.score-label { font-size: 12px; color: #7070a0; width: 140px; flex-shrink: 0; }
.score-bar-bg { flex: 1; height: 6px; background: rgba(255,255,255,0.07); border-radius: 99px; overflow: hidden; }
.score-bar { height: 100%; border-radius: 99px; }
.score-num { font-size: 12px; font-weight: 600; width: 28px; text-align: right; }
.score-total { font-family: 'Syne', sans-serif; font-size: 36px; font-weight: 800; text-align: center; margin: 0.8rem 0 0.2rem; }
.score-nivel { font-size: 13px; font-weight: 600; text-align: center; margin-bottom: 1rem; }
.score-feedback { font-size: 12px; color: rgba(240,240,248,0.7); line-height: 1.65; padding: 0.8rem 1rem; background: rgba(255,255,255,0.03); border-radius: 10px; border-left: 2px solid #6c63ff; margin-top: 1rem; }
.post-header { display: flex; align-items: center; gap: 14px; margin-bottom: 1.2rem; }
.post-icon { width: 46px; height: 46px; background: linear-gradient(135deg, #6c63ff, #9333ea); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.dash-metric { background: #13131a; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: 10px; }
.dash-metric-num { font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 800; color: #f0f0f8; }
.dash-metric-label { font-size: 12px; color: #7070a0; margin-top: 2px; }
.dash-bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.dash-bar-label { font-size: 12px; color: #d0d0e0; width: 130px; flex-shrink: 0; }
.dash-bar-bg { flex: 1; height: 8px; background: rgba(255,255,255,0.06); border-radius: 99px; overflow: hidden; }
.dash-bar-fill { height: 100%; border-radius: 99px; }
.dash-bar-val { font-size: 12px; color: #7070a0; width: 24px; text-align: right; }
.stButton > button { font-family: 'Syne', sans-serif !important; font-weight: 700 !important; border-radius: 14px !important; border: none !important; transition: all 0.2s !important; background: linear-gradient(135deg, #e03131, #c92a2a) !important; color: white !important; box-shadow: 0 4px 18px rgba(224,49,49,0.35) !important; }
.stButton > button:hover { background: linear-gradient(135deg, #c92a2a, #b02020) !important; }
hr { border-color: rgba(255,255,255,0.07) !important; margin: 1.5rem 0 !important; }
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Supabase helpers ───────────────────────────────────────────────────────────

def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

def sb_cargar_historial():
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/linkedin_historial?order=id.desc&limit=200",
            headers=_sb_headers(), timeout=10
        )
        if r.status_code == 200:
            return r.json()
        else:
            st.error(f"Error Supabase (Cargar Historial): {r.status_code} - {r.text}")
    except Exception as e:
        st.error(f"Error de red (Cargar Historial): {e}")
    return []

def sb_guardar_post(entrada: dict):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/linkedin_historial",
            headers=_sb_headers(),
            json=entrada, timeout=10
        )
        if r.status_code not in (200, 201):
            st.error(f"Error Supabase (Guardar Post): {r.status_code} - {r.text}")
    except Exception as e:
        st.error(f"Error de red (Guardar Post): {e}")

def sb_cargar_config(clave: str, default):
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/linkedin_config?clave=eq.{clave}&limit=1",
            headers=_sb_headers(), timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                return json.loads(data[0]["valor"])
        else:
            st.error(f"Error Supabase (Cargar Config): {r.status_code} - {r.text}")
    except Exception as e:
        st.error(f"Error de red (Cargar Config): {e}")
    return default

def sb_guardar_config(clave: str, valor):
    try:
        headers = {**_sb_headers(), "Prefer": "resolution=merge-duplicates"}
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/linkedin_config",
            headers=headers,
            json={"clave": clave, "valor": json.dumps(valor)}, timeout=10
        )
        if r.status_code not in (200, 201):
            st.error(f"Error Supabase (Guardar Config): {r.status_code} - {r.text}")
    except Exception as e:
        st.error(f"Error de red (Guardar Config): {e}")

# ── Helpers ────────────────────────────────────────────────────────────────────

def es_relevante(titulo, resumen, keywords):
    texto = (titulo + " " + resumen).lower()
    return any(kw.lower() in texto for kw in keywords)

# Palabras negativas comunes — descartan noticias irrelevantes o dañinas
_NEG_COMUNES = [
    "acoso","menor","menores","niño","niños","adolescente","pornografía","desnudo","abuso",
    "violencia","delito","denuncia","demanda","escándalo","corrupción",
    "auricular","auriculares","smartphone","consola","videojuego","televisor","tablet",
    "coche eléctrico","vehículo","automóvil","oferta","rebaja","tienda","amazon",
]
# IA negocio — descartan noticias alarmistas, regulatorias o irrelevantes
PALABRAS_NEGATIVAS_IA_NEGOCIO = _NEG_COMUNES + [
    "peligro ia","apocalipsis","amenaza","desempleo masivo","destrucción empleo",
    "robot roba trabajo","máquinas sustituyen","fin del trabajo","discriminación algoritmo",
    "prohibir ia","ban ia","deepfake","fake news ia","manipulación ia",
    "vigilancia masiva","espionaje ia","privacidad violada ia","IA mata","IA peligrosa",
    "regulación restrictiva ia","multa ia","sanción ia",
]
# IA finanzas — descartan noticias de cripto especulativa, escándalos o alarmismo
PALABRAS_NEGATIVAS_IA_FINANZAS = _NEG_COMUNES + [
    "cripto","bitcoin","ethereum","nft","blockchain especulativa","token",
    "estafa","fraude cripto","ponzi","colapso","quiebra","crack","derrumbe",
    "pérdidas millonarias","caída bolsa","escándalo financiero",
    "burbuja","especulación","ciberataque banco","hackeo bancario",
    "peligro ia","regulación prohibición fintech",
]

def es_noticia_valida(titulo, resumen, sector):
    """Descarta noticias con palabras negativas según el sector."""
    texto = (titulo + " " + resumen).lower()
    if sector == "ia_negocio":
        lista = PALABRAS_NEGATIVAS_IA_NEGOCIO
    elif sector == "ia_finanzas":
        lista = PALABRAS_NEGATIVAS_IA_FINANZAS
    else:
        lista = _NEG_COMUNES
    return not any(p.lower() in texto for p in lista)

def extraer_imagen(entry):
    if hasattr(entry, "media_content"):
        for m in entry.media_content:
            url = m.get("url", "")
            if url and any(url.lower().endswith(ext) for ext in [".jpg",".jpeg",".png",".webp"]):
                return url
    if hasattr(entry, "media_thumbnail"):
        for m in entry.media_thumbnail:
            url = m.get("url", "")
            if url: return url
    if hasattr(entry, "enclosures"):
        for enc in entry.enclosures:
            if enc.get("type","").startswith("image"):
                return enc.get("href", enc.get("url",""))
    if hasattr(entry, "summary"):
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.summary)
        if match: return match.group(1)
    return ""

def guardar_en_historial(post, noticia, sector, tono):
    if "historial" not in st.session_state:
        st.session_state.historial = []
    etiqueta = SECTORES.get(sector, {}).get("etiqueta", sector)
    tono_label = TONOS.get(tono, {}).get("label", tono)
    entrada = {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "titulo": noticia.get("titulo",""),
        "fuente": noticia.get("fuente",""),
        "sector": etiqueta,
        "tono": tono_label,
        "preview": post[:200],
    }
    st.session_state.historial.insert(0, entrada)
    # Marcar la URL como usada para que no vuelva a aparecer
    url_noticia = noticia.get("url","")
    if url_noticia and url_noticia not in st.session_state.usadas:
        st.session_state.usadas.append(url_noticia)
    sb_guardar_post(entrada)

def calcular_racha():
    if "historial" not in st.session_state or not st.session_state.historial:
        return 0, 0
    ahora = datetime.now()
    inicio_semana = (ahora - timedelta(days=ahora.weekday())).replace(hour=0,minute=0,second=0)
    posts_semana = sum(1 for h in st.session_state.historial
        if datetime.strptime(h["fecha"], "%d/%m/%Y %H:%M") >= inicio_semana)
    semanas = set()
    for h in st.session_state.historial:
        d = datetime.strptime(h["fecha"], "%d/%m/%Y %H:%M")
        semanas.add((d.year, d.isocalendar()[1]))
    semanas_cons = 0
    sa, ya = ahora.isocalendar()[1], ahora.year
    for i in range(52):
        s, a = sa - i, ya
        if s <= 0: s += 52; a -= 1
        if (a, s) in semanas: semanas_cons += 1
        else: break
    return posts_semana, semanas_cons

def parsear_un_feed(sector, excluir_urls):
    """Obtiene una noticia nueva de un sector excluyendo URLs ya usadas."""
    cfg = SECTORES[sector]
    keywords = cfg.get("keywords", [])
    gnews_queries = cfg.get("gnews", [])

    # Para ia_negocio e ia_finanzas: Google News como fuente principal
    # Mezclar todas las queries para maximizar variedad
    if gnews_queries:
        import random as _random
        queries_shuffled = gnews_queries[:]
        _random.shuffle(queries_shuffled)
        candidatos = []
        for q in queries_shuffled:
            arts = _gnews_buscar(q, sector, limite=20)
            for art in arts:
                if art["url"] not in excluir_urls:
                    candidatos.append(art)
        # Quitar duplicados por URL
        vistos = set()
        candidatos_unicos = []
        for art in candidatos:
            if art["url"] not in vistos:
                vistos.add(art["url"])
                candidatos_unicos.append(art)
        if candidatos_unicos:
            # Elegir aleatoriamente del pool (no siempre el más reciente)
            elegido = _random.choice(candidatos_unicos[:10])
            elegido["_sector"] = sector
            return {k: v for k, v in elegido.items() if k != "_pub"}

    # Para banca y estrategia: RSS directo
    hace_7_dias = datetime.now() - timedelta(days=7)
    feeds = list(cfg["feeds"])
    random.shuffle(feeds)
    for fuente, url in feeds:
        try:
            feed = feedparser.parse(url)
            entradas = [e for e in feed.entries if e.get("link","") not in excluir_urls]
            random.shuffle(entradas)
            for entry in entradas[:12]:
                published = None
                if hasattr(entry,"published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                if published and published < hace_7_dias: continue
                resumen = entry.get("summary", entry.get("description",""))[:400]
                titulo = entry.get("title","")
                if not titulo or len(resumen) < 60: continue
                if keywords and not es_relevante(titulo, resumen, keywords): continue
                if not es_noticia_valida(titulo, resumen, sector): continue
                return {"fuente": fuente, "titulo": titulo, "resumen": resumen,
                        "url": entry.get("link",""),
                        "fecha": published.strftime("%d/%m/%Y") if published else "reciente",
                        "imagen": extraer_imagen(entry), "_sector": sector}
        except Exception: pass
    return None

# ── Funciones Gemini ───────────────────────────────────────────────────────────

def _newsapi_buscar(query_es, fuente_label):
    """Busca noticias via NewsAPI en español. Devuelve lista de artículos normalizados."""
    try:
        desde = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query_es,
                "language": "es",
                "sortBy": "publishedAt",
                "pageSize": 10,
                "from": desde,
                "apiKey": NEWSAPI_KEY,
            },
            timeout=10
        )
        if r.status_code != 200:
            return []
        arts = r.json().get("articles", [])
        resultado = []
        for a in arts:
            titulo = a.get("title","") or ""
            resumen = a.get("description","") or a.get("content","") or ""
            url = a.get("url","")
            if not titulo or not url or len(resumen) < 60: continue
            # Filtrar artículos en inglés por heurística simple
            palabras_ingles = ["the ","this ","that ","with ","from ","have ","will ","your ","their "]
            texto_lower = (titulo + " " + resumen).lower()
            if sum(1 for p in palabras_ingles if p in texto_lower) >= 3: continue
            try:
                published = datetime.fromisoformat(a.get("publishedAt","").replace("Z",""))
            except Exception:
                published = datetime.now()
            resultado.append({
                "fuente": a.get("source",{}).get("name", fuente_label),
                "titulo": titulo[:200],
                "resumen": resumen[:400],
                "url": url,
                "fecha": published.strftime("%d/%m/%Y"),
                "imagen": a.get("urlToImage","") or "",
            })
        return resultado
    except Exception:
        return []

def _gnews_buscar(query, sector, limite=15):
    """Busca en Google News RSS. Gratuito, sin limites, excelente cobertura."""
    import urllib.parse
    resultados = []
    keywords = SECTORES.get(sector, {}).get("keywords", [])
    try:
        q_enc = urllib.parse.quote(query)
        url_g = f"https://news.google.com/rss/search?q={q_enc}&hl=es&gl=ES&ceid=ES:es"
        feed = feedparser.parse(url_g)
        hace_10_dias = datetime.now() - timedelta(days=10)
        for entry in feed.entries[:limite]:
            titulo = entry.get("title", "") or ""
            resumen = entry.get("summary", entry.get("description", ""))[:500] or ""
            resumen_limpio = re.sub(r'<[^>]+>', '', resumen).strip()[:400]
            url_art = entry.get("link", "")
            if not titulo or not url_art: continue
            try:
                pub = datetime(*entry.published_parsed[:6]) if hasattr(entry,"published_parsed") and entry.published_parsed else datetime.now()
            except Exception:
                pub = datetime.now()
            if pub < hace_10_dias: continue
            if not es_noticia_valida(titulo, resumen_limpio, sector): continue
            if keywords and not es_relevante(titulo, resumen_limpio, keywords): continue
            resultados.append({
                "fuente": "Google News",
                "titulo": titulo[:200],
                "resumen": resumen_limpio if len(resumen_limpio) > 40 else titulo,
                "url": url_art,
                "fecha": pub.strftime("%d/%m/%Y"),
                "imagen": "",
                "_pub": pub,
            })
    except Exception:
        pass
    return resultados

@st.cache_data(ttl=900, show_spinner=False)
def fetch_noticias_por_sector():
    hace_7_dias = datetime.now() - timedelta(days=7)

    def parsear_rss(feeds, keywords, sector_key):
        noticias = []
        for fuente, url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:8]:
                    published = None
                    if hasattr(entry,"published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])
                    if published and published < hace_7_dias: continue
                    titulo = entry.get("title","")
                    resumen = entry.get("summary", entry.get("description",""))[:400]
                    if not titulo or len(resumen) < 60: continue
                    if keywords and not es_relevante(titulo, resumen, keywords): continue
                    if not es_noticia_valida(titulo, resumen, sector_key): continue
                    noticias.append({"fuente": fuente, "titulo": titulo, "resumen": resumen,
                        "url": entry.get("link",""),
                        "fecha": published.strftime("%d/%m/%Y") if published else "reciente",
                        "imagen": extraer_imagen(entry),
                        "_pub": published or datetime.now()})
            except Exception: pass
        return noticias

    resultado = {}
    for sector_key, cfg in SECTORES.items():
        keywords = cfg.get("keywords", [])
        pool = parsear_rss(cfg["feeds"], keywords, sector_key)

        # ia_negocio e ia_finanzas: Google News como fuente principal
        gnews_queries = cfg.get("gnews", [])
        for q in gnews_queries:
            arts = _gnews_buscar(q, sector_key)
            for art in arts:
                if art["url"] not in [p["url"] for p in pool]:
                    pool.append(art)
            if len(pool) >= 10:
                break

        # Ordenar por fecha, elegir una al azar del top-5 más recientes
        pool.sort(key=lambda x: x.get("_pub", datetime.now()), reverse=True)
        pool_clean = [{k: v for k, v in p.items() if k != "_pub"} for p in pool]
        resultado[sector_key] = random.choice(pool_clean[:5]) if pool_clean else None
    return resultado

def generar_dos_posts(noticia, perfil, tono):
    client = genai.Client(api_key=GEMINI_API_KEY)
    instruccion_tono = TONOS.get(tono, TONOS["aprendiendo"])["instruccion"]
    base = f"""Escribe un post de LinkedIn sobre la siguiente noticia del sector de {perfil}.
NOTICIA: {noticia['titulo']} | {noticia['fuente']} | {noticia['resumen']}
TONO: {instruccion_tono}

REGLAS ESTRICTAS DE FORMATO Y ESTILO:
1. ESTRUCTURA: Escribe párrafos cortos de máximo 2-3 líneas. Usa siempre un doble salto de línea entre párrafos para evitar muros de texto.
2. EMOJIS: Usa un máximo de 2 emojis en todo el texto (solo al principio o al final de las frases).
3. CIERRE: Termina con una pregunta polarizante o desafiante sobre el sector que invite al debate en los comentarios.
4. PARÁMETROS: Post en ESPAÑOL (150-250 palabras). Gancho → análisis (3-5 insights) → pregunta. 5-8 hashtags al final.
5. IMPORTANTE: NO menciones en ningún momento que eres estudiante, consultor junior, que estudias un máster ni ningún rol o título académico. Escribe con criterio propio sin etiquetar al autor.
NO menciones que eres una IA. Devuelve SOLO el texto del post."""
    resp_a = client.models.generate_content(model="gemini-flash-latest", contents=base+"\nESTILO: Analítico y técnico.")
    resp_b = client.models.generate_content(model="gemini-flash-latest", contents=base+"\nESTILO: Cercano y reflexivo, storytelling.")
    post_a, post_b = resp_a.text.strip(), resp_b.text.strip()
    try:
        resp_rec = client.models.generate_content(model="gemini-flash-latest",
            contents=f'Noticia: {noticia["titulo"]} | Sector: {perfil}\nA=analítica, B=reflexiva. ¿Cuál encaja mejor? JSON SOLO: {{"recomendada":"A"o"B","razon":"max 15 palabras"}}')
        rec = json.loads(resp_rec.text.strip().replace("```json","").replace("```","").strip())
        recomendada, razon = rec.get("recomendada","A"), rec.get("razon","")
    except Exception:
        recomendada, razon = "A", ""
    return post_a, post_b, recomendada, razon

def generar_post(noticia, perfil, tono="aprendiendo"):
    client = genai.Client(api_key=GEMINI_API_KEY)
    instruccion_tono = TONOS.get(tono, TONOS["aprendiendo"])["instruccion"]
    prompt = f"""Escribe un post de LinkedIn sobre la siguiente noticia del sector de {perfil}.
NOTICIA: {noticia['titulo']} | {noticia['fuente']} | {noticia['resumen']}
TONO: {instruccion_tono}

REGLAS ESTRICTAS DE FORMATO Y ESTILO:
1. ESTRUCTURA: Escribe párrafos cortos de máximo 2-3 líneas. Usa siempre un doble salto de línea entre párrafos para evitar muros de texto.
2. EMOJIS: Usa un máximo de 2 emojis en todo el texto (solo al principio o al final de las frases).
3. CIERRE: Termina con una pregunta polarizante o desafiante sobre el sector que invite al debate en los comentarios.
4. PARÁMETROS: Post en ESPAÑOL (150-250 palabras). Gancho → análisis (3-5 insights) → pregunta. 5-8 hashtags al final.
5. IMPORTANTE: NO menciones en ningún momento que eres estudiante, consultor junior, que estudias un máster ni ningún rol o título académico. Escribe con criterio propio sin etiquetar al autor.
NO menciones que eres una IA. Devuelve SOLO el texto del post."""
    return client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()

def editar_post_guiado(post, instruccion):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Editor experto LinkedIn. POST:\n{post}\nINSTRUCCIÓN: {instruccion}\nApplica SOLO el cambio. Devuelve SOLO el post modificado."""
    return client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()

def cambiar_pregunta_final(post, modo):
    """Regenera solo la pregunta final del post según el modo elegido."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    instrucciones = {
        "favor": "Reescribe SOLO la pregunta final del post con una pregunta que posicione al autor a FAVOR del tema de la noticia, que invite al debate desde una perspectiva positiva hacia la innovación y el avance del sector. El resto del post queda exactamente igual.",
        "debate": "Reescribe SOLO la pregunta final del post con una pregunta muy provocadora y polarizante que genere debate, sin posicionarse en contra del tema principal. Que enfrente dos posturas del sector. El resto del post queda exactamente igual.",
        "reflexion": "Reescribe SOLO la pregunta final del post con una pregunta reflexiva y abierta que invite a compartir experiencias personales del lector sobre el tema. Nada de polémica, solo reflexión. El resto del post queda exactamente igual.",
    }
    instruccion = instrucciones.get(modo, instrucciones["debate"])
    prompt = f"""Editor experto LinkedIn. POST:\n{post}\nINSTRUCCIÓN: {instruccion}\nDevuelve SOLO el post completo con la nueva pregunta final."""
    return client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()

def traducir_post_ingles(post):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Adapta este post al inglés para Big 4, strategy consulting y banking. No literal — adapta tono y hashtags.\nPOST: {post}\nSOLO el texto en inglés."""
    return client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()

def puntuar_post(post):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Experto marketing B2B LinkedIn. Analiza y devuelve SOLO JSON sin markdown:
POST: {post}
{{"gancho":<1-10>,"claridad":<1-10>,"valor":<1-10>,"engagement":<1-10>,"hashtags":<1-10>,"total":<1-100>,"nivel":"<Excelente|Muy bueno|Bueno|Mejorable>","feedback":"<2-3 frases>"}}"""
    raw = client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()
    return json.loads(raw.replace("```json","").replace("```","").strip())

def analizar_competencia(sector):
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = SECTORES.get(sector, {})
    perfil = cfg.get("perfil", "consultor junior")
    etiqueta = cfg.get("etiqueta", sector)
    prompt = f"""Eres un experto en estrategia de contenido LinkedIn para el sector de {etiqueta} en España.
Basándote en tu conocimiento del mercado laboral español y LinkedIn, analiza qué tipo de contenido publican típicamente los consultores junior y analistas de {perfil} en LinkedIn España.
Devuelve SOLO un JSON válido sin markdown con este formato exacto:
{{"formatos_populares":["f1","f2","f3","f4"],"temas_trending":["t1","t2","t3","t4","t5"],"ganchos_efectivos":["g1","g2","g3"],"hashtags_top":["#h1","#h2","#h3","#h4","#h5","#h6"],"mejor_dia_hora":"día y hora","consejo_diferenciacion":"2-3 frases","error_comun":"el error más común"}}"""
    raw = client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()
    return json.loads(raw.replace("```json","").replace("```","").strip())

def generar_contenido_carrusel(post, noticia, sector):
    client = genai.Client(api_key=GEMINI_API_KEY)
    etiqueta = SECTORES.get(sector, {}).get("etiqueta", sector)
    prompt = f"""Convierte este post de LinkedIn en un carrusel de 5 slides profesional.
POST ORIGINAL: {post}
NOTICIA BASE: {noticia.get('titulo','')} | SECTOR: {etiqueta}
Devuelve SOLO JSON válido sin markdown:
{{"sector":"{etiqueta}","titulo_portada":"máx 8 palabras impactante","subtitulo_portada":"máx 12 palabras","slides":[{{"titulo":"máx 6 palabras","cuerpo":"2-3 frases concretas","dato_destacado":"cifra o null"}},{{"titulo":"","cuerpo":"","dato_destacado":null}},{{"titulo":"","cuerpo":"","dato_destacado":"stat o null"}},{{"titulo":"","cuerpo":"","dato_destacado":null}},{{"titulo":"","cuerpo":"","dato_destacado":null}}],"pregunta_final":"máx 15 palabras provocadora","cta":"Sígueme para más análisis · Comenta tu opinión"}}"""
    raw = client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()
    return json.loads(raw.replace("```json","").replace("```","").strip())

def sugerir_estrategia_proximo_post(datos_audiencia):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Basado en estos datos reales de audiencia de LinkedIn: {datos_audiencia}
Analiza qué perfiles están leyendo el contenido y sugiere UNA estrategia clara para el PRÓXIMO post.
Dime: qué tema tocar, qué tono usar y a qué sector específico atacar para crecer.
Responde de forma concisa (máx 60 palabras)."""
    return client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()

# ── Funciones de datos macroeconómicos e IA & Tech ────────────────────────────

def fetch_datos_bce(url_api):
    try:
        r = requests.get(url_api, timeout=12, headers={"Accept": "application/json"})
        if r.status_code != 200: return []
        data = r.json()
        series = data.get("dataSets",[{}])[0].get("series",{})
        if not series: return []
        obs = list(series.values())[0].get("observations",{})
        periodos = data.get("structure",{}).get("dimensions",{}).get("observation",[{}])[0].get("values",[])
        resultado = []
        for idx, periodo in enumerate(periodos):
            val = obs.get(str(idx), [None])[0]
            if val is not None:
                resultado.append((periodo.get("name", str(idx)), float(val)))
        return resultado[-24:]
    except Exception:
        return []

def fetch_datos_ine(url_api):
    try:
        r = requests.get(url_api, timeout=12)
        if r.status_code != 200: return []
        data = r.json()
        datos = data.get("Data", [])
        resultado = []
        for d in datos:
            fecha = d.get("NombrePeriodo","")
            val = d.get("Valor")
            if val is not None and fecha:
                resultado.append((fecha, float(str(val).replace(",","."))))
        return resultado
    except Exception:
        return []

def fetch_datos_eurostat(url_api):
    try:
        r = requests.get(url_api, timeout=12, headers={"Accept": "application/json"})
        if r.status_code != 200: return []
        data = r.json()
        dimensiones = data.get("dimension", {})
        tiempo = None
        for k, v in dimensiones.items():
            if "time" in k.lower() or k == "time":
                tiempo = v
                break
        if not tiempo:
            tiempo = list(dimensiones.values())[-1]
        periodos = {str(v): k for k, v in tiempo.get("category", {}).get("index", {}).items()}
        valores = data.get("value", {})
        resultado = []
        for idx_str, val in valores.items():
            if val is not None:
                periodo = periodos.get(idx_str, idx_str)
                resultado.append((periodo, float(val)))
        return sorted(resultado, key=lambda x: x[0])
    except Exception:
        return []

def obtener_datos_indicador(indicador_id, tipo_sector):
    cfg = INDICADORES_MACRO.get(indicador_id, {}) if tipo_sector == "macro" else INDICADORES_IA_TECH.get(indicador_id, {})
    if not cfg: return [], cfg
    # Prioridad: datos hardcodeados > API en vivo
    hardcoded = cfg.get("datos_hardcoded")
    if hardcoded is not None:
        return hardcoded, cfg
    # Solo BCE usa API en vivo
    url = cfg.get("url_api")
    if not url:
        return [], cfg
    if "ecb.europa.eu" in url:
        datos = fetch_datos_bce(url)
    else:
        datos = []
    return datos, cfg

def generar_grafico_png(datos, cfg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import io as _io

    fechas = [d[0] for d in datos]
    valores = [d[1] for d in datos]
    color = cfg.get("color", "#6c63ff")

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#0a0a0f")
    ax.set_facecolor("#13131a")

    if cfg.get("tipo_grafico") == "bar":
        ax.bar(range(len(fechas)), valores, color=color, alpha=0.85, zorder=3, width=0.6)
        ax.set_xticks(range(len(fechas)))
        ax.set_xticklabels(fechas, rotation=45, ha="right", fontsize=9, color="#a0a0c0")
    else:
        ax.plot(range(len(fechas)), valores, color=color, linewidth=2.5, zorder=3, marker="o", markersize=4)
        ax.fill_between(range(len(fechas)), valores, alpha=0.12, color=color)
        step = max(1, len(fechas)//10)
        ax.set_xticks(range(0, len(fechas), step))
        ax.set_xticklabels([fechas[i] for i in range(0, len(fechas), step)],
                           rotation=45, ha="right", fontsize=9, color="#a0a0c0")

    ax.set_title(cfg.get("nombre",""), fontsize=14, fontweight="bold", color="#f0f0f8", pad=16)
    ax.set_ylabel(cfg.get("eje_y",""), fontsize=10, color="#a0a0c0")
    ax.tick_params(axis="y", labelcolor="#a0a0c0", labelsize=9)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#2a2a4a"); ax.spines["bottom"].set_color("#2a2a4a")
    ax.grid(axis="y", color="#2a2a4a", linewidth=0.6, zorder=0)
    fig.text(0.5, -0.04, f"Fuente: {cfg.get('fuente','')} · {cfg.get('descripcion','')}", ha="center", fontsize=8, color="#7070a0", style="italic")
    fig.tight_layout()

    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()

def generar_dashboard_png(datos, cfg, estilo="powerbi"):
    """
    Genera una imagen estilo dashboard con KPIs + gráfico.
    estilo: "powerbi" = colores Microsoft Power BI
            "dark"    = colores del agente (oscuro + morado)
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.ticker as mticker
    import io as _io

    fechas = [d[0] for d in datos]
    valores = [d[1] for d in datos]
    nombre = cfg.get("nombre", "Indicador")
    fuente = cfg.get("fuente", "")
    eje_y = cfg.get("eje_y", "")
    tipo_g = cfg.get("tipo_grafico", "line")

    # ── Paleta según estilo ────────────────────────────────────────────────
    if estilo == "powerbi":
        BG_OUTER   = "#F3F2F1"   # gris claro fondo exterior
        BG_HEADER  = "#243A5E"   # azul oscuro Power BI
        BG_CARD    = "#FFFFFF"   # blanco tarjetas
        BG_CHART   = "#FFFFFF"   # blanco gráfico
        COLOR_LINE = "#118DFF"   # azul Power BI
        COLOR_BAR  = "#118DFF"
        COLOR_ACC  = "#F2C811"   # amarillo Power BI
        TXT_HEADER = "#FFFFFF"
        TXT_CARD   = "#252423"
        TXT_SUB    = "#605E5C"
        TXT_AXIS   = "#605E5C"
        GRID_COL   = "#E8E6E3"
        BORDER_COL = "#D2D0CE"
        LOGO_TXT   = ""
    else:  # dark
        BG_OUTER   = "#0a0a0f"
        BG_HEADER  = "#13131a"
        BG_CARD    = "#1c1c2e"
        BG_CHART   = "#13131a"
        COLOR_LINE = "#6c63ff"
        COLOR_BAR  = "#6c63ff"
        COLOR_ACC  = "#fbbf24"
        TXT_HEADER = "#f0f0f8"
        TXT_CARD   = "#f0f0f8"
        TXT_SUB    = "#a78bfa"
        TXT_AXIS   = "#7070a0"
        GRID_COL   = "#2a2a4a"
        BORDER_COL = "#2a2a4a"
        LOGO_TXT   = ""

    # ── Layout: 1200x700 px ───────────────────────────────────────────────
    fig = plt.figure(figsize=(12, 7), facecolor=BG_OUTER)

    # Grid: cabecera + [3 KPIs | gráfico] + footer
    gs = fig.add_gridspec(
        3, 4,
        height_ratios=[0.12, 0.72, 0.08],
        width_ratios=[1, 1, 1, 3],
        hspace=0.18, wspace=0.3,
        left=0.04, right=0.97, top=0.96, bottom=0.04
    )

    # ── Cabecera ──────────────────────────────────────────────────────────
    ax_hdr = fig.add_subplot(gs[0, :])
    ax_hdr.set_facecolor(BG_HEADER)
    ax_hdr.set_xlim(0, 1); ax_hdr.set_ylim(0, 1)
    ax_hdr.axis("off")
    ax_hdr.text(0.02, 0.55, nombre, color=TXT_HEADER,
                fontsize=13, fontweight="bold", va="center")
    ax_hdr.text(0.02, 0.15, f"Fuente: {fuente}  ·  {datetime.now().strftime('%d/%m/%Y')}",
                color=TXT_HEADER, fontsize=8, va="center", alpha=0.75)


    # ── KPIs (3 tarjetas) ─────────────────────────────────────────────────
    ultimo = datos[-1] if datos else ("—", 0)
    penultimo = datos[-2] if len(datos) >= 2 else None
    variacion = ((ultimo[1] - penultimo[1]) / abs(penultimo[1]) * 100) if penultimo and penultimo[1] != 0 else 0
    maximo = max(valores) if valores else 0
    minimo = min(valores) if valores else 0
    media = sum(valores) / len(valores) if valores else 0

    kpis = [
        ("Ultimo valor\n(" + ultimo[0] + ")", f"{ultimo[1]:.2f}", f"{variacion:+.1f}% vs anterior",
         COLOR_ACC if variacion >= 0 else "#ef4444"),
        ("Maximo\ndel periodo", f"{maximo:.2f}", "Periodo: " + (fechas[valores.index(maximo)] if valores else "-"), TXT_SUB),
        ("Media\ndel periodo", f"{media:.2f}", eje_y, TXT_SUB),
    ]

    for col_i, (titulo, valor, subtitulo, col_sub) in enumerate(kpis):
        ax_k = fig.add_subplot(gs[1, col_i])
        ax_k.set_facecolor(BG_CARD)
        ax_k.set_xlim(0, 1); ax_k.set_ylim(0, 1)
        ax_k.axis("off")
        # Borde
        for spine_pos in ['top','bottom','left','right']:
            ax_k.spines[spine_pos].set_visible(True)
            ax_k.spines[spine_pos].set_color(BORDER_COL)
            ax_k.spines[spine_pos].set_linewidth(0.8)
        ax_k.set_frame_on(True)
        # Línea color arriba
        ax_k.add_patch(mpatches.FancyBboxPatch((0, 0.93), 1, 0.07,
            boxstyle="square,pad=0", facecolor=COLOR_LINE, linewidth=0))
        ax_k.text(0.5, 0.78, titulo, color=TXT_SUB, fontsize=8,
                  ha="center", va="center", linespacing=1.4)
        ax_k.text(0.5, 0.48, valor, color=TXT_CARD, fontsize=22,
                  fontweight="bold", ha="center", va="center")
        ax_k.text(0.5, 0.18, subtitulo, color=col_sub, fontsize=8,
                  ha="center", va="center")

    # ── Gráfico principal ─────────────────────────────────────────────────
    ax_chart = fig.add_subplot(gs[1, 3])
    ax_chart.set_facecolor(BG_CHART)

    n_pts = len(fechas)
    if tipo_g == "bar":
        bars = ax_chart.bar(range(n_pts), valores, color=COLOR_BAR, alpha=0.85,
                            width=0.6, zorder=3)
        # Último bar destacado
        if bars:
            bars[-1].set_facecolor(COLOR_ACC)
        ax_chart.set_xticks(range(n_pts))
        ax_chart.set_xticklabels(fechas, rotation=45, ha="right",
                                  fontsize=8, color=TXT_AXIS)
    else:
        ax_chart.plot(range(n_pts), valores, color=COLOR_LINE,
                      linewidth=2.5, zorder=3, marker="o", markersize=4)
        ax_chart.fill_between(range(n_pts), valores, alpha=0.12, color=COLOR_LINE)
        # Último punto destacado
        if valores:
            ax_chart.scatter([n_pts-1], [valores[-1]], color=COLOR_ACC,
                             s=80, zorder=5)
            ax_chart.annotate(f"{valores[-1]:.2f}",
                              xy=(n_pts-1, valores[-1]),
                              xytext=(n_pts-1, valores[-1] + (max(valores)-min(valores))*0.08 + 0.01),
                              fontsize=9, fontweight="bold", color=COLOR_ACC, ha="center")
        step = max(1, n_pts // 8)
        ax_chart.set_xticks(range(0, n_pts, step))
        ax_chart.set_xticklabels([fechas[i] for i in range(0, n_pts, step)],
                                  rotation=45, ha="right", fontsize=8, color=TXT_AXIS)

    ax_chart.set_ylabel(eje_y, fontsize=9, color=TXT_AXIS)
    ax_chart.tick_params(axis="y", labelcolor=TXT_AXIS, labelsize=8)
    ax_chart.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax_chart.spines["top"].set_visible(False)
    ax_chart.spines["right"].set_visible(False)
    ax_chart.spines["left"].set_color(BORDER_COL)
    ax_chart.spines["bottom"].set_color(BORDER_COL)
    ax_chart.grid(axis="y", color=GRID_COL, linewidth=0.6, zorder=0)

    # ── Footer ────────────────────────────────────────────────────────────
    ax_foot = fig.add_subplot(gs[2, :])
    ax_foot.set_facecolor(BG_OUTER)
    ax_foot.axis("off")
    ax_foot.set_xlim(0, 1); ax_foot.set_ylim(0, 1)
    ax_foot.text(0.5, 0.5, LOGO_TXT, color=TXT_AXIS, fontsize=8,
                 ha="center", va="center", style="italic")

    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()

def buscar_noticia_indicador(cfg):
    """Busca en NewsAPI la noticia mas reciente relacionada con el indicador.
    Devuelve dict con titulo, resumen, fuente, url, fecha o None si no encuentra nada."""
    QUERIES_INDICADOR = {
        "Tipo de interes BCE": '"BCE" OR "banco central europeo" OR "tipo de interes" OR "tipos BCE"',
        "IPC": '"IPC" OR "inflacion España" OR "precios consumo" OR "INE inflacion"',
        "PIB": '"PIB España" OR "producto interior bruto" OR "crecimiento economico España"',
        "paro": '"paro España" OR "desempleo España" OR "EPA" OR "tasa desempleo"',
        "Euribor": '"Euribor" OR "tipo hipoteca" OR "interes hipotecario"',
        "IA": '"inteligencia artificial empresa" OR "IA empresas" OR "adopcion IA"',
        "cloud": '"cloud computing empresa" OR "nube empresas España" OR "computacion nube"',
        "Big Data": '"big data empresa" OR "analisis datos empresa" OR "datos masivos"',
        "automatizacion": '"automatizacion empleo" OR "robots trabajo" OR "IA empleo"',
    }
    nombre = cfg.get("nombre", "")
    query = None
    for kw, q in QUERIES_INDICADOR.items():
        if kw.lower() in nombre.lower():
            query = q
            break
    if not query:
        fuente = cfg.get("fuente", "")
        query = '"' + nombre[:40] + '"'
    try:
        desde = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "es",
                "sortBy": "publishedAt",
                "pageSize": 5,
                "from": desde,
                "apiKey": NEWSAPI_KEY,
            },
            timeout=10
        )
        if r.status_code != 200:
            return None
        arts = r.json().get("articles", [])
        for a in arts:
            titulo = a.get("title", "") or ""
            resumen = a.get("description", "") or a.get("content", "") or ""
            url = a.get("url", "")
            if not titulo or not url or len(resumen) < 40: continue
            palabras_ingles = ["the ", "this ", "that ", "with ", "from ", "have "]
            texto_lower = (titulo + " " + resumen).lower()
            if sum(1 for p in palabras_ingles if p in texto_lower) >= 3: continue
            try:
                published = datetime.fromisoformat(a.get("publishedAt", "").replace("Z", ""))
            except Exception:
                published = datetime.now()
            return {
                "titulo": titulo[:200],
                "resumen": resumen[:400],
                "fuente": a.get("source", {}).get("name", "NewsAPI"),
                "url": url,
                "fecha": published.strftime("%d/%m/%Y"),
            }
    except Exception:
        pass
    return None

def actualizar_dato_indicador(cfg, noticia):
    """Usa Gemini para extraer el valor mas reciente del indicador desde una noticia.
    Devuelve (periodo, valor) o None si no puede extraer."""
    if not noticia:
        return None
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Eres un extractor de datos economicos. Lee el siguiente titular y resumen de noticia
y extrae el valor numerico mas reciente del indicador indicado.

INDICADOR: {cfg.get('nombre','')}
UNIDAD: {cfg.get('eje_y','')}
TITULAR: {noticia.get('titulo','')}
RESUMEN: {noticia.get('resumen','')}
FECHA NOTICIA: {noticia.get('fecha','')}

Devuelve SOLO un JSON valido sin markdown:
{{"periodo": "ej: Mar-25 o T1-25 o 2025", "valor": 3.5, "encontrado": true}}
Si no encuentras un valor numerico claro, devuelve: {{"periodo": "", "valor": 0, "encontrado": false}}"""
    try:
        raw = client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()
        result = json.loads(raw.replace("```json","").replace("```","").strip())
        if result.get("encontrado") and result.get("periodo") and result.get("valor") != 0:
            return (result["periodo"], float(result["valor"]))
    except Exception:
        pass
    return None

def generar_post_desde_datos(datos, cfg, tono, tipo_sector, noticia_relacionada=None):
    client = genai.Client(api_key=GEMINI_API_KEY)
    instruccion_tono = TONOS.get(tono, TONOS["aprendiendo"])["instruccion"]
    if datos:
        ultimos = datos[-8:]
        resumen_datos = ", ".join([f"{f}: {v:.2f}" for f, v in ultimos])
        tendencia = "alcista" if len(datos) >= 2 and datos[-1][1] > datos[-2][1] else "bajista" if len(datos) >= 2 and datos[-1][1] < datos[-2][1] else "estable"
        ultimo_valor = f"{datos[-1][1]:.2f}"
        ultima_fecha = datos[-1][0]
    else:
        resumen_datos = "datos no disponibles"
        tendencia = "incierta"
        ultimo_valor = "N/D"
        ultima_fecha = "reciente"
    sector_label = "macroeconomia y finanzas" if tipo_sector == "macro" else "tecnologia e inteligencia artificial empresarial"

    bloque_noticia = ""
    if noticia_relacionada:
        bloque_noticia = f"""
NOTICIA DE ACTUALIDAD RELACIONADA (usar como contexto adicional):
Titular: {noticia_relacionada.get('titulo','')}
Fuente: {noticia_relacionada.get('fuente','')} · {noticia_relacionada.get('fecha','')}
Resumen: {noticia_relacionada.get('resumen','')}

INSTRUCCION EXTRA: Conecta los datos historicos del grafico con esta noticia de actualidad.
Menciona el titular o el hecho reciente en el cuerpo del post para dar contexto de hoy.
"""

    prompt = f"""Escribe un post de LinkedIn basado en datos reales de {sector_label}.

INDICADOR: {cfg.get('nombre','')}
DESCRIPCION: {cfg.get('descripcion','')}
FUENTE: {cfg.get('fuente','')}
ULTIMO VALOR: {ultimo_valor} ({ultima_fecha})
TENDENCIA: {tendencia}
EVOLUCION RECIENTE: {resumen_datos}
{bloque_noticia}
TONO: {instruccion_tono}

REGLAS ESTRICTAS:
1. Empieza con el dato mas llamativo o la tendencia mas relevante como gancho.
2. Analiza que significa este dato para las empresas, el empleo o la economia espanola.
3. Incluye 2-3 insights concretos basados en la tendencia.
4. Incluye una reflexion de futuro: que puede pasar en los proximos 6-12 meses?
5. Cierra con una pregunta provocadora sobre el impacto real del indicador.
6. Maximo 2 emojis, parrafos cortos (max 3 lineas), doble salto entre parrafos.
7. Post en ESPANOL, 150-250 palabras. 5-8 hashtags al final.
8. NO menciones que eres IA, estudiante, ni ningun rol o titulo academico.
9. Presenta el dato como si tu mismo lo hubieras analizado.

Devuelve SOLO el texto del post."""
    return client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()


# ── Funciones IBEX 35 ─────────────────────────────────────────────────────────

def buscar_resultados_empresa(empresa_key):
    """Busca resultados financieros via Google News RSS (principal) + CNMV + NewsAPI."""
    cfg = EMPRESAS_IBEX.get(empresa_key, {})
    ticker = cfg.get("ticker", "")
    anio_actual = datetime.now().year
    resultados = []
    nombre_lower = empresa_key.lower()
    ticker_lower = ticker.lower()
    hace_365 = datetime.now() - timedelta(days=365)

    # 1. Google News RSS — sin limitaciones, indexa prensa española en tiempo real
    # Varias queries para maximizar cobertura
    google_queries = [
        f"{empresa_key} resultados financieros {anio_actual}",
        f"{empresa_key} beneficio neto {anio_actual}",
        f"{empresa_key} resultados anuales {anio_actual - 1}",
        f"{empresa_key} ganancias trimestre {anio_actual}",
        f"{empresa_key} EBITDA ingresos {anio_actual - 1}",
    ]
    for q in google_queries:
        try:
            import urllib.parse
            q_enc = urllib.parse.quote(q)
            url_gnews = f"https://news.google.com/rss/search?q={q_enc}&hl=es&gl=ES&ceid=ES:es"
            feed = feedparser.parse(url_gnews)
            for entry in feed.entries[:10]:
                titulo = entry.get("title", "") or ""
                resumen = entry.get("summary", entry.get("description", ""))[:500] or ""
                url_art = entry.get("link", "")
                if not titulo or not url_art: continue
                try:
                    pub = datetime(*entry.published_parsed[:6]) if hasattr(entry,"published_parsed") and entry.published_parsed else datetime.now()
                except Exception:
                    pub = datetime.now()
                if pub < hace_365: continue
                # Limpiar HTML del resumen de Google News
                resumen_limpio = re.sub(r'<[^>]+>', '', resumen).strip()[:500]
                resultados.append({
                    "titulo": titulo[:200],
                    "resumen": resumen_limpio if len(resumen_limpio) > 30 else titulo,
                    "fuente": "Google News",
                    "url": url_art,
                    "fecha": pub.strftime("%d/%m/%Y"),
                    "_ts": pub,
                })
        except Exception:
            pass

    # 2. CNMV RSS — hechos relevantes oficiales (siempre intentar)
    try:
        feed = feedparser.parse("https://www.cnmv.es/portal/HR/RSSHechosRelevantes.ashx")
        for entry in feed.entries[:60]:
            titulo = entry.get("title", "") or ""
            if nombre_lower not in titulo.lower() and ticker_lower not in titulo.lower():
                continue
            resumen = entry.get("summary", entry.get("description", ""))[:500]
            url_art = entry.get("link", "")
            try:
                pub = datetime(*entry.published_parsed[:6]) if hasattr(entry,"published_parsed") and entry.published_parsed else datetime.now()
            except Exception:
                pub = datetime.now()
            resultados.append({
                "titulo": titulo[:200], "resumen": resumen,
                "fuente": "CNMV · Hechos Relevantes",
                "url": url_art, "fecha": pub.strftime("%d/%m/%Y"),
                "_ts": pub,
            })
    except Exception:
        pass

    # 3. RSS prensa financiera — búsqueda por nombre en titulares recientes
    RSS_FINANCIERO = [
        ("Expansión",   "https://e00-expansion.uecdn.es/rss/empresas.xml"),
        ("El Economista","https://www.eleconomista.es/rss/rss-empresas.php"),
        ("Cinco Días",  "https://cincodias.elpais.com/rss/cincodias/ultimas_noticias/"),
    ]
    keywords_res = ["resultado", "beneficio", "ganancia", "ventas", "trimestre", "ebitda", "ingreso", "facturación"]
    for fuente, url_rss in RSS_FINANCIERO:
        try:
            feed = feedparser.parse(url_rss)
            for entry in feed.entries[:30]:
                titulo = entry.get("title", "") or ""
                resumen = entry.get("summary", entry.get("description", ""))[:500] or ""
                t_lower = titulo.lower()
                if nombre_lower not in t_lower and ticker_lower not in t_lower:
                    continue
                # Relajar filtro: basta con que mencione la empresa
                url_art = entry.get("link", "")
                try:
                    pub = datetime(*entry.published_parsed[:6]) if hasattr(entry,"published_parsed") and entry.published_parsed else datetime.now()
                except Exception:
                    pub = datetime.now()
                resultados.append({
                    "titulo": titulo[:200], "resumen": resumen,
                    "fuente": fuente, "url": url_art,
                    "fecha": pub.strftime("%d/%m/%Y"),
                    "_ts": pub,
                })
        except Exception:
            pass

    # 4. NewsAPI — query simple, sin fecha para maximizar resultados en plan free
    try:
        query_simple = f"{empresa_key} resultados beneficio"
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query_simple, "language": "es", "sortBy": "publishedAt",
                    "pageSize": 10, "apiKey": NEWSAPI_KEY},
            timeout=10
        )
        if r.status_code == 200:
            for a in r.json().get("articles", []):
                titulo = a.get("title", "") or ""
                resumen = a.get("description", "") or a.get("content", "") or ""
                url_art = a.get("url", "")
                if not titulo or not url_art or len(resumen) < 30: continue
                palabras_en = ["the ", "this ", "with ", "from ", "have "]
                if sum(1 for p in palabras_en if p in (titulo + resumen).lower()) >= 3: continue
                try:
                    pub = datetime.fromisoformat(a.get("publishedAt","").replace("Z",""))
                except Exception:
                    pub = datetime.now()
                resultados.append({
                    "titulo": titulo[:200], "resumen": resumen[:500],
                    "fuente": a.get("source",{}).get("name","NewsAPI"),
                    "url": url_art, "fecha": pub.strftime("%d/%m/%Y"),
                    "_ts": pub,
                })
    except Exception:
        pass

    # Ordenar por fecha descendente, deduplicar por URL
    vistos = set()
    unicos = []
    for item in sorted(resultados, key=lambda x: x.get("_ts", datetime.now()), reverse=True):
        if item["url"] not in vistos:
            vistos.add(item["url"])
            item.pop("_ts", None)
            unicos.append(item)
    return unicos[:8]


def extraer_kpis_empresa(empresa_key, noticias):
    """Usa Gemini para extraer KPIs financieros de las noticias recientes."""
    if not noticias:
        return None
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = EMPRESAS_IBEX.get(empresa_key, {})
    partes = []
    for n in noticias[:4]:
        partes.append("TITULAR: " + n["titulo"] + " | FECHA: " + n["fecha"] + " | RESUMEN: " + n["resumen"])
    textos = " --- ".join(partes)
    prompt = f"""Eres un analista financiero experto en empresas del IBEX 35.
Lee estas noticias sobre {empresa_key} ({cfg.get('sector','')}) y extrae los KPIs financieros mas recientes.

NOTICIAS:
{textos}

Devuelve SOLO un JSON valido sin markdown con este formato exacto:
{{
  "periodo": "ej: T4-2024 o 2024 o H1-2025",
  "encontrado": true,
  "kpis": [
    {{"nombre": "Beneficio neto", "valor": 1234, "unidad": "M EUR", "variacion_pct": 12.5}},
    {{"nombre": "Ingresos", "valor": 5678, "unidad": "M EUR", "variacion_pct": 8.2}},
    {{"nombre": "EBITDA", "valor": 2345, "unidad": "M EUR", "variacion_pct": 5.1}}
  ],
  "resumen_ejecutivo": "2-3 frases sobre los resultados",
  "noticia_principal": "{noticias[0]['titulo'][:120] if noticias else ''}",
  "fuente_principal": "{noticias[0]['fuente'] if noticias else ''}",
  "fecha_noticia": "{noticias[0]['fecha'] if noticias else ''}"
}}
Si no encuentras datos financieros concretos, devuelve {{"encontrado": false}}"""
    try:
        raw = client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()
        result = json.loads(raw.replace("```json","").replace("```","").strip())
        if result.get("encontrado"):
            return result
    except Exception:
        pass

    # Fallback: construir KPIs desde historico hardcodeado si Gemini no extrae nada
    cfg_emp = EMPRESAS_IBEX.get(empresa_key, {})
    historico = cfg_emp.get("historico", {})
    if historico:
        kpis_fallback = []
        for nombre_k, datos_k in historico.items():
            if not datos_k: continue
            ult = datos_k[-1]
            pen = datos_k[-2] if len(datos_k) >= 2 else None
            var = ((ult[1] - pen[1]) / abs(pen[1]) * 100) if pen and pen[1] != 0 else 0
            es_pct = "%" in nombre_k
            unidad = "%" if es_pct else "M EUR"
            kpis_fallback.append({
                "nombre": nombre_k.split("(")[0].strip(),
                "valor": ult[1],
                "unidad": unidad,
                "variacion_pct": round(var, 1),
            })
        periodo_fb = datos_k[-1][0] if datos_k else str(datetime.now().year - 1)
        noticia_titulo = noticias[0]["titulo"] if noticias else ""
        noticia_fuente = noticias[0]["fuente"] if noticias else "Datos históricos"
        noticia_fecha  = noticias[0]["fecha"]  if noticias else datetime.now().strftime("%d/%m/%Y")
        return {
            "periodo": periodo_fb,
            "encontrado": True,
            "kpis": kpis_fallback[:3],
            "resumen_ejecutivo": f"Datos históricos de {empresa_key}. Último periodo disponible: {periodo_fb}. Los KPIs muestran la evolución publicada en informes oficiales.",
            "noticia_principal": noticia_titulo[:120],
            "fuente_principal": noticia_fuente,
            "fecha_noticia": noticia_fecha,
        }
    return None


def generar_dashboard_empresa_png(empresa_key, kpi_data, historico_key, estilo="powerbi"):
    """Dashboard adaptativo: todos los KPIs historicos juntos en el grafico."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.ticker as mticker
    import numpy as np
    import io as _io

    cfg = EMPRESAS_IBEX.get(empresa_key, {})
    historico = cfg.get("historico", {})

    if estilo == "powerbi":
        BG_OUTER = "#F3F2F1"; BG_HEADER = "#243A5E"; BG_CARD = "#FFFFFF"
        BG_CHART = "#FFFFFF"; TXT_HEADER = "#FFFFFF"; TXT_CARD = "#252423"
        TXT_SUB = "#605E5C"; TXT_AXIS = "#605E5C"; GRID_COL = "#E8E6E3"
        BORDER_COL = "#D2D0CE"; COLOR_LINE = "#118DFF"; COLOR_ACC = "#F2C811"
        PALETA = ["#118DFF", "#F2C811", "#E66C37", "#43A047", "#8B5CF6"]
    else:
        BG_OUTER = "#0a0a0f"; BG_HEADER = "#13131a"; BG_CARD = "#1c1c2e"
        BG_CHART = "#13131a"; TXT_HEADER = "#f0f0f8"; TXT_CARD = "#f0f0f8"
        TXT_SUB = "#a78bfa"; TXT_AXIS = "#7070a0"; GRID_COL = "#2a2a4a"
        BORDER_COL = "#2a2a4a"; COLOR_LINE = "#6c63ff"; COLOR_ACC = "#fbbf24"
        PALETA = ["#6c63ff", "#fbbf24", "#4ade80", "#f87171", "#a78bfa"]

    # ── Analizar KPIs: separar los que tienen escala M EUR de los que son % ──
    kpis_eur = {}   # nombre -> lista de (periodo, valor)
    kpis_pct = {}   # nombre -> lista de (periodo, valor)
    for nombre_k, datos_k in historico.items():
        if "%" in nombre_k:
            kpis_pct[nombre_k] = datos_k
        else:
            kpis_eur[nombre_k] = datos_k

    # Periodos comunes (unión de todos)
    todos_periodos = []
    for datos_k in list(kpis_eur.values()) + list(kpis_pct.values()):
        for p, _ in datos_k:
            if p not in todos_periodos:
                todos_periodos.append(p)

    # ── Layout ──
    fig = plt.figure(figsize=(12, 7), facecolor=BG_OUTER)
    gs = fig.add_gridspec(3, 4, height_ratios=[0.12, 0.72, 0.08],
                          width_ratios=[1, 1, 1, 3], hspace=0.18, wspace=0.3,
                          left=0.04, right=0.97, top=0.96, bottom=0.04)

    # Cabecera
    ax_hdr = fig.add_subplot(gs[0, :])
    ax_hdr.set_facecolor(BG_HEADER); ax_hdr.set_xlim(0,1); ax_hdr.set_ylim(0,1); ax_hdr.axis("off")
    ax_hdr.text(0.02, 0.55, cfg.get("emoji","") + " " + empresa_key + " — " + cfg.get("sector",""),
                color=TXT_HEADER, fontsize=13, fontweight="bold", va="center")
    periodo_txt = kpi_data.get("periodo","") if kpi_data else todos_periodos[-1] if todos_periodos else ""
    ax_hdr.text(0.02, 0.15, f"Resultados {periodo_txt}  ·  Fuente: CNMV / Prensa  ·  {datetime.now().strftime('%d/%m/%Y')}",
                color=TXT_HEADER, fontsize=8, va="center", alpha=0.75)

    # ── 3 tarjetas KPI — ultimo valor de cada indicador historico ──
    todos_kpis = list(kpis_eur.items()) + list(kpis_pct.items())
    for col_i in range(3):
        ax_k = fig.add_subplot(gs[1, col_i])
        ax_k.set_facecolor(BG_CARD); ax_k.set_xlim(0,1); ax_k.set_ylim(0,1); ax_k.axis("off")
        for sp in ['top','bottom','left','right']:
            ax_k.spines[sp].set_visible(True); ax_k.spines[sp].set_color(BORDER_COL)
            ax_k.spines[sp].set_linewidth(0.8)
        ax_k.set_frame_on(True)
        color_card = PALETA[col_i % len(PALETA)]
        ax_k.add_patch(mpatches.FancyBboxPatch((0, 0.93), 1, 0.07,
            boxstyle="square,pad=0", facecolor=color_card, linewidth=0))
        if col_i < len(todos_kpis):
            nombre_k, datos_k = todos_kpis[col_i]
            ult = datos_k[-1] if datos_k else ("", 0)
            pen = datos_k[-2] if len(datos_k) >= 2 else None
            var = ((ult[1] - pen[1]) / abs(pen[1]) * 100) if pen and pen[1] != 0 else 0
            col_var = COLOR_ACC if var >= 0 else "#ef4444"
            es_pct = "%" in nombre_k
            val_str = f"{ult[1]:.1f}%" if es_pct else f"{ult[1]:,.0f}".replace(",",".")
            titulo_corto = nombre_k.split("(")[0].strip()[:20]
            ax_k.text(0.5, 0.78, titulo_corto, color=TXT_SUB, fontsize=7,
                      ha="center", va="center", linespacing=1.3)
            ax_k.text(0.5, 0.50, val_str, color=TXT_CARD, fontsize=18,
                      fontweight="bold", ha="center", va="center")
            ax_k.text(0.5, 0.22, f"{var:+.1f}% · {ult[0]}", color=col_var,
                      fontsize=7, ha="center", va="center")
        else:
            ax_k.text(0.5, 0.50, "—", color=TXT_SUB, fontsize=14, ha="center", va="center")

    # ── Grafico principal — adaptativo ──
    ax_chart = fig.add_subplot(gs[1, 3])
    ax_chart.set_facecolor(BG_CHART)

    n_periodos = len(todos_periodos)

    if kpis_eur and len(kpis_pct) == 0:
        # Solo KPIs en M EUR → barras agrupadas
        n_grupos = len(kpis_eur)
        ancho = 0.7 / n_grupos
        for gi, (nombre_k, datos_k) in enumerate(kpis_eur.items()):
            vals = []
            for p in todos_periodos:
                v = next((d[1] for d in datos_k if d[0] == p), 0)
                vals.append(v)
            offset = (gi - n_grupos/2 + 0.5) * ancho
            bars = ax_chart.bar([x + offset for x in range(n_periodos)], vals,
                                width=ancho * 0.9, color=PALETA[gi % len(PALETA)],
                                alpha=0.85, label=nombre_k.split("(")[0].strip(), zorder=3)
        ax_chart.set_ylabel("M EUR", fontsize=8, color=TXT_AXIS)
        ax_chart.legend(fontsize=7, loc="upper left",
                        facecolor=BG_CARD, edgecolor=BORDER_COL, labelcolor=TXT_AXIS)

    elif kpis_eur and kpis_pct:
        # KPIs mixtos → eje doble: barras para M EUR, línea para %
        ax2 = ax_chart.twinx()
        for gi, (nombre_k, datos_k) in enumerate(kpis_eur.items()):
            vals = [next((d[1] for d in datos_k if d[0] == p), 0) for p in todos_periodos]
            n_eur = len(kpis_eur)
            ancho = 0.6 / n_eur
            offset = (gi - n_eur/2 + 0.5) * ancho
            ax_chart.bar([x + offset for x in range(n_periodos)], vals,
                         width=ancho*0.9, color=PALETA[gi % len(PALETA)],
                         alpha=0.75, label=nombre_k.split("(")[0].strip(), zorder=3)
        for gi, (nombre_k, datos_k) in enumerate(kpis_pct.items()):
            vals = [next((d[1] for d in datos_k if d[0] == p), None) for p in todos_periodos]
            xs = [i for i, v in enumerate(vals) if v is not None]
            ys = [v for v in vals if v is not None]
            ax2.plot(xs, ys, color=PALETA[(len(kpis_eur)+gi) % len(PALETA)],
                     linewidth=2, marker="o", markersize=5,
                     label=nombre_k.split("(")[0].strip(), zorder=5)
        ax_chart.set_ylabel("M EUR", fontsize=8, color=TXT_AXIS)
        ax2.set_ylabel("%", fontsize=8, color=TXT_AXIS)
        ax2.tick_params(axis="y", labelcolor=TXT_AXIS, labelsize=7)
        ax2.spines["right"].set_color(BORDER_COL)
        # Leyenda combinada
        lines1, labels1 = ax_chart.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax_chart.legend(lines1+lines2, labels1+labels2, fontsize=6, loc="upper left",
                        facecolor=BG_CARD, edgecolor=BORDER_COL, labelcolor=TXT_AXIS)
    else:
        # Solo ratios % → líneas
        for gi, (nombre_k, datos_k) in enumerate(kpis_pct.items()):
            vals = [next((d[1] for d in datos_k if d[0] == p), None) for p in todos_periodos]
            xs = [i for i, v in enumerate(vals) if v is not None]
            ys = [v for v in vals if v is not None]
            ax_chart.plot(xs, ys, color=PALETA[gi % len(PALETA)],
                          linewidth=2.5, marker="o", markersize=5,
                          label=nombre_k.split("(")[0].strip(), zorder=3)
        ax_chart.set_ylabel("%", fontsize=8, color=TXT_AXIS)
        ax_chart.legend(fontsize=7, loc="upper left",
                        facecolor=BG_CARD, edgecolor=BORDER_COL, labelcolor=TXT_AXIS)

    ax_chart.set_xticks(range(n_periodos))
    ax_chart.set_xticklabels(todos_periodos, rotation=25, ha="right", fontsize=8, color=TXT_AXIS)
    ax_chart.tick_params(axis="y", labelcolor=TXT_AXIS, labelsize=8)
    ax_chart.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",",".")))
    ax_chart.spines["top"].set_visible(False); ax_chart.spines["right"].set_visible(False)
    ax_chart.spines["left"].set_color(BORDER_COL); ax_chart.spines["bottom"].set_color(BORDER_COL)
    ax_chart.grid(axis="y", color=GRID_COL, linewidth=0.6, zorder=0)

    # Footer
    ax_foot = fig.add_subplot(gs[2, :])
    ax_foot.set_facecolor(BG_OUTER); ax_foot.axis("off")

    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generar_post_empresa(empresa_key, kpi_data, historico_key, tono):
    """Genera post LinkedIn sobre resultados de empresa IBEX."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    instruccion_tono = TONOS.get(tono, TONOS["aprendiendo"])["instruccion"]
    cfg = EMPRESAS_IBEX.get(empresa_key, {})
    historico = cfg.get("historico", {})
    datos_hist = historico.get(historico_key, [])

    resumen_hist = ""
    if datos_hist:
        resumen_hist = ", ".join([f"{f}: {v:,.0f}".replace(",",".") for f, v in datos_hist])

    kpis_txt = ""
    kpis_txt = ""
    if kpi_data and kpi_data.get("kpis"):
        partes_k = []
        for k in kpi_data["kpis"]:
            var_k = k.get("variacion_pct", 0) or 0
            linea = "- " + k["nombre"] + ": " + f"{k['valor']:,.0f}".replace(",",".") + " " + k.get("unidad","") + " (" + f"{var_k:+.1f}" + "%)"
            partes_k.append(linea)
        kpis_txt = " | ".join(partes_k)

    periodo = kpi_data.get("periodo", "2024") if kpi_data else "2024"
    resumen_ej = kpi_data.get("resumen_ejecutivo", "") if kpi_data else ""
    noticia_p = kpi_data.get("noticia_principal", "") if kpi_data else ""

    prompt = f"""Escribe un post de LinkedIn sobre los resultados financieros de {empresa_key}.

EMPRESA: {empresa_key} ({cfg.get('emoji','')} {cfg.get('sector','')})
PERIODO: {periodo}
KPIS RECIENTES:
{kpis_txt if kpis_txt else "Datos no disponibles"}
HISTORICO {historico_key}: {resumen_hist}
CONTEXTO: {resumen_ej}
NOTICIA CLAVE: {noticia_p}

TONO: {instruccion_tono}

REGLAS:
1. Gancho con el dato mas impactante (beneficio, crecimiento o tendencia).
2. Analiza que significan estos resultados para el sector y la economia espanola.
3. Compara con el historico si hay tendencia clara.
4. Reflexion sobre los proximos 6-12 meses.
5. Pregunta provocadora al final.
6. Max 2 emojis, parrafos cortos, doble salto entre parrafos.
7. ESPANOL, 150-250 palabras, 5-8 hashtags al final.
8. NO menciones que eres IA, estudiante, ni titulo academico.

Devuelve SOLO el texto del post."""
    return client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()

# ── Carrusel PDF vertical ─────────────────────────────────────────────────────
def crear_carrusel_pdf(contenido: dict) -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib import colors
    import io

    W, H = 540, 675
    BG   = colors.HexColor("#0a0a0f")
    CARD = colors.HexColor("#1c1c2e")
    PUR  = colors.HexColor("#6c63ff")
    PURT = colors.HexColor("#a78bfa")
    TXT  = colors.HexColor("#f0f0f8")
    MUT  = colors.HexColor("#7070a0")
    WHT  = colors.HexColor("#ffffff")
    AMB  = colors.HexColor("#fbbf24")

    def wrap(c, text, font, size, max_w):
        words = (text or "").split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            if c.stringWidth(test, font, size) <= max_w:
                cur.append(w)
            else:
                if cur: lines.append(" ".join(cur))
                cur = [w]
        if cur: lines.append(" ".join(cur))
        return lines

    def base(c, num, total):
        c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(MUT); c.setFont("Helvetica", 7)
        c.drawRightString(W - 12, 10, f"{num} / {total}")

    def draw_portada(c, data, total):
        base(c, 1, total)
        MARGIN = 24
        c.setFillColor(colors.HexColor("#0e0e22"))
        c.rect(0, MARGIN, W, H - MARGIN, fill=1, stroke=0)
        c.setFillColor(PUR); c.rect(0, MARGIN, 5, H - MARGIN, fill=1, stroke=0)
        c.setFillColor(PUR); c.setFillAlpha(0.13)
        c.circle(W + 10, H, 160, fill=1, stroke=0)
        c.setFillAlpha(1.0)
        sector_txt = data.get("sector","").replace("🏦","").replace("♟️","").replace("📊","").replace("🤖","").strip().upper()
        for font_size in [30, 26, 22]:
            t_lines = wrap(c, data.get("titulo_portada",""), "Helvetica-Bold", font_size, W * 0.82)
            if len(t_lines) <= 3: break
        line_h = font_size + 10
        sub_lines = wrap(c, data.get("subtitulo_portada",""), "Helvetica", 13, W * 0.82)[:3]
        badge_h = 18
        total_h = badge_h + 16 + len(t_lines)*line_h + 18 + len(sub_lines)*20
        box_h = H - MARGIN * 2
        start_y = MARGIN + (box_h + total_h) / 2
        bw = max(100, c.stringWidth(sector_txt, "Helvetica-Bold", 7) + 24)
        c.setFillColor(colors.HexColor("#1a1830"))
        c.roundRect(18, start_y, bw, badge_h, 9, fill=1, stroke=0)
        c.setStrokeColor(PUR); c.setLineWidth(0.6)
        c.roundRect(18, start_y, bw, badge_h, 9, fill=0, stroke=1)
        c.setFillColor(PURT); c.setFont("Helvetica-Bold", 7)
        c.drawString(28, start_y + 6, sector_txt)
        c.setFillColor(TXT); y = start_y - 36
        for line in t_lines:
            c.setFont("Helvetica-Bold", font_size); c.drawString(18, y, line); y -= line_h
        c.setFillColor(MUT); ys = y - 10
        for sl in sub_lines:
            c.setFont("Helvetica", 13); c.drawString(18, ys, sl); ys -= 20
        c.setFillColor(MUT); c.setFont("Helvetica", 8)
        c.drawString(18, MARGIN + 10, "Julen · Business & Data Analytics · MSc Big Data & IA")
        c.showPage()

    def draw_contenido(c, slide, idx, total):
        base(c, idx + 2, total)
        c.setFillColor(PUR); c.rect(0, H - 4, W, 4, fill=1, stroke=0)
        c.setFillColor(PUR); c.circle(28, H - 32, 17, fill=1, stroke=0)
        c.setFillColor(WHT); c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(28, H - 37, str(idx + 1))
        c.setFillColor(TXT); c.setFont("Helvetica-Bold", 18)
        titulo = slide.get("titulo","")[:40]
        c.drawString(52, H - 40, titulo)
        c.setStrokeColor(colors.HexColor("#2a2a3e")); c.setLineWidth(1)
        c.line(12, H - 56, W - 12, H - 56)
        cuerpo = slide.get("cuerpo","")
        dato = slide.get("dato_destacado")
        MARGIN_BOTTOM = 24
        if dato:
            cuerpo_lines = wrap(c, cuerpo, "Helvetica", 13, W - 28)
            c.setFillColor(TXT); y = H - 76
            for line in cuerpo_lines[:5]:
                c.setFont("Helvetica", 13); c.drawString(14, y, line); y -= 20
            bh = 160; by = MARGIN_BOTTOM; bx = 14; bw2 = W - 28
            c.setFillColor(CARD); c.roundRect(bx, by, bw2, bh, 8, fill=1, stroke=0)
            c.setStrokeColor(PUR); c.setLineWidth(1)
            c.roundRect(bx, by, bw2, bh, 8, fill=0, stroke=1)
            c.setFillColor(PUR); c.rect(bx+10, by+bh-4, bw2-20, 4, fill=1, stroke=0)
            dato_lines = wrap(c, dato, "Helvetica-Bold", 16, bw2 - 24)
            total_h_dato = len(dato_lines) * 24
            dy = by + bh/2 + total_h_dato/2 - 4
            c.setFillColor(AMB)
            for dl in dato_lines:
                c.setFont("Helvetica-Bold", 16)
                dw = c.stringWidth(dl, "Helvetica-Bold", 16)
                c.drawString(bx + (bw2 - dw)/2, dy, dl); dy -= 24
        else:
            box_top = H - 64; box_bot = MARGIN_BOTTOM
            box_h = box_top - box_bot; bx = 12; bw2 = W - 24
            c.setFillColor(colors.HexColor("#0e0e22"))
            c.roundRect(bx, box_bot, bw2, box_h, 8, fill=1, stroke=0)
            c.setFillColor(PUR); c.roundRect(bx, box_bot, 5, box_h, 3, fill=1, stroke=0)
            for font_size in [20, 16, 13]:
                lines = wrap(c, cuerpo, "Helvetica-Bold", font_size, bw2 - 36)
                if len(lines) <= 6: break
            line_h = font_size + 8
            text_total_h = len(lines) * line_h
            text_start_y = box_bot + box_h/2 + text_total_h/2 - line_h * 0.3
            c.setFillColor(TXT); y_txt = text_start_y
            for line in lines:
                c.setFont("Helvetica-Bold", font_size)
                c.drawString(bx + 18, y_txt, line); y_txt -= line_h
        c.showPage()

    def draw_cta(c, data, total):
        base(c, total, total)
        c.setFillColor(PUR); c.setFillAlpha(0.10)
        c.circle(W/2, H/2, 200, fill=1, stroke=0)
        c.setFillAlpha(1.0)
        c.setFillColor(PUR); c.rect(0, 0, W, 26, fill=1, stroke=0)
        c.setFillColor(PURT); c.setFont("Helvetica-Bold", 8)
        label = "¿QUÉ OPINAS TÚ?"
        c.drawString((W - c.stringWidth(label,"Helvetica-Bold",8))/2, H - 44, label)
        preg_lines = wrap(c, data.get("pregunta_final",""), "Helvetica-Bold", 20, W - 60)
        c.setFillColor(TXT); y = H - 90
        for line in preg_lines[:4]:
            c.setFont("Helvetica-Bold", 20)
            c.drawString((W - c.stringWidth(line,"Helvetica-Bold",20))/2, y, line); y -= 30
        cta_lines = wrap(c, data.get("cta",""), "Helvetica", 11, W - 60)
        c.setFillColor(MUT); yc = y - 14
        for cl in cta_lines[:2]:
            c.setFont("Helvetica", 11)
            c.drawString((W - c.stringWidth(cl,"Helvetica",11))/2, yc, cl); yc -= 18
        autor = "Julen · Business & Data Analytics · MSc Big Data & IA"
        c.setFillColor(WHT); c.setFont("Helvetica", 8)
        c.drawString((W - c.stringWidth(autor,"Helvetica",8))/2, 9, autor)
        c.showPage()

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))
    slides = contenido.get("slides", [])
    total = len(slides) + 2
    draw_portada(c, contenido, total)
    for idx, s in enumerate(slides):
        draw_contenido(c, s, idx, total)
    draw_cta(c, contenido, total)
    c.save()
    buf.seek(0)
    return buf.read()

def enviar_telegram(texto, noticia):
    separador = "─" * 35
    mensaje = f"""🤖 *Agente LinkedIn — Nuevo post*
{separador}

{texto}

{separador}
📰 *Fuente:* {noticia['fuente']}
🗓 *Fecha:* {noticia['fecha']}
🔗 {noticia['url']}

_Revisa, edita con tu toque personal y publica en LinkedIn_ ✅""".strip()
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown", "disable_web_page_preview": False}
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except Exception:
        return False

def color_barra(val, max_val=10):
    pct = val / max_val
    if pct >= 0.8: return "#4ade80"
    if pct >= 0.6: return "#fbbf24"
    return "#f87171"

def color_total(val):
    if val >= 80: return "#4ade80"
    if val >= 60: return "#fbbf24"
    return "#f87171"

def render_linkedin_preview(post):
    preview = "\n".join(post.split("\n")[:8])
    if len(post.split("\n")) > 8: preview += "\n..."
    preview_safe = preview.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    preview_html = re.sub(r'(#\w+)', r'<span class="li-hashtag">\1</span>', preview_safe)
    st.markdown(f"""
    <div class="li-card">
        <div class="li-header">
            <div class="li-avatar">J</div>
            <div>
                <div class="li-name">Julen</div>
                <div class="li-headline">Business & Data Analytics · MSc Big Data & IA</div>
                <div class="li-time">ahora · 🌐</div>
            </div>
        </div>
        <div class="li-body">{preview_html}</div>
        <div class="li-reactions">
            <span>👍 ❤️ 💡</span>
            <span style="margin-left:8px">Sé el primero en reaccionar</span>
            <span style="margin-left:auto">0 comentarios · 0 reposts</span>
        </div>
    </div>
    <div style="font-size:11px;color:#7070a0;text-align:center;margin-top:-0.5rem">Vista previa aproximada</div>
    """, unsafe_allow_html=True)

def render_puntuacion(score):
    metricas = [("Gancho inicial",score.get("gancho",0)),("Claridad",score.get("claridad",0)),
                ("Valor aportado",score.get("valor",0)),("Potencial engagement",score.get("engagement",0)),
                ("Hashtags",score.get("hashtags",0))]
    total = score.get("total",0); nivel = score.get("nivel",""); feedback = score.get("feedback","")
    ct = color_total(total)
    barras = ""
    for label, val in metricas:
        color = color_barra(val)
        barras += f'<div class="score-row"><div class="score-label">{label}</div><div class="score-bar-bg"><div class="score-bar" style="width:{val*10}%;background:{color}"></div></div><div class="score-num" style="color:{color}">{val}</div></div>'
    st.markdown(f"""
    <div class="score-wrapper">
        <div class="score-title">📊 Puntuación del post</div>
        <div class="score-total" style="color:{ct}">{total}<span style="font-size:16px;color:#7070a0">/100</span></div>
        <div class="score-nivel" style="color:{ct}">{nivel}</div>
        {barras}
        <div class="score-feedback">{feedback}</div>
    </div>""", unsafe_allow_html=True)

def render_opcion(post, label, es_recomendada, razon, key):
    if es_recomendada:
        st.markdown(f'<div class="section-label" style="color:#4ade80">{label}</div><div class="recomendada-badge">✦ Recomendada para esta noticia</div><div class="opcion-card-recomendada">{post}</div>{"<div class=\'razon-badge\'>💡 "+razon+"</div>" if razon else ""}', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="section-label">{label}</div><div class="opcion-card">{post}</div>', unsafe_allow_html=True)
    if st.button("✦  Elegir esta versión", key=key, use_container_width=True):
        st.session_state.post_generado = post
        st.session_state.fase = "post"
        st.rerun()

def render_imagen_noticia(noticia):
    imagen_url = noticia.get("imagen","")
    if not imagen_url: return
    try:
        r = requests.head(imagen_url, timeout=5, allow_redirects=True)
        if r.status_code != 200: return
    except Exception: return
    st.markdown('<div class="section-label">🖼️ Imagen de portada</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="img-wrapper"><img src="{imagen_url}" style="width:100%;display:block;"></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="img-caption">Mantén pulsada la imagen para guardarla (móvil) · <a href="{imagen_url}" target="_blank" style="color:#6c63ff;text-decoration:none">Abrir imagen ↗</a></div>', unsafe_allow_html=True)

def render_historial():
    historial = st.session_state.get("historial",[])
    if not historial:
        st.markdown("<div style='text-align:center;color:#7070a0;font-size:13px;padding:2rem 0'>Aún no has generado ningún post.</div>", unsafe_allow_html=True)
        return
    pill_map = {
        "🏦 Banca":"sector-pill-banca",
        "♟️ Estrategia":"sector-pill-estrategia",
        "📊 Datos & BI":"sector-pill-datos",
        "🤖 Inteligencia Artificial":"sector-pill-ia",
    }
    for h in historial:
        pill = pill_map.get(h["sector"],"source-pill")
        st.markdown(f'<div class="historial-item"><div class="historial-meta"><span class="{pill}">{h["sector"]}</span><span class="source-pill">{h.get("tono","")}</span><span class="historial-fecha">🗓 {h["fecha"]}</span></div><div class="card-title" style="font-size:13px;margin-bottom:4px">{h["titulo"]}</div><div class="historial-preview">{h["preview"]}...</div></div>', unsafe_allow_html=True)

def render_calendario():
    dias_pub = st.session_state.get("dias_publicacion", [1, 4])
    historial = st.session_state.get("historial", [])
    ahora = datetime.now()
    inicio_semana = ahora - timedelta(days=ahora.weekday())
    st.markdown('<div class="section-label">📅 Esta semana</div>', unsafe_allow_html=True)
    dias_con_post = set()
    for h in historial:
        d = datetime.strptime(h["fecha"], "%d/%m/%Y %H:%M")
        if d >= inicio_semana.replace(hour=0,minute=0,second=0):
            dias_con_post.add(d.weekday())
    html_dias = '<div class="cal-row">'
    for i, dia in enumerate(DIAS_SEMANA):
        es_hoy = (i == ahora.weekday())
        clase = "cal-day cal-day-hoy" if es_hoy else "cal-day"
        if i in dias_con_post:
            contenido_dia = '<div class="cal-day-pub">✓ Publicado</div>'
        elif i in dias_pub:
            contenido_dia = '<div class="cal-day-pub">📝 Toca</div>'
        else:
            contenido_dia = '<div class="cal-day-empty">—</div>'
        html_dias += f'<div class="{clase}"><div class="cal-day-name">{dia[:3].upper()}</div>{contenido_dia}</div>'
    html_dias += '</div>'
    st.markdown(html_dias, unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;color:#7070a0;margin-top:8px;margin-bottom:6px">Configura tus días de publicación:</div>', unsafe_allow_html=True)

    def _guardar_dias():
        nuevos = st.session_state.sel_dias_pub
        st.session_state.dias_publicacion = nuevos
        sb_guardar_config("dias_publicacion", nuevos)

    st.multiselect("", options=list(range(7)), default=dias_pub,
        format_func=lambda x: DIAS_SEMANA[x], label_visibility="collapsed",
        key="sel_dias_pub", on_change=_guardar_dias)

    pendientes = len([d for d in dias_pub if d >= ahora.weekday() and d not in dias_con_post])
    if ahora.weekday() in dias_pub and ahora.weekday() not in dias_con_post:
        st.markdown('<div style="background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.3);border-radius:12px;padding:10px 14px;font-size:13px;color:#a78bfa;margin-top:10px">⚡ Hoy toca publicar — ¡busca una noticia!</div>', unsafe_allow_html=True)
    elif pendientes > 0:
        st.markdown(f'<div style="background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.25);border-radius:12px;padding:10px 14px;font-size:13px;color:#fbbf24;margin-top:10px">📅 Te quedan {pendientes} publicación{"es" if pendientes>1 else ""} esta semana</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:rgba(74,222,128,0.08);border:1px solid rgba(74,222,128,0.25);border-radius:12px;padding:10px 14px;font-size:13px;color:#4ade80;margin-top:10px">✅ ¡Has cumplido tu plan de publicación esta semana!</div>', unsafe_allow_html=True)

def render_analisis_competencia(data):
    def lista_items(items):
        return "".join([f'<div class="comp-item">{item}</div>' for item in items])
    st.markdown(f"""
    <div class="comp-card">
        <div class="comp-section">📋 Formatos más populares</div>{lista_items(data.get("formatos_populares",[]))}
        <div class="comp-section">🔥 Temas en tendencia</div>{lista_items(data.get("temas_trending",[]))}
        <div class="comp-section">🎣 Ganchos que funcionan</div>{lista_items(data.get("ganchos_efectivos",[]))}
        <div class="comp-section">🏷️ Hashtags top</div>
        <div style="font-size:13px;color:#6c9fff;line-height:2">{" ".join(data.get("hashtags_top",[]))}</div>
        <div class="comp-section">⏰ Mejor momento para publicar</div>
        <div class="comp-item">{data.get("mejor_dia_hora","")}</div>
        <div class="comp-section">⚡ Cómo diferenciarte</div>
        <div style="font-size:13px;color:#d0d0e0;line-height:1.7;padding:10px 14px;background:rgba(108,99,255,0.08);border-radius:10px;border-left:2px solid #6c63ff">{data.get("consejo_diferenciacion","")}</div>
        <div class="comp-section">⚠️ Error más común a evitar</div>
        <div style="font-size:13px;color:#d0d0e0;line-height:1.7;padding:10px 14px;background:rgba(248,113,113,0.08);border-radius:10px;border-left:2px solid #f87171">{data.get("error_comun","")}</div>
    </div>""", unsafe_allow_html=True)

def render_dashboard():
    historial = st.session_state.get("historial", [])
    if not historial:
        st.markdown("<div style='text-align:center;color:#7070a0;font-size:13px;padding:3rem 0'>Aún no hay datos.<br>¡Publica tu primer post para ver estadísticas!</div>", unsafe_allow_html=True)
        return
    total = len(historial)
    _, semanas_cons = calcular_racha()
    ahora = datetime.now()
    semanas_set = set()
    for h in historial:
        d = datetime.strptime(h["fecha"], "%d/%m/%Y %H:%M")
        semanas_set.add((d.year, d.isocalendar()[1]))
    racha_max = 0; racha_actual = 0
    sa, ya = ahora.isocalendar()[1], ahora.year
    for i in range(104):
        s, a = sa - i, ya
        if s <= 0: s += 52; a -= 1
        if (a, s) in semanas_set:
            racha_actual += 1
            racha_max = max(racha_max, racha_actual)
        else:
            racha_actual = 0
    semanas_labels = []
    semanas_counts = []
    for i in range(7, -1, -1):
        ref = ahora - timedelta(weeks=i)
        iso = ref.isocalendar()
        key = (iso[0], iso[1])
        count = sum(1 for h in historial
            if datetime.strptime(h["fecha"], "%d/%m/%Y %H:%M").isocalendar()[:2] == key[:2])
        semanas_labels.append(f"S{iso[1]}")
        semanas_counts.append(count)
    sector_counts = {}
    for h in historial:
        s = h.get("sector","Otro")
        sector_counts[s] = sector_counts.get(s, 0) + 1
    tono_counts = {}
    for h in historial:
        t = h.get("tono","Otro")
        tono_counts[t] = tono_counts.get(t, 0) + 1
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="dash-metric"><div class="dash-metric-num">{total}</div><div class="dash-metric-label">posts totales</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="dash-metric"><div class="dash-metric-num">🔥 {semanas_cons}</div><div class="dash-metric-label">semanas seguidas</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="dash-metric"><div class="dash-metric-num">⭐ {racha_max}</div><div class="dash-metric-label">racha máxima</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">📈 Posts por semana (últimas 8 semanas)</div>', unsafe_allow_html=True)
    max_count = max(semanas_counts) if max(semanas_counts) > 0 else 1
    bars_html = '<div style="display:flex;gap:8px;align-items:flex-end;height:100px;margin-bottom:8px">'
    for i, (label, count) in enumerate(zip(semanas_labels, semanas_counts)):
        height_pct = int((count / max_count) * 80) if count > 0 else 4
        is_current = (i == 7)
        color = "#6c63ff" if is_current else "#2a2a4a"
        border = "2px solid #a78bfa" if is_current else "none"
        bars_html += f'''<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px">
            <div style="font-size:10px;color:#7070a0">{count if count > 0 else ""}</div>
            <div style="width:100%;height:{height_pct}px;background:{color};border-radius:4px 4px 0 0;border:{border}"></div>
            <div style="font-size:9px;color:#7070a0">{label}</div>
        </div>'''
    bars_html += '</div>'
    st.markdown(bars_html, unsafe_allow_html=True)
    st.markdown('<div class="section-label">🏷️ Sectores más publicados</div>', unsafe_allow_html=True)
    sector_colors = {
        "🏦 Banca": "#3b82f6",
        "♟️ Estrategia": "#a855f7",
        "📊 Datos & BI": "#14b8a6",
        "🤖 Inteligencia Artificial": "#fbbf24",
    }
    sector_html = ""
    for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
        pct = int((count / total) * 100)
        color = sector_colors.get(sector, "#6c63ff")
        sector_html += f'''<div class="dash-bar-row">
            <div class="dash-bar-label">{sector}</div>
            <div class="dash-bar-bg"><div class="dash-bar-fill" style="width:{pct}%;background:{color}"></div></div>
            <div class="dash-bar-val">{count}</div>
        </div>'''
    st.markdown(f'<div style="background:#13131a;border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:1rem 1.2rem">{sector_html}</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">🎭 Tonos utilizados</div>', unsafe_allow_html=True)
    tono_colors = {"🎓 Estoy aprendiendo": "#fbbf24", "💼 Quiero parecer senior": "#6c63ff", "🔥 Quiero generar debate": "#f87171"}
    tono_html = ""
    for tono, count in sorted(tono_counts.items(), key=lambda x: -x[1]):
        pct = int((count / total) * 100)
        color = tono_colors.get(tono, "#6c63ff")
        tono_html += f'''<div class="dash-bar-row">
            <div class="dash-bar-label" style="width:180px">{tono}</div>
            <div class="dash-bar-bg"><div class="dash-bar-fill" style="width:{pct}%;background:{color}"></div></div>
            <div class="dash-bar-val">{count}</div>
        </div>'''
    st.markdown(f'<div style="background:#13131a;border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:1rem 1.2rem">{tono_html}</div>', unsafe_allow_html=True)

# ── UI ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <div class="badge">⚡ Agente LinK</div>
    <div class="main-title">Tu voz<br>en el sector</div>
    <div class="main-sub">Noticias españolas de los últimos 5 días · Analizadas con IA<br>Elige una y publica en LinkedIn</div>
</div>
""", unsafe_allow_html=True)

for key, val in [("noticias",[]),("post_generado",""),("noticia_elegida",None),
                  ("usadas",[]),("fase","inicio"),("puntuacion",None),
                  ("sector_elegido",""),("sectores_data",{}),
                  ("post_a",""),("post_b",""),("recomendada","A"),("razon",""),
                  ("tono_elegido","aprendiendo"),
                  ("post_en",""),("edicion_key",0),
                  ("competencia_data",None),("competencia_sector",""),
                  ("carrusel_pdf",None),("sb_cargado",False),
                  ("datos_li_guardados",None),
                  ("datos_sector","macro"),("indicador_elegido",None),
                  ("datos_grafico_png",None),("datos_post_generado",""),
                  ("datos_puntuacion",None),("datos_post_en",""),
                  ("datos_carrusel_pdf",None),("datos_edicion_key",0),
                  ("datos_dashboard_pbi",None),("datos_dashboard_dark",None),
                  ("datos_noticia_rel",None),("datos_update_msg",""),
                  ("ibex_empresa","Santander"),("ibex_noticias",[]),
                  ("ibex_kpi_data",None),("ibex_historico_key",""),
                  ("ibex_dashboard_pbi",None),("ibex_dashboard_dark",None),
                  ("ibex_post_generado",""),("ibex_edicion_key",0),
                  ("ibex_tono_elegido","aprendiendo")]:
    if key not in st.session_state:
        st.session_state[key] = val

if not st.session_state.sb_cargado:
    historial_sb = sb_cargar_historial()
    st.session_state.historial = historial_sb if historial_sb else []
    dias_sb = sb_cargar_config("dias_publicacion", [1, 4])
    st.session_state.dias_publicacion = dias_sb
    st.session_state.sb_cargado = True

# ── INICIO ─────────────────────────────────────────────────────────────────────
if st.session_state.fase == "inicio":
    posts_semana, semanas_cons = calcular_racha()
    total_posts = len(st.session_state.historial)
    if total_posts > 0:
        fuego = "🔥" if semanas_cons >= 2 else "📅"
        st.markdown(f"""
        <div class="stats-row">
            <div class="stat-card"><div class="stat-num">{total_posts}</div><div class="stat-label">posts generados</div></div>
            <div class="stat-card"><div class="stat-num">{posts_semana}</div><div class="stat-label">esta semana</div></div>
            <div class="stat-card"><div class="stat-num racha-fire">{fuego} {semanas_cons}</div><div class="stat-label">semanas seguidas</div></div>
        </div>""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("⚡  Buscar noticias", use_container_width=True, type="primary"):
            with st.spinner("Buscando noticias españolas..."):
                sectores_data = fetch_noticias_por_sector()
                noticias = []
                for sector, noticia in sectores_data.items():
                    if noticia and noticia["url"] not in st.session_state.usadas:
                        noticia["_sector"] = sector
                        noticias.append(noticia)
                if not noticias:
                    st.error("Sin noticias nuevas.")
                else:
                    st.session_state.noticias = noticias
                    st.session_state.fase = "noticias"
                    st.rerun()

    if st.session_state.usadas:
        st.markdown(f"<div style='text-align:center;color:#7070a0;font-size:12px;margin-top:8px'>{len(st.session_state.usadas)} noticia{'s' if len(st.session_state.usadas)>1 else ''} ya usada{'s' if len(st.session_state.usadas)>1 else ''} — no se repetirán</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    if st.button("📈  Resultados IBEX 35", use_container_width=True):
        st.session_state.fase = "ibex"
        st.session_state.ibex_noticias = []
        st.session_state.ibex_kpi_data = None
        st.session_state.ibex_dashboard_pbi = None
        st.session_state.ibex_dashboard_dark = None
        st.session_state.ibex_post_generado = ""
        st.rerun()

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    if st.button("🔍  Ver qué publica la competencia", use_container_width=True):
        st.session_state.fase = "competencia"
        st.rerun()

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    render_calendario()

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    col_h, col_d = st.columns(2)
    with col_h:
        if st.button("📚  Ver historial", use_container_width=True):
            st.session_state.fase = "historial"
            st.rerun()
    with col_d:
        if st.button("📊  Dashboard", use_container_width=True):
            st.session_state.fase = "dashboard"
            st.rerun()

# ── DASHBOARD ──────────────────────────────────────────────────────────────────
elif st.session_state.fase == "dashboard":
    st.markdown("""
    <div class="post-header">
        <div class="post-icon">📊</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">Dashboard</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">Analítica y actividad en LinkedIn</div>
        </div>
    </div>""", unsafe_allow_html=True)

    tab_app, tab_linkedin = st.tabs(["⚡ Actividad del Agente", "📈 Analítica de LinkedIn"])

    with tab_app:
        render_dashboard()

    with tab_linkedin:
        import plotly.express as px
        import plotly.graph_objects as go

        # ── Helpers para parsear Excel de LinkedIn ─────────────────────────────
        def _get_val(df, label):
            try:
                fila = df[df[0].astype(str).str.contains(label, case=False, na=False)]
                return int(pd.to_numeric(fila.iloc[0, 1], errors='coerce'))
            except: return 0

        def _get_txt(df, label):
            try:
                fila = df[df[0].astype(str).str.contains(label, case=False, na=False)]
                return str(fila.iloc[0, 1])
            except: return ""

        def _parse_fecha(s):
            """Convierte '15 mar. 2026' → date"""
            meses = {"ene":1,"feb":2,"mar":3,"abr":4,"may":5,"jun":6,
                     "jul":7,"ago":8,"sep":9,"oct":10,"nov":11,"dic":12}
            try:
                parts = s.replace(".","").strip().split()
                d, m, y = int(parts[0]), meses.get(parts[1].lower()[:3], 1), int(parts[2])
                from datetime import date
                return date(y, m, d)
            except: return None

        def parsear_excel_li(file_bytes):
            """Parsea un Excel de LinkedIn y devuelve dict listo para Supabase."""
            df_r = pd.read_excel(file_bytes, sheet_name=0, header=None)
            df_d = pd.read_excel(file_bytes, sheet_name=1)
            df_d.columns = [str(c).strip().lower() for c in df_d.columns]
            col_cat, col_val2, col_pct2 = df_d.columns[0], df_d.columns[1], df_d.columns[2]
            df_d[col_pct2] = (pd.to_numeric(df_d[col_pct2], errors='coerce') * 100).round(1)

            url = _get_txt(df_r, "URL de la publicación")
            fecha_str = _get_txt(df_r, "Fecha de publicación")
            fecha = _parse_fecha(fecha_str)

            # Audiencia detallada como JSON
            audiencia = {}
            for cat in df_d[col_cat].dropna().unique():
                rows = df_d[df_d[col_cat] == cat][[col_val2, col_pct2]].values.tolist()
                audiencia[str(cat)] = [{"valor": r[0], "pct": r[1]} for r in rows]

            return {
                "url": url,
                "fecha": str(fecha) if fecha else None,
                "hora": _get_txt(df_r, "Hora de publicación"),
                "impresiones": _get_val(df_r, "Impresiones"),
                "alcance": _get_val(df_r, "Miembros alcanzados"),
                "reacciones": _get_val(df_r, "Reacciones"),
                "comentarios": _get_val(df_r, "Comentarios"),
                "compartidos": _get_val(df_r, "Veces compartido"),
                "guardados": _get_val(df_r, "Veces guardado"),
                "visitas_perfil": _get_val(df_r, "Visualizaciones del perfil"),
                "seguidores_ganados": _get_val(df_r, "Seguidores obtenidos"),
                "visitas_enlaces": _get_val(df_r, "Visitas a los enlaces"),
                "cargo_principal": _get_txt(df_r, "Cargo principal"),
                "ubicacion_principal": _get_txt(df_r, "Ubicación principal"),
                "sector_principal": _get_txt(df_r, "Sector principal"),
                "audiencia_detalle": json.dumps(audiencia, ensure_ascii=False),
            }

        def sb_guardar_analytics(entrada: dict):
            """Upsert en linkedin_posts_analytics (URL como clave única)."""
            try:
                headers = {**_sb_headers(), "Prefer": "resolution=merge-duplicates"}
                r = requests.post(
                    f"{SUPABASE_URL}/rest/v1/linkedin_posts_analytics",
                    headers=headers, json=entrada, timeout=10
                )
                return r.status_code in (200, 201)
            except: return False

        def sb_cargar_analytics():
            """Carga todos los posts de analytics ordenados por fecha."""
            try:
                r = requests.get(
                    f"{SUPABASE_URL}/rest/v1/linkedin_posts_analytics?order=fecha.asc&limit=500",
                    headers=_sb_headers(), timeout=10
                )
                if r.status_code == 200:
                    return r.json()
            except: pass
            return []

        # ── Cargar datos históricos desde Supabase ─────────────────────────────
        if "analytics_posts" not in st.session_state:
            st.session_state.analytics_posts = sb_cargar_analytics()

        posts_data = st.session_state.analytics_posts

        # ── Uploader múltiple ──────────────────────────────────────────────────
        st.markdown('<div class="section-label">📥 Subir Excels de LinkedIn</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#7070a0;margin-bottom:12px">Puedes subir varios a la vez — se acumulan en la base de datos sin duplicarse</div>', unsafe_allow_html=True)

        archivos = st.file_uploader(
            "Arrastra uno o varios Excels de LinkedIn",
            type=["xlsx"],
            accept_multiple_files=True,
            key="li_uploader"
        )

        if archivos:
            nuevos = 0; duplicados = 0; errores = 0
            urls_existentes = {p.get("url","") for p in posts_data}
            for archivo in archivos:
                try:
                    datos = parsear_excel_li(archivo)
                    if datos["url"] in urls_existentes:
                        duplicados += 1
                        continue
                    ok = sb_guardar_analytics(datos)
                    if ok:
                        nuevos += 1
                        posts_data.append(datos)
                        urls_existentes.add(datos["url"])
                    else:
                        errores += 1
                except Exception as e:
                    errores += 1
            st.session_state.analytics_posts = posts_data

            msg = []
            if nuevos: msg.append(f"✅ {nuevos} post{'s' if nuevos>1 else ''} guardado{'s' if nuevos>1 else ''}")
            if duplicados: msg.append(f"⚠️ {duplicados} ya existía{'n' if duplicados>1 else ''}")
            if errores: msg.append(f"❌ {errores} error{'es' if errores>1 else ''}")
            if msg: st.info(" · ".join(msg))

        # ── Dashboard solo si hay datos ────────────────────────────────────────
        if not posts_data:
            st.markdown("<div style='text-align:center;color:#7070a0;font-size:13px;padding:3rem 0'>Sube tu primer Excel de LinkedIn para ver el dashboard</div>", unsafe_allow_html=True)
        else:
            df = pd.DataFrame(posts_data)
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            df = df.dropna(subset=["fecha"]).sort_values("fecha")
            df["engagement"] = df["reacciones"] + df["comentarios"] + df["compartidos"] + df["guardados"]

            total_posts = len(df)
            total_imp = int(df["impresiones"].sum())
            total_reac = int(df["reacciones"].sum())
            total_com = int(df["comentarios"].sum())
            mejor_post = df.loc[df["impresiones"].idxmax()]
            eng_rate = round((df["engagement"].sum() / df["impresiones"].sum() * 100), 2) if total_imp > 0 else 0

            # ── KPIs ───────────────────────────────────────────────────────────
            st.markdown('<div class="section-label">📊 Resumen total</div>', unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Posts", total_posts)
            c2.metric("Impresiones", f"{total_imp:,}".replace(",","."))
            c3.metric("Reacciones", total_reac)
            c4.metric("Comentarios", total_com)
            c5.metric("Engagement rate", f"{eng_rate}%")

            # ── Gráfico evolución temporal ─────────────────────────────────────
            st.markdown('<div class="section-label">📈 Evolución por post</div>', unsafe_allow_html=True)

            df["fecha_str"] = df["fecha"].dt.strftime("%d %b")

            fig_evo = go.Figure()
            fig_evo.add_trace(go.Scatter(
                x=df["fecha_str"], y=df["impresiones"],
                name="Impresiones", mode="lines+markers",
                line=dict(color="#6c63ff", width=2.5),
                marker=dict(size=8, color="#6c63ff"),
                fill="tozeroy", fillcolor="rgba(108,99,255,0.08)"
            ))
            fig_evo.add_trace(go.Scatter(
                x=df["fecha_str"], y=df["reacciones"],
                name="Reacciones", mode="lines+markers",
                line=dict(color="#4ade80", width=2.5),
                marker=dict(size=8, color="#4ade80")
            ))
            fig_evo.add_trace(go.Scatter(
                x=df["fecha_str"], y=df["comentarios"],
                name="Comentarios", mode="lines+markers",
                line=dict(color="#fbbf24", width=2.5),
                marker=dict(size=8, color="#fbbf24")
            ))
            fig_evo.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f0f0f8",
                height=340,
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
                xaxis=dict(showgrid=False, tickfont=dict(size=10)),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickfont=dict(size=10)),
                hovermode="x unified"
            )
            st.plotly_chart(fig_evo, use_container_width=True, config={"displayModeBar": False})

            # ── Mejor post ─────────────────────────────────────────────────────
            st.markdown('<div class="section-label">🏆 Mejor post hasta ahora</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="background:#13131a;border:1px solid rgba(108,99,255,0.3);border-radius:14px;padding:1rem 1.2rem">
                <div style="font-size:11px;color:#a78bfa;margin-bottom:6px">📅 {mejor_post['fecha'].strftime('%d %b %Y') if pd.notnull(mejor_post['fecha']) else ''} · {mejor_post.get('sector_principal','')}</div>
                <div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:8px">
                    <div style="text-align:center"><div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#6c63ff">{int(mejor_post['impresiones'])}</div><div style="font-size:10px;color:#7070a0">impresiones</div></div>
                    <div style="text-align:center"><div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#4ade80">{int(mejor_post['reacciones'])}</div><div style="font-size:10px;color:#7070a0">reacciones</div></div>
                    <div style="text-align:center"><div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#fbbf24">{int(mejor_post['comentarios'])}</div><div style="font-size:10px;color:#7070a0">comentarios</div></div>
                    <div style="text-align:center"><div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#f0f0f8">{int(mejor_post['visitas_perfil'])}</div><div style="font-size:10px;color:#7070a0">visitas perfil</div></div>
                </div>
                <div style="margin-top:10px"><a href="{mejor_post.get('url','')}" target="_blank" style="font-size:11px;color:#6c63ff;text-decoration:none">Ver post en LinkedIn ↗</a></div>
            </div>""", unsafe_allow_html=True)

            # ── Audiencia agregada ─────────────────────────────────────────────
            st.markdown('<div class="section-label">👥 Audiencia agregada</div>', unsafe_allow_html=True)

            # Consolidar audiencia de todos los posts
            sector_agg = {}; ciudad_agg = {}; cargo_agg = {}
            for p in posts_data:
                try:
                    aud = json.loads(p.get("audiencia_detalle") or "{}")
                    for cat, items in aud.items():
                        cat_l = cat.lower()
                        for item in items:
                            v, pct = item.get("valor",""), item.get("pct", 0)
                            if "sector" in cat_l:
                                sector_agg[v] = sector_agg.get(v, 0) + pct
                            elif "ubicación" in cat_l or "ubicacion" in cat_l:
                                ciudad_agg[v] = ciudad_agg.get(v, 0) + pct
                            elif "cargo" in cat_l:
                                cargo_agg[v] = cargo_agg.get(v, 0) + pct
                except: pass

            col_aud1, col_aud2 = st.columns(2)

            with col_aud1:
                if sector_agg:
                    df_sec = pd.DataFrame(sorted(sector_agg.items(), key=lambda x:-x[1])[:6], columns=["Sector","Score"])
                    fig_sec2 = px.bar(df_sec, x="Score", y="Sector", orientation="h",
                                      color_discrete_sequence=["#6c63ff"])
                    fig_sec2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                           font_color="#f0f0f8", height=260, margin=dict(l=0,r=0,t=20,b=0),
                                           xaxis=dict(showgrid=False, visible=False),
                                           yaxis=dict(tickfont=dict(size=10)))
                    st.markdown("<div style='font-size:12px;color:#d0d0e0;margin-bottom:4px'>Sectores que te leen</div>", unsafe_allow_html=True)
                    st.plotly_chart(fig_sec2, use_container_width=True, config={"displayModeBar": False})

            with col_aud2:
                if ciudad_agg:
                    df_ciu = pd.DataFrame(sorted(ciudad_agg.items(), key=lambda x:-x[1])[:5], columns=["Ciudad","Score"])
                    fig_ciu2 = px.pie(df_ciu, values="Score", names="Ciudad", hole=0.55,
                                      color_discrete_sequence=["#6c63ff","#a78bfa","#4ade80","#fbbf24","#f87171"])
                    fig_ciu2.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#f0f0f8",
                                           height=260, margin=dict(t=20,b=0,l=0,r=0),
                                           legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)"))
                    st.markdown("<div style='font-size:12px;color:#d0d0e0;margin-bottom:4px'>Ciudades</div>", unsafe_allow_html=True)
                    st.plotly_chart(fig_ciu2, use_container_width=True, config={"displayModeBar": False})

            if cargo_agg:
                df_car = pd.DataFrame(sorted(cargo_agg.items(), key=lambda x:-x[1])[:6], columns=["Cargo","Score"])
                fig_car = px.bar(df_car, x="Score", y="Cargo", orientation="h",
                                 color_discrete_sequence=["#4ade80"])
                fig_car.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                      font_color="#f0f0f8", height=240, margin=dict(l=0,r=0,t=20,b=0),
                                      xaxis=dict(showgrid=False, visible=False),
                                      yaxis=dict(tickfont=dict(size=10)))
                st.markdown('<div class="section-label">💼 Cargos que te leen</div>', unsafe_allow_html=True)
                st.plotly_chart(fig_car, use_container_width=True, config={"displayModeBar": False})

            # ── Insight Gemini ─────────────────────────────────────────────────
            if len(df) >= 2:
                st.markdown('<div class="section-label">💡 Insight IA</div>', unsafe_allow_html=True)
                if st.button("🤖 Analizar mis datos y dame estrategia", use_container_width=True, key="btn_insight"):
                    with st.spinner("Gemini analizando tus datos reales..."):
                        ctx = {
                            "total_posts": total_posts,
                            "impresiones_totales": total_imp,
                            "engagement_rate": eng_rate,
                            "mejor_sector": mejor_post.get("sector_principal",""),
                            "sectores_audiencia": list(sector_agg.keys())[:5],
                            "ciudades": list(ciudad_agg.keys())[:3],
                            "cargos": list(cargo_agg.keys())[:3],
                            "evolucion_impresiones": df["impresiones"].tolist(),
                        }
                        st.success(sugerir_estrategia_proximo_post(ctx))

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver al inicio"):
        st.session_state.fase = "inicio"
        st.rerun()

# ── ANÁLISIS DE DATOS (fichas Macro e IA & Tech) ──────────────────────────────
elif st.session_state.fase == "datos_sector":
    tipo = st.session_state.datos_sector
    indicadores = INDICADORES_MACRO if tipo == "macro" else INDICADORES_IA_TECH
    etiqueta_sector = "📈 Macro & Economía" if tipo == "macro" else "🤖 IA & Tech Empresarial"

    st.markdown(f"""
    <div class="post-header">
        <div class="post-icon">{"📈" if tipo == "macro" else "🤖"}</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">{etiqueta_sector}</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">Datos reales · Gráfico PNG descargable · Post con reflexión de futuro</div>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">Elige el indicador a analizar</div>', unsafe_allow_html=True)
    opciones = {k: v["nombre"] for k, v in indicadores.items()}
    indicador_sel = st.selectbox("", options=list(opciones.keys()),
        format_func=lambda x: opciones[x], label_visibility="collapsed", key="sel_indicador")
    cfg_sel = indicadores[indicador_sel]
    st.markdown(f'<div style="font-size:12px;color:#7070a0;margin-bottom:0.5rem">{cfg_sel["descripcion"]} · <span style="color:#a78bfa">{cfg_sel["fuente"]}</span></div>', unsafe_allow_html=True)

    if st.button("📊  Cargar datos y generar gráfico", use_container_width=True, key="btn_cargar"):
        with st.spinner("Cargando datos reales..."):
            datos, cfg = obtener_datos_indicador(indicador_sel, tipo)
        if not datos:
            st.error("No se pudieron obtener datos de la API. Inténtalo de nuevo en unos minutos.")
        else:
            with st.spinner("Generando gráfico..."):
                png_bytes = generar_grafico_png(datos, cfg)
            st.session_state.indicador_elegido = {"id": indicador_sel, "cfg": cfg, "datos": datos, "tipo": tipo}
            st.session_state.datos_grafico_png = png_bytes
            st.session_state.datos_post_generado = ""
            st.session_state.datos_puntuacion = None
            st.session_state.datos_edicion_key += 1
            st.rerun()

    if st.session_state.datos_grafico_png and st.session_state.indicador_elegido:
        ind = st.session_state.indicador_elegido
        cfg_act = ind["cfg"]; datos_act = ind["datos"]; tipo_act = ind["tipo"]

        st.markdown('<div class="section-label">📊 Gráfico generado</div>', unsafe_allow_html=True)
        st.image(st.session_state.datos_grafico_png, use_container_width=True)
        nombre_archivo = re.sub(r"[^a-z0-9]+", "_", cfg_act.get("nombre","grafico").lower())[:40]
        st.download_button(label="⬇️  Descargar gráfico PNG", data=st.session_state.datos_grafico_png,
            file_name=f"grafico_{nombre_archivo}.png", mime="image/png",
            use_container_width=True, key="dl_grafico")
        st.markdown('<div style="font-size:12px;color:#7070a0;margin-top:4px;margin-bottom:1rem">💡 Descarga el gráfico y súbelo como imagen a LinkedIn junto con el post de texto</div>', unsafe_allow_html=True)

        # ── Dashboards estilo Power BI ─────────────────────────────────────
        st.markdown('<div class="section-label">🖥️ Vista Dashboard para LinkedIn</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#7070a0;margin-bottom:12px">Genera una imagen estilo cuadro de mando profesional para subir como imagen junto al post</div>', unsafe_allow_html=True)
        col_db1, col_db2 = st.columns(2)
        with col_db1:
            if st.button("📊  Estilo Power BI", use_container_width=True, key="btn_dash_pbi"):
                with st.spinner("Generando dashboard Power BI..."):
                    st.session_state.datos_dashboard_pbi = generar_dashboard_png(datos_act, cfg_act, "powerbi")
                    st.rerun()
        with col_db2:
            if st.button("🌙  Estilo Dark (Agente)", use_container_width=True, key="btn_dash_dark"):
                with st.spinner("Generando dashboard oscuro..."):
                    st.session_state.datos_dashboard_dark = generar_dashboard_png(datos_act, cfg_act, "dark")
                    st.rerun()

        if st.session_state.datos_dashboard_pbi:
            st.markdown('<div style="font-size:11px;color:#a78bfa;font-weight:600;margin-top:12px;margin-bottom:6px">📊 ESTILO POWER BI</div>', unsafe_allow_html=True)
            st.image(st.session_state.datos_dashboard_pbi, use_container_width=True)
            nom_pbi = re.sub(r"[^a-z0-9]+", "_", cfg_act.get("nombre","dashboard").lower())[:30]
            st.download_button(label="⬇️  Descargar dashboard Power BI", data=st.session_state.datos_dashboard_pbi,
                file_name=f"dashboard_pbi_{nom_pbi}.png", mime="image/png",
                use_container_width=True, key="dl_dash_pbi")

        if st.session_state.datos_dashboard_dark:
            st.markdown('<div style="font-size:11px;color:#6c63ff;font-weight:600;margin-top:12px;margin-bottom:6px">🌙 ESTILO DARK</div>', unsafe_allow_html=True)
            st.image(st.session_state.datos_dashboard_dark, use_container_width=True)
            nom_dark = re.sub(r"[^a-z0-9]+", "_", cfg_act.get("nombre","dashboard").lower())[:30]
            st.download_button(label="⬇️  Descargar dashboard Dark", data=st.session_state.datos_dashboard_dark,
                file_name=f"dashboard_dark_{nom_dark}.png", mime="image/png",
                use_container_width=True, key="dl_dash_dark")

        if datos_act:
            valores = [d[1] for d in datos_act]
            ultimo = datos_act[-1]
            penultimo = datos_act[-2] if len(datos_act) >= 2 else None
            variacion = ((ultimo[1] - penultimo[1]) / abs(penultimo[1]) * 100) if penultimo and penultimo[1] != 0 else 0
            c1, c2, c3 = st.columns(3)
            c1.metric(f"Último ({ultimo[0]})", f"{ultimo[1]:.2f}")
            c2.metric("Variación", f"{variacion:+.2f}%")
            c3.metric("Máximo período", f"{max(valores):.2f}")

        # ── Capa 2: Noticia de actualidad relacionada ─────────────────────────
        st.markdown('<div class="section-label">📰 Noticia de actualidad relacionada</div>', unsafe_allow_html=True)
        col_n1, col_n2 = st.columns([3, 1])
        with col_n1:
            if st.session_state.datos_noticia_rel:
                nr = st.session_state.datos_noticia_rel
                st.markdown(f'<div style="background:#13131a;border:1px solid rgba(108,99,255,0.25);border-radius:12px;padding:10px 14px;font-size:12px"><span style="color:#a78bfa;font-size:10px;font-weight:700">{nr["fuente"]} · {nr["fecha"]}</span><br><span style="color:#f0f0f8;font-weight:600">{nr["titulo"][:120]}</span><br><span style="color:#7070a0;font-size:11px">{nr["resumen"][:160]}...</span><br><a href="{nr["url"]}" target="_blank" style="font-size:10px;color:#6c63ff">Ver noticia ↗</a></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-size:12px;color:#7070a0;padding:8px 0">Busca una noticia reciente para enriquecer el post con contexto de actualidad</div>', unsafe_allow_html=True)
        with col_n2:
            if st.button("🔍 Buscar noticia", use_container_width=True, key="btn_buscar_noticia"):
                with st.spinner("Buscando..."):
                    st.session_state.datos_noticia_rel = buscar_noticia_indicador(cfg_act)
                    if not st.session_state.datos_noticia_rel:
                        st.warning("No se encontro noticia reciente.")
                    st.rerun()
            if st.session_state.datos_noticia_rel:
                if st.button("✕ Quitar", use_container_width=True, key="btn_quitar_noticia"):
                    st.session_state.datos_noticia_rel = None
                    st.rerun()

        # ── Capa 3: Actualizar dato desde noticia ──────────────────────────────
        if st.session_state.datos_noticia_rel:
            st.markdown('<div style="font-size:12px;color:#7070a0;margin-top:8px;margin-bottom:4px">¿La noticia contiene un dato más reciente que el gráfico? Extráelo con IA:</div>', unsafe_allow_html=True)
            col_u1, col_u2 = st.columns([3, 1])
            with col_u1:
                if st.session_state.datos_update_msg:
                    color_msg = "#4ade80" if "actualizado" in st.session_state.datos_update_msg else "#fbbf24"
                    st.markdown(f'<div style="font-size:12px;color:{color_msg};padding:6px 0">{st.session_state.datos_update_msg}</div>', unsafe_allow_html=True)
            with col_u2:
                if st.button("🔄 Extraer dato", use_container_width=True, key="btn_update_dato"):
                    with st.spinner("Gemini extrayendo dato..."):
                        resultado = actualizar_dato_indicador(cfg_act, st.session_state.datos_noticia_rel)
                        if resultado:
                            periodo, valor = resultado
                            # Solo añadir si el periodo no existe ya
                            periodos_existentes = [d[0] for d in datos_act]
                            if periodo not in periodos_existentes:
                                datos_act.append((periodo, valor))
                                st.session_state.indicador_elegido["datos"] = datos_act
                                # Regenerar gráfico con el nuevo dato
                                st.session_state.datos_grafico_png = generar_grafico_png(datos_act, cfg_act)
                                st.session_state.datos_dashboard_pbi = None
                                st.session_state.datos_dashboard_dark = None
                                st.session_state.datos_update_msg = f"✅ Dato actualizado: {periodo} = {valor:.2f}"
                            else:
                                st.session_state.datos_update_msg = f"⚠️ El periodo {periodo} ya existe en los datos"
                        else:
                            st.session_state.datos_update_msg = "No se pudo extraer un dato claro de la noticia"
                    st.rerun()

        st.markdown('<div class="section-label">✦ Generar post LinkedIn</div>', unsafe_allow_html=True)

        if not st.session_state.datos_post_generado:
            st.markdown('<div style="font-size:12px;color:#7070a0;margin-bottom:12px">Elige el tono y Gemini analizará los datos para generar un post con reflexión de futuro</div>', unsafe_allow_html=True)
            if st.session_state.datos_noticia_rel:
                st.markdown('<div style="font-size:11px;color:#4ade80;margin-bottom:8px">✦ El post incluirá la noticia de actualidad como contexto</div>', unsafe_allow_html=True)
            col_t1, col_t2, col_t3 = st.columns(3)
            for i, (tono_key, tono_cfg) in enumerate(TONOS.items()):
                with [col_t1, col_t2, col_t3][i]:
                    if st.button(tono_cfg["label"], key=f"datos_tono_{tono_key}", use_container_width=True):
                        with st.spinner("Gemini analizando datos..."):
                            post = generar_post_desde_datos(datos_act, cfg_act, tono_key, tipo_act,
                                                            noticia_relacionada=st.session_state.datos_noticia_rel)
                            st.session_state.datos_post_generado = post
                            st.session_state.tono_elegido = tono_key
                            st.session_state.datos_edicion_key += 1
                            st.rerun()
        else:
            tono_label = TONOS.get(st.session_state.tono_elegido, {}).get("label","")
            st.markdown(f'<div style="font-size:11px;color:#7070a0;margin-bottom:8px">Tono: {tono_label}</div>', unsafe_allow_html=True)
            post_edit = st.text_area("", value=st.session_state.datos_post_generado, height=320,
                label_visibility="collapsed", key=f"datos_editor_{st.session_state.datos_edicion_key}")
            if post_edit != st.session_state.datos_post_generado:
                st.session_state.datos_post_generado = post_edit

            st.markdown('<div class="edicion-guiada-label">✨ Edición guiada</div>', unsafe_allow_html=True)
            ce1, ce2, ce3 = st.columns(3)
            with ce1:
                if st.button("✂️ Más corto", use_container_width=True, key="ded_corto"):
                    with st.spinner("Condensando..."):
                        st.session_state.datos_post_generado = editar_post_guiado(st.session_state.datos_post_generado, "Reduce a máximo 150 palabras. Conserva datos clave y pregunta final.")
                        st.session_state.datos_edicion_key += 1; st.rerun()
            with ce2:
                if st.button("🎣 Nuevo gancho", use_container_width=True, key="ded_gancho"):
                    with st.spinner("Reescribiendo gancho..."):
                        st.session_state.datos_post_generado = editar_post_guiado(st.session_state.datos_post_generado, "Reescribe SOLO las primeras 1-2 líneas con el dato más impactante como gancho. El resto igual.")
                        st.session_state.datos_edicion_key += 1; st.rerun()
            with ce3:
                if st.button("🔮 Más futuro", use_container_width=True, key="ded_futuro"):
                    with st.spinner("Ampliando predicción..."):
                        st.session_state.datos_post_generado = editar_post_guiado(st.session_state.datos_post_generado, "Amplía SOLO la reflexión de futuro. Añade una predicción más concreta para los próximos 6-12 meses. El resto igual.")
                        st.session_state.datos_edicion_key += 1; st.rerun()

            st.markdown('<div class="edicion-guiada-label">🔄 Cambiar pregunta final</div>', unsafe_allow_html=True)
            cp1, cp2, cp3 = st.columns(3)
            with cp1:
                if st.button("💪 A favor del tema", use_container_width=True, key="dpreg_favor"):
                    with st.spinner("Reescribiendo..."): st.session_state.datos_post_generado = cambiar_pregunta_final(st.session_state.datos_post_generado, "favor"); st.session_state.datos_edicion_key += 1; st.rerun()
            with cp2:
                if st.button("🔥 Provocar debate", use_container_width=True, key="dpreg_debate"):
                    with st.spinner("Reescribiendo..."): st.session_state.datos_post_generado = cambiar_pregunta_final(st.session_state.datos_post_generado, "debate"); st.session_state.datos_edicion_key += 1; st.rerun()
            with cp3:
                if st.button("💭 Reflexión abierta", use_container_width=True, key="dpreg_reflexion"):
                    with st.spinner("Reescribiendo..."): st.session_state.datos_post_generado = cambiar_pregunta_final(st.session_state.datos_post_generado, "reflexion"); st.session_state.datos_edicion_key += 1; st.rerun()

            st.markdown("<hr>", unsafe_allow_html=True)
            ca1, ca2 = st.columns(2)
            with ca1:
                if st.button("📋  Copiar post", use_container_width=True, key="dcopiar"):
                    st.code(st.session_state.datos_post_generado, language=None)
                    st.success("Copia el texto de arriba ↑")
            with ca2:
                if st.button("📨  Enviar a Telegram", use_container_width=True, key="dtelegram"):
                    with st.spinner("Enviando..."):
                        nf = {"fuente": cfg_act.get("fuente","Datos"), "fecha": datetime.now().strftime("%d/%m/%Y"),
                              "url": cfg_act.get("url_api",""), "titulo": cfg_act.get("nombre","")}
                        ok = enviar_telegram(st.session_state.datos_post_generado, nf)
                        if ok:
                            guardar_en_historial(st.session_state.datos_post_generado, nf,
                                "banca" if tipo_act == "macro" else "ia", st.session_state.tono_elegido)
                            st.success("✅ Enviado y guardado en historial.")
                        else: st.error("❌ Error al enviar.")
            ca3, ca4 = st.columns(2)
            with ca3:
                if st.button("🔄  Regenerar post", use_container_width=True, key="dregen"):
                    st.session_state.datos_post_generado = ""; st.session_state.datos_edicion_key += 1; st.rerun()
            with ca4:
                if st.button("🔄  Cambiar indicador", use_container_width=True, key="dcambiar"):
                    st.session_state.indicador_elegido = None; st.session_state.datos_grafico_png = None
                    st.session_state.datos_post_generado = ""; st.session_state.datos_noticia_rel = None
                    st.session_state.datos_update_msg = ""; st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver al inicio", key="datos_volver"):
        st.session_state.fase = "inicio"
        st.session_state.indicador_elegido = None
        st.session_state.datos_grafico_png = None
        st.session_state.datos_post_generado = ""
        st.session_state.datos_noticia_rel = None
        st.session_state.datos_update_msg = ""
        st.rerun()

# ── IBEX 35 — Resultados empresas ────────────────────────────────────────────
elif st.session_state.fase == "ibex":
    st.markdown("""
    <div class="post-header">
        <div class="post-icon">📈</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">Resultados IBEX 35</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">KPIs reales · Dashboard + Post LinkedIn · Fuentes: CNMV + Prensa financiera</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Selector empresa
    st.markdown('<div class="section-label">Elige la empresa</div>', unsafe_allow_html=True)
    empresa_sel = st.selectbox("", options=list(EMPRESAS_IBEX.keys()),
        format_func=lambda x: EMPRESAS_IBEX[x]["emoji"] + " " + x + " · " + EMPRESAS_IBEX[x]["sector"],
        label_visibility="collapsed", key="sel_ibex_empresa",
        index=list(EMPRESAS_IBEX.keys()).index(st.session_state.ibex_empresa)
            if st.session_state.ibex_empresa in EMPRESAS_IBEX else 0)

    if empresa_sel != st.session_state.ibex_empresa:
        st.session_state.ibex_empresa = empresa_sel
        st.session_state.ibex_noticias = []
        st.session_state.ibex_kpi_data = None
        st.session_state.ibex_dashboard_pbi = None
        st.session_state.ibex_dashboard_dark = None
        st.session_state.ibex_post_generado = ""
        st.rerun()

    cfg_ibex = EMPRESAS_IBEX[empresa_sel]

    # Sin selector — usamos todos los KPIs del historico juntos
    historico_keys = list(cfg_ibex.get("historico", {}).keys())
    ibex_hist_key = historico_keys[0] if historico_keys else ""
    st.session_state.ibex_historico_key = ibex_hist_key

    st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)

    if st.button("🔍  Buscar resultados recientes", use_container_width=True, key="btn_ibex_buscar"):
        with st.spinner(f"Buscando resultados de {empresa_sel} en CNMV y prensa..."):
            noticias = buscar_resultados_empresa(empresa_sel)
            st.session_state.ibex_noticias = noticias
            st.session_state.ibex_kpi_data = None
            st.session_state.ibex_dashboard_pbi = None
            st.session_state.ibex_dashboard_dark = None
            st.session_state.ibex_post_generado = ""
        if noticias:
            with st.spinner("Gemini extrayendo KPIs financieros..."):
                kpi_data = extraer_kpis_empresa(empresa_sel, noticias)
                st.session_state.ibex_kpi_data = kpi_data
        st.rerun()

    # Mostrar noticias encontradas con boton de generar post
    if st.session_state.ibex_noticias:
        st.markdown('<div class="section-label">📰 Fuentes encontradas</div>', unsafe_allow_html=True)
        for ni, n in enumerate(st.session_state.ibex_noticias[:4]):
            st.markdown(f'<div style="background:#13131a;border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:8px 12px;margin-bottom:4px;font-size:12px"><span style="color:#a78bfa;font-size:10px">{n["fuente"]} · {n["fecha"]}</span><br><span style="color:#f0f0f8">{n["titulo"][:140]}</span><br><a href="{n["url"]}" target="_blank" style="font-size:10px;color:#6c63ff">Ver noticia ↗</a></div>', unsafe_allow_html=True)
            if st.button("❖ Generar post desde esta noticia", key=f"ibex_noticia_post_{ni}", use_container_width=True):
                noticia_adapt = {
                    "titulo": n["titulo"],
                    "resumen": n.get("resumen", n["titulo"]),
                    "fuente": n["fuente"],
                    "url": n["url"],
                    "fecha": n["fecha"],
                    "imagen": "",
                    "_sector": "banca",
                }
                st.session_state.noticia_elegida = noticia_adapt
                st.session_state.sector_elegido = "banca"
                st.session_state.fase = "elegir_tono"
                st.session_state.puntuacion = None
                st.session_state.post_en = ""
                st.session_state.carrusel_pdf = None
                st.rerun()
            st.markdown("<div style='margin-bottom:4px'></div>", unsafe_allow_html=True)

    # KPIs extraidos
    if st.session_state.ibex_kpi_data:
        kd = st.session_state.ibex_kpi_data
        st.markdown('<div class="section-label">💰 KPIs extraidos por IA</div>', unsafe_allow_html=True)
        periodo_txt = kd.get("periodo","")
        st.markdown(f'<div style="font-size:11px;color:#a78bfa;margin-bottom:8px">Periodo: {periodo_txt}</div>', unsafe_allow_html=True)

        kpis = kd.get("kpis",[])
        if kpis:
            cols_k = st.columns(len(kpis[:3]))
            for ci, k in enumerate(kpis[:3]):
                var = k.get("variacion_pct", 0) or 0
                col_var = "#4ade80" if var >= 0 else "#f87171"
                with cols_k[ci]:
                    st.markdown(f'<div class="dash-metric"><div class="dash-metric-num" style="font-size:20px">{k.get("valor",0):,.0f}</div><div class="dash-metric-label">{k.get("nombre","")} ({k.get("unidad","")})</div><div style="font-size:11px;color:{col_var};margin-top:4px">{var:+.1f}% vs anterior</div></div>'.replace(",","."), unsafe_allow_html=True)

        resumen_ej = kd.get("resumen_ejecutivo","")
        if resumen_ej:
            st.markdown(f'<div style="background:rgba(108,99,255,0.08);border-left:2px solid #6c63ff;border-radius:8px;padding:10px 14px;font-size:12px;color:#d0d0e0;margin-top:8px">{resumen_ej}</div>', unsafe_allow_html=True)

        # Historico
        if ibex_hist_key and cfg_ibex.get("historico",{}).get(ibex_hist_key):
            st.markdown(f'<div class="section-label">📊 Histórico: {ibex_hist_key}</div>', unsafe_allow_html=True)
            datos_h = cfg_ibex["historico"][ibex_hist_key]
            c1h, c2h, c3h = st.columns(3)
            ult_h = datos_h[-1]; penult_h = datos_h[-2] if len(datos_h)>=2 else None
            var_h = ((ult_h[1]-penult_h[1])/abs(penult_h[1])*100) if penult_h and penult_h[1]!=0 else 0
            c1h.metric(f"Ultimo ({ult_h[0]})", f"{ult_h[1]:,.0f}".replace(",","."))
            c2h.metric("Variacion", f"{var_h:+.1f}%")
            c3h.metric("Maximo", f"{max(d[1] for d in datos_h):,.0f}".replace(",","."))

        # Dashboards
        st.markdown('<div class="section-label">🖥️ Dashboard para LinkedIn</div>', unsafe_allow_html=True)
        col_ib1, col_ib2 = st.columns(2)
        with col_ib1:
            if st.button("📊  Estilo Power BI", use_container_width=True, key="btn_ibex_pbi"):
                with st.spinner("Generando dashboard..."):
                    st.session_state.ibex_dashboard_pbi = generar_dashboard_empresa_png(
                        empresa_sel, st.session_state.ibex_kpi_data, ibex_hist_key, "powerbi")
                    st.rerun()
        with col_ib2:
            if st.button("🌙  Estilo Dark", use_container_width=True, key="btn_ibex_dark"):
                with st.spinner("Generando dashboard..."):
                    st.session_state.ibex_dashboard_dark = generar_dashboard_empresa_png(
                        empresa_sel, st.session_state.ibex_kpi_data, ibex_hist_key, "dark")
                    st.rerun()

        if st.session_state.ibex_dashboard_pbi:
            st.markdown('<div style="font-size:11px;color:#a78bfa;font-weight:600;margin-top:12px;margin-bottom:6px">📊 ESTILO POWER BI</div>', unsafe_allow_html=True)
            st.image(st.session_state.ibex_dashboard_pbi, use_container_width=True)
            nom_e = re.sub(r"[^a-z0-9]+","_", empresa_sel.lower())
            st.download_button("⬇️  Descargar Power BI", data=st.session_state.ibex_dashboard_pbi,
                file_name=f"dashboard_pbi_{nom_e}.png", mime="image/png",
                use_container_width=True, key="dl_ibex_pbi")

        if st.session_state.ibex_dashboard_dark:
            st.markdown('<div style="font-size:11px;color:#6c63ff;font-weight:600;margin-top:12px;margin-bottom:6px">🌙 ESTILO DARK</div>', unsafe_allow_html=True)
            st.image(st.session_state.ibex_dashboard_dark, use_container_width=True)
            nom_e = re.sub(r"[^a-z0-9]+","_", empresa_sel.lower())
            st.download_button("⬇️  Descargar Dark", data=st.session_state.ibex_dashboard_dark,
                file_name=f"dashboard_dark_{nom_e}.png", mime="image/png",
                use_container_width=True, key="dl_ibex_dark")

        # Generar post
        st.markdown('<div class="section-label">✦ Generar post LinkedIn</div>', unsafe_allow_html=True)
        if not st.session_state.ibex_post_generado:
            col_it1, col_it2, col_it3 = st.columns(3)
            for ii, (tono_key, tono_cfg) in enumerate(TONOS.items()):
                with [col_it1, col_it2, col_it3][ii]:
                    if st.button(tono_cfg["label"], key=f"ibex_tono_{tono_key}", use_container_width=True):
                        with st.spinner("Gemini generando post..."):
                            post = generar_post_empresa(empresa_sel, st.session_state.ibex_kpi_data,
                                                        ibex_hist_key, tono_key)
                            st.session_state.ibex_post_generado = post
                            st.session_state.ibex_tono_elegido = tono_key
                            st.session_state.ibex_edicion_key += 1
                            st.rerun()
        else:
            tono_lbl = TONOS.get(st.session_state.ibex_tono_elegido,{}).get("label","")
            st.markdown(f'<div style="font-size:11px;color:#7070a0;margin-bottom:8px">Tono: {tono_lbl}</div>', unsafe_allow_html=True)
            post_edit_i = st.text_area("", value=st.session_state.ibex_post_generado, height=320,
                label_visibility="collapsed", key=f"ibex_editor_{st.session_state.ibex_edicion_key}")
            if post_edit_i != st.session_state.ibex_post_generado:
                st.session_state.ibex_post_generado = post_edit_i

            st.markdown('<div class="edicion-guiada-label">✨ Edicion guiada</div>', unsafe_allow_html=True)
            ie1, ie2, ie3 = st.columns(3)
            with ie1:
                if st.button("✂️ Mas corto", use_container_width=True, key="ibex_corto"):
                    with st.spinner("..."):
                        st.session_state.ibex_post_generado = editar_post_guiado(st.session_state.ibex_post_generado, "Reduce a maximo 150 palabras. Conserva datos clave y pregunta final.")
                        st.session_state.ibex_edicion_key += 1; st.rerun()
            with ie2:
                if st.button("🎣 Nuevo gancho", use_container_width=True, key="ibex_gancho"):
                    with st.spinner("..."):
                        st.session_state.ibex_post_generado = editar_post_guiado(st.session_state.ibex_post_generado, "Reescribe SOLO las primeras 1-2 lineas con el dato mas impactante. El resto igual.")
                        st.session_state.ibex_edicion_key += 1; st.rerun()
            with ie3:
                if st.button("🔥 Provocar debate", use_container_width=True, key="ibex_debate"):
                    with st.spinner("..."):
                        st.session_state.ibex_post_generado = cambiar_pregunta_final(st.session_state.ibex_post_generado, "debate")
                        st.session_state.ibex_edicion_key += 1; st.rerun()

            st.markdown("<hr>", unsafe_allow_html=True)
            ica1, ica2 = st.columns(2)
            with ica1:
                if st.button("📋  Copiar post", use_container_width=True, key="ibex_copiar"):
                    st.code(st.session_state.ibex_post_generado, language=None)
                    st.success("Copia el texto de arriba")
            with ica2:
                if st.button("📨  Enviar a Telegram", use_container_width=True, key="ibex_telegram"):
                    with st.spinner("Enviando..."):
                        nf = {"fuente": "CNMV / Prensa", "fecha": datetime.now().strftime("%d/%m/%Y"),
                              "url": st.session_state.ibex_noticias[0]["url"] if st.session_state.ibex_noticias else "",
                              "titulo": empresa_sel + " — Resultados " + kd.get("periodo","")}
                        ok = enviar_telegram(st.session_state.ibex_post_generado, nf)
                        if ok:
                            guardar_en_historial(st.session_state.ibex_post_generado, nf,
                                "banca", st.session_state.ibex_tono_elegido)
                            st.success("Enviado y guardado en historial.")
                        else: st.error("Error al enviar.")
            if st.button("🔄  Regenerar", use_container_width=True, key="ibex_regen"):
                st.session_state.ibex_post_generado = ""; st.session_state.ibex_edicion_key += 1; st.rerun()

    elif st.session_state.ibex_noticias and not st.session_state.ibex_kpi_data:
        st.info("No se encontraron noticias con KPIs financieros recientes. Puedes generar el dashboard y post con los datos históricos disponibles.")
        if st.button("📊 Generar con datos históricos", use_container_width=True, key="btn_ibex_historico"):
            cfg_emp = EMPRESAS_IBEX[empresa_sel]
            historico = cfg_emp.get("historico", {})
            kpis_hist = []
            for nombre_k, datos_k in historico.items():
                if not datos_k: continue
                ult = datos_k[-1]
                pen = datos_k[-2] if len(datos_k) >= 2 else None
                var = ((ult[1]-pen[1])/abs(pen[1])*100) if pen and pen[1]!=0 else 0
                kpis_hist.append({"nombre": nombre_k.split("(")[0].strip(), "valor": ult[1],
                                   "unidad": "%" if "%" in nombre_k else "M EUR", "variacion_pct": round(var,1)})
            ult_periodo = list(historico.values())[0][-1][0] if historico else "2025"
            st.session_state.ibex_kpi_data = {
                "periodo": ult_periodo, "encontrado": True, "kpis": kpis_hist[:3],
                "resumen_ejecutivo": f"Datos históricos oficiales de {empresa_sel}. Último dato: {ult_periodo}.",
                "noticia_principal": "", "fuente_principal": "Datos históricos", "fecha_noticia": datetime.now().strftime("%d/%m/%Y"),
            }
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver al inicio", key="ibex_volver"):
        st.session_state.fase = "inicio"
        st.rerun()

# ── COMPETENCIA ────────────────────────────────────────────────────────────────
elif st.session_state.fase == "competencia":
    st.markdown("""
    <div class="post-header">
        <div class="post-icon">🔍</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">¿Qué publica la competencia?</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">Análisis de contenido en LinkedIn por sector</div>
        </div>
    </div>""", unsafe_allow_html=True)
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","ia_negocio":"sector-pill-ia","ia_finanzas":"sector-pill-macro"}
    for sector_key, cfg in SECTORES.items():
        if st.button(cfg["etiqueta"], key=f"comp_{sector_key}", use_container_width=True):
            with st.spinner("Analizando..."):
                try:
                    data = analizar_competencia(sector_key)
                    st.session_state.competencia_data = data
                    st.session_state.competencia_sector = sector_key
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")
    if st.session_state.competencia_data:
        sector_key = st.session_state.competencia_sector
        cfg = SECTORES.get(sector_key, {})
        pill = pill_class.get(sector_key, "source-pill")
        st.markdown(f'<div style="margin:1rem 0 0.5rem"><span class="{pill}">{cfg.get("etiqueta","")}</span></div>', unsafe_allow_html=True)
        render_analisis_competencia(st.session_state.competencia_data)
    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver al inicio"):
        st.session_state.fase = "inicio"
        st.session_state.competencia_data = None
        st.rerun()

# ── HISTORIAL ──────────────────────────────────────────────────────────────────
elif st.session_state.fase == "historial":
    st.markdown("""<div class="post-header"><div class="post-icon">📚</div><div><div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">Historial de posts</div><div style="font-size:12px;color:#7070a0;margin-top:2px">Guardado en Supabase</div></div></div>""", unsafe_allow_html=True)
    render_historial()
    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver al inicio"):
        st.session_state.fase = "inicio"
        st.rerun()

# ── NOTICIAS ───────────────────────────────────────────────────────────────────
elif st.session_state.fase == "noticias":
    st.markdown('<div class="section-label">Elige una noticia</div>', unsafe_allow_html=True)
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","ia_negocio":"sector-pill-ia","ia_finanzas":"sector-pill-macro"}

    for i, n in enumerate(st.session_state.noticias):
        sector = n.get("_sector","")
        cfg = SECTORES.get(sector,{})
        etiqueta = cfg.get("etiqueta",sector)
        pill = pill_class.get(sector,"source-pill")
        resumen_limpio = n["resumen"].replace("<","").replace(">","").replace("&","&amp;")[:280]
        st.markdown(f"""
        <div class="news-card">
            <div class="card-meta"><span class="{pill}">{etiqueta}</span><span class="source-pill">{n['fuente']}</span><span class="date-pill">🗓 {n['fecha']}</span></div>
            <div class="card-title">{n['titulo']}</div>
            <div class="card-desc">{resumen_limpio}</div>
        </div>""", unsafe_allow_html=True)

        # ── Botones Seleccionar + Cambiar ──────────────────────────────────────
        col_sel, col_ref = st.columns([3, 1])
        with col_sel:
            if st.button("✦  Seleccionar esta noticia", key=f"sel_{i}", use_container_width=True):
                st.session_state.noticia_elegida = n
                st.session_state.sector_elegido = sector
                st.session_state.fase = "elegir_tono"
                st.rerun()
        with col_ref:
            if st.button("↺ Cambiar", key=f"ref_{i}", use_container_width=True):
                with st.spinner("Buscando otra noticia..."):
                    urls_actuales = [x.get("url","") for x in st.session_state.noticias]
                    nueva = parsear_un_feed(sector, urls_actuales + st.session_state.usadas)
                    if nueva:
                        st.session_state.noticias[i] = nueva
                    st.rerun()

        st.markdown("<div style='margin-bottom:0.8rem'></div>", unsafe_allow_html=True)

    st.markdown('<div class="section-label">O analiza datos reales</div>', unsafe_allow_html=True)
    col_fmacro, col_fia = st.columns(2)
    with col_fmacro:
        st.markdown("""<div class="news-card" style="border-color:rgba(16,185,129,0.3);background:rgba(16,185,129,0.04)">
            <div class="card-meta"><span class="sector-pill-macro">📈 Macro &amp; Economía</span></div>
            <div class="card-title" style="font-size:0.9rem">Tipos BCE, IPC, PIB, Paro</div>
            <div class="card-desc">Datos reales del BCE e INE. Gráfico PNG descargable + post con predicción de futuro.</div>
        </div>""", unsafe_allow_html=True)
        if st.button("✦  Análisis Macro", use_container_width=True, key="sel_macro"):
            st.session_state.datos_sector = "macro"
            st.session_state.indicador_elegido = None
            st.session_state.datos_grafico_png = None
            st.session_state.datos_post_generado = ""
            st.session_state.fase = "datos_sector"
            st.rerun()
    with col_fia:
        st.markdown("""<div class="news-card" style="border-color:rgba(239,68,68,0.3);background:rgba(239,68,68,0.04)">
            <div class="card-meta"><span class="sector-pill-ia_tech">🤖 IA &amp; Tech Empresarial</span></div>
            <div class="card-title" style="font-size:0.9rem">Adopción IA, Cloud, Big Data</div>
            <div class="card-desc">Datos reales de Eurostat. Gráfico PNG descargable + post con reflexión de futuro.</div>
        </div>""", unsafe_allow_html=True)
        if st.button("✦  Análisis IA & Tech", use_container_width=True, key="sel_ia_tech"):
            st.session_state.datos_sector = "ia_tech"
            st.session_state.indicador_elegido = None
            st.session_state.datos_grafico_png = None
            st.session_state.datos_post_generado = ""
            st.session_state.fase = "datos_sector"
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver"):
        st.session_state.fase = "inicio"
        st.session_state.noticias = []
        st.rerun()

# ── ELEGIR TONO ────────────────────────────────────────────────────────────────
elif st.session_state.fase == "elegir_tono":
    n = st.session_state.noticia_elegida
    sector = st.session_state.sector_elegido
    cfg = SECTORES.get(sector,{})
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","ia_negocio":"sector-pill-ia","ia_finanzas":"sector-pill-macro"}
    pill = pill_class.get(sector,"source-pill")
    st.markdown("""
    <div class="post-header">
        <div class="post-icon">🎯</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">¿Qué quieres transmitir hoy?</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">El tono define cómo te percibirá tu audiencia</div>
        </div>
    </div>""", unsafe_allow_html=True)
    st.markdown(f'<div style="display:flex;gap:8px;align-items:center;margin-bottom:1.5rem;flex-wrap:wrap"><span class="{pill}">{cfg.get("etiqueta","")}</span><span class="source-pill">{n["fuente"]}</span><span class="date-pill">🗓 {n["fecha"]}</span></div><div class="card-title" style="margin-bottom:1.5rem">{n["titulo"]}</div>', unsafe_allow_html=True)
    for tono_key, tono_cfg in TONOS.items():
        if st.button(tono_cfg["label"], key=f"tono_{tono_key}", use_container_width=True):
            perfil = cfg.get("perfil","consultor junior")
            st.session_state.tono_elegido = tono_key
            with st.spinner("Gemini está generando 2 versiones del post..."):
                post_a, post_b, recomendada, razon = generar_dos_posts(n, perfil, tono_key)
                st.session_state.post_a = post_a
                st.session_state.post_b = post_b
                st.session_state.recomendada = recomendada
                st.session_state.razon = razon
                st.session_state.puntuacion = None
                st.session_state.post_en = ""
                st.session_state.carrusel_pdf = None
                st.session_state.usadas.append(n["url"])
                st.session_state.fase = "elegir_post"
                st.rerun()
    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver a noticias"):
        st.session_state.fase = "noticias"
        st.rerun()

# ── ELEGIR POST ────────────────────────────────────────────────────────────────
elif st.session_state.fase == "elegir_post":
    tono_label = TONOS.get(st.session_state.tono_elegido,{}).get("label","")
    st.markdown(f"""
    <div class="post-header">
        <div class="post-icon">✦</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">Elige tu versión</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">Tono: {tono_label} · La versión en verde es la recomendada</div>
        </div>
    </div>""", unsafe_allow_html=True)
    rec = st.session_state.recomendada
    razon = st.session_state.razon
    render_opcion(st.session_state.post_a,"Versión A — Analítica",(rec=="A"),razon if rec=="A" else "","elegir_a")
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)
    render_opcion(st.session_state.post_b,"Versión B — Reflexiva",(rec=="B"),razon if rec=="B" else "","elegir_b")
    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver a noticias"):
        st.session_state.fase = "noticias"
        st.rerun()

# ── POST FINAL ─────────────────────────────────────────────────────────────────
elif st.session_state.fase == "post":
    n = st.session_state.noticia_elegida
    sector = st.session_state.sector_elegido
    cfg = SECTORES.get(sector,{})
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","ia_negocio":"sector-pill-ia","ia_finanzas":"sector-pill-macro"}
    pill = pill_class.get(sector,"source-pill")
    etiqueta = cfg.get("etiqueta","")
    tono_label = TONOS.get(st.session_state.tono_elegido,{}).get("label","")

    st.markdown("""
    <div class="post-header">
        <div class="post-icon">✦</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">Post listo</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">Revisa, edita y publica en LinkedIn</div>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:1rem;flex-wrap:wrap">
        <span class="{pill}">{etiqueta}</span>
        <span class="source-pill">{tono_label}</span>
        <span class="source-pill">{n['fuente']}</span>
        <span class="date-pill">🗓 {n['fecha']}</span>
        <a href="{n['url']}" target="_blank" style="font-size:11px;color:#6c63ff;text-decoration:none">Ver noticia original ↗</a>
    </div>""", unsafe_allow_html=True)

    render_imagen_noticia(n)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["✏️ Editar", "🎨 Carrusel PDF", "🌍 Inglés", "👁️ Vista previa", "📊 Puntuación"])

    with tab1:
        post_editado = st.text_area(label="", value=st.session_state.post_generado,
            height=320, label_visibility="collapsed", key=f"editor_{st.session_state.edicion_key}")
        if post_editado != st.session_state.post_generado:
            st.session_state.post_generado = post_editado
        st.markdown('<div class="edicion-guiada-label">✨ Edición guiada</div>', unsafe_allow_html=True)
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            if st.button("✂️ Más corto", use_container_width=True, key="ed_corto"):
                with st.spinner("Condensando..."):
                    st.session_state.post_generado = editar_post_guiado(st.session_state.post_generado,"Reduce a máximo 150 palabras. Conserva mejores insights y pregunta final.")
                    st.session_state.puntuacion = None; st.session_state.edicion_key += 1; st.rerun()
        with col_e2:
            if st.button("🎣 Nuevo gancho", use_container_width=True, key="ed_gancho"):
                with st.spinner("Reescribiendo gancho..."):
                    st.session_state.post_generado = editar_post_guiado(st.session_state.post_generado,"Reescribe SOLO las primeras 1-2 líneas con un gancho más impactante. El resto igual.")
                    st.session_state.puntuacion = None; st.session_state.edicion_key += 1; st.rerun()
        with col_e3:
            if st.button("📊 Añade dato", use_container_width=True, key="ed_dato"):
                with st.spinner("Añadiendo dato..."):
                    st.session_state.post_generado = editar_post_guiado(st.session_state.post_generado,"Incorpora un dato, cifra o estadística concreta. Si no hay, invéntalo de forma verosímil.")
                    st.session_state.puntuacion = None; st.session_state.edicion_key += 1; st.rerun()

        st.markdown('<div class="edicion-guiada-label">🔄 Cambiar pregunta final</div>', unsafe_allow_html=True)
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            if st.button("💪 A favor del tema", use_container_width=True, key="preg_favor"):
                with st.spinner("Reescribiendo pregunta..."):
                    st.session_state.post_generado = cambiar_pregunta_final(st.session_state.post_generado, "favor")
                    st.session_state.puntuacion = None; st.session_state.edicion_key += 1; st.rerun()
        with col_p2:
            if st.button("🔥 Provocar debate", use_container_width=True, key="preg_debate"):
                with st.spinner("Reescribiendo pregunta..."):
                    st.session_state.post_generado = cambiar_pregunta_final(st.session_state.post_generado, "debate")
                    st.session_state.puntuacion = None; st.session_state.edicion_key += 1; st.rerun()
        with col_p3:
            if st.button("💭 Reflexión abierta", use_container_width=True, key="preg_reflexion"):
                with st.spinner("Reescribiendo pregunta..."):
                    st.session_state.post_generado = cambiar_pregunta_final(st.session_state.post_generado, "reflexion")
                    st.session_state.puntuacion = None; st.session_state.edicion_key += 1; st.rerun()

    with tab2:
        st.markdown('<div class="section-label">🎨 Carrusel PDF para LinkedIn</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#7070a0;margin-bottom:1rem">Genera un PDF vertical listo para subir directamente a LinkedIn como carrusel</div>', unsafe_allow_html=True)
        if not st.session_state.carrusel_pdf:
            if st.button("🎨  Generar carrusel PDF", use_container_width=True, key="gen_carrusel"):
                with st.spinner("Gemini estructurando el carrusel..."):
                    try:
                        contenido = generar_contenido_carrusel(st.session_state.post_generado, n, sector)
                        with st.spinner("Generando el PDF..."):
                            pdf_bytes = crear_carrusel_pdf(contenido)
                            st.session_state.carrusel_pdf = pdf_bytes
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error generando carrusel: {e}")
        else:
            st.success("✅ Carrusel PDF generado correctamente")
            titulo_archivo = re.sub(r'[^a-z0-9]+', '_', n.get("titulo","carrusel").lower())[:30]
            st.download_button(
                label="⬇️  Descargar carrusel.pdf",
                data=st.session_state.carrusel_pdf,
                file_name=f"carrusel_{titulo_archivo}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            st.markdown('<div style="font-size:12px;color:#7070a0;margin-top:8px">💡 Descarga el PDF y súbelo directamente a LinkedIn como documento — aparecerá como carrusel</div>', unsafe_allow_html=True)
            if st.button("🔄  Regenerar carrusel", use_container_width=False, key="regen_carrusel"):
                st.session_state.carrusel_pdf = None
                st.rerun()

    with tab3:
        st.markdown('<div class="section-label">Versión adaptada al inglés</div>', unsafe_allow_html=True)
        if not st.session_state.post_en:
            if st.button("🌍  Generar versión en inglés", use_container_width=True, key="gen_en"):
                with st.spinner("Adaptando al inglés..."):
                    st.session_state.post_en = traducir_post_ingles(st.session_state.post_generado)
                    st.rerun()
        else:
            post_en_editado = st.text_area(label="", value=st.session_state.post_en,
                height=320, label_visibility="collapsed", key="editor_en")
            st.session_state.post_en = post_en_editado
            col_en1, col_en2 = st.columns(2)
            with col_en1:
                if st.button("📋  Copiar en inglés", use_container_width=True, key="copy_en"):
                    st.code(st.session_state.post_en, language=None)
                    st.success("Copia el texto de arriba ↑")
            with col_en2:
                if st.button("📨  Telegram (inglés)", use_container_width=True, key="tg_en"):
                    with st.spinner("Enviando..."):
                        ok = enviar_telegram(st.session_state.post_en, n)
                        st.success("✅ Enviado." if ok else "❌ Error.")
            if st.button("🔄  Regenerar en inglés", use_container_width=False, key="regen_en"):
                st.session_state.post_en = ""
                st.rerun()

    with tab4:
        st.markdown('<div class="section-label">Así se verá en LinkedIn</div>', unsafe_allow_html=True)
        render_linkedin_preview(st.session_state.post_generado)

    with tab5:
        if st.session_state.puntuacion is None:
            if st.button("📊  Analizar y puntuar post", use_container_width=True):
                with st.spinner("Gemini está analizando tu post..."):
                    try:
                        st.session_state.puntuacion = puntuar_post(st.session_state.post_generado)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al puntuar: {e}")
        else:
            render_puntuacion(st.session_state.puntuacion)
            if st.button("🔄  Volver a puntuar"):
                st.session_state.puntuacion = None
                st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋  Copiar post", use_container_width=True):
            st.code(st.session_state.post_generado, language=None)
            st.success("Copia el texto de arriba ↑")
    with col2:
        if st.button("📨  Enviar a Telegram", use_container_width=True, type="primary"):
            with st.spinner("Enviando..."):
                ok = enviar_telegram(st.session_state.post_generado, n)
                if ok:
                    guardar_en_historial(st.session_state.post_generado, n, sector, st.session_state.tono_elegido)
                    st.success("✅ Enviado a Telegram y guardado en historial.")
                else:
                    st.error("❌ Error al enviar.")

    st.markdown("<hr>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    with col3:
        if st.button("🔄  Regenerar post", use_container_width=True):
            perfil = cfg.get("perfil","consultor junior")
            with st.spinner("Regenerando con Gemini..."):
                st.session_state.post_generado = generar_post(n, perfil, st.session_state.tono_elegido)
                st.session_state.puntuacion = None
                st.session_state.post_en = ""
                st.session_state.carrusel_pdf = None
                st.session_state.edicion_key += 1
                st.rerun()
    with col4:
        if st.button("← Buscar más noticias", use_container_width=True):
            st.session_state.fase = "inicio"
            st.session_state.noticias = []
            st.session_state.post_generado = ""
            st.session_state.noticia_elegida = None
            st.session_state.puntuacion = None
            st.session_state.sector_elegido = ""
            st.session_state.post_en = ""
            st.session_state.carrusel_pdf = None
            st.rerun()
