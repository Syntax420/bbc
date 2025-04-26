import os
import logging
import hmac
import hashlib
import time
import requests
import json
from typing import Dict, Optional, Tuple

logger = logging.getLogger("api.auth")

def validate_api_keys(api_key: str, api_secret: str, testnet: bool = False) -> bool:
    """
    Validiert API-Keys durch Test-Anfrage an Bybit API
    
    Args:
        api_key: Bybit API-Key
        api_secret: Bybit API-Secret
        testnet: Ob Testnet verwendet werden soll
        
    Returns:
        True wenn API-Keys gültig sind, False sonst
    """
    try:
        logger.info("Validiere API-Keys...")
        
        if not api_key or not api_secret:
            logger.error("API-Key oder API-Secret fehlt")
            return False
            
        # Definiere API-Endpunkt basierend auf Testnet-Flag
        endpoint = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        path = "/v5/account/wallet-balance"
        url = f"{endpoint}{path}"
        
        # Generiere Timestamp für Signatur
        timestamp = str(int(time.time() * 1000))
        
        # Bereite Parameter vor
        params = {
            "accountType": "UNIFIED",
            "timestamp": timestamp
        }
        
        # Generiere Signatur
        query_string = "&".join([f"{key}={params[key]}" for key in sorted(params.keys())])
        signature_payload = timestamp + api_key + query_string
        signature = hmac.new(
            api_secret.encode('utf-8'),
            signature_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Erstelle Header
        headers = {
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature
        }
        
        # Sende Anfrage
        response = requests.get(url, params=params, headers=headers)
        
        # Prüfe Antwort
        if response.status_code != 200:
            logger.error(f"API-Anfrage fehlgeschlagen: HTTP {response.status_code}")
            return False
            
        data = response.json()
        
        if "retCode" in data and data["retCode"] == 0:
            logger.info("API-Keys erfolgreich validiert ✅")
            return True
        else:
            error_code = data.get("retCode", "unbekannt")
            error_msg = data.get("retMsg", "Keine Fehlermeldung")
            logger.error(f"API-Key-Fehler (Code {error_code}): {error_msg}")
            
            # Spezifische Fehlerbehandlung für häufige Probleme
            if error_code == 10001:
                logger.error("Ungültiger API-Key: Bitte überprüfe deine API-Keys")
            elif error_code == 10003:
                logger.error("Ungültige Signatur: API-Secret könnte falsch sein")
            
            return False
            
    except Exception as e:
        logger.critical(f"Kritischer API-Fehler bei der Validierung: {str(e)}", exc_info=True)
        return False

def get_server_time(testnet: bool = False) -> Optional[int]:
    """
    Ruft die aktuelle Serverzeit von Bybit ab
    
    Args:
        testnet: Ob Testnet verwendet werden soll
        
    Returns:
        Serverzeit in Millisekunden oder None bei Fehler
    """
    try:
        endpoint = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        url = f"{endpoint}/v5/market/time"
        
        response = requests.get(url)
        
        if response.status_code != 200:
            logger.error(f"Serverzeit-Anfrage fehlgeschlagen: HTTP {response.status_code}")
            return None
            
        data = response.json()
        
        if "retCode" in data and data["retCode"] == 0:
            time_sec = data.get("result", {}).get("timeSecond", 0)
            return int(float(time_sec) * 1000)  # In Millisekunden umwandeln
        else:
            logger.error(f"Serverzeit-Anfrage fehlgeschlagen: {data.get('retMsg', 'Unbekannter Fehler')}")
            return None
            
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Serverzeit: {str(e)}")
        return None
        
def calculate_time_offset(testnet: bool = False) -> Tuple[int, bool]:
    """
    Berechnet den Zeitversatz zwischen lokalem System und Bybit-Server
    
    Args:
        testnet: Ob Testnet verwendet werden soll
        
    Returns:
        Tuple mit (Zeitversatz in ms, Erfolg-Flag)
    """
    try:
        server_time = get_server_time(testnet)
        
        if server_time is None:
            return 0, False
            
        local_time = int(time.time() * 1000)
        offset = server_time - local_time
        
        if abs(offset) > 5000:  # Mehr als 5 Sekunden Unterschied
            logger.warning(f"Große Zeitdifferenz zwischen System und Server: {offset}ms")
        else:
            logger.debug(f"Zeitdifferenz zum Server: {offset}ms")
            
        return offset, True
        
    except Exception as e:
        logger.error(f"Fehler bei der Berechnung des Zeitversatzes: {str(e)}")
        return 0, False 