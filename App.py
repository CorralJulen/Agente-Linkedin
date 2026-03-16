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
    ("Harvard Business Review ES", "https://hbr.org/subscriber-content/feed"),
    ("MIT Sloan",                  "https://sloanreview.mit.edu/feed/"),
]
RSS_DATOS = [
    ("El Confidencial - Tech", "https://www.elconfidencial.com/rss/tecnologia/"),
    ("Xataka",                 "https://feeds.weblogssl.com/xataka"),
    ("MIT Technology Review",  "https://www.technologyreview.com/feed/"),
    ("VentureBeat AI",         "https://venturebeat.com/ai/feed/"),
    ("The Batch",              "https://www.deeplearning.ai/the-batch/feed/"),
]
KEYWORDS_BANCA = ["banco","banca","financiero","finanzas","crédito","hipoteca","tipos de interés","BCE","banco central","entidad financiera","inversión","bolsa","mercado","deuda","capital","fondo","dividendo","acción","cotización","préstamo","morosidad","regulación bancaria"]
KEYWORDS_ESTRATEGIA = ["estrategia","empresa","CEO","directivo","fusión","adquisición","resultado","beneficio","facturación","negocio","mercado","competencia","innovación","transformación","consultor","management","liderazgo","startup","venture","inteligencia artificial","IA","digital"]
KEYWORDS_DATOS = ["inteligencia artificial","IA","machine learning","big data","datos","algoritmo","modelo","ChatGPT","LLM","automatización","analytics","tecnología","digital","software","plataforma","cloud","ciberseguridad","robot","deep learning","neural","OpenAI","Google","Microsoft","Meta"]

