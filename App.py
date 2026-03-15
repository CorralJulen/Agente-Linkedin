import streamlit as st
import random
import json
import feedparser
import requests
from datetime import datetime, timedelta
from google import genai

# ── Configuración ──────────────────────────────────────────────────────────────
GEMINI_API_KEY   = st.secrets.get("GEMINI_API_KEY")
TELEGRAM_TOKEN   = st.secrets.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")
NEWSAPI_KEY      = st.secrets.get("NEWSAPI_KEY")

# ── Fuentes RSS ────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    ("Banco Central Europeo",             "https://www.ecb.europa.eu/rss/press.html"),
    ("Bank for International Settlements","https://www.bis.org/rss/press_releases.htm"),
    ("El Economista - Banca",             "https://www.eleconomista.es/rss/rss-banca.php"),
    ("Expansión - Finanzas",              "https://e00-expansion.uecdn.es/rss/mercados.xml"),
    ("McKinsey Insights",                 "https://www.mckinsey.com/feeds/rss"),
    ("Harvard Business Review",           "https://hbr.org/subscriber-content/feed"),
    ("MIT Sloan Management Review",       "https://sloanreview.mit.edu/feed/"),
    ("MIT Technology Review",             "https://www.technologyreview.com/feed/"),
    ("VentureBeat AI",                    "https://venturebeat.com/ai/feed/"),
    ("The Batch (DeepLearning.AI)",       "https://www.deeplearning.ai/the-batch/feed/"),
    ("Eurostat News",                     "https://ec.europa.eu/eurostat/web/rss"),
    ("FT - Economics",                    "https://www.ft.com/rss/home"),
]

TEMAS = [
    "inteligencia artificial en banca",
    "consultoría de estrategia",
    "análisis de datos financieros",
    "transformación digital banca",
    "regulación bancaria europea",
    "machine learning finanzas",
    "indicadores macroeconómicos eurozona",
    "Big 4 estrategia",
    "riesgos financieros IA",
]

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

