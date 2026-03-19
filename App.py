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
# Datos + BI — fuentes 100% especializadas en datos y negocio
RSS_DATOS = [
    ("Datanalytics",             "https://www.datanalytics.com/feed/"),
    ("Analytics Lane",           "https://www.analyticslane.com/feed/"),
    ("BBVA Open Mind",           "https://www.bbvaopenmind.com/feed/"),
    ("Silicon.es",               "https://www.silicon.es/feed"),
    ("El Economista - Empresas", "https://www.eleconomista.es/rss/rss-empresas.php"),
]
# IA — fuentes tech empresarial especializadas (Microsoft, Google, IA en empresa)
RSS_IA = [
    ("Silicon.es",               "https://www.silicon.es/feed"),
    ("Muycomputer",              "https://www.muycomputer.com/feed/"),
    ("Hipertextual",             "https://hipertextual.com/feed"),
    ("El Referente",             "https://elreferente.es/feed/"),
    ("El Economista - Tech",     "https://www.eleconomista.es/rss/rss-tecnologia.php"),
]

KEYWORDS_BANCA = ["banco","banca","financiero","finanzas","crédito","hipoteca","tipos de interés","BCE","banco central","entidad financiera","inversión","bolsa","mercado","deuda","capital","fondo","dividendo","acción","cotización","préstamo","morosidad","regulación bancaria"]
KEYWORDS_ESTRATEGIA = ["estrategia","empresa","CEO","directivo","fusión","adquisición","resultado","beneficio","facturación","negocio","mercado","competencia","innovación","transformación","consultor","management","liderazgo","startup","venture","inteligencia artificial","IA","digital"]
KEYWORDS_DATOS = ["business intelligence","BI","analítica de datos","cuadro de mando","dashboard","power bi","tableau","data warehouse","ETL","lago de datos","modelo predictivo","ciencia de datos","data science","analista de datos","visualización de datos","gobernanza del dato","arquitectura de datos","KPI","reporting","minería de datos"]
KEYWORDS_IA = ["Microsoft IA","Google IA","OpenAI","Gemini","Copilot","Azure IA","Google Cloud IA","lanzamiento IA","inversión IA","IA empresarial","IA generativa empresa","adopción IA empresa","productividad IA","automatización empresarial","transformación digital IA","IA y negocio","herramienta IA","modelo lenguaje empresa","IA aplicada negocio","startup IA"]

