# 📊 Crypto Bot — Tracker Macro Personnel

Bot automatisé d'analyse macro crypto.
Exécution quotidienne via GitHub Actions.
Alertes Telegram intelligentes.

---

## 🎯 Ce que fait le bot

- Analyse momentum (RSI BTC + ETH)
- Analyse sentiment (Fear & Greed Index)
- Analyse dominance BTC
- Détecte rotation altseason
- Détecte zones accumulation extrême
- Suggère allocation dynamique Crypto/ETF
- Envoie alertes uniquement si changement de phase

---

## 📊 Indicateurs utilisés

| Indicateur | Source | Utilité |
|------------|--------|---------|
| RSI BTC/ETH | CoinGecko | Momentum |
| Fear & Greed | Alternative.me | Sentiment |
| Dominance BTC | CoinGecko | Rotation capital |
| Score Cycle | Calculé | Phase macro |

---

## 🚀 Déploiement

Le bot tourne sur GitHub Actions (gratuit).

Exécution : 1 fois par jour à 09:00 UTC

Repo : https://github.com/AD93160/crypto-bot

---

## 🔐 Configuration

Variables d'environnement (GitHub Secrets) :

TELEGRAM_TOKEN = ton_token
CHAT_ID = ton_chat_id

Configurées dans : Settings → Secrets and variables → Actions

---

## 🧠 Logique d'allocation

| Score | Phase | Allocation suggérée |
|-------|-------|---------------------|
| 0–25 | Bear | 35% crypto |
| 25–50 | Accumulation | 50% crypto |
| 50–75 | Bull intermédiaire | 60% crypto |
| 75+ | Bull fort | 70% crypto |

Ajustements dynamiques :

- +10% si accumulation extrême (RSI < 35 + Fear < 20)
- +5% si altseason probable
- -10% si correction > -20%

Limites : 20% min / 80% max

---

## 🟢 Zone accumulation

Affichée si :

RSI BTC < 35 ET Fear & Greed < 20

---

## 🔥 Altseason

Détectée si :

Dominance BTC < 48% ET RSI ETH > RSI BTC

---

## 🛠️ Installation locale

git clone https://github.com/AD93160/crypto-bot.git
cd crypto-bot
pip3 install -r requirements.txt
python3 bot.py

---

## 📦 Dépendances

requests
pandas
ta

---

## 📅 Historique

- Mars 2025 : Création V1 (BTC + RSI)
- Mars 2025 : V2 (ETH + Score progressif)
- Mars 2025 : V3 (Dominance + Altseason + Allocation dynamique)
- Mars 2025 : Déploiement GitHub Actions

---

## 🧠 Philosophie

Ce bot ne prédit rien.
Il structure ton comportement d'investisseur.
Il retire l'émotion de l'équation.

---

## 📬 Contact

Bot créé avec l'aide de Claude (Anthropic).
Repo GitHub : https://github.com/AD93160/crypto-bot

---

## ⚠️ Disclaimer

Aucun conseil financier.
Utilisation à tes propres risques.
Les performances passées ne garantissent pas les résultats futurs.