.news-card { background: #13131a; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 1.4rem 1.6rem; margin-bottom: 1rem; }
.card-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 0.8rem; flex-wrap: wrap; }
.source-pill { background: rgba(108,99,255,0.15); border: 1px solid rgba(108,99,255,0.3); color: #a78bfa; font-size: 10px; font-weight: 600; letter-spacing: 0.06em; padding: 3px 12px; border-radius: 99px; }
.date-pill { color: #7070a0; font-size: 11px; }
.card-title { font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 700; color: #f0f0f8; line-height: 1.35; margin-bottom: 0.6rem; }
.card-desc { color: rgba(112,112,160,0.9); font-size: 13px; line-height: 1.65; }

.section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #7070a0; margin: 1.8rem 0 1rem; display: flex; align-items: center; gap: 10px; }
.section-label::after { content: ''; flex: 1; height: 1px; background: rgba(255,255,255,0.07); }

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

# ── Funciones ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_rss_news(max_per_feed: int = 3) -> list:
    noticias = []
    hace_5_dias = datetime.now() - timedelta(days=5)
    for fuente, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                if published and published < hace_5_dias:
                    continue
                noticias.append({
                    "fuente": fuente,
                    "titulo": entry.get("title", ""),
                    "resumen": entry.get("summary", entry.get("description", ""))[:400],
                    "url": entry.get("link", ""),
                    "fecha": published.strftime("%d/%m/%Y") if published else "reciente",
                })
        except Exception:
            pass
    return noticias

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_newsapi_news() -> list:
    if not NEWSAPI_KEY:
        return []
    noticias = []
    tema = random.choice(TEMAS)
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": tema, "language": "es", "sortBy": "publishedAt",
            "pageSize": 5, "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for art in data.get("articles", []):
            noticias.append({
                "fuente": art.get("source", {}).get("name", "NewsAPI"),
                "titulo": art.get("title", ""),
                "resumen": (art.get("description") or "")[:400],
                "url": art.get("url", ""),
                "fecha": art.get("publishedAt", "")[:10],
            })
    except Exception:
        pass
    return noticias

def generar_post(noticia: dict) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
Eres un consultor junior especializado en banca, estrategia empresarial y analítica de datos.
Tienes formación en Business Management y estás cursando un Máster en Big Data, IA y Business Analytics.
Tu objetivo es crear contenido en LinkedIn que demuestre pensamiento analítico y conocimiento del sector.

NOTICIA DE REFERENCIA:
Título: {noticia['titulo']}
Fuente: {noticia['fuente']} ({noticia['fecha']})
Resumen: {noticia['resumen']}
URL: {noticia['url']}

INSTRUCCIONES:
1. Escribe un post de LinkedIn en ESPAÑOL de entre 150 y 250 palabras.
2. Estructura: gancho inicial potente (1-2 líneas) → análisis con tu perspectiva → reflexión o pregunta al lector.
3. Añade 3-5 insights concretos derivados de la noticia.
4. Termina con UNA pregunta abierta que invite a debatir.
5. Añade entre 5 y 8 hashtags relevantes al final.
6. Tono: profesional pero cercano, como alguien que está aprendiendo y reflexionando.
7. NO uses frases como "En conclusión" o lenguaje corporativo vacío.
8. NO menciones que eres una IA.

Devuelve SOLO el texto del post, sin explicaciones adicionales.
"""
    response = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
    return response.text.strip()

def puntuar_post(post: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Eres un experto en marketing de contenidos B2B en LinkedIn, especializado en consultoría y finanzas.

Analiza este post y devuelve SOLO un JSON válido sin texto adicional ni markdown:

POST:
{post}

Formato exacto:
{{
  "gancho": <1-10>,
  "claridad": <1-10>,
  "valor": <1-10>,
  "engagement": <1-10>,
  "hashtags": <1-10>,
  "total": <1-100>,
  "nivel": "<Excelente|Muy bueno|Bueno|Mejorable>",
  "feedback": "<2-3 frases concretas de mejora>"
}}"""
    response = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

def enviar_telegram(texto: str, noticia: dict) -> bool:
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

def render_linkedin_preview(post: str):
    import re
    preview_lines = post.split("\n")[:8]
    preview = "\n".join(preview_lines)
    if len(post.split("\n")) > 8:
        preview += "\n..."
    preview_safe = preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
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

def render_puntuacion(score: dict):
    metricas = [
        ("Gancho inicial",       score.get("gancho", 0)),
        ("Claridad",             score.get("claridad", 0)),
        ("Valor aportado",       score.get("valor", 0)),
        ("Potencial engagement", score.get("engagement", 0)),
        ("Hashtags",             score.get("hashtags", 0)),
    ]
    total = score.get("total", 0)
    nivel = score.get("nivel", "")
    feedback = score.get("feedback", "")
    ct = color_total(total)

    barras = ""
    for label, val in metricas:
        color = color_barra(val)
        barras += f"""
        <div class="score-row">
            <div class="score-label">{label}</div>
            <div class="score-bar-bg"><div class="score-bar" style="width:{val*10}%;background:{color}"></div></div>
            <div class="score-num" style="color:{color}">{val}</div>
        </div>"""

    st.markdown(f"""
    <div class="score-wrapper">
        <div class="score-title">📊 Puntuación del post</div>
        <div class="score-total" style="color:{ct}">{total}<span style="font-size:16px;color:#7070a0">/100</span></div>
        <div class="score-nivel" style="color:{ct}">{nivel}</div>
        {barras}
        <div class="score-feedback">{feedback}</div>
    </div>
    """, unsafe_allow_html=True)

# ── UI ─────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
    <div class="badge">⚡ LinkedIn Agent</div>
    <div class="main-title">Tu voz<br>en el sector</div>
    <div class="main-sub">Noticias reales de los últimos 5 días · Analizadas con IA<br>Elige una y publica en LinkedIn</div>
</div>
""", unsafe_allow_html=True)

for key, val in [("noticias", []), ("post_generado", ""), ("noticia_elegida", None),
                  ("usadas", []), ("fase", "inicio"), ("puntuacion", None)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── INICIO ─────────────────────────────────────────────────────────────────────
if st.session_state.fase == "inicio":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("⚡  Buscar noticias", use_container_width=True, type="primary"):
            with st.spinner("Buscando noticias de los últimos 5 días..."):
                rss = fetch_rss_news()
                api = fetch_newsapi_news()
                todas = rss + api
                disponibles = [n for n in todas if n["url"] not in st.session_state.usadas and n["titulo"]]
                con_resumen = [n for n in disponibles if len(n.get("resumen", "")) > 80]
                pool = con_resumen if con_resumen else disponibles
                if not pool:
                    st.error("No se encontraron noticias nuevas. Prueba más tarde.")
                else:
                    st.session_state.noticias = random.sample(pool, min(3, len(pool)))
                    st.session_state.fase = "noticias"
                    st.rerun()

    if st.session_state.usadas:
        st.markdown(f"<div style='text-align:center;color:#7070a0;font-size:12px;margin-top:12px'>{len(st.session_state.usadas)} noticia{'s' if len(st.session_state.usadas)>1 else ''} ya usada{'s' if len(st.session_state.usadas)>1 else ''} — no se repetirán</div>", unsafe_allow_html=True)

# ── NOTICIAS ───────────────────────────────────────────────────────────────────
elif st.session_state.fase == "noticias":
    st.markdown('<div class="section-label">Elige una noticia</div>', unsafe_allow_html=True)

    for i, n in enumerate(st.session_state.noticias):
        resumen_limpio = n["resumen"].replace("<", "").replace(">", "").replace("&", "&amp;")[:280]
        st.markdown(f"""
        <div class="news-card">
            <div class="card-meta">
                <span class="source-pill">{n['fuente']}</span>
                <span class="date-pill">🗓 {n['fecha']}</span>
            </div>
            <div class="card-title">{n['titulo']}</div>
            <div class="card-desc">{resumen_limpio}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("✦  Seleccionar esta noticia", key=f"sel_{i}", use_container_width=True):
            st.session_state.noticia_elegida = n
            with st.spinner("Generando tu post con Gemini..."):
                st.session_state.post_generado = generar_post(n)
                st.session_state.puntuacion = None
                st.session_state.usadas.append(n["url"])
                st.session_state.fase = "post"
                st.rerun()

        st.markdown("<div style='margin-bottom:0.5rem'></div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver"):
        st.session_state.fase = "inicio"
        st.session_state.noticias = []
        st.rerun()

# ── POST ───────────────────────────────────────────────────────────────────────
elif st.session_state.fase == "post":
    n = st.session_state.noticia_elegida

    st.markdown("""
    <div class="post-header">
        <div class="post-icon">✦</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">Post listo</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">Revisa, edita y publica en LinkedIn</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:1rem;flex-wrap:wrap">
        <span class="source-pill">{n['fuente']}</span>
        <span class="date-pill">🗓 {n['fecha']}</span>
        <a href="{n['url']}" target="_blank" style="font-size:11px;color:#6c63ff;text-decoration:none">Ver noticia original ↗</a>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["✏️ Editar", "👁️ Vista previa LinkedIn", "📊 Puntuación"])

    with tab1:
        post_editado = st.text_area(
            label="", value=st.session_state.post_generado,
            height=380, label_visibility="collapsed", key="editor"
        )
        st.session_state.post_generado = post_editado

    with tab2:
        st.markdown('<div class="section-label">Así se verá en LinkedIn</div>', unsafe_allow_html=True)
        render_linkedin_preview(st.session_state.post_generado)

    with tab3:
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
                    st.success("✅ Enviado a Telegram.")
                else:
                    st.error("❌ Error al enviar.")

    st.markdown("<hr>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    with col3:
        if st.button("🔄  Regenerar post", use_container_width=True):
            with st.spinner("Regenerando con Gemini..."):
                st.session_state.post_generado = generar_post(n)
                st.session_state.puntuacion = None
                st.rerun()
    with col4:
        if st.button("← Buscar más noticias", use_container_width=True):
            st.session_state.fase = "inicio"
            st.session_state.noticias = []
            st.session_state.post_generado = ""
            st.session_state.noticia_elegida = None
            st.session_state.puntuacion = None
            st.rerun()
