# Bybit Trading Bot - Verbesserungen

Diese Dokumentation beschreibt die Verbesserungen, die am Bybit Trading Bot vorgenommen wurden, um Stabilität, Sicherheit und Funktionalität zu erhöhen.

## Übersicht der Verbesserungen

1. **API-Key-Validierung & Fehlerbehandlung**
   - Robustere Überprüfung von API-Keys vor Handelsaktivitäten
   - Detaillierte Fehlermeldungen für API-Probleme

2. **Zentralisiertes Logging-System**
   - Strukturierte Logs mit Rotationsmechanismus
   - Separate Logs für verschiedene Bereiche (API, Strategien, Fehler)

3. **Trade-History-CSV**
   - Automatische Protokollierung aller Trades mit umfangreichen Metadaten
   - Tägliche CSV-Dateien für einfache Nachverfolgung und Analyse

4. **WebSocket-Verbesserungen**
   - Robuste Neuverbindungslogik mit Exponential-Backoff
   - Bessere Fehlerbehandlung für WebSocket-Verbindungen

5. **Konfigurationssystem**
   - Unterstützung für .env-Dateien
   - Flexible Konfigurationsoptionen mit Validierung

6. **Error-Handling-Wrapper**
   - Dekoratoren für einheitliche Fehlerbehandlung
   - Automatische Wiederholversuche für instabile Funktionen

7. **Verbesserte Strategie-Framework**
   - Objektorientiertes Design für Handelsstrategien
   - Besseres Backtesting und Signalgenerierung

## Installation und Setup

### Voraussetzungen

- Python 3.9 oder höher
- Bybit-Konto mit API-Schlüsseln

### Installation

1. Installiere die erforderlichen Pakete:

```bash
pip install -r requirements.txt
```

2. Kopiere die Datei `config/env_example.txt` nach `.env` und fülle deine API-Keys ein:

```bash
cp config/env_example.txt .env
```

3. Bearbeite die .env-Datei mit deinen persönlichen Einstellungen:

```
BYBIT_API_KEY = "dein_api_key_hier"
BYBIT_API_SECRET = "dein_api_secret_hier"
TESTNET = True  # Auf False setzen für Live-Trading
```

## Verwendung

### Bot starten

```bash
python main.py
```

Der Bot wird beim Start nach dem Modus fragen (Paper oder Live Trading).

### Module und ihre Funktionen

- **api/auth.py**: API-Key-Validierung
- **api/websocket.py**: Verbesserte WebSocket-Verbindungen
- **utils/trade_logger.py**: Trade-History-Protokollierung
- **utils/decorators.py**: Error-Handling-Wrapper
- **config/settings.py**: Konfigurationsmanagement
- **strategy/base_strategy.py**: Basis-Strategieklasse
- **strategy/donchian_strategy.py**: Verbesserte Donchian-Strategie

## Beispiel für Donchian-Strategie

Die verbesserte Donchian-Channel-Strategie bietet folgende Features:

- Automatische Stop-Loss- und Take-Profit-Berechnung
- Volumenbestätigung für Signale
- Trendfilter zur Vermeidung von Fehlsignalen
- Dynamische Positionsgrößenberechnung

Beispielcode für die Verwendung:

```python
from strategy.donchian_strategy import DonchianStrategy
from api.bybit_api import BybitAPI
from utils.trade_logger import TradeLogger

# Initialisiere API
api = BybitAPI(api_key="DEIN_API_KEY", api_secret="DEIN_API_SECRET", testnet=True)
api.initialize()

# Initialisiere Strategie
strategy = DonchianStrategy(period=20, timeframe="15m")

# Logge Trades
trade_logger = TradeLogger()

# Hole Daten und analysiere
symbol = "BTCUSDT"
candles = api.get_kline(symbol=symbol, interval="15", limit=100)
if candles.success:
    analysis = strategy.analyze(candles.data, symbol=symbol)
    
    if analysis["signal"] == "buy":
        # Berechne Positionsgröße
        position_size = strategy.calculate_position_size(
            price=analysis["price"],
            stop_loss=analysis["stop_loss_level"],
            risk_amount=10,  # $10 Risiko pro Trade
            account_size=1000  # $1000 Kontostand
        )
        
        # Führe Order aus und protokolliere
        order = api.place_market_order(
            symbol=symbol,
            side="Buy",
            qty=position_size["position_size"],
            stop_loss=position_size["stop_loss"]
        )
        
        # Protokolliere Trade
        trade_logger.log_trade(
            symbol=symbol,
            side="Buy",
            qty=position_size["position_size"],
            price=analysis["price"],
            order_id=order.data.get("orderId"),
            strategy="Donchian"
        )
```

## Fehlerbehandlung

Der Bot enthält jetzt robuste Fehlerbehandlung:

- Automatische Wiederholversuche für temporäre Fehler
- Detaillierte Fehlerprotokolle für Diagnose
- Graceful Shutdown bei kritischen Fehlern

## Weiterentwicklung

Zukünftige Verbesserungen könnten beinhalten:

- Implementierung weiterer Strategien
- Webinterface zur Steuerung und Überwachung
- Erweitertes Backtesting-Framework
- Integration von ML-basierten Signalgeneratoren

## Troubleshooting

Bei Problemen:

1. Überprüfe die Logdateien im Verzeichnis `logs/`
2. Validiere deine API-Schlüssel mit `python test_api_connection.py`
3. Stelle sicher, dass dein Konto genügend Guthaben hat

## Haftungsausschluss

Dieses Handelssystem dient nur zu Bildungszwecken. Handeln Sie auf eigenes Risiko und nur mit Kapital, dessen Verlust Sie sich leisten können. 