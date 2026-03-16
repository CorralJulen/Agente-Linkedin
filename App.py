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

# ── Fuentes RSS por sector (solo España) ───────────────────────────────────────
RSS_BANCA = [
    ("El Economista - Banca",      "https://www.eleconomista.es/rss/rss-banca.php"),
    ("Expansión - Finanzas",       "https://e00-expansion.uecdn.es/rss/mercados.xml"),
    ("Cinco Días",                 "https://cincodias.elpais.com/rss/cincodias/ultimas_noticias/"),
    ("El Confidencial - Economía", "https://www.elconfidencial.com/rss/economia/"),
    ("El País - Economía",         "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada"),
]
RSS_ESTRATEGIA = [
    ("Expansión - Empresas",        "https://e00-expansion.uecdn.es/rss/empresas.xml"),
    ("El Economista - Empresas",    "https://www.eleconomista.es/rss/rss-empresas.php"),
    ("El Confidencial - Empresas",  "https://www.elconfidencial.com/rss/empresas/"),
    ("El País - Economía",          "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada"),
    ("Cinco Días",                  "https://cincodias.elpais.com/rss/cincodias/ultimas_noticias/"),
]
RSS_DATOS = [
    ("El Confidencial - Tech",  "https://www.elconfidencial.com/rss/tecnologia/"),
    ("El País - Tecnología",    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/tecnologia/portada"),
    ("Xataka",                  "https://feeds.weblogssl.com/xataka"),
    ("El Español - Tech",       "https://www.elespanol.com/rss/economia/"),
    ("ABC - Tecnología",        "https://www.abc.es/rss/feeds/abc_tecnologia.xml"),
]
SECTORES = {
    "banca":      {"feeds": RSS_BANCA,      "etiqueta": "🏦 Banca",            "perfil": "consultor de banca y finanzas"},
    "estrategia": {"feeds": RSS_ESTRATEGIA, "etiqueta": "♟️ Estrategia & IA",  "perfil": "consultor de estrategia e IA"},
    "datos":      {"feeds": RSS_DATOS,      "etiqueta": "📊 Analista de Datos", "perfil": "analista de datos"},
}

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

def extraer_imagen(entry) -> str:
    """Extrae la URL de la imagen de portada de una entrada RSS."""
    # 1. media:content
    if hasattr(entry, "media_content"):
        for m in entry.media_content:
            url = m.get("url", "")
            if url and any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return url
    # 2. media:thumbnail
    if hasattr(entry, "media_thumbnail"):
        for m in entry.media_thumbnail:
            url = m.get("url", "")
            if url:
                return url
    # 3. enclosures
    if hasattr(entry, "enclosures"):
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href", enc.get("url", ""))
    # 4. og:image en el summary HTML
    if hasattr(entry, "summary"):
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.summary)
        if match:
            return match.group(1)
    return ""

# ── Funciones ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_noticias_por_sector() -> dict:
    hace_5_dias = datetime.now() - timedelta(days=5)
    def parsear_feeds(feeds):
        noticias = []
        for fuente, url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:4]:
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
                        "imagen": extraer_imagen(entry),  # ← NUEVO
                    })
            except Exception:
                pass
        return noticias
    resultado = {}
    for sector, cfg in SECTORES.items():
        pool = parsear_feeds(cfg["feeds"])
        validas = [n for n in pool if n["titulo"] and len(n.get("resumen", "")) > 80]
        elegidas = validas if validas else pool
        resultado[sector] = random.choice(elegidas) if elegidas else None
    return resultado