SECTORES = {
    "banca":      {"feeds": RSS_BANCA,      "etiqueta": "🏦 Banca",                  "perfil": "consultor de banca y finanzas",  "keywords": KEYWORDS_BANCA},
    "estrategia": {"feeds": RSS_ESTRATEGIA, "etiqueta": "♟️ Estrategia",             "perfil": "consultor de estrategia",        "keywords": KEYWORDS_ESTRATEGIA},
    "datos":      {"feeds": RSS_DATOS,      "etiqueta": "📊 Datos & BI",              "perfil": "analista de datos y BI",         "keywords": KEYWORDS_DATOS},
    "ia":         {"feeds": RSS_IA,         "etiqueta": "🤖 Inteligencia Artificial", "perfil": "consultor de IA",               "keywords": KEYWORDS_IA},
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

# Palabras negativas — descartan noticias irrelevantes o dañinas para el perfil
PALABRAS_NEGATIVAS_IA = [
    "peligro","peligros","acoso","menor","menores","niño","niños","adolescente",
    "demanda","denuncia","delito","abuso","violencia","pornografía","desnudo",
    "auricular","auriculares","smartphone","móvil","consola","videojuego",
    "coche eléctrico","vehículo","automóvil","televisor","tablet","reloj inteligente",
    "precio","oferta","compra","tienda","amazon","rebaja",
]
PALABRAS_NEGATIVAS_DATOS = [
    "coche eléctrico","vehículo","automóvil","ayuda industrial","subvención coche",
    "auricular","smartphone","consola","videojuego","televisor",
    "precio","oferta","compra","tienda","rebaja",
    "peligro","acoso","menor","demanda judicial","denuncia",
]

def es_noticia_valida(titulo, resumen, sector):
    """Descarta noticias con palabras negativas según el sector."""
    texto = (titulo + " " + resumen).lower()
    lista = PALABRAS_NEGATIVAS_IA if sector == "ia" else PALABRAS_NEGATIVAS_DATOS if sector == "datos" else []
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
    hace_5_dias = datetime.now() - timedelta(days=5)
    cfg = SECTORES[sector]
    keywords = cfg.get("keywords", [])
    feeds = list(cfg["feeds"])
    random.shuffle(feeds)
    for fuente, url in feeds:
        try:
            feed = feedparser.parse(url)
            entradas = [e for e in feed.entries if e.get("link","") not in excluir_urls]
            random.shuffle(entradas)
            for entry in entradas[:10]:
                published = None
                if hasattr(entry,"published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                if published and published < hace_5_dias: continue
                resumen = entry.get("summary", entry.get("description",""))[:400]
                titulo = entry.get("title","")
                if not titulo or len(resumen) < 80: continue
                if keywords and not es_relevante(titulo, resumen, keywords): continue
                if not es_noticia_valida(titulo, resumen, sector): continue
                return {"fuente": fuente, "titulo": titulo, "resumen": resumen,
                        "url": entry.get("link",""),
                        "fecha": published.strftime("%d/%m/%Y") if published else "reciente",
                        "imagen": extraer_imagen(entry), "_sector": sector}
        except Exception: pass
    # Respaldo NewsAPI para BI e IA si RSS no encuentra nada
    NEWSAPI_QUERIES = {
        "datos": ('("business intelligence" OR "analítica de datos" OR "data warehouse" OR "ciencia de datos")', "NewsAPI BI"),
        "ia":    ('("Microsoft IA" OR "Google IA" OR "OpenAI" OR "Gemini" OR "Copilot" OR "IA empresarial" OR "adopción inteligencia artificial")', "NewsAPI IA"),
    }
    if sector in NEWSAPI_QUERIES:
        query, label = NEWSAPI_QUERIES[sector]
        arts = _newsapi_buscar(query, label)
        for art in arts:
            if art["url"] in excluir_urls: continue
            if es_relevante(art["titulo"], art["resumen"], keywords) and es_noticia_valida(art["titulo"], art["resumen"], sector):
                art["_sector"] = sector
                return art
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


def fetch_noticias_por_sector():
    hace_5_dias = datetime.now() - timedelta(days=5)

    def parsear_rss(feeds, keywords):
        noticias = []
        for fuente, url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:6]:
                    published = None
                    if hasattr(entry,"published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])
                    if published and published < hace_5_dias: continue
                    titulo = entry.get("title","")
                    resumen = entry.get("summary", entry.get("description",""))[:400]
                    if not titulo or len(resumen) < 80: continue
                    if keywords and not es_relevante(titulo, resumen, keywords): continue
                    if not es_noticia_valida(titulo, resumen, sector): continue
                    noticias.append({"fuente": fuente, "titulo": titulo, "resumen": resumen,
                        "url": entry.get("link",""),
                        "fecha": published.strftime("%d/%m/%Y") if published else "reciente",
                        "imagen": extraer_imagen(entry)})
            except Exception: pass
        return noticias

    # Queries NewsAPI por sector (solo para BI e IA donde RSS falla más)
    NEWSAPI_QUERIES = {
        "datos": ('("business intelligence" OR "analítica de datos" OR "data warehouse" OR "cuadro de mando" OR "ciencia de datos")', "NewsAPI BI"),
        "ia":    ('("Microsoft IA" OR "Google IA" OR "OpenAI" OR "Gemini" OR "Copilot" OR "IA empresarial" OR "IA generativa empresa" OR "adopción inteligencia artificial")', "NewsAPI IA"),
    }

    resultado = {}
    for sector, cfg in SECTORES.items():
        keywords = cfg.get("keywords", [])
        # 1. Intentar RSS primero
        pool = parsear_rss(cfg["feeds"], keywords)
        # 2. Si es BI o IA y el pool está vacío o pequeño, completar con NewsAPI
        if sector in NEWSAPI_QUERIES and len(pool) < 3:
            query, label = NEWSAPI_QUERIES[sector]
            api_arts = _newsapi_buscar(query, label)
            # Filtrar por keywords también
            for art in api_arts:
                if es_relevante(art["titulo"], art["resumen"], keywords) and es_noticia_valida(art["titulo"], art["resumen"], sector):
                    pool.append(art)
        resultado[sector] = random.choice(pool) if pool else None
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
                  ("datos_li_guardados",None)]:
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
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","datos":"sector-pill-datos","ia":"sector-pill-ia"}
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
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","datos":"sector-pill-datos","ia":"sector-pill-ia"}

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
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","datos":"sector-pill-datos","ia":"sector-pill-ia"}
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
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","datos":"sector-pill-datos","ia":"sector-pill-ia"}
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
