import csv
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Union

logger = logging.getLogger("utils.trade_logger")

class TradeLogger:
    """
    Logger für Handelsaktivitäten, der CSV-Dateien nach Datum sortiert erstellt
    """
    def __init__(self, base_dir: str = "trade_history"):
        self.trade_dir = Path(base_dir)
        self.trade_dir.mkdir(exist_ok=True)
        
        # Dateiname im Format trades_YYYYMMDD.csv
        self.current_date = datetime.now().strftime('%Y%m%d')
        self.file_path = self.trade_dir / f"trades_{self.current_date}.csv"
        
        # Felder für CSV
        self.fields = [
            "timestamp", "symbol", "side", "quantity", 
            "price", "order_id", "order_link_id", "status", 
            "profit_loss", "leverage", "order_type", "position_value",
            "entry_price", "exit_price", "stop_loss", "take_profit",
            "strategy", "trade_id", "notes"
        ]
        
        # Initialisiere CSV, falls nicht vorhanden
        self._init_csv()
        
        logger.info(f"Trade-Logger initialisiert. Speicherort: {self.file_path}")

    def _init_csv(self):
        """Initialisiert die CSV-Datei mit Header, falls sie noch nicht existiert"""
        if not self.file_path.exists():
            try:
                with open(self.file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.fields)
                logger.info(f"Neue Trade-History-Datei erstellt: {self.file_path}")
            except Exception as e:
                logger.error(f"Fehler beim Erstellen der Trade-History-Datei: {e}")
    
    def _check_date(self):
        """
        Prüft, ob sich das Datum geändert hat und erstellt eine neue Datei
        für das aktuelle Datum, falls erforderlich
        """
        current_date = datetime.now().strftime('%Y%m%d')
        
        if current_date != self.current_date:
            self.current_date = current_date
            self.file_path = self.trade_dir / f"trades_{self.current_date}.csv"
            self._init_csv()
            logger.info(f"Datum hat sich geändert. Neue Log-Datei: {self.file_path}")

    def log_trade(self, 
                 symbol: str, 
                 side: str, 
                 qty: float, 
                 price: float, 
                 order_id: str = None,
                 order_link_id: str = None,
                 status: str = "FILLED", 
                 pnl: float = None,
                 leverage: float = None,
                 order_type: str = None,
                 position_value: float = None,
                 entry_price: float = None,
                 exit_price: float = None,
                 stop_loss: float = None,
                 take_profit: float = None,
                 strategy: str = None,
                 trade_id: str = None,
                 notes: str = None) -> bool:
        """
        Loggt einen Trade in die CSV-Datei
        
        Args:
            symbol: Trading-Symbol (z.B. BTCUSDT)
            side: Handelsrichtung (BUY/SELL)
            qty: Handelsmenge
            price: Ausführungspreis
            order_id: ID der Order von der Börse
            order_link_id: Benutzerdefinierte Order-ID
            status: Status der Order (z.B. FILLED, CANCELED)
            pnl: Gewinn/Verlust des Trades
            leverage: Verwendeter Hebel
            order_type: Ordertyp (MARKET, LIMIT, etc.)
            position_value: Wert der Position
            entry_price: Einstiegspreis
            exit_price: Ausstiegspreis
            stop_loss: Stop-Loss-Preis
            take_profit: Take-Profit-Preis
            strategy: Verwendete Handelsstrategie
            trade_id: Eindeutige Trade-ID
            notes: Zusätzliche Notizen
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        # Prüfe, ob ein neuer Tag begonnen hat
        self._check_date()
        
        try:
            # Erstellung einer eindeutigen Trade-ID, falls nicht vorhanden
            if not trade_id:
                timestamp = int(datetime.now().timestamp())
                trade_id = f"trade-{symbol}-{timestamp}"
            
            # Bereite Daten vor
            row_data = {field: None for field in self.fields}
            
            # Timestamp formatieren
            row_data["timestamp"] = datetime.now().isoformat()
            
            # Fülle Pflichtfelder
            row_data["symbol"] = symbol
            row_data["side"] = side
            row_data["quantity"] = qty
            row_data["price"] = price
            row_data["trade_id"] = trade_id
            
            # Optionale Felder
            if order_id:
                row_data["order_id"] = order_id
            if order_link_id:
                row_data["order_link_id"] = order_link_id
            if status:
                row_data["status"] = status
            if pnl is not None:
                row_data["profit_loss"] = pnl
            if leverage is not None:
                row_data["leverage"] = leverage
            if order_type:
                row_data["order_type"] = order_type
            if position_value is not None:
                row_data["position_value"] = position_value
            if entry_price is not None:
                row_data["entry_price"] = entry_price
            if exit_price is not None:
                row_data["exit_price"] = exit_price
            if stop_loss is not None:
                row_data["stop_loss"] = stop_loss
            if take_profit is not None:
                row_data["take_profit"] = take_profit
            if strategy:
                row_data["strategy"] = strategy
            if notes:
                row_data["notes"] = notes
            
            # In CSV schreiben
            with open(self.file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                writer.writerow(row_data)
            
            # Log-Eintrag
            log_msg = f"Trade protokolliert: {side} {qty} {symbol} @ {price}"
            if pnl is not None:
                log_msg += f", PnL: {pnl:.2f}"
            if strategy:
                log_msg += f", Strategie: {strategy}"
                
            logger.info(log_msg)
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Protokollieren des Trades: {e}")
            return False
    
    def log_trade_dict(self, trade_data: Dict) -> bool:
        """
        Loggt einen Trade aus einem Dictionary
        
        Args:
            trade_data: Dictionary mit Trade-Daten
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            required_fields = ["symbol", "side", "quantity", "price"]
            
            # Prüfe, ob alle Pflichtfelder vorhanden sind
            missing_fields = [field for field in required_fields if field not in trade_data]
            if missing_fields:
                logger.error(f"Fehlende Pflichtfelder in Trade-Daten: {missing_fields}")
                return False
            
            # Extrahiere Pflichtfelder
            symbol = trade_data["symbol"]
            side = trade_data["side"]
            qty = float(trade_data["quantity"])
            price = float(trade_data["price"])
            
            # Extrahiere optionale Felder
            kwargs = {}
            for field in self.fields:
                if field in trade_data and field not in ["symbol", "side", "quantity", "price"]:
                    kwargs[field] = trade_data[field]
            
            # Logge Trade
            return self.log_trade(symbol, side, qty, price, **kwargs)
            
        except Exception as e:
            logger.error(f"Fehler beim Protokollieren des Trades aus Dictionary: {e}")
            return False
    
    def get_daily_trades(self, date_str: str = None) -> List[Dict]:
        """
        Lädt Trades für ein bestimmtes Datum
        
        Args:
            date_str: Datum im Format YYYYMMDD, None für aktuelles Datum
            
        Returns:
            Liste der Trades als Dictionaries
        """
        if date_str is None:
            date_str = self.current_date
            
        file_path = self.trade_dir / f"trades_{date_str}.csv"
        
        if not file_path.exists():
            logger.warning(f"Keine Trade-History für Datum {date_str} gefunden")
            return []
            
        try:
            trades = []
            with open(file_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Konvertiere numerische Werte
                    for field in ["quantity", "price", "profit_loss", "leverage", "position_value", 
                                  "entry_price", "exit_price", "stop_loss", "take_profit"]:
                        if field in row and row[field] not in [None, ""]:
                            try:
                                row[field] = float(row[field])
                            except ValueError:
                                pass  # Belasse als String falls Konvertierung fehlschlägt
                    trades.append(row)
            
            logger.info(f"{len(trades)} Trades für {date_str} geladen")
            return trades
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Trades für {date_str}: {e}")
            return []
    
    def get_trade_by_id(self, trade_id: str) -> Optional[Dict]:
        """
        Sucht einen Trade anhand seiner ID
        
        Args:
            trade_id: Zu suchende Trade-ID
            
        Returns:
            Trade-Dictionary oder None, wenn nicht gefunden
        """
        # Liste alle Trade-Dateien
        trade_files = [f for f in os.listdir(self.trade_dir) if f.startswith("trades_") and f.endswith(".csv")]
        
        # Durchsuche alle Dateien
        for file_name in trade_files:
            file_path = self.trade_dir / file_name
            
            try:
                with open(file_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("trade_id") == trade_id:
                            logger.debug(f"Trade mit ID {trade_id} gefunden")
                            return row
            except Exception as e:
                logger.error(f"Fehler beim Durchsuchen von {file_path}: {e}")
        
        logger.warning(f"Trade mit ID {trade_id} nicht gefunden")
        return None
    
    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Sucht Trades für ein bestimmtes Symbol
        
        Args:
            symbol: Zu suchendes Symbol
            limit: Maximale Anzahl der zurückzugebenden Trades
            
        Returns:
            Liste der Trades als Dictionaries
        """
        # Liste alle Trade-Dateien
        trade_files = [f for f in os.listdir(self.trade_dir) if f.startswith("trades_") and f.endswith(".csv")]
        trade_files.sort(reverse=True)  # Neueste zuerst
        
        trades = []
        
        # Durchsuche alle Dateien
        for file_name in trade_files:
            if len(trades) >= limit:
                break
                
            file_path = self.trade_dir / file_name
            
            try:
                with open(file_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("symbol") == symbol:
                            trades.append(row)
                            if len(trades) >= limit:
                                break
            except Exception as e:
                logger.error(f"Fehler beim Durchsuchen von {file_path}: {e}")
        
        logger.info(f"{len(trades)} Trades für Symbol {symbol} gefunden")
        return trades
    
    def get_trade_statistics(self, start_date: str = None, end_date: str = None, 
                            symbol: str = None, strategy: str = None) -> Dict:
        """
        Berechnet Handelsstatistiken für einen bestimmten Zeitraum
        
        Args:
            start_date: Startdatum im Format YYYYMMDD
            end_date: Enddatum im Format YYYYMMDD
            symbol: Optionale Filterung nach Symbol
            strategy: Optionale Filterung nach Strategie
            
        Returns:
            Dictionary mit Statistiken
        """
        # Liste alle Trade-Dateien
        trade_files = [f for f in os.listdir(self.trade_dir) if f.startswith("trades_") and f.endswith(".csv")]
        
        # Filtere nach Datum
        filtered_files = []
        for file_name in trade_files:
            # Extrahiere Datum aus Dateinamen
            try:
                date_str = file_name.replace("trades_", "").replace(".csv", "")
                
                # Prüfe, ob Datum im gewünschten Bereich liegt
                if start_date and date_str < start_date:
                    continue
                if end_date and date_str > end_date:
                    continue
                    
                filtered_files.append(file_name)
            except Exception:
                logger.warning(f"Konnte Datum nicht aus Dateinamen extrahieren: {file_name}")
        
        # Sammle alle Trades
        all_trades = []
        for file_name in filtered_files:
            file_path = self.trade_dir / file_name
            
            try:
                with open(file_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Filterung nach Symbol
                        if symbol and row.get("symbol") != symbol:
                            continue
                            
                        # Filterung nach Strategie
                        if strategy and row.get("strategy") != strategy:
                            continue
                            
                        # Füge Trade hinzu
                        all_trades.append(row)
            except Exception as e:
                logger.error(f"Fehler beim Laden von {file_path}: {e}")
        
        # Wenn keine Trades gefunden wurden
        if not all_trades:
            logger.warning("Keine Trades für die angegebenen Filter gefunden")
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "net_profit": 0.0,
                "max_profit": 0.0,
                "max_loss": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0
            }
        
        # Berechne Statistiken
        total_trades = len(all_trades)
        
        # Gewinne und Verluste
        profits = []
        losses = []
        
        for trade in all_trades:
            pnl = trade.get("profit_loss")
            
            # Überspringe Trades ohne PnL
            if pnl is None or pnl == "":
                continue
                
            # Konvertiere zu float falls nötig
            if isinstance(pnl, str):
                try:
                    pnl = float(pnl)
                except ValueError:
                    continue
                    
            if pnl > 0:
                profits.append(pnl)
            elif pnl < 0:
                losses.append(pnl)
        
        # Berechne Metriken
        winning_trades = len(profits)
        losing_trades = len(losses)
        
        total_profit = sum(profits) if profits else 0.0
        total_loss = sum(losses) if losses else 0.0
        net_profit = total_profit + total_loss
        
        max_profit = max(profits) if profits else 0.0
        max_loss = min(losses) if losses else 0.0
        
        avg_profit = total_profit / winning_trades if winning_trades > 0 else 0.0
        avg_loss = total_loss / losing_trades if losing_trades > 0 else 0.0
        
        win_rate = (winning_trades / (winning_trades + losing_trades)) * 100 if (winning_trades + losing_trades) > 0 else 0.0
        
        stats = {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "total_loss": total_loss,
            "net_profit": net_profit,
            "max_profit": max_profit,
            "max_loss": max_loss,
            "avg_profit": avg_profit,
            "avg_loss": avg_loss
        }
        
        logger.info(f"Handelsstatistiken berechnet: {total_trades} Trades, Win-Rate: {win_rate:.1f}%, Net-Profit: {net_profit:.2f}")
        return stats
    
    def export_to_json(self, output_file: str = None) -> bool:
        """
        Exportiert alle Trades als JSON-Datei
        
        Args:
            output_file: Pfad zur Ausgabedatei, None für auto-generiert
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        if output_file is None:
            output_file = self.trade_dir / f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        # Liste alle Trade-Dateien
        trade_files = [f for f in os.listdir(self.trade_dir) if f.startswith("trades_") and f.endswith(".csv")]
        
        # Sammle alle Trades
        all_trades = []
        for file_name in trade_files:
            file_path = self.trade_dir / file_name
            
            try:
                with open(file_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        all_trades.append(row)
            except Exception as e:
                logger.error(f"Fehler beim Laden von {file_path}: {e}")
        
        # Speichere als JSON
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_trades, f, indent=2)
                
            logger.info(f"{len(all_trades)} Trades als JSON exportiert: {output_file}")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Exportieren als JSON: {e}")
            return False 