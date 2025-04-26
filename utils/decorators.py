import functools
import time
import logging
import traceback
from typing import Callable, Any, Optional, Dict, Type

logger = logging.getLogger("utils.decorators")

def handle_errors(func: Callable) -> Callable:
    """
    Dekorator für allgemeine Fehlerbehandlung
    
    Fängt alle Ausnahmen ab, protokolliert sie und gibt None zurück
    
    Args:
        func: Zu dekorierende Funktion
        
    Returns:
        Dekorierte Funktion mit Fehlerbehandlung
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fehler in {func.__name__}: {str(e)}", exc_info=True)
            
            # Spezifische Fehlerbehandlung basierend auf Fehlertyp oder -nachricht
            error_msg = str(e).lower()
            
            if "api key" in error_msg:
                logger.critical("API-Key-Fehler. Bitte überprüfe deine API-Zugangsdaten.")
            elif "symbol" in error_msg:
                logger.error("Symbol-Fehler. Überprüfe die verwendeten Trading-Symbole.")
            elif "connection" in error_msg or "timeout" in error_msg:
                logger.error("Verbindungsfehler. Überprüfe deine Internetverbindung.")
            elif "permission" in error_msg or "access" in error_msg:
                logger.critical("Berechtigungsfehler. Überprüfe die API-Key-Berechtigungen.")
            elif "insufficient balance" in error_msg or "insufficient fund" in error_msg:
                logger.critical("Unzureichendes Guthaben für die Operation.")
            elif "rate limit" in error_msg:
                logger.warning("Rate-Limit erreicht. Die Anfrage wird verlangsamt.")
            
            return None
    
    return wrapper

def retry(max_attempts: int = 3, delay: float = 2.0, 
         exponential_backoff: bool = True,
         allowed_exceptions: Optional[Dict[Type[Exception], bool]] = None) -> Callable:
    """
    Dekorator für automatische Wiederholungen bei Ausnahmen
    
    Args:
        max_attempts: Maximale Anzahl von Versuchen
        delay: Verzögerung zwischen Versuchen in Sekunden
        exponential_backoff: Ob die Verzögerung exponentiell erhöht werden soll
        allowed_exceptions: Dict mit Ausnahmen und ob sie wiederholt werden sollen
                           None = alle Ausnahmen wiederholen
                           
    Returns:
        Dekorierte Funktion mit Wiederholungslogik
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            # Standardmäßig alle Ausnahmen wiederholen, wenn nicht angegeben
            if allowed_exceptions is None:
                should_retry = lambda e: True
            else:
                # Prüft, ob die Ausnahme in der Liste der erlaubten Ausnahmen ist
                should_retry = lambda e: any(
                    isinstance(e, exc_type) and should_retry_flag
                    for exc_type, should_retry_flag in allowed_exceptions.items()
                )
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Bestimme, ob wir wiederholen sollen
                    if not should_retry(e):
                        logger.info(f"Ausnahme {type(e).__name__} wird nicht wiederholt.")
                        raise
                    
                    # Beende, wenn dies der letzte Versuch war
                    if attempt == max_attempts:
                        logger.error(f"Maximale Anzahl von Versuchen ({max_attempts}) erreicht. Letzter Fehler: {str(e)}")
                        raise
                    
                    # Berechne Verzögerung
                    if exponential_backoff:
                        current_delay = delay * (2 ** (attempt - 1))
                    else:
                        current_delay = delay
                    
                    logger.warning(f"Versuch {attempt}/{max_attempts} fehlgeschlagen mit {type(e).__name__}: {str(e)}. "
                                  f"Wiederholung in {current_delay:.2f}s...")
                    
                    # Warte vor dem nächsten Versuch
                    time.sleep(current_delay)
            
            # Sollte nie erreicht werden, da entweder ein Ergebnis zurückgegeben wird
            # oder die Ausnahme des letzten Versuchs erneut ausgelöst wird
            raise last_exception
        
        return wrapper
    
    return decorator

def log_execution_time(logger_obj=None) -> Callable:
    """
    Dekorator zur Protokollierung der Ausführungszeit einer Funktion
    
    Args:
        logger_obj: Logger-Objekt, das verwendet werden soll (optional)
                   Falls None, wird der Standard-Logger verwendet
    
    Returns:
        Dekorierte Funktion, die ihre Ausführungszeit protokolliert
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Bestimme, welcher Logger verwendet werden soll
            log = logger_obj or logger
            
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                log.debug(f"Funktion {func.__name__} ausgeführt in {execution_time:.4f} Sekunden")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                log.error(f"Funktion {func.__name__} fehlgeschlagen nach {execution_time:.4f} Sekunden: {str(e)}")
                raise
                
        return wrapper
    
    return decorator

def safe_api_call(func: Callable) -> Callable:
    """
    Dekorator speziell für API-Aufrufe mit besserer Fehlerbehandlung
    
    Kombiniert Wiederholungsversuche und Fehlerprotokollierung für API-Aufrufe
    
    Args:
        func: API-Aufruf-Funktion
        
    Returns:
        Dekorierte Funktion mit API-Fehlerbehandlung
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Bestimme Endpunkt-Name für bessere Protokollierung
            endpoint = func.__name__ if hasattr(func, "__name__") else "unknown_endpoint"
            
            # Messe Ausführungszeit
            start_time = time.time()
            
            # Führe API-Aufruf aus
            response = func(*args, **kwargs)
            
            # Berechne Latenz
            latency = (time.time() - start_time) * 1000  # in Millisekunden
            
            # Prüfe auf verschiedene API-Antwortformate
            if isinstance(response, dict):
                # Neues Format mit retCode
                if "retCode" in response:
                    if response["retCode"] == 0:
                        logger.debug(f"API-Aufruf {endpoint} erfolgreich in {latency:.2f}ms")
                        return response.get("result", response)
                    else:
                        error_code = response.get("retCode", "unbekannt")
                        error_msg = response.get("retMsg", "Keine Fehlermeldung")
                        logger.error(f"API-Fehler bei {endpoint}: Code {error_code}, Meldung: {error_msg}")
                        
                        # Spezifische Behandlung häufiger Fehler
                        if error_code == 10001:
                            logger.critical("Ungültiger API-Key: Bitte überprüfe deine API-Keys")
                        elif error_code == 10003:
                            logger.error("Ungültige Signatur: API-Secret könnte falsch sein")
                        elif error_code == 10006 or error_code == 10016:
                            logger.warning("Rate-Limit überschritten")
                            # Warte kurz und versuche es erneut
                            time.sleep(2)
                            return func(*args, **kwargs)
                        
                        return None
                # Legacy-Format oder anderes Antwortformat
                else:
                    logger.debug(f"API-Aufruf {endpoint} erfolgreich in {latency:.2f}ms (altes Format)")
                    return response
            else:
                logger.warning(f"Unerwartetes Antwortformat von {endpoint}: {type(response)}")
                return response
            
        except Exception as e:
            error_msg = f"API-Aufruffehler in {func.__name__}: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Spezifische Fehlerbehandlung
            if "Connection" in str(e) or "Timeout" in str(e):
                logger.error("Verbindungsproblem mit der API. Prüfe deine Internetverbindung.")
            
            return None
            
    return wrapper 