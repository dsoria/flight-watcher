# ✈️ Flight Watcher

Vigila el precio de **un vuelo específico** y te avisa por Telegram el día
que el precio baje a lo que tú definas. Corre gratis con GitHub Actions,
sin servidores, sin API keys de pago.

Usa [`fast-flights`](https://github.com/AWeirdDev/flights), una librería que
llama directo al endpoint interno de Google Flights (no HTML scraping, no
navegador) — por eso no necesita API key ni cuesta nada.

## 1. Crea el repo en GitHub

1. Crea un repositorio nuevo (puede ser privado) en tu cuenta de GitHub.
2. Sube estos archivos tal cual están.

## 2. Crea tu bot de Telegram (gratis, 2 minutos)

1. En Telegram, busca **@BotFather** y mándale `/newbot`.
2. Sigue las instrucciones y te dará un **token** (algo como
   `123456789:ABCdefGhIJKlmNoPQRstuVwxyZ`). Guárdalo.
3. Ahora necesitas tu **chat_id**:
   - Búscate a **@userinfobot** en Telegram y mándale cualquier mensaje;
     te devuelve tu `Id` numérico. Ese es tu `chat_id`.
   - (O bien: mándale un mensaje a tu bot nuevo, luego abre en el navegador
     `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y busca el campo
     `"chat":{"id": ...}`.)

## 3. Configura los secrets en GitHub

En tu repo: **Settings → Secrets and variables → Actions → New repository secret**

- `TELEGRAM_BOT_TOKEN` → el token que te dio BotFather
- `TELEGRAM_CHAT_ID` → tu chat_id numérico

## 4. Configura tu vuelo

Copia `config.example.json` a `config.json` y edítalo:

```json
{
  "origin": "MEX",
  "destination": "MAD",
  "depart_date": "2026-12-10",
  "return_date": "2026-12-20",
  "target_price": 600,
  "currency": "USD",
  "seat": "economy",
  "adults": 1
}
```

- `origin` / `destination`: códigos IATA de aeropuerto (ej. `MEX`, `MAD`, `JFK`).
- `depart_date` / `return_date`: formato `YYYY-MM-DD`. Si es solo ida,
  **borra la línea `return_date`** por completo.
- `target_price`: el precio al que quieres que te avisen (número, sin símbolo).
- `seat`: `economy`, `premium-economy`, `business` o `first`.

Sube ese `config.json` al repo (con `git add config.json` etc., o subiéndolo
desde la web de GitHub).

## 5. Listo — se ejecuta solo

El workflow en `.github/workflows/check-price.yml` corre automáticamente
2 veces al día (13:00 y 23:00 UTC — ajusta la hora si quieres, con
[crontab.guru](https://crontab.guru) para armar el cron). También puedes
probarlo ya mismo sin esperar: pestaña **Actions** de tu repo → selecciona
"Check flight price" → **Run workflow**.

Cuando el precio esté en o por debajo de tu objetivo, te llega un mensaje
como:

```
✈️ ¡Baja de precio detectada!

MEX → MAD
Salida: 2026-12-10
Regreso: 2026-12-20

💰 Precio actual: 580 USD
🎯 Tu objetivo era: 600 USD

Aerolínea(s): Iberia

Revisado: 2026-10-03T13:00:12+00:00
```

Solo te avisa **una vez** cuando cruza el umbral (no te va a estar
mandando el mismo aviso cada rato); si el precio vuelve a subir por
encima del objetivo y luego vuelve a bajar, se reactiva la alerta.

## Probarlo en tu computadora (opcional)

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="tu_token"
export TELEGRAM_CHAT_ID="tu_chat_id"
python flight_watch.py
```

## Notas

- `fast-flights` llama a Google Flights de forma no oficial (ingeniería
  inversa de su endpoint interno). Es gratis y no requiere key, pero al no
  ser una API oficial, en teoría Google podría cambiar algo y romperla en
  el futuro — si eso pasa, revisa si hay una versión nueva del paquete
  (`pip install -U fast-flights`).
- `state.json` lo genera y actualiza el propio script; no lo edites a mano.
