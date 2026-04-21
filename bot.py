import json
import os
import time
import requests
import pandas as pd
import ta
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RENDER_BUY_PRICE = float(os.environ.get("RENDER_BUY_PRICE", "0"))

STATE_FILE = "market_state.json"


# ----------------------------
# DATA FUNCTIONS
# ----------------------------

def safe_get(url, params=None):
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
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
# RENDER TRACKING
# ----------------------------

def get_render_report():
    render_price = get_current_price("render-token")
    if render_price is None:
        return "❌ Impossible de récupérer le prix RENDER"

    lines = [f"🖥️ RENDER: {round(render_price, 2)}$"]

    if RENDER_BUY_PRICE > 0:
        pct = ((render_price - RENDER_BUY_PRICE) / RENDER_BUY_PRICE) * 100
        lines.append(f"   Prix d'achat: {RENDER_BUY_PRICE}$")
        lines.append(f"   P&L: {round(pct, 1)}%")

        if pct >= 200:
            lines.append("🚨 ALERTE +200% — Sécurise 50% de la position")
        elif pct <= -60:
            lines.append("🔴 ALERTE -60% — Tiens le plan (pas de vente panique)")

    return "\n".join(lines)


# ----------------------------
# NARRATIVE SCORING
# ----------------------------

CATEGORY_IDS = {
    "AI": "artificial-intelligence",
    "RWA": "real-world-assets-rwa",
    "Layer 2": "layer-2",
    "DeFi": "decentralized-finance-defi",
}


def get_category_coins(category_id, limit=10):
    time.sleep(1)   # éviter le rate limit CoinGecko
    data = safe_get(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={
            "vs_currency": "usd",
            "category": category_id,
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "price_change_percentage": "7d,30d",
        },
    )
    return data if isinstance(data, list) else []


def score_coin(coin, fear, phase, altseason):
    score = 50

    change_7d = coin.get("price_change_percentage_7d_in_currency") or 0
    change_30d = coin.get("price_change_percentage_30d_in_currency") or 0
    rank = coin.get("market_cap_rank") or 999

    # Momentum 7j — sweet spot : début de mouvement, pas encore euphorique
    if 3 <= change_7d <= 25:
        score += 25
    elif change_7d > 25:
        score += 5      # déjà pumped
    elif change_7d < -15:
        score -= 20
    elif change_7d < 0:
        score -= 10

    # Tendance 30j
    if change_30d > 10:
        score += 15
    elif change_30d > 0:
        score += 8
    elif change_30d < -30:
        score -= 15
    elif change_30d < 0:
        score -= 8

    # Phase : en Bear, éviter les small caps
    if "Bear" in phase and rank > 100:
        score -= 20
    if "Bull fort" in phase and rank < 15:
        score -= 5      # large caps = moins d'upside en bull fort

    # Altseason : booster les alts
    if altseason == "✅ Probable":
        score += 10

    # Peur extrême + dip 30j = opportunité d'accumulation
    if fear and fear < 25 and change_30d < -20:
        score += 10

    return score


def get_narrative_recommendation(fear, phase, altseason):
    results = {}
    for narrative, cat_id in CATEGORY_IDS.items():
        coins = get_category_coins(cat_id)
        if not coins:
            continue
        best = max(coins, key=lambda c: score_coin(c, fear, phase, altseason))
        results[narrative] = {
            "name": best["name"],
            "symbol": best["symbol"].upper(),
            "price": best["current_price"],
            "change_7d": best.get("price_change_percentage_7d_in_currency") or 0,
            "change_30d": best.get("price_change_percentage_30d_in_currency") or 0,
            "rank": best.get("market_cap_rank"),
            "score": score_coin(best, fear, phase, altseason),
        }
    return results


def format_narrative_report(fear, phase, altseason):
    try:
        results = get_narrative_recommendation(fear, phase, altseason)
        if not results:
            return "⚠️ Données narratives indisponibles"

        winner_key = max(results, key=lambda k: results[k]["score"])
        lines = ["🏆 MEILLEURE CRYPTO PAR NARRATIVE"]

        for narrative, d in results.items():
            star = " ⭐" if narrative == winner_key else ""
            sign_7d = "+" if d["change_7d"] >= 0 else ""
            sign_30d = "+" if d["change_30d"] >= 0 else ""
            lines.append(
                f"{narrative}{star}: {d['name']} ({d['symbol']})\n"
                f"   {d['price']}$ | 7j: {sign_7d}{round(d['change_7d'], 1)}% | "
                f"30j: {sign_30d}{round(d['change_30d'], 1)}%"
            )

        w = results[winner_key]
        lines.append(f"\n→ Meilleur choix pour tes 50€ : {w['name']} ({winner_key})")
        return "\n".join(lines)
    except Exception as e:
        print(f"Narrative scoring error: {e}")
        return "⚠️ Scoring narratif temporairement indisponible"


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
  ☐ Vérifier P&L RENDER (+200% → sécuriser 50% / -60% → tenir le plan)
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

    tao_report = get_render_report()
    narrative_report = format_narrative_report(fear, phase, altseason)
    quarterly = get_quarterly_report()

    allocation = """🎯 DCA mensuel fixe (300€/mois) :
  • 90€  CW8 — MSCI World (PEA)
  • 30€  S&P500 (PEA)
  • 30€  PAASI — Asie émergente (PEA)
  • 70€  BTC (OKX)
  • 30€  ETH (OKX)
  • 50€  Narrative trimestrielle → RENDER Q2 2026"""

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

{narrative_report}

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
