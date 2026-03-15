import streamlit as st
import random
import feedparser
import requests
from datetime import datetime, timedelta
from google import genai

# ── Configuración ──────────────────────────────────────────────────────────────
GEMINI_API_KEY   = st.secrets.get("GEMINI_API_KEY", "AIzaSyDqcU6EAm5VFKJq8qXa6oA-Cvk5sO-DMig")
TELEGRAM_TOKEN   = st.secrets.get("TELEGRAM_TOKEN", "8699316221:AAHzZMalPaw224JjpbQFkI1i2MFe50JmupE")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "6267952113")
NEWSAPI_KEY      = st.secrets.get("NEWSAPI_KEY", "231afc3ea3d845fcae8acafe7f314c44")

# ── Fuentes RSS (igual que en agent.py) ───────────────────────────────────────
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

# ── CSS personalizado ──────────────────────────────────────────────────────────
st.set_page_config(page_title="LinkedIn Agent", page_icon="⚡", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: #0a0a0f;
    color: #f0f0f8;
}

/* Header principal */
.main-header {
    text-align: center;
    padding: 2rem 0 2.5rem;
}
.badge {
    display: inline-block;
    background: rgba(108,99,255,0.15);
    border: 1px solid rgba(108,99,255,0.35);
    color: #a78bfa;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 5px 16px;
    border-radius: 99px;
    margin-bottom: 1.2rem;
}
.main-title {
    font-family: 'Syne', sans-serif;
    font-size: 2.6rem;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, #f0f0f8 30%, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.7rem;
}
.main-sub {
    color: #7070a0;
    font-size: 15px;
    line-height: 1.6;
}

/* Tarjetas de noticias */
.news-card {
    background: #13131a;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s;
}
.news-card:hover {
    border-color: rgba(255,255,255,0.18);
}
.card-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 0.8rem;
    flex-wrap: wrap;
}
.source-pill {
    background: rgba(108,99,255,0.15);
    border: 1px solid rgba(108,99,255,0.3);
    color: #a78bfa;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    padding: 3px 12px;
    border-radius: 99px;
}
.date-pill {
    color: #7070a0;
    font-size: 11px;
}
.card-title {
    font-family: 'Syne', sans-serif;
    font-size: 1rem;
    font-weight: 700;
    color: #f0f0f8;
    line-height: 1.35;
    margin-bottom: 0.6rem;
}
.card-desc {
    color: rgba(112,112,160,0.9);
    font-size: 13px;
    line-height: 1.65;
}

/* Post generado */
.post-box {
    background: #13131a;
    border: 1px solid rgba(108,99,255,0.25);
    border-radius: 20px;
    padding: 1.6rem;
    font-size: 14px;
    line-height: 1.85;
    color: #f0f0f8;
    white-space: pre-wrap;
    word-break: break-word;
}
.post-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 1.2rem;
}
.post-icon {
    width: 46px;
    height: 46px;
    background: linear-gradient(135deg, #6c63ff, #9333ea);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
}

/* Sección título */
.section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #7070a0;
    margin: 1.8rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 10px;
}
.section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: rgba(255,255,255,0.07);
}

