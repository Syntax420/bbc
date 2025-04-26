import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from .base_strategy import BaseStrategy
from utils.decorators import handle_errors, log_execution_time

logger = logging.getLogger("strategy.donchian")

class DonchianStrategy(BaseStrategy):
    """
    Verbesserte Donchian-Channel-Strategie
    
    Handelt auf Basis des Donchian-Kanal-Indikators mit Trendfilter und Volumenbestätigung
    """
    def __init__(self, 
                period: int = 20, 
                exit_period: int = 10,
                atr_period: int = 14,
                atr_multiplier: float = 2.0,
                volume_threshold: float = 1.5,
                timeframe: str = "15m"):
        """
        Initialisiert die Donchian-Channel-Strategie
        
        Args:
            period: Periodenlänge für Donchian-Kanäle
            exit_period: Periodenlänge für Ausstiegspunkte
            atr_period: Periodenlänge für ATR-Berechnung
            atr_multiplier: Multiplikator für ATR (Stop-Loss Bestimmung)
            volume_threshold: Volumenschwelle (Multiplikator des durchschnittlichen Volumens)
            timeframe: Zeitrahmen für die Analyse
        """
        super().__init__(name="DonchianChannel", timeframe=timeframe)
        
        self.period = period
        self.exit_period = exit_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.volume_threshold = volume_threshold
        
        self.logger.info(f"Donchian-Strategie initialisiert: Periode={period}, "
                        f"Exit-Periode={exit_period}, ATR-Periode={atr_period}, "
                        f"ATR-Multiplikator={atr_multiplier}, Volumenschwelle={volume_threshold}")
    
    def get_min_required_candles(self) -> int:
        """
        Gibt die Mindestanzahl an Kerzen zurück, die für die Strategie benötigt werden
        
        Returns:
            Mindestanzahl an Kerzen
        """
        # ATR benötigt die meisten historischen Daten in dieser Strategie
        # Wir brauchen etwas mehr als die längste Periode für zuverlässige Berechnungen
        return max(self.period, self.atr_period) + 10
    
    @handle_errors
    def calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Berechnet technische Indikatoren für die Donchian-Channel-Strategie
        
        Args:
            df: DataFrame mit OHLCV-Daten
            
        Returns:
            Dictionary mit berechneten Indikatoren
        """
        # Sicherstellen, dass die Daten aufsteigend nach Zeit sortiert sind
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp", ascending=True)
            
        # Donchian-Kanäle berechnen
        highest_high = df["high"].rolling(window=self.period).max()
        lowest_low = df["low"].rolling(window=self.period).min()
        
        # Mittellinie
        middle_line = (highest_high + lowest_low) / 2
        
        # Ausstiegskanal berechnen (kürzere Periode)
        exit_high = df["high"].rolling(window=self.exit_period).max()
        exit_low = df["low"].rolling(window=self.exit_period).min()
        
        # ATR berechnen (Average True Range)
        tr1 = df["high"] - df["low"]  # Aktueller Bereich
        tr2 = abs(df["high"] - df["close"].shift(1))  # Hoch vs. vorheriges Schließen
        tr3 = abs(df["low"] - df["close"].shift(1))  # Tief vs. vorheriges Schließen
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        # Volumen-Indikator (Verhältnis zum Durchschnittsvolumen)
        avg_volume = df["volume"].rolling(window=self.period).mean()
        volume_ratio = df["volume"] / avg_volume
        
        # Trendfilter berechnen
        sma20 = df["close"].rolling(window=20).mean()
        sma50 = df["close"].rolling(window=50).mean()
        trend_up = sma20 > sma50
        
        # Volatilitätsindikator
        volatility = atr / df["close"] * 100  # Volatilität in Prozent
        
        # Stop-Loss- und Take-Profit-Levels
        stop_loss_long = df["close"] - (atr * self.atr_multiplier)
        stop_loss_short = df["close"] + (atr * self.atr_multiplier)
        take_profit_long = df["close"] + (atr * self.atr_multiplier * 1.5)
        take_profit_short = df["close"] - (atr * self.atr_multiplier * 1.5)
        
        # Momentum-Indikator (Rate of Change)
        roc = (df["close"] / df["close"].shift(self.period)) - 1
        
        # Ergebnisse zusammenfassen
        indicators = {
            "highest_high": highest_high.iloc[-1],
            "lowest_low": lowest_low.iloc[-1],
            "middle_line": middle_line.iloc[-1],
            "exit_high": exit_high.iloc[-1],
            "exit_low": exit_low.iloc[-1],
            "atr": atr.iloc[-1],
            "volume_ratio": volume_ratio.iloc[-1],
            "trend_up": trend_up.iloc[-1],
            "volatility": volatility.iloc[-1],
            "stop_loss_long": stop_loss_long.iloc[-1],
            "stop_loss_short": stop_loss_short.iloc[-1],
            "take_profit_long": take_profit_long.iloc[-1],
            "take_profit_short": take_profit_short.iloc[-1],
            "roc": roc.iloc[-1],
            
            # Für Charts und erweiterte Analyse
            "highest_high_series": highest_high.values,
            "lowest_low_series": lowest_low.values,
            "middle_line_series": middle_line.values,
            "atr_series": atr.values,
            "close": df["close"].iloc[-1],
            "timestamp": df["timestamp"].iloc[-1] if "timestamp" in df.columns else None
        }
        
        return indicators
    
    @handle_errors
    def generate_signals(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generiert Handelssignale basierend auf berechneten Indikatoren
        
        Args:
            df: DataFrame mit OHLCV-Daten
            indicators: Dictionary mit berechneten Indikatoren
            
        Returns:
            Dictionary mit Handelssignalen
        """
        # Sicherstellen, dass die Daten in absteigender Reihenfolge sortiert sind
        # (neueste Daten zuerst), um die letzten Werte leicht abzurufen
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp", ascending=False)
        
        # Aktuelle Schlusskurse und indikatoren
        current_close = df["close"].iloc[0]
        previous_close = df["close"].iloc[1] if len(df) > 1 else None
        
        # Extrahiere Indikatoren
        highest_high = indicators["highest_high"]
        lowest_low = indicators["lowest_low"]
        exit_high = indicators["exit_high"]
        exit_low = indicators["exit_low"]
        atr = indicators["atr"]
        volume_ratio = indicators["volume_ratio"]
        trend_up = indicators["trend_up"]
        volatility = indicators["volatility"]
        roc = indicators["roc"]
        
        # Initialisiere das Signal als neutral
        signal = "neutral"
        strength = 0.0
        reason = "Keine klaren Signale"
        
        # Kaufsignal: Schlusskurs bricht über den höchsten Hoch der Periode
        # mit Volumenbestätigung und Aufwärtstrend
        if (current_close > highest_high and 
            previous_close <= highest_high and
            volume_ratio > self.volume_threshold and
            trend_up):
            signal = "buy"
            # Berechne Signalstärke basierend auf mehreren Faktoren
            # Höhere Volatilität, höheres Volumen und stärkerer Momentum erhöhen die Signalstärke
            strength = min(0.9, (0.5 + 
                          (volume_ratio / 10) + 
                          (roc * 10 if roc > 0 else 0) + 
                          (volatility / 100)))
            reason = f"Ausbruch über Donchian-Oberband ({highest_high:.2f}) mit erhöhtem Volumen ({volume_ratio:.2f}x) im Aufwärtstrend"
        
        # Verkaufssignal: Schlusskurs bricht unter das niedrigste Tief der Periode
        # mit Volumenbestätigung und Abwärtstrend
        elif (current_close < lowest_low and 
              previous_close >= lowest_low and
              volume_ratio > self.volume_threshold and
              not trend_up):
            signal = "sell"
            # Berechne Signalstärke
            strength = min(0.9, (0.5 + 
                          (volume_ratio / 10) + 
                          (abs(roc) * 10 if roc < 0 else 0) + 
                          (volatility / 100)))
            reason = f"Ausbruch unter Donchian-Unterband ({lowest_low:.2f}) mit erhöhtem Volumen ({volume_ratio:.2f}x) im Abwärtstrend"
        
        # Exit-Signale für bestehende Positionen
        # Ausstieg aus Long, wenn Preis unter kurzfristiges Tief fällt
        elif current_close < exit_low and previous_close >= exit_low:
            signal = "exit_long"
            strength = 0.7
            reason = f"Preis unterhalb des kurzfristigen Tiefs ({exit_low:.2f})"
        
        # Ausstieg aus Short, wenn Preis über kurzfristiges Hoch steigt
        elif current_close > exit_high and previous_close <= exit_high:
            signal = "exit_short"
            strength = 0.7
            reason = f"Preis oberhalb des kurzfristigen Hochs ({exit_high:.2f})"
            
        # Schwächere Signale bei Annäherung an Ausbruchspunkte
        elif current_close > (highest_high - atr * 0.5) and current_close < highest_high:
            signal = "buy_weak"
            strength = 0.3
            reason = f"Annäherung an obere Kanalbegrenzung ({highest_high:.2f})"
            
        elif current_close < (lowest_low + atr * 0.5) and current_close > lowest_low:
            signal = "sell_weak"
            strength = 0.3
            reason = f"Annäherung an untere Kanalbegrenzung ({lowest_low:.2f})"
        
        # Erweiterte Signaldetails
        details = {
            "signal": signal,
            "strength": strength,
            "reason": reason,
            "price": current_close,
            "highest_high": highest_high,
            "lowest_low": lowest_low,
            "exit_high": exit_high,
            "exit_low": exit_low,
            "stop_loss_level": indicators["stop_loss_long"] if signal == "buy" else
                              indicators["stop_loss_short"] if signal == "sell" else None,
            "take_profit_level": indicators["take_profit_long"] if signal == "buy" else
                                indicators["take_profit_short"] if signal == "sell" else None,
            "atr": atr,
            "volume_ratio": volume_ratio,
            "trend_up": trend_up,
            "risk_reward_ratio": 1.5  # Standard Risiko-Ertrags-Verhältnis
        }
        
        # Füge letzte Kerze zur besseren Analyse hinzu
        if not df.empty:
            last_candle = {
                "timestamp": df["timestamp"].iloc[0] if "timestamp" in df.columns else None,
                "open": df["open"].iloc[0],
                "high": df["high"].iloc[0],
                "low": df["low"].iloc[0],
                "close": df["close"].iloc[0],
                "volume": df["volume"].iloc[0] if "volume" in df.columns else None
            }
            details["last_candle"] = last_candle
        
        return details
    
    def get_recommended_symbols(self) -> List[str]:
        """
        Gibt eine Liste von empfohlenen Symbolen für diese Strategie zurück
        
        Returns:
            Liste von empfohlenen Symbolen
        """
        # Donchian-Strategie funktioniert gut bei Symbolen mit klaren Trends und mittlerer Volatilität
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT", "MATICUSDT", "AAVEUSDT", "DOGEUSDT"]
    
    def calculate_position_size(self, price: float, stop_loss: float, 
                               risk_amount: float, account_size: float = None,
                               max_risk_percent: float = 1.0) -> Dict[str, Any]:
        """
        Berechnet die optimale Positionsgröße basierend auf Risikomanagement-Parametern
        
        Args:
            price: Aktueller Preis
            stop_loss: Stop-Loss-Preis
            risk_amount: Maximaler Verlustbetrag für diesen Trade
            account_size: Gesamtkontostand (optional)
            max_risk_percent: Maximaler Prozentsatz des Kontos für diesen Trade
            
        Returns:
            Dictionary mit Positionsgrößendaten
        """
        # Berechne Verlust pro Einheit
        risk_per_unit = abs(price - stop_loss)
        
        if risk_per_unit <= 0:
            return {
                "position_size": 0,
                "error": "Stop-Loss ist zu nah am Eintrittspreis"
            }
        
        # Berechne Positionsgröße basierend auf risikiertem Betrag
        position_size = risk_amount / risk_per_unit
        
        # Beschränke Risiko auf maximalen Prozentsatz des Kontos
        if account_size is not None:
            max_risk_amount = account_size * (max_risk_percent / 100)
            max_position_size = max_risk_amount / risk_per_unit
            
            if position_size > max_position_size:
                position_size = max_position_size
                
        # Runde auf angemessene Anzahl von Dezimalstellen ab
        if price < 1:
            position_size = round(position_size, 3)  # Für niedrigpreisige Assets
        elif price < 10:
            position_size = round(position_size, 2)
        elif price < 1000:
            position_size = round(position_size, 1)
        else:
            position_size = round(position_size)  # Für hochpreisige Assets
        
        # Stelle sicher, dass die Position nicht Null ist
        if position_size <= 0:
            return {
                "position_size": 0,
                "error": "Berechnete Positionsgröße ist zu klein"
            }
            
        # Berechne die tatsächlichen Risikometriken
        actual_risk_amount = position_size * risk_per_unit
        risk_percent = (actual_risk_amount / account_size * 100) if account_size else None
        
        return {
            "position_size": position_size,
            "risk_per_unit": risk_per_unit,
            "actual_risk_amount": actual_risk_amount,
            "risk_percent": risk_percent,
            "entry_price": price,
            "stop_loss": stop_loss
        } 