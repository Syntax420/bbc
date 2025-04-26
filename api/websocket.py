import logging
import time
import threading
import hmac
import hashlib
import json
from typing import Dict, List, Callable, Optional, Any

logger = logging.getLogger("api.websocket")

class BybitWebSocket:
    """
    Verbesserte WebSocket-Klasse für Bybit API mit Fehlerbehandlung und auto-reconnect
    """
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True, time_offset: int = 0):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.time_offset = time_offset
        self.ws = None
        self.callbacks = {}
        self.topics = set()
        self.is_running = True
        self.reconnect_interval = 30  # Sekunden
        self.last_ping_time = 0
        self.ping_interval = 20  # Sekunden
        self.connect_timestamp = 0
        self.monitor_thread = None
        
        # Init WebSocket
        self.endpoint = (
            "wss://stream-testnet.bybit.com/realtime" 
            if testnet 
            else "wss://stream.bybit.com/realtime"
        )
        
        # Import pybit nur wenn benötigt, mit Fehlerbehandlung
        try:
            from pybit.unified_trading import WebSocket
            self.WebSocket = WebSocket
            logger.debug("pybit WebSocket-Modul erfolgreich importiert")
        except ImportError:
            logger.critical("pybit-Modul nicht gefunden. Installiere es mit 'pip install pybit'")
            self.WebSocket = None
            return
        
        # Initialisiere die WebSocket-Verbindung
        self.connect()
        
    def connect(self) -> bool:
        """
        Stellt die WebSocket-Verbindung her und abonniert vorhandene Topics erneut
        
        Returns:
            True bei erfolgreicher Verbindung, False sonst
        """
        try:
            if not self.WebSocket:
                logger.error("WebSocket konnte nicht initialisiert werden: WebSocket-Klasse nicht verfügbar")
                return False
            
            logger.info(f"Verbinde zu Bybit WebSocket: {self.endpoint}")
            
            # Speichere aktuelle Topics für späteren Resubscribe
            current_topics = list(self.topics)
            
            # Schließe bestehende Verbindung falls vorhanden
            if self.ws:
                try:
                    self.ws.exit()
                    logger.debug("Bestehende WebSocket-Verbindung geschlossen")
                except Exception as e:
                    logger.warning(f"Fehler beim Schließen der bestehenden WebSocket-Verbindung: {e}")
                # Warte kurz bevor neue Verbindung geöffnet wird
                time.sleep(2)
            
            # Erstelle Authentifizierung mit korrigiertem Timestamp
            expires = int(time.time() * 1000 + self.time_offset + 10000)  # 10 Sekunden Gültigkeit
            
            # Signature für private WebSocket erstellen
            signature_payload = f"GET/realtime{expires}"
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                signature_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            logger.debug(f"WebSocket Auth: timestamp={expires}, signature={signature[:5]}...")
            
            try:
                # Erstelle WebSocket-Verbindung
                self.ws = self.WebSocket(
                    testnet=self.testnet,
                    channel_type="private",
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    # Explizit Zeitversatz verwenden um Authentifizierungsprobleme zu vermeiden
                    ts_init=expires,
                    sign_init=signature
                )
                
                # Gib Zeit für Verbindungsaufbau
                time.sleep(2)
                
                # Prüfe, ob Verbindung erfolgreich ist
                is_connected = False
                if hasattr(self.ws, 'ws') and self.ws.ws:
                    try:
                        is_connected = self.ws.ws.sock and self.ws.ws.sock.connected
                    except:
                        is_connected = False
                
                if not is_connected:
                    logger.error("WebSocket-Verbindung fehlgeschlagen: Keine aktive Verbindung")
                    return False
                
                # Setze Reconnect-Timestamp
                self.connect_timestamp = time.time()
                
                # Bei erfolgreicher Verbindung alle Topics erneut abonnieren
                if current_topics:
                    logger.info(f"Abonniere {len(current_topics)} vorherige Topics erneut")
                    for topic in current_topics:
                        self._subscribe_topic(topic)
                
                # Starte Monitor-Thread falls noch nicht aktiv
                if not self.monitor_thread or not self.monitor_thread.is_alive():
                    self.is_running = True
                    self.monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
                    self.monitor_thread.start()
                    logger.debug("Monitor-Thread für WebSocket gestartet")
                
                logger.info("WebSocket-Verbindung erfolgreich hergestellt")
                return True
            
            except TypeError as type_error:
                # Falls TypeError auftritt, versuche mit weniger Parametern
                error_msg = str(type_error)
                logger.warning(f"WebSocket-Initialisierungsfehler: {error_msg}")
                
                # Versuche mit minimalen Parametern
                try:
                    self.ws = self.WebSocket(
                        testnet=self.testnet,
                        channel_type="private",
                        api_key=self.api_key,
                        api_secret=self.api_secret
                    )
                    time.sleep(2)
                    logger.info("WebSocket-Verbindung mit minimalen Parametern hergestellt")
                    return True
                except Exception as e:
                    logger.error(f"Zweiter Verbindungsversuch fehlgeschlagen: {e}")
                    return False
            
        except Exception as e:
            logger.error(f"Fehler beim Herstellen der WebSocket-Verbindung: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False

    def _monitor_connection(self):
        """
        Überwacht die WebSocket-Verbindung und führt bei Bedarf Reconnect durch
        """
        reconnect_attempts = 0
        max_consecutive_failures = 5
        
        while self.is_running:
            try:
                # Prüfe, ob Verbindung noch aktiv ist
                is_connected = False
                if self.ws and hasattr(self.ws, 'ws') and self.ws.ws:
                    try:
                        is_connected = self.ws.ws.sock and self.ws.ws.sock.connected
                    except:
                        is_connected = False
                
                # Bei Verbindungsverlust Reconnect durchführen
                if not is_connected:
                    logger.warning("WebSocket nicht verbunden, führe Reconnect durch...")
                    success = self.connect()
                    
                    if success:
                        reconnect_attempts = 0
                        logger.info("WebSocket erfolgreich wieder verbunden")
                    else:
                        reconnect_attempts += 1
                        logger.error(f"WebSocket-Reconnect fehlgeschlagen ({reconnect_attempts}/{max_consecutive_failures})")
                        
                        # Bei zu vielen Fehlern kritischen Fehler loggen
                        if reconnect_attempts >= max_consecutive_failures:
                            logger.critical(f"WebSocket-Verbindung konnte nach {max_consecutive_failures} Versuchen nicht hergestellt werden")
                            # Warte länger vor nächstem Versuch
                            time.sleep(self.reconnect_interval * 2)
                        else:
                            time.sleep(self.reconnect_interval)
                        
                        continue
                
                # Ping senden um Verbindung am Leben zu halten
                current_time = time.time()
                if current_time - self.last_ping_time > self.ping_interval:
                    self._send_ping()
                    self.last_ping_time = current_time
                
                # Warte vor nächster Prüfung
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Fehler im WebSocket-Monitor: {e}")
                time.sleep(self.reconnect_interval)
    
    def _send_ping(self):
        """Sendet Ping an Server um Verbindung am Leben zu halten"""
        try:
            if self.ws and hasattr(self.ws, 'ws') and self.ws.ws and hasattr(self.ws.ws, 'sock'):
                if self.ws.ws.sock and self.ws.ws.sock.connected:
                    self.ws.ws.ping()
                    logger.debug("WebSocket Ping gesendet")
        except Exception as e:
            if "Connection is already closed" in str(e):
                pass  # Ignoriere "bereits geschlossen" Fehler
            else:
                logger.warning(f"Fehler beim Senden des WebSocket-Pings: {e}")
    
    def subscribe(self, topics: List[str], callback: Callable = None):
        """
        Abonniert die angegebenen Topics
        
        Args:
            topics: Liste der zu abonnierenden Topics
            callback: Optionale Callback-Funktion für Updates
        """
        if not self.ws:
            logger.error("WebSocket nicht verbunden, kann Topics nicht abonnieren")
            return False
        
        success = True
        for topic in topics:
            topic_success = self._subscribe_topic(topic, callback)
            success = success and topic_success
            
            if topic_success:
                self.topics.add(topic)
            
        return success
    
    def _subscribe_topic(self, topic: str, callback: Callable = None) -> bool:
        """
        Abonniert ein einzelnes Topic
        
        Args:
            topic: Zu abonnierendes Topic
            callback: Callback-Funktion für Updates
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            if not self.ws:
                logger.error(f"WebSocket nicht verbunden, kann {topic} nicht abonnieren")
                return False
            
            # Speichere Callback für dieses Topic
            if callback:
                self.callbacks[topic] = callback
            
            # Unterscheide nach Topic-Typ
            if topic.startswith("position"):
                self.ws.position_stream(callback=self._on_position_update)
            elif topic.startswith("execution"):
                self.ws.execution_stream(callback=self._on_execution_update)
            elif topic.startswith("order"):
                self.ws.order_stream(callback=self._on_order_update)
            elif topic.startswith("wallet"):
                self.ws.wallet_stream(callback=self._on_wallet_update)
            elif topic.startswith("ticker"):
                symbol = topic.split(".", 1)[1] if "." in topic else None
                if symbol:
                    self.ws.ticker_stream(symbol=symbol, callback=self._on_ticker_update)
                else:
                    logger.error(f"Ungültiges Ticker-Topic: {topic}")
                    return False
            elif topic.startswith("kline"):
                parts = topic.split(".")
                if len(parts) == 3:
                    interval, symbol = parts[1], parts[2]
                    self.ws.kline_stream(interval=interval, symbol=symbol, callback=self._on_kline_update)
                else:
                    logger.error(f"Ungültiges Kline-Topic: {topic}")
                    return False
            else:
                logger.warning(f"Unbekanntes Topic-Format: {topic}")
                return False
            
            logger.info(f"Topic {topic} erfolgreich abonniert")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Abonnieren von {topic}: {e}")
            return False
    
    def unsubscribe(self, topics: List[str]):
        """
        Kündigt das Abonnement für die angegebenen Topics
        
        Args:
            topics: Liste der zu kündigenden Topics
        """
        try:
            if not self.ws:
                logger.error("WebSocket nicht verbunden, kann Abonnements nicht kündigen")
                return False
            
            for topic in topics:
                try:
                    # Entferne aus aktiven Topics
                    if topic in self.topics:
                        self.topics.remove(topic)
                    
                    # Entferne Callback
                    if topic in self.callbacks:
                        del self.callbacks[topic]
                    
                    logger.info(f"Abonnement für {topic} gekündigt")
                except Exception as e:
                    logger.warning(f"Fehler beim Kündigen des Abonnements für {topic}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Fehler beim Kündigen von Abonnements: {e}")
            return False
    
    def close(self):
        """Schließt die WebSocket-Verbindung ordnungsgemäß"""
        try:
            logger.info("Schließe WebSocket-Verbindung...")
            
            # Stoppe Monitor-Thread
            self.is_running = False
            
            # Schließe WebSocket
            if self.ws:
                try:
                    # Markiere als beendet bevor tatsächlich beendet wird
                    if hasattr(self.ws, '_client'):
                        self.ws._client.exited = True
                    
                    self.ws.exit()
                except Exception as e:
                    if "Connection is already closed" in str(e):
                        logger.info("WebSocket-Verbindung war bereits geschlossen")
                    else:
                        logger.warning(f"Fehler beim Schließen der WebSocket-Verbindung: {e}")
                finally:
                    self.ws = None
            
            logger.info("WebSocket-Verbindung geschlossen")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Schließen der WebSocket-Verbindung: {e}")
            return False
    
    # --- Callback-Handler für verschiedene Datentypen ---
    
    def _on_position_update(self, message):
        """Behandelt Position-Updates"""
        try:
            topic = "position"
            logger.debug(f"Position-Update empfangen: {json.dumps(message)[:100]}...")
            
            # Rufe gespeicherten Callback auf
            if topic in self.callbacks and callable(self.callbacks[topic]):
                self.callbacks[topic](message)
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung des Position-Updates: {e}")

    def _on_execution_update(self, message):
        """Behandelt Execution-Updates"""
        try:
            topic = "execution"
            logger.debug(f"Execution-Update empfangen: {json.dumps(message)[:100]}...")
            
            # Rufe gespeicherten Callback auf
            if topic in self.callbacks and callable(self.callbacks[topic]):
                self.callbacks[topic](message)
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung des Execution-Updates: {e}")

    def _on_order_update(self, message):
        """Behandelt Order-Updates"""
        try:
            topic = "order"
            logger.debug(f"Order-Update empfangen: {json.dumps(message)[:100]}...")
            
            # Rufe gespeicherten Callback auf
            if topic in self.callbacks and callable(self.callbacks[topic]):
                self.callbacks[topic](message)
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung des Order-Updates: {e}")

    def _on_wallet_update(self, message):
        """Behandelt Wallet-Updates"""
        try:
            topic = "wallet"
            logger.debug(f"Wallet-Update empfangen: {json.dumps(message)[:100]}...")
            
            # Rufe gespeicherten Callback auf
            if topic in self.callbacks and callable(self.callbacks[topic]):
                self.callbacks[topic](message)
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung des Wallet-Updates: {e}")
    
    def _on_ticker_update(self, message):
        """Behandelt Ticker-Updates"""
        try:
            # Extrahiere Symbol aus Nachricht
            symbol = message.get("data", {}).get("symbol", "unknown")
            topic = f"ticker.{symbol}"
            
            logger.debug(f"Ticker-Update für {symbol} empfangen")
            
            # Rufe gespeicherten Callback auf
            if topic in self.callbacks and callable(self.callbacks[topic]):
                self.callbacks[topic](message)
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung des Ticker-Updates: {e}")
    
    def _on_kline_update(self, message):
        """Behandelt Kline-Updates"""
        try:
            # Extrahiere Symbol und Intervall aus Nachricht
            data = message.get("data", {})
            symbol = data.get("symbol", "unknown")
            interval = data.get("interval", "unknown")
            topic = f"kline.{interval}.{symbol}"
            
            logger.debug(f"Kline-Update für {symbol} ({interval}) empfangen")
            
            # Rufe gespeicherten Callback auf
            if topic in self.callbacks and callable(self.callbacks[topic]):
                self.callbacks[topic](message)
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung des Kline-Updates: {e}") 