def generar_dos_posts(noticia: dict, perfil: str) -> tuple:
    client = genai.Client(api_key=GEMINI_API_KEY)
    base = f"""
Eres un {perfil} junior.
Tienes formación en Business Management y estás cursando un Máster en Big Data, IA y Business Analytics.

NOTICIA:
Título: {noticia['titulo']}
Fuente: {noticia['fuente']} ({noticia['fecha']})
Resumen: {noticia['resumen']}

INSTRUCCIONES COMUNES:
- Post en ESPAÑOL de 150-250 palabras
- Gancho potente → análisis → pregunta abierta al final
- 3-5 insights concretos
- 5-8 hashtags al final
- NO menciones que eres IA
- Devuelve SOLO el texto del post
"""
    prompt_a = base + "\nESTILO: Analítico y técnico. Usa datos, cifras si las hay, jerga del sector. Tono experto pero accesible."
    prompt_b = base + "\nESTILO: Cercano y reflexivo. Arranca con una pregunta o provocación personal. Más storytelling, menos técnico. Tono humano y conversacional."

    resp_a = client.models.generate_content(model="gemini-flash-latest", contents=prompt_a)
    resp_b = client.models.generate_content(model="gemini-flash-latest", contents=prompt_b)
    post_a = resp_a.text.strip()
    post_b = resp_b.text.strip()

    prompt_rec = f"""Eres un experto en contenido LinkedIn para profesionales de consultoría y finanzas.

Dada esta noticia:
Título: {noticia['titulo']}
Sector: {perfil}
Resumen: {noticia['resumen']}

Y estos dos estilos de post:
- Versión A: analítica y técnica, usa datos y jerga del sector
- Versión B: cercana y reflexiva, storytelling personal y conversacional

¿Cuál encaja mejor con esta noticia concreta? Responde SOLO con este JSON sin texto adicional ni markdown:
{{"recomendada": "A" o "B", "razon": "Una frase corta explicando por qué (máximo 15 palabras)"}}"""

    try:
        resp_rec = client.models.generate_content(model="gemini-flash-latest", contents=prompt_rec)
        raw = resp_rec.text.strip().replace("```json", "").replace("```", "").strip()
        rec = json.loads(raw)
        recomendada = rec.get("recomendada", "A")
        razon = rec.get("razon", "")
    except Exception:
        recomendada = "A"
        razon = ""

    return post_a, post_b, recomendada, razon

def generar_post(noticia: dict, perfil: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
Eres un {perfil} junior.
Tienes formación en Business Management y estás cursando un Máster en Big Data, IA y Business Analytics.
NOTICIA:
Título: {noticia['titulo']}
Fuente: {noticia['fuente']} ({noticia['fecha']})
Resumen: {noticia['resumen']}
INSTRUCCIONES:
1. Post en ESPAÑOL de 150-250 palabras.
2. Gancho potente → análisis → pregunta abierta.
3. 3-5 insights concretos.
4. 5-8 hashtags al final.
5. Tono profesional pero cercano.
6. NO uses lenguaje corporativo vacío ni menciones que eres IA.
Devuelve SOLO el texto del post.
"""
    response = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
    return response.text.strip()

def puntuar_post(post: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Eres un experto en marketing de contenidos B2B en LinkedIn.
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

def render_opcion(post: str, label: str, es_recomendada: bool, razon: str, key: str):
    if es_recomendada:
        st.markdown(f"""
        <div class="section-label" style="color:#4ade80">{label}</div>
        <div class="recomendada-badge">✦ Recomendada para esta noticia</div>
        <div class="opcion-card-recomendada">{post}</div>
        {"<div class='razon-badge'>💡 " + razon + "</div>" if razon else ""}
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="section-label">{label}</div>
        <div class="opcion-card">{post}</div>
        """, unsafe_allow_html=True)
    if st.button(f"✦  Elegir esta versión", key=key, use_container_width=True):
        st.session_state.post_generado = post
        st.session_state.fase = "post"
        st.rerun()

def render_imagen_noticia(noticia: dict):
    """Muestra la imagen de portada si existe, con enlace para abrirla."""
    imagen_url = noticia.get("imagen", "")
    if not imagen_url:
        return
    try:
        # Verificar que la imagen carga antes de mostrarla
        r = requests.head(imagen_url, timeout=5, allow_redirects=True)
        if r.status_code != 200:
            return
    except Exception:
        return

    st.markdown('<div class="section-label">🖼️ Imagen de portada</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="img-wrapper"><img src="{imagen_url}" style="width:100%;display:block;"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="img-caption">Mantén pulsada la imagen para guardarla (móvil) · '
        f'<a href="{imagen_url}" target="_blank" style="color:#6c63ff;text-decoration:none">Abrir imagen ↗</a></div>',
        unsafe_allow_html=True
    )

# ── UI ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <div class="badge">⚡ LinkedIn Agent</div>
    <div class="main-title">Tu voz<br>en el sector</div>
    <div class="main-sub">Noticias españolas de los últimos 5 días · Analizadas con IA<br>Elige una y publica en LinkedIn</div>
</div>
""", unsafe_allow_html=True)

for key, val in [("noticias", []), ("post_generado", ""), ("noticia_elegida", None),
                  ("usadas", []), ("fase", "inicio"), ("puntuacion", None),
                  ("sector_elegido", ""), ("sectores_data", {}),
                  ("post_a", ""), ("post_b", ""),
                  ("recomendada", "A"), ("razon", "")]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── INICIO ─────────────────────────────────────────────────────────────────────
if st.session_state.fase == "inicio":
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
        st.markdown(f"<div style='text-align:center;color:#7070a0;font-size:12px;margin-top:12px'>{len(st.session_state.usadas)} noticia{'s' if len(st.session_state.usadas)>1 else ''} ya usada{'s' if len(st.session_state.usadas)>1 else ''} — no se repetirán</div>", unsafe_allow_html=True)

