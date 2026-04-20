import json
import os
import requests
import pandas as pd
import ta
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TAO_BUY_PRICE = float(os.environ.get("TAO_BUY_PRICE", "0"))

STATE_FILE = "market_state.json"


# ----------------------------
# DATA FUNCTIONS
# ----------------------------

def safe_get(url, params=None):
    try:
        return requests.get(url, params=params, timeout=10).json()
    except requests.RequestException:
        return None


def get_crypto_data(coin_id):
    params = {"vs_currency": "usd", "days": 120, "interval": "daily"}
    data = safe_get(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
        params=params,
    )
    if not data or "prices" not in data:
        return None
    prices = [p[1] for p in data["prices"]]
    df = pd.DataFrame(prices, columns=["close"])
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    return df


def get_current_price(coin_id):
    data = safe_get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": coin_id, "vs_currencies": "usd"},
    )
    if data and coin_id in data:
        return data[coin_id]["usd"]
    return None


def get_fear_greed():
    data = safe_get("https://api.alternative.me/fng/")
    if data:
        return int(data["data"][0]["value"])
    return None


def get_btc_dominance():
    data = safe_get("https://api.coingecko.com/api/v3/global")
    if data:
        return data["data"]["market_cap_percentage"]["btc"]
    return None


# ----------------------------
# STATE
# ----------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# ----------------------------
# TAO TRACKING
# ----------------------------

def get_tao_report():
    tao_price = get_current_price("bittensor")
    if tao_price is None:
        return "❌ Impossible de récupérer le prix TAO"

    lines = [f"🤖 TAO/Bittensor: {round(tao_price, 2)}$"]

    if TAO_BUY_PRICE > 0:
        pct = ((tao_price - TAO_BUY_PRICE) / TAO_BUY_PRICE) * 100
        lines.append(f"   Prix d'achat: {TAO_BUY_PRICE}$")
        lines.append(f"   P&L: {round(pct, 1)}%")

        if pct >= 200:
            lines.append("🚨 ALERTE +200% — Sécurise 50% de la position")
        elif pct <= -60:
            lines.append("🔴 ALERTE -60% — Tiens le plan (pas de vente panique)")

    return "\n".join(lines)


# ----------------------------
# QUARTERLY NARRATIVE REPORT
# ----------------------------

NARRATIVES = ["AI", "RWA", "Layer 2", "DeFi"]


def is_quarterly_check():
    return datetime.now().month in [1, 4, 7, 10] and datetime.now().day <= 7


def get_quarterly_report():
    if not is_quarterly_check():
        return ""

    quarter_map = {1: "Q1", 4: "Q2", 7: "Q3", 10: "Q4"}
    quarter = quarter_map[datetime.now().month]
    year = datetime.now().year

    narrative_list = "\n".join(f"  ☐ {n}" for n in NARRATIVES)

    return f"""
📅 RAPPORT TRIMESTRIEL — {quarter} {year}

Narratives à checker (30 min) :
{narrative_list}

Checklist :
  ☐ Quelle narrative a le plus performé ce trimestre ?
  ☐ Allouer 50€ à la prochaine narrative
  ☐ Ne pas vendre la position précédente
  ☐ Vérifier P&L TAO (+200% → sécuriser 50% / -60% → tenir le plan)
  ☐ Confirmer DCA BTC/ETH du mois"""


# ----------------------------
# ANALYSIS
# ----------------------------

def analyze():
    btc = get_crypto_data("bitcoin")
    eth = get_crypto_data("ethereum")

    if btc is None or eth is None:
        return "❌ Erreur récupération données marché"

    btc_price = btc["close"].iloc[-1]
    eth_price = eth["close"].iloc[-1]
    btc_rsi = btc["rsi"].iloc[-1]
    eth_rsi = eth["rsi"].iloc[-1]

    fear = get_fear_greed()
    dominance = get_btc_dominance()

    score = 0
    score += max(0, min((btc_rsi - 30) * 1.5, 30))
    score += max(0, min((eth_rsi - 30) * 1.2, 25))
    if fear:
        score += max(0, min((fear - 20) * 0.8, 25))
    score = int(score)

    if score < 25:
        phase = "🐻 Bear"
    elif score < 50:
        phase = "🧊 Accumulation"
    elif score < 75:
        phase = "📈 Bull intermédiaire"
    else:
        phase = "🚀 Bull fort"

    accumulation_alert = ""
    if btc_rsi < 35 and fear and fear < 20:
        accumulation_alert = "🟢 Zone d'accumulation probable (peur extrême)"

    altseason = "❌ Non"
    if dominance and dominance < 48 and eth_rsi > btc_rsi:
        altseason = "✅ Probable"

    correction_alert = ""
    btc_recent_high = btc["close"].rolling(window=4).max().iloc[-1]
    if btc_price < btc_recent_high * 0.8:
        correction_alert = "⚠️ Correction > -20% détectée"

    tao_report = get_tao_report()
    quarterly = get_quarterly_report()

    allocation = """🎯 DCA mensuel fixe (300€/mois) :
  • 90€  CW8 — MSCI World (PEA)
  • 30€  S&P500 (PEA)
  • 30€  PAASI — Asie émergente (PEA)
  • 70€  BTC (OKX)
  • 30€  ETH (OKX)
  • 50€  Narrative trimestrielle → TAO/Bittensor Q2 2026"""

    message = f"""📊 CRYPTO DASHBOARD

BTC: {round(btc_price, 2)}$
ETH: {round(eth_price, 2)}$
Dominance BTC: {round(dominance, 2) if dominance else "N/A"}%

RSI BTC: {round(btc_rsi, 1)}
RSI ETH: {round(eth_rsi, 1)}
Fear & Greed: {fear if fear else "N/A"}

Score Cycle: {score}/100
Phase: {phase}

{allocation}

{tao_report}

Altseason: {altseason}
{accumulation_alert}
{correction_alert}

Date: {datetime.now().date()}"""

    if quarterly:
        message += f"\n{quarterly}"

    previous_state = load_state()
    current_state = {
        "phase": phase,
        "score_level": (
            "low" if score < 25 else
            "mid" if score < 50 else
            "high" if score < 75 else
            "extreme"
        ),
        "altseason": altseason,
        "accumulation": bool(accumulation_alert),
        "correction": bool(correction_alert),
    }

    alert_message = ""
    if previous_state:
        if previous_state.get("phase") != current_state["phase"]:
            alert_message += f"🚨 Changement de phase: {previous_state.get('phase')} → {phase}\n"
        if previous_state.get("score_level") != current_state["score_level"]:
            alert_message += "📊 Score franchit un seuil important\n"
        if previous_state.get("altseason") != current_state["altseason"] and altseason == "✅ Probable":
            alert_message += "🔥 Altseason détectée\n"
        if not previous_state.get("accumulation") and current_state["accumulation"]:
            alert_message += "🟢 Nouvelle zone accumulation détectée\n"
        if not previous_state.get("correction") and current_state["correction"]:
            alert_message += "⚠️ Correction > -20% détectée\n"

    save_state(current_state)

    if alert_message:
        message = "🚨 ALERTE MARCHÉ 🚨\n\n" + alert_message + "\n\n" + message

    return message


# ----------------------------
# TELEGRAM
# ----------------------------

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload, timeout=10)
        print("Telegram response:", response.status_code)
    except requests.RequestException as e:
        print("Telegram error:", e)


# ----------------------------
# RUN
# ----------------------------

if __name__ == "__main__":
    msg = analyze()
    print(msg)
    send_telegram(msg)
