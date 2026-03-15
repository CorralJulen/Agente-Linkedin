# Agente LinkedIn — Guía de instalación

## 1. Subir archivos a Oracle Cloud

```bash
# Desde tu máquina local con PowerShell
scp -r linkedin_agent/ ubuntu@TU_IP_ORACLE:/home/ubuntu/
```

## 2. Instalar dependencias en el servidor

```bash
ssh ubuntu@TU_IP_ORACLE
cd linkedin_agent
pip3 install -r requirements.txt --break-system-packages
```

## 3. Configurar credenciales

```bash
cp .env.example .env
nano .env   # rellena tus claves reales
```

### Cómo obtener cada clave:

**GEMINI_API_KEY**
→ https://aistudio.google.com/app/apikey (gratuito)

**TELEGRAM_BOT_TOKEN**
→ Abre Telegram → busca @BotFather → escribe /newbot → sigue los pasos → copia el token

**TELEGRAM_CHAT_ID**
→ Abre Telegram → busca @userinfobot → escríbele cualquier cosa → te responde con tu Chat ID

**NEWSAPI_KEY** (opcional)
→ https://newsapi.org/register (gratuito, 100 peticiones/día)

## 4. Probar manualmente

```bash
python3 agent.py
```

Si todo va bien, recibirás un mensaje en Telegram con el post generado.

## 5. Programar con cron (lunes y jueves a las 8:00)

```bash
crontab -e
```

Añade esta línea al final:

```
0 8 * * 1,4 cd /home/ubuntu/linkedin_agent && python3 agent.py >> /home/ubuntu/linkedin_agent/logs.txt 2>&1
```

Guarda y sal. Para verificar que está activo:

```bash
crontab -l
```

## 6. Ver logs

```bash
tail -f /home/ubuntu/linkedin_agent/logs.txt
```

## Flujo completo

```
Cron (lunes y jueves 8:00)
        ↓
Busca noticias (RSS + NewsAPI)
        ↓
Selecciona la más relevante
        ↓
Gemini genera el post en español
        ↓
Telegram te lo envía
        ↓
Tú lo revisas, añades tu toque y publicas en LinkedIn ✅
```