/* Botones de Streamlit — override */
.stButton > button {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    border-radius: 14px !important;
    border: none !important;
    transition: all 0.2s !important;
    background: linear-gradient(135deg, #e03131, #c92a2a) !important;
    color: white !important;
    box-shadow: 0 4px 18px rgba(224,49,49,0.35) !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #c92a2a, #b02020) !important;
    box-shadow: 0 6px 24px rgba(224,49,49,0.5) !important;
    transform: translateY(-1px) !important;
}

/* Info / success boxes */
.stSuccess {
    background: rgba(74,222,128,0.1) !important;
    border: 1px solid rgba(74,222,128,0.25) !important;
    border-radius: 12px !important;
    color: #4ade80 !important;
}
.stInfo {
    background: rgba(108,99,255,0.1) !important;
    border: 1px solid rgba(108,99,255,0.25) !important;
    border-radius: 12px !important;
}

/* Divider */
hr {
    border-color: rgba(255,255,255,0.07) !important;
    margin: 1.5rem 0 !important;
}

/* Ocultar menu de streamlit */
#MainMenu, footer, header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ── Funciones del agente (igual que agent.py) ──────────────────────────────────

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
            "q": tema,
            "language": "es",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": NEWSAPI_KEY,
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

# ── UI Principal ───────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
    <div class="badge">⚡ LinkedIn Agent</div>
    <div class="main-title">Tu voz<br>en el sector</div>
    <div class="main-sub">Noticias reales de los últimos 5 días · Analizadas con IA<br>Elige una y publica en LinkedIn</div>
</div>
""", unsafe_allow_html=True)

# ── Estado de sesión ───────────────────────────────────────────────────────────
if "noticias" not in st.session_state:
    st.session_state.noticias = []
if "post_generado" not in st.session_state:
    st.session_state.post_generado = ""
if "noticia_elegida" not in st.session_state:
    st.session_state.noticia_elegida = None
if "usadas" not in st.session_state:
    st.session_state.usadas = []
if "fase" not in st.session_state:
    st.session_state.fase = "inicio"  # inicio | noticias | post

# ── FASE: INICIO ──────────────────────────────────────────────────────────────
if st.session_state.fase == "inicio":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("⚡  Buscar noticias", use_container_width=True, type="primary"):
            with st.spinner("Buscando noticias de los últimos 5 días..."):
                rss = fetch_rss_news()
                api = fetch_newsapi_news()
                todas = rss + api

                # Filtrar usadas
                disponibles = [n for n in todas if n["url"] not in st.session_state.usadas and n["titulo"]]
                con_resumen = [n for n in disponibles if len(n.get("resumen", "")) > 80]
                pool = con_resumen if con_resumen else disponibles

                if len(pool) < 1:
                    st.error("No se encontraron noticias nuevas. Prueba más tarde.")
                else:
                    elegidas = random.sample(pool, min(3, len(pool)))
                    st.session_state.noticias = elegidas
                    st.session_state.fase = "noticias"
                    st.rerun()

    if st.session_state.usadas:
        st.markdown(f"<div style='text-align:center;color:#7070a0;font-size:12px;margin-top:12px'>{len(st.session_state.usadas)} noticia{'s' if len(st.session_state.usadas)>1 else ''} ya usada{'s' if len(st.session_state.usadas)>1 else ''} — no se repetirán</div>", unsafe_allow_html=True)

# ── FASE: NOTICIAS ─────────────────────────────────────────────────────────────
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

        if st.button(f"✦  Seleccionar esta noticia", key=f"sel_{i}", use_container_width=True):
            st.session_state.noticia_elegida = n
            with st.spinner("Generando tu post con Gemini..."):
                post = generar_post(n)
                st.session_state.post_generado = post
                st.session_state.usadas.append(n["url"])
                st.session_state.fase = "post"
                st.rerun()

        st.markdown("<div style='margin-bottom:0.5rem'></div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver", use_container_width=False):
        st.session_state.fase = "inicio"
        st.session_state.noticias = []
        st.rerun()

# ── FASE: POST GENERADO ────────────────────────────────────────────────────────
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

    # Fuente
    st.markdown(f"""
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:1rem;flex-wrap:wrap">
        <span class="source-pill">{n['fuente']}</span>
        <span class="date-pill">🗓 {n['fecha']}</span>
        <a href="{n['url']}" target="_blank" style="font-size:11px;color:#6c63ff;text-decoration:none">Ver noticia original ↗</a>
    </div>
    """, unsafe_allow_html=True)

    # Post editable
    post_editado = st.text_area(
        label="",
        value=st.session_state.post_generado,
        height=380,
        label_visibility="collapsed"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋  Copiar post", use_container_width=True):
            st.code(post_editado, language=None)
            st.success("Copia el texto de arriba ↑")

    with col2:
        if st.button("📨  Enviar a Telegram", use_container_width=True, type="primary"):
            with st.spinner("Enviando..."):
                ok = enviar_telegram(post_editado, n)
                if ok:
                    st.success("✅ Enviado a Telegram. Revisa tu bot y publica en LinkedIn.")
                else:
                    st.error("❌ Error al enviar. Comprueba el token de Telegram.")

    st.markdown("<hr>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        if st.button("🔄  Regenerar post", use_container_width=True):
            with st.spinner("Regenerando con Gemini..."):
                nuevo_post = generar_post(n)
                st.session_state.post_generado = nuevo_post
                st.rerun()
    with col4:
        if st.button("← Buscar más noticias", use_container_width=True):
            st.session_state.fase = "inicio"
            st.session_state.noticias = []
            st.session_state.post_generado = ""
            st.session_state.noticia_elegida = None
            st.rerun()