SECTORES = {
    "banca":      {"feeds": RSS_BANCA,      "etiqueta": "🏦 Banca",            "perfil": "consultor de banca y finanzas",  "keywords": KEYWORDS_BANCA},
    "estrategia": {"feeds": RSS_ESTRATEGIA, "etiqueta": "♟️ Estrategia & IA",  "perfil": "consultor de estrategia e IA",   "keywords": KEYWORDS_ESTRATEGIA},
    "datos":      {"feeds": RSS_DATOS,      "etiqueta": "📊 Analista de Datos", "perfil": "analista de datos",              "keywords": KEYWORDS_DATOS},
}
TONOS = {
    "aprendiendo": {"label": "🎓 Estoy aprendiendo",    "instruccion": "Escribe desde la perspectiva de alguien que está aprendiendo y reflexionando sobre el sector. Muestra curiosidad y ganas de crecer."},
    "senior":      {"label": "💼 Quiero parecer senior", "instruccion": "Escribe con tono experto y seguro. Analiza con criterio profesional, usa terminología del sector con naturalidad."},
    "debate":      {"label": "🔥 Quiero generar debate",  "instruccion": "Escribe con una opinión fuerte y provocadora. Toma partido, cuestiona el status quo, invita a la discusión."},
}

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# ── Página ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="LinkedIn Agent", page_icon="⚡", layout="centered")
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
.stButton > button { font-family: 'Syne', sans-serif !important; font-weight: 700 !important; border-radius: 14px !important; border: none !important; transition: all 0.2s !important; background: linear-gradient(135deg, #e03131, #c92a2a) !important; color: white !important; box-shadow: 0 4px 18px rgba(224,49,49,0.35) !important; }
.stButton > button:hover { background: linear-gradient(135deg, #c92a2a, #b02020) !important; }
hr { border-color: rgba(255,255,255,0.07) !important; margin: 1.5rem 0 !important; }
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────

def es_relevante(titulo, resumen, keywords):
    texto = (titulo + " " + resumen).lower()
    return any(kw.lower() in texto for kw in keywords)

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
    st.session_state.historial.insert(0, {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "titulo": noticia.get("titulo",""),
        "fuente": noticia.get("fuente",""),
        "sector": etiqueta, "tono": tono_label,
        "preview": post[:200],
    })

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
                return {"fuente": fuente, "titulo": titulo, "resumen": resumen,
                        "url": entry.get("link",""),
                        "fecha": published.strftime("%d/%m/%Y") if published else "reciente",
                        "imagen": extraer_imagen(entry), "_sector": sector}
        except Exception: pass
    return None

# ── Funciones Gemini ───────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_noticias_por_sector():
    hace_5_dias = datetime.now() - timedelta(days=5)
    def parsear(feeds, keywords):
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
                    noticias.append({"fuente": fuente, "titulo": titulo, "resumen": resumen,
                        "url": entry.get("link",""),
                        "fecha": published.strftime("%d/%m/%Y") if published else "reciente",
                        "imagen": extraer_imagen(entry)})
            except Exception: pass
        return noticias
    resultado = {}
    for sector, cfg in SECTORES.items():
        pool = parsear(cfg["feeds"], cfg.get("keywords",[]))
        resultado[sector] = random.choice(pool) if pool else None
    return resultado

def generar_dos_posts(noticia, perfil, tono):
    client = genai.Client(api_key=GEMINI_API_KEY)
    instruccion_tono = TONOS.get(tono, TONOS["aprendiendo"])["instruccion"]
    base = f"""Eres un {perfil} junior. MSc Big Data, IA y Business Analytics en curso.
NOTICIA: {noticia['titulo']} | {noticia['fuente']} | {noticia['resumen']}
TONO: {instruccion_tono}
Post ESPAÑOL 150-250 palabras. Gancho → análisis → pregunta abierta. 3-5 insights. 5-8 hashtags. NO menciones IA. SOLO el texto."""
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
    prompt = f"""Eres un {perfil} junior. MSc Big Data, IA y Business Analytics.
NOTICIA: {noticia['titulo']} | {noticia['fuente']} | {noticia['resumen']}
TONO: {instruccion_tono}
Post ESPAÑOL 150-250 palabras. Gancho → análisis → pregunta. 3-5 insights. 5-8 hashtags. NO IA. SOLO texto."""
    return client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()

def editar_post_guiado(post, instruccion):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Editor experto LinkedIn. POST:\n{post}\nINSTRUCCIÓN: {instruccion}\nApplica SOLO el cambio. Devuelve SOLO el post modificado."""
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
{{
  "formatos_populares": ["formato1", "formato2", "formato3", "formato4"],
  "temas_trending": ["tema1", "tema2", "tema3", "tema4", "tema5"],
  "ganchos_efectivos": ["ejemplo gancho 1", "ejemplo gancho 2", "ejemplo gancho 3"],
  "hashtags_top": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5", "#hashtag6"],
  "mejor_dia_hora": "día y hora con más engagement",
  "consejo_diferenciacion": "Un consejo concreto de 2-3 frases para diferenciarte de la competencia en este sector",
  "error_comun": "El error más común que cometen los profesionales junior en este sector en LinkedIn"
}}"""
    raw = client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()
    return json.loads(raw.replace("```json","").replace("```","").strip())

def generar_contenido_carrusel(post, noticia, sector):
    client = genai.Client(api_key=GEMINI_API_KEY)
    etiqueta = SECTORES.get(sector, {}).get("etiqueta", sector)
    prompt = f"""Convierte este post de LinkedIn en un carrusel de 5 slides profesional.

POST ORIGINAL:
{post}

NOTICIA BASE: {noticia.get('titulo','')}
SECTOR: {etiqueta}

Devuelve SOLO un JSON válido sin markdown:
{{
  "sector": "{etiqueta}",
  "titulo_portada": "Título impactante máximo 8 palabras",
  "subtitulo_portada": "Subtítulo explicativo máximo 12 palabras",
  "slides": [
    {{"titulo": "Título slide 1 (máx 6 palabras)", "cuerpo": "Texto del slide 1 (2-3 frases cortas, concretas)", "dato_destacado": "Dato o cifra llamativa opcional, si no hay pon null"}},
    {{"titulo": "Título slide 2", "cuerpo": "Texto slide 2", "dato_destacado": null}},
    {{"titulo": "Título slide 3", "cuerpo": "Texto slide 3", "dato_destacado": "cifra o stat"}},
    {{"titulo": "Título slide 4", "cuerpo": "Texto slide 4", "dato_destacado": null}},
    {{"titulo": "Título slide 5", "cuerpo": "Texto slide 5", "dato_destacado": null}}
  ],
  "pregunta_final": "Pregunta provocadora para generar debate (máx 15 palabras)",
  "cta": "Sígueme para más análisis sobre {etiqueta} · Comenta tu opinión"
}}"""
    raw = client.models.generate_content(model="gemini-flash-latest", contents=prompt).text.strip()
    return json.loads(raw.replace("```json","").replace("```","").strip())

# ── Generador de carrusel PDF — Python puro, sin Node.js ─────────────────────
def crear_carrusel_pdf(contenido: dict) -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    import io

    W, H = landscape(A4)
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
        c.setFillColor(MUT); c.setFont("Helvetica", 9)
        c.drawRightString(W - 18, 16, f"{num} / {total}")

    def draw_portada(c, data, total):
        base(c, 1, total)
        c.setFillColor(PUR); c.setFillAlpha(0.13)
        c.circle(W - 60, H + 10, 220, fill=1, stroke=0)
        c.setFillAlpha(1.0)
        c.setFillColor(PUR); c.rect(0, 0, 7, H, fill=1, stroke=0)
        sector_txt = data.get("sector","").replace("🏦","").replace("♟️","").replace("📊","").strip().upper()
        bw = max(150, c.stringWidth(sector_txt, "Helvetica-Bold", 9) + 32)
        c.setFillColor(colors.HexColor("#1a1830"))
        c.roundRect(28, H - 60, bw, 26, 13, fill=1, stroke=0)
        c.setStrokeColor(PUR); c.setLineWidth(0.8)
        c.roundRect(28, H - 60, bw, 26, 13, fill=0, stroke=1)
        c.setFillColor(PURT); c.setFont("Helvetica-Bold", 9)
        c.drawString(28 + 14, H - 47, sector_txt)
        titulo_lines = wrap(c, data.get("titulo_portada",""), "Helvetica-Bold", 46, W * 0.62)
        c.setFillColor(TXT); y = H - 135
        for line in titulo_lines[:3]:
            c.setFont("Helvetica-Bold", 46); c.drawString(28, y, line); y -= 62
        c.setFillColor(MUT); c.setFont("Helvetica", 18)
        c.drawString(28, y - 10, data.get("subtitulo_portada","")[:70])
        c.setFillColor(MUT); c.setFont("Helvetica", 11)
        c.drawString(28, 32, "Julen · Business & Data Analytics · MSc Big Data & IA")
        c.showPage()

    def draw_contenido(c, slide, idx, total):
        base(c, idx + 2, total)
        c.setFillColor(PUR); c.rect(0, H - 6, W, 6, fill=1, stroke=0)
        c.setFillColor(PUR); c.circle(46, H - 52, 26, fill=1, stroke=0)
        c.setFillColor(WHT); c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(46, H - 60, str(idx + 1))
        c.setFillColor(TXT); c.setFont("Helvetica-Bold", 28)
        c.drawString(86, H - 64, slide.get("titulo","")[:52])
        c.setStrokeColor(colors.HexColor("#2a2a3e")); c.setLineWidth(1.5)
        c.line(20, H - 88, W - 20, H - 88)
        cuerpo = slide.get("cuerpo","")
        dato = slide.get("dato_destacado")
        MARGIN_BOTTOM = 36
        if dato:
            cuerpo_lines = wrap(c, cuerpo, "Helvetica", 19, W * 0.52)
            c.setFillColor(TXT); y = H - 122
            for line in cuerpo_lines:
                c.setFont("Helvetica", 19); c.drawString(22, y, line); y -= 30
            bx = W * 0.60; by = MARGIN_BOTTOM; bw2 = W * 0.36; bh = H - 100 - MARGIN_BOTTOM
            c.setFillColor(CARD); c.roundRect(bx, by, bw2, bh, 12, fill=1, stroke=0)
            c.setStrokeColor(PUR); c.setLineWidth(1.5)
            c.roundRect(bx, by, bw2, bh, 12, fill=0, stroke=1)
            c.setFillColor(PUR); c.rect(bx + 16, by + bh - 5, bw2 - 32, 5, fill=1, stroke=0)
            dato_lines = wrap(c, dato, "Helvetica-Bold", 22, bw2 - 40)
            total_h_dato = len(dato_lines) * 32
            dy = by + bh / 2 + total_h_dato / 2 - 4
            c.setFillColor(AMB)
            for dl in dato_lines:
                c.setFont("Helvetica-Bold", 22)
                dw = c.stringWidth(dl, "Helvetica-Bold", 22)
                c.drawString(bx + (bw2 - dw) / 2, dy, dl); dy -= 32
        else:
            box_top = H - 96; box_bot = MARGIN_BOTTOM
            box_h = box_top - box_bot; box_x = 20; box_w = W - 40
            c.setFillColor(colors.HexColor("#0e0e22"))
            c.roundRect(box_x, box_bot, box_w, box_h, 12, fill=1, stroke=0)
            c.setFillColor(PUR)
            c.roundRect(box_x, box_bot, 6, box_h, 3, fill=1, stroke=0)
            test_lines_28 = wrap(c, cuerpo, "Helvetica-Bold", 28, box_w - 60)
            test_lines_22 = wrap(c, cuerpo, "Helvetica-Bold", 22, box_w - 60)
            if len(test_lines_28) <= 4:
                font_size, line_h, lines = 28, 44, test_lines_28
            else:
                font_size, line_h, lines = 22, 34, test_lines_22
            text_total_h = len(lines) * line_h
            text_start_y = box_bot + box_h / 2 + text_total_h / 2 - line_h * 0.3
            c.setFillColor(TXT); y_txt = text_start_y
            for line in lines:
                c.setFont("Helvetica-Bold", font_size)
                c.drawString(box_x + 26, y_txt, line); y_txt -= line_h
        c.showPage()

    def draw_cta(c, data, total):
        base(c, total, total)
        c.setFillColor(PUR); c.setFillAlpha(0.10)
        c.circle(W / 2, H / 2 + 20, 260, fill=1, stroke=0)
        c.setFillAlpha(1.0)
        c.setFillColor(PUR); c.rect(0, 0, W, 36, fill=1, stroke=0)
        c.setFillColor(PURT); c.setFont("Helvetica-Bold", 10)
        label = "¿QUÉ OPINAS TÚ?"
        c.drawString((W - c.stringWidth(label,"Helvetica-Bold",10)) / 2, H - 65, label)
        preg_lines = wrap(c, data.get("pregunta_final",""), "Helvetica-Bold", 30, W - 100)
        c.setFillColor(TXT); y = H - 130
        for line in preg_lines[:3]:
            c.setFont("Helvetica-Bold", 30)
            c.drawString((W - c.stringWidth(line,"Helvetica-Bold",30)) / 2, y, line); y -= 46
        cta_lines = wrap(c, data.get("cta",""), "Helvetica", 15, W - 100)
        c.setFillColor(MUT); yc = y - 20
        for cl in cta_lines[:2]:
            c.setFont("Helvetica", 15)
            c.drawString((W - c.stringWidth(cl,"Helvetica",15)) / 2, yc, cl); yc -= 24
        autor = "Julen · Business & Data Analytics · MSc Big Data & IA"
        c.setFillColor(WHT); c.setFont("Helvetica", 10)
        c.drawString((W - c.stringWidth(autor,"Helvetica",10)) / 2, 12, autor)
        c.showPage()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
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
    pill_map = {"🏦 Banca":"sector-pill-banca","♟️ Estrategia & IA":"sector-pill-estrategia","📊 Analista de Datos":"sector-pill-datos"}
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
    opciones = st.multiselect(
        label="",
        options=list(range(7)),
        default=dias_pub,
        format_func=lambda x: DIAS_SEMANA[x],
        label_visibility="collapsed",
        key="sel_dias_pub"
    )
    if opciones != dias_pub:
        st.session_state.dias_publicacion = opciones
        st.rerun()
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
        <div class="comp-section">📋 Formatos más populares</div>
        {lista_items(data.get("formatos_populares",[]))}
        <div class="comp-section">🔥 Temas en tendencia</div>
        {lista_items(data.get("temas_trending",[]))}
        <div class="comp-section">🎣 Ganchos que funcionan</div>
        {lista_items(data.get("ganchos_efectivos",[]))}
        <div class="comp-section">🏷️ Hashtags top</div>
        <div style="font-size:13px;color:#6c9fff;line-height:2">{" ".join(data.get("hashtags_top",[]))}</div>
        <div class="comp-section">⏰ Mejor momento para publicar</div>
        <div class="comp-item">{data.get("mejor_dia_hora","")}</div>
        <div class="comp-section">⚡ Cómo diferenciarte</div>
        <div style="font-size:13px;color:#d0d0e0;line-height:1.7;padding:10px 14px;background:rgba(108,99,255,0.08);border-radius:10px;border-left:2px solid #6c63ff">{data.get("consejo_diferenciacion","")}</div>
        <div class="comp-section">⚠️ Error más común a evitar</div>
        <div style="font-size:13px;color:#d0d0e0;line-height:1.7;padding:10px 14px;background:rgba(248,113,113,0.08);border-radius:10px;border-left:2px solid #f87171">{data.get("error_comun","")}</div>
    </div>
    """, unsafe_allow_html=True)

# ── UI ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <div class="badge">⚡ LinkedIn Agent</div>
    <div class="main-title">Tu voz<br>en el sector</div>
    <div class="main-sub">Noticias españolas de los últimos 5 días · Analizadas con IA<br>Elige una y publica en LinkedIn</div>
</div>
""", unsafe_allow_html=True)

for key, val in [("noticias",[]),("post_generado",""),("noticia_elegida",None),
                  ("usadas",[]),("fase","inicio"),("puntuacion",None),
                  ("sector_elegido",""),("sectores_data",{}),
                  ("post_a",""),("post_b",""),("recomendada","A"),("razon",""),
                  ("tono_elegido","aprendiendo"),("historial",[]),
                  ("post_en",""),("edicion_key",0),
                  ("dias_publicacion",[0,3]),
                  ("competencia_data",None),("competencia_sector",""),
                  ("carrusel_pdf",None)]:
    if key not in st.session_state:
        st.session_state[key] = val

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
        </div>
        """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("⚡  Buscar noticias", use_container_width=True, type="primary"):
            with st.spinner("Buscando noticias españolas de los últimos 5 días..."):
                sectores_data = fetch_noticias_por_sector()
                noticias = []
                for sector, noticia in sectores_data.items():
                    if noticia and noticia["url"] not in st.session_state.usadas:
                        noticia["_sector"] = sector
                        noticias.append(noticia)
                if not noticias:
                    st.error("No se encontraron noticias nuevas. Prueba más tarde.")
                else:
                    st.session_state.noticias = noticias
                    st.session_state.sectores_data = sectores_data
                    st.session_state.fase = "noticias"
                    st.rerun()

    if st.session_state.usadas:
        st.markdown(f"<div style='text-align:center;color:#7070a0;font-size:12px;margin-top:8px'>{len(st.session_state.usadas)} noticia{'s' if len(st.session_state.usadas)>1 else ''} ya usada{'s' if len(st.session_state.usadas)>1 else ''} — no se repetirán</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    if st.button("🔍  Ver qué publica la competencia", use_container_width=True):
        st.session_state.fase = "competencia"
        st.rerun()

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    render_calendario()

    if st.session_state.historial:
        st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
        if st.button("📚  Ver historial de posts", use_container_width=True):
            st.session_state.fase = "historial"
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
    </div>
    """, unsafe_allow_html=True)
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","datos":"sector-pill-datos"}
    for sector_key, cfg in SECTORES.items():
        if st.button(cfg["etiqueta"], key=f"comp_{sector_key}", use_container_width=True):
            with st.spinner(f"Analizando contenido de {cfg['etiqueta']}..."):
                try:
                    data = analizar_competencia(sector_key)
                    st.session_state.competencia_data = data
                    st.session_state.competencia_sector = sector_key
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
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
    st.markdown("""
    <div class="post-header">
        <div class="post-icon">📚</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">Historial de posts</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">Todos los posts que has generado</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    render_historial()
    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver al inicio"):
        st.session_state.fase = "inicio"
        st.rerun()

# ── NOTICIAS ───────────────────────────────────────────────────────────────────
elif st.session_state.fase == "noticias":
    st.markdown('<div class="section-label">Elige una noticia</div>', unsafe_allow_html=True)
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","datos":"sector-pill-datos"}
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
        col_sel, col_ref = st.columns([3,1])
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
                    if nueva: st.session_state.noticias[i] = nueva
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
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","datos":"sector-pill-datos"}
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
    render_opcion(st.session_state.post_a,"Versión A — Analítica y técnica",(rec=="A"),razon if rec=="A" else "","elegir_a")
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)
    render_opcion(st.session_state.post_b,"Versión B — Cercana y reflexiva",(rec=="B"),razon if rec=="B" else "","elegir_b")
    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver a noticias"):
        st.session_state.fase = "noticias"
        st.rerun()

# ── POST ───────────────────────────────────────────────────────────────────────
elif st.session_state.fase == "post":
    n = st.session_state.noticia_elegida
    sector = st.session_state.sector_elegido
    cfg = SECTORES.get(sector,{})
    pill_class = {"banca":"sector-pill-banca","estrategia":"sector-pill-estrategia","datos":"sector-pill-datos"}
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
                    st.session_state.puntuacion = None
                    st.session_state.edicion_key += 1
                    st.rerun()
        with col_e2:
            if st.button("🎣 Nuevo gancho", use_container_width=True, key="ed_gancho"):
                with st.spinner("Reescribiendo gancho..."):
                    st.session_state.post_generado = editar_post_guiado(st.session_state.post_generado,"Reescribe SOLO las primeras 1-2 líneas con un gancho más impactante. El resto igual.")
                    st.session_state.puntuacion = None
                    st.session_state.edicion_key += 1
                    st.rerun()
        with col_e3:
            if st.button("📊 Añade dato", use_container_width=True, key="ed_dato"):
                with st.spinner("Añadiendo dato..."):
                    st.session_state.post_generado = editar_post_guiado(st.session_state.post_generado,"Incorpora un dato, cifra o estadística concreta. Si no hay, invéntalo de forma verosímil.")
                    st.session_state.puntuacion = None
                    st.session_state.edicion_key += 1
                    st.rerun()

    with tab2:
        st.markdown('<div class="section-label">🎨 Carrusel PDF para LinkedIn</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#7070a0;margin-bottom:1rem">Genera un PDF con 7 slides listo para subir directamente a LinkedIn como carrusel</div>', unsafe_allow_html=True)
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
