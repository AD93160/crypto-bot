import json
import os
import requests
import pandas as pd
import ta
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("8738159038:AAHgt7_wfZBcuTBn9CKeuSnCZt5wl7DrcLg")
CHAT_ID = os.environ.get("8639724254")

# ----------------------------
# DATA FUNCTIONS
# ----------------------------

def safe_get(url):
    try:
        return requests.get(url, timeout=10).json()
    except:
        return None


def get_crypto_data(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": "usd",
            "days": 120,
            "interval": "daily"
        }

        data = requests.get(url, params=params, timeout=10).json()

        prices = [p[1] for p in data["prices"]]

        df = pd.DataFrame(prices, columns=["close"])
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

        return df

    except:
        return None

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "_","_","_","_","_","_"
    ])

    df["close"] = df["close"].astype(float)
    df["time"] = pd.to_datetime(df["time"], unit='ms')
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

    return df


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
# ANALYSIS
# ----------------------------

STATE_FILE = "market_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
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

    # Progressive Score
    score = 0
    score += max(0, min((btc_rsi - 30) * 1.5, 30))
    score += max(0, min((eth_rsi - 30) * 1.2, 25))

    if fear:
        score += max(0, min((fear - 20) * 0.8, 25))

    score = int(score)

# Phase + Allocation dynamique

    if score < 25:
        phase = "🐻 Bear"
        base_allocation = 35
    elif score < 50:
        phase = "🧊 Accumulation"
        base_allocation = 50
    elif score < 75:
        phase = "📈 Bull intermédiaire"
        base_allocation = 60
    else:
        phase = "🚀 Bull fort"
        base_allocation = 70

    allocation_pct = base_allocation

    # Accumulation alert
    accumulation_alert = ""
    if btc_rsi < 35 and fear and fear < 20:
        accumulation_alert = "🟢 Zone d'accumulation probable (peur extrême)"
        allocation_pct += 10

    # Altseason detection
    altseason = "❌ Non"
    if dominance and dominance < 48 and eth_rsi > btc_rsi:
        altseason = "✅ Probable"
        allocation_pct += 5

    # Correction -20%
    correction_alert = ""
    btc_recent_high = btc["close"].rolling(window=4).max().iloc[-1]
    if btc_price < btc_recent_high * 0.8:
        correction_alert = "⚠️ Correction > -20% détectée"
        allocation_pct -= 10

    # Limites de sécurité
    allocation_pct = max(20, min(allocation_pct, 80))

    allocation = f"Crypto {allocation_pct}% / ETF {100 - allocation_pct}%"

    message = f"""
📊 CRYPTO DASHBOARD V3

BTC: {round(btc_price,2)}$
ETH: {round(eth_price,2)}$

Dominance BTC: {round(dominance,2) if dominance else "N/A"}%

RSI BTC: {round(btc_rsi,1)}
RSI ETH: {round(eth_rsi,1)}
Fear & Greed: {fear if fear else "N/A"}

Score Cycle: {score}/100
Phase: {phase}

🎯 Allocation suggérée:
{allocation}

Altseason: {altseason}

{accumulation_alert}
{correction_alert}

Date: {datetime.now().date()}
"""

    # ----------------------------
    # ALERT LOGIC
    # ----------------------------

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
        "correction": bool(correction_alert)
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
    print("Sending telegram...")
    print("Token exists:", TELEGRAM_TOKEN is not None)
    print("Chat ID:", CHAT_ID)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    response = requests.post(url, data=payload, timeout=10)
    print("Telegram response:", response.text)
