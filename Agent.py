"""
LinkedIn Content Agent
======================
Busca noticias relevantes, genera un post con Gemini y lo envía por Telegram.
Ejecutar 2x semana con cron: 0 8 * * 1,4  (lunes y jueves a las 8:00)
"""

import os
import re
import json
import random
import feedparser
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai

load_dotenv()

# ── Configuración ──────────────────────────────────────────────────────────────
GEMINI_API_KEY   = "AIzaSyDqcU6EAm5VFKJq8qXa6oA-Cvk5sO-DMig"
TELEGRAM_TOKEN   = "8699316221:AAHzZMalPaw224JjpbQFkI1i2MFe50JmupE"
TELEGRAM_CHAT_ID = "6267952113"
NEWSAPI_KEY      = "231afc3ea3d845fcae8acafe7f314c44"

# ── Fuentes RSS (100% gratuitas, sin API key) ──────────────────────────────────
RSS_FEEDS = [
    # Banca y finanzas
    ("Banco Central Europeo",        "https://www.ecb.europa.eu/rss/press.html"),
    ("Bank for International Settlements", "https://www.bis.org/rss/press_releases.htm"),
    ("El Economista - Banca",        "https://www.eleconomista.es/rss/rss-banca.php"),
    ("Expansión - Finanzas",         "https://e00-expansion.uecdn.es/rss/mercados.xml"),
    # Consultoría y estrategia
    ("McKinsey Insights",            "https://www.mckinsey.com/feeds/rss"),
    ("Harvard Business Review",      "https://hbr.org/subscribe?tpcc=orgsocial_edit"),
    ("MIT Sloan Management Review",  "https://sloanreview.mit.edu/feed/"),
    # IA y datos aplicados
    ("MIT Technology Review",        "https://www.technologyreview.com/feed/"),
    ("VentureBeat AI",               "https://venturebeat.com/ai/feed/"),
    ("The Batch (DeepLearning.AI)",  "https://www.deeplearning.ai/the-batch/feed/"),
    # Macro y economía
    ("Eurostat News",                "https://ec.europa.eu/eurostat/web/rss"),
    ("FT - Economics",               "https://www.ft.com/rss/home"),
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

# ── Obtener noticias ───────────────────────────────────────────────────────────

def fetch_rss_news(max_per_feed: int = 3) -> list[dict]:
    """Extrae noticias recientes de los feeds RSS."""
    noticias = []
    hace_7_dias = datetime.now() - timedelta(days=7)

    for fuente, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                if published and published < hace_7_dias:
                    continue

                noticias.append({
                    "fuente": fuente,
                    "titulo": entry.get("title", ""),
                    "resumen": entry.get("summary", entry.get("description", ""))[:500],
                    "url": entry.get("link", ""),
                    "fecha": published.strftime("%d/%m/%Y") if published else "reciente",
                })
        except Exception as e:
            print(f"[RSS] Error en {fuente}: {e}")

    return noticias


def fetch_newsapi_news() -> list[dict]:
    """Obtiene noticias adicionales de NewsAPI (free tier: 100 req/día)."""
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
            "from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for art in data.get("articles", []):
            noticias.append({
                "fuente": art.get("source", {}).get("name", "NewsAPI"),
                "titulo": art.get("title", ""),
                "resumen": (art.get("description") or "")[:500],
                "url": art.get("url", ""),
                "fecha": art.get("publishedAt", "")[:10],
            })
    except Exception as e:
        print(f"[NewsAPI] Error: {e}")

    return noticias


# ── Generar post con Gemini ────────────────────────────────────────────────────

def seleccionar_mejor_noticia(noticias: list[dict]) -> dict:
    """Elige la noticia más relevante aleatoriamente entre las top."""
    if not noticias:
        raise ValueError("No se encontraron noticias.")
    # Prioriza noticias con resumen sustancial
    con_resumen = [n for n in noticias if len(n["resumen"]) > 100]
    pool = con_resumen if con_resumen else noticias
    return random.choice(pool[:15])  # elige al azar entre las 15 primeras


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

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt
    )
    return response.text.strip()


# ── Enviar por Telegram ────────────────────────────────────────────────────────

def enviar_telegram(texto: str, noticia: dict) -> bool:
    """Envía el post generado al chat de Telegram."""
    separador = "─" * 35
    mensaje = f"""
🤖 *Agente LinkedIn — Nuevo post*
{separador}

{texto}

{separador}
📰 *Fuente:* {noticia['fuente']}
🗓 *Fecha:* {noticia['fecha']}
🔗 {noticia['url']}

_Revisa, edita con tu toque personal y publica en LinkedIn_ ✅
""".strip()

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            print("✅ Post enviado a Telegram correctamente.")
            return True
        else:
            print(f"❌ Error Telegram: {r.status_code} — {r.text}")
            return False
    except Exception as e:
        print(f"❌ Excepción al enviar a Telegram: {e}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*45}")
    print(f"  Agente LinkedIn  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*45}\n")

    print("📡 Buscando noticias...")
    noticias_rss = fetch_rss_news()
    noticias_api = fetch_newsapi_news()
    todas = noticias_rss + noticias_api
    print(f"   → {len(todas)} noticias encontradas ({len(noticias_rss)} RSS + {len(noticias_api)} NewsAPI)\n")

    noticia = seleccionar_mejor_noticia(todas)
    print(f"📌 Noticia seleccionada:\n   {noticia['titulo']} ({noticia['fuente']})\n")

    print("✍️  Generando post con Gemini...")
    post = generar_post(noticia)
    print(f"\n--- PREVIEW ---\n{post}\n--- FIN ---\n")

    print("📨 Enviando a Telegram...")
    enviar_telegram(post, noticia)


if __name__ == "__main__":
    main()