# ── NOTICIAS ───────────────────────────────────────────────────────────────────
elif st.session_state.fase == "noticias":
    st.markdown('<div class="section-label">Elige una noticia</div>', unsafe_allow_html=True)
    pill_class = {"banca": "sector-pill-banca", "estrategia": "sector-pill-estrategia", "datos": "sector-pill-datos"}
    for i, n in enumerate(st.session_state.noticias):
        sector = n.get("_sector", "")
        cfg = SECTORES.get(sector, {})
        etiqueta = cfg.get("etiqueta", sector)
        pill = pill_class.get(sector, "source-pill")
        resumen_limpio = n["resumen"].replace("<", "").replace(">", "").replace("&", "&amp;")[:280]
        st.markdown(f"""
        <div class="news-card">
            <div class="card-meta">
                <span class="{pill}">{etiqueta}</span>
                <span class="source-pill">{n['fuente']}</span>
                <span class="date-pill">🗓 {n['fecha']}</span>
            </div>
            <div class="card-title">{n['titulo']}</div>
            <div class="card-desc">{resumen_limpio}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✦  Seleccionar esta noticia", key=f"sel_{i}", use_container_width=True):
            perfil = cfg.get("perfil", "consultor junior")
            st.session_state.noticia_elegida = n
            st.session_state.sector_elegido = sector
            with st.spinner("Gemini está generando 2 versiones del post..."):
                post_a, post_b, recomendada, razon = generar_dos_posts(n, perfil)
                st.session_state.post_a = post_a
                st.session_state.post_b = post_b
                st.session_state.recomendada = recomendada
                st.session_state.razon = razon
                st.session_state.puntuacion = None
                st.session_state.usadas.append(n["url"])
                st.session_state.fase = "elegir_post"
                st.rerun()
        st.markdown("<div style='margin-bottom:0.5rem'></div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver"):
        st.session_state.fase = "inicio"
        st.session_state.noticias = []
        st.rerun()

# ── ELEGIR POST ────────────────────────────────────────────────────────────────
elif st.session_state.fase == "elegir_post":
    st.markdown("""
    <div class="post-header">
        <div class="post-icon">✦</div>
        <div>
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#f0f0f8">Elige tu versión</div>
            <div style="font-size:12px;color:#7070a0;margin-top:2px">La versión en verde es la recomendada para esta noticia</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    rec = st.session_state.recomendada
    razon = st.session_state.razon
    render_opcion(
        post=st.session_state.post_a,
        label="Versión A — Analítica y técnica",
        es_recomendada=(rec == "A"),
        razon=razon if rec == "A" else "",
        key="elegir_a"
    )
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)
    render_opcion(
        post=st.session_state.post_b,
        label="Versión B — Cercana y reflexiva",
        es_recomendada=(rec == "B"),
        razon=razon if rec == "B" else "",
        key="elegir_b"
    )
    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("← Volver a noticias"):
        st.session_state.fase = "noticias"
        st.rerun()

# ── POST ───────────────────────────────────────────────────────────────────────
elif st.session_state.fase == "post":
    n = st.session_state.noticia_elegida
    sector = st.session_state.sector_elegido
    cfg = SECTORES.get(sector, {})
    pill_class = {"banca": "sector-pill-banca", "estrategia": "sector-pill-estrategia", "datos": "sector-pill-datos"}
    pill = pill_class.get(sector, "source-pill")
    etiqueta = cfg.get("etiqueta", "")

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
        <span class="{pill}">{etiqueta}</span>
        <span class="source-pill">{n['fuente']}</span>
        <span class="date-pill">🗓 {n['fecha']}</span>
        <a href="{n['url']}" target="_blank" style="font-size:11px;color:#6c63ff;text-decoration:none">Ver noticia original ↗</a>
    </div>
    """, unsafe_allow_html=True)

    # ── Imagen de portada ──────────────────────────────────────────────────────
    render_imagen_noticia(n)

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
            perfil = cfg.get("perfil", "consultor junior")
            with st.spinner("Regenerando con Gemini..."):
                st.session_state.post_generado = generar_post(n, perfil)
                st.session_state.puntuacion = None
                st.rerun()
    with col4:
        if st.button("← Buscar más noticias", use_container_width=True):
            st.session_state.fase = "inicio"
            st.session_state.noticias = []
            st.session_state.post_generado = ""
            st.session_state.noticia_elegida = None
            st.session_state.puntuacion = None
            st.session_state.sector_elegido = ""
            st.rerun()
