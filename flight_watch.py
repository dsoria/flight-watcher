"""
flight_watch.py
----------------
Consulta el precio de un vuelo específico en Google Flights (vía fast-flights,
sin necesidad de API key) y manda un aviso a Telegram cuando el precio baja
al objetivo que definiste en config.json.

Pensado para correr automáticamente con GitHub Actions (ver
.github/workflows/check-price.yml), pero también puedes ejecutarlo a mano:

    python flight_watch.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

try:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
except ImportError:
    from fast_flights import FlightData, Passengers, get_flights

    FlightQuery = None
    create_query = None

CONFIG_PATH = "config.json"
STATE_PATH = "state.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def send_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("⚠️  Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID; no se pudo notificar.")
        print("Mensaje que se hubiera enviado:\n", message)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=20,
    )
    if not resp.ok:
        print(f"⚠️  Error enviando Telegram: {resp.status_code} {resp.text}")


def get_depart_dates(cfg):
    dates = cfg.get("depart_dates")
    if dates is not None:
        if isinstance(dates, str):
            return [dates]
        return [str(date) for date in dates]

    depart_date = cfg.get("depart_date")
    return [depart_date] if depart_date else []


def build_query(cfg):
    direct_only = cfg.get("direct_only", False)
    max_stops = 0 if direct_only else None

    if create_query is not None and FlightQuery is not None:
        flights = [
            FlightQuery(
                date=cfg["depart_date"],
                from_airport=cfg["origin"],
                to_airport=cfg["destination"],
            )
        ]
        trip = "one-way"
        if cfg.get("return_date"):
            flights.append(
                FlightQuery(
                    date=cfg["return_date"],
                    from_airport=cfg["destination"],
                    to_airport=cfg["origin"],
                )
            )
            trip = "round-trip"

        return create_query(
            flights=flights,
            trip=trip,
            seat=cfg.get("seat", "economy"),
            passengers=Passengers(adults=cfg.get("adults", 1)),
            currency=cfg.get("currency", "USD"),
            max_stops=max_stops,
        )

    flight_data = [
        FlightData(
            date=cfg["depart_date"],
            from_airport=cfg["origin"],
            to_airport=cfg["destination"],
            max_stops=max_stops,
        )
    ]
    trip = "one-way"
    if cfg.get("return_date"):
        flight_data.append(
            FlightData(
                date=cfg["return_date"],
                from_airport=cfg["destination"],
                to_airport=cfg["origin"],
                max_stops=max_stops,
            )
        )
        trip = "round-trip"

    return {
        "flight_data": flight_data,
        "trip": trip,
        "seat": cfg.get("seat", "economy"),
        "passengers": Passengers(
            adults=cfg.get("adults", 1),
            children=cfg.get("children", 0),
        ),
        "max_stops": max_stops,
    }


def build_queries(cfg):
    depart_dates = get_depart_dates(cfg)
    if not depart_dates:
        raise ValueError("No se encontró ninguna fecha de salida en config.json")

    queries = []
    for depart_date in depart_dates:
        day_cfg = dict(cfg)
        day_cfg["depart_date"] = depart_date
        queries.append(build_query(day_cfg))
    return depart_dates, queries


def parse_price(value):
    if value is None:
        return float("inf")
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text.lower() == "price unavailable":
        return float("inf")

    numeric = text.replace("$", "").replace(",", "")
    if numeric.lower().startswith("mx"):
        numeric = numeric[2:]
    try:
        return float(numeric)
    except ValueError:
        return float("inf")


def get_flight_date(flight, depart_dates):
    departure = getattr(flight, "departure", None)
    if not departure:
        return None

    raw_date = str(departure).split(" on ", 1)[-1].strip()
    normalized_raw = raw_date.replace(" 0", " ")

    for depart_date in depart_dates:
        dt = datetime.strptime(depart_date, "%Y-%m-%d")
        candidates = {
            dt.strftime("%a, %b %d").replace(" 0", " "),
            dt.strftime("%a, %b %-d").replace(" 0", " "),
        }
        if normalized_raw in candidates:
            return depart_date

    return None


def main():
    cfg = load_json(CONFIG_PATH, None)
    if cfg is None:
        print("❌ No encontré config.json. Copia config.example.json y ajústalo.")
        sys.exit(1)

    state = load_json(STATE_PATH, {"notified": False, "best_price": None})

    depart_dates, queries = build_queries(cfg)
    all_flights = []
    for query in queries:
        if create_query is not None and FlightQuery is not None:
            result = get_flights(query)
        else:
            result = get_flights(**query)

        flights = getattr(result, "flights", result if isinstance(result, list) else [])
        all_flights.extend(flights)

    if not all_flights:
        print("❌ No se encontraron vuelos para esa búsqueda.")
        sys.exit(1)

    cheapest = min(all_flights, key=lambda f: parse_price(getattr(f, "price", None)))
    price = parse_price(getattr(cheapest, "price", None))
    if price == float("inf"):
        print("❌ No se pudo obtener un precio válido para la opción más barata.")
        sys.exit(1)

    currency = cfg.get("currency", "USD")
    target = cfg.get("target_price")
    dates_text = ", ".join(depart_dates)
    cheapest_date = get_flight_date(cheapest, depart_dates) or depart_dates[0]

    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"{cfg['origin']} → {cfg['destination']} en {dates_text}: "
          f"precio más barato = {price} {currency} (objetivo: {target} {currency})")

    now_iso = datetime.now(timezone.utc).isoformat()
    state["last_checked"] = now_iso
    state["last_price"] = price

    departure_time = getattr(cheapest, "departure", "N/A")
    arrival_time = getattr(cheapest, "arrival", "N/A")
    departure_label = cfg.get("depart_date") if len(depart_dates) == 1 else dates_text

    if len(depart_dates) > 1:
        date_line = (
            f"Fechas consultadas: {dates_text}\n"
            f"Fecha con mejor precio: {cheapest_date}\n"
            f"Opción más barata entre esas fechas: {price} {currency}"
        )
    else:
        date_line = f"Salida: {departure_label}"

    msg = (
        f"✈️ <b>Precio más barato encontrado</b>\n\n"
        f"{cfg['origin']} → {cfg['destination']}\n"
        + date_line
        + (f"\nHora de salida: {departure_time}" if departure_time and departure_time != "N/A" else "")
        + (f"\nRegreso: {cfg['return_date']}" if cfg.get("return_date") else "")
        + (f"\nHora de llegada: {arrival_time}" if arrival_time and arrival_time != "N/A" and cfg.get("return_date") is None else "")
        + f"\n\n💰 Precio actual: <b>{price} {currency}</b>\n"
        + (f"🎯 Objetivo configurado: {target} {currency}\n" if target is not None else "")
        + f"Aerolínea(s): {getattr(cheapest, 'name', 'N/A')}\n\n"
        + f"Revisado: {now_iso}"
    )

    send_telegram(msg)
    state["notified"] = True
    print("✅ Precio más barato enviado por Telegram.")

    save_json(STATE_PATH, state)


if __name__ == "__main__":
    main()
