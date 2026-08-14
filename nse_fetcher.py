"""
nse_fetcher.py — Robust NSE Option Chain Data Fetcher
Handles session cookie initialization, cloud server anti-bot bypass,
and error handling for Streamlit deployment.
"""

from __future__ import annotations
import time
import pandas as pd
from typing import Tuple, Dict, Any, Optional

try:
    from curl_cffi import requests as impersonate_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import requests as impersonate_requests
    CURL_CFFI_AVAILABLE = False


class NSEFetcher:
    """Fetches real-time option chain data from NSE India with automated session management."""

    BASE_URL = "https://www.nseindia.com"
    API_URL_INDEX = "https://www.nseindia.com/api/option-chain-indices?symbol="

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/option-chain",
    }

    def __init__(self):
        self.session = None
        self._init_session()

    def _init_session(self):
        """Initializes a browser-impersonated session to acquire valid cookies."""
        try:
            if CURL_CFFI_AVAILABLE:
                self.session = impersonate_requests.Session(impersonate="chrome120")
            else:
                import requests
                self.session = requests.Session()

            self.session.headers.update(self.HEADERS)
            # Warm up session by visiting home page first
            resp = self.session.get(self.BASE_URL, timeout=10)
            if resp.status_code != 200:
                time.sleep(1)
                self.session.get(self.BASE_URL, timeout=10)
        except Exception:
            self.session = None

    def fetch_raw_data(self, symbol: str = "NIFTY", retries: int = 3) -> Optional[Dict[str, Any]]:
        """Fetches raw option chain JSON from NSE API with retry attempts."""
        symbol = symbol.upper()
        url = f"{self.API_URL_INDEX}{symbol}"

        for attempt in range(retries):
            try:
                if self.session is None:
                    self._init_session()

                if self.session is None:
                    continue

                response = self.session.get(url, timeout=10)

                if response and response.status_code == 200:
                    return response.json()

                # If cookie expired, re-initialize session and retry
                if response and response.status_code in [401, 403]:
                    self._init_session()
                    time.sleep(1)

            except Exception:
                self._init_session()
                time.sleep(1)

        return None


def fetch_nse_option_chain(symbol: str = "NIFTY") -> Tuple[pd.DataFrame, float]:
    """
    Fetches and processes NSE Option Chain into a standard DataFrame with TTE calculation.
    
    Returns:
        Tuple[pd.DataFrame, spot_price]
    """
    fetcher = NSEFetcher()
    raw_data = fetcher.fetch_raw_data(symbol)

    if not raw_data or "records" not in raw_data:
        raise RuntimeError(
            f"NSE API block detected for {symbol}. Cloud IP (Streamlit) was restricted by NSE firewall. "
            f"Please refresh the page or try running locally."
        )

    records = raw_data["records"]
    spot_price = float(records.get("underlyingValue", 0.0))
    expiry_dates = records.get("expiryDates", [])

    if not expiry_dates:
        raise ValueError("No expiry dates found in NSE response.")

    target_expiry = expiry_dates[0]  # Select nearest expiry
    data_list = records.get("data", [])

    chain_rows = []
    
    # Calculate Days to Expiry (DTE) and Time to Expiration (TTE in years)
    today = pd.Timestamp.now().normalize()
    try:
        exp_date = pd.to_datetime(target_expiry, format="%d-%b-%Y")
        dte = max((exp_date - today).days, 0.5)
    except Exception:
        dte = 1.0
    
    tte = dte / 365.0  # Annualized time to expiration

    for item in data_list:
        if item.get("expiryDate") != target_expiry:
            continue

        strike = float(item.get("strikePrice", 0))
        ce = item.get("CE", {})
        pe = item.get("PE", {})

        call_oi = float(ce.get("openInterest", 0))
        put_oi = float(pe.get("openInterest", 0))

        # Handle IV values safely (convert percentage to decimal)
        call_iv = float(ce.get("impliedVolatility", 0.0)) / 100.0
        put_iv = float(pe.get("impliedVolatility", 0.0)) / 100.0

        # Fallback default IV if zero
        if call_iv <= 0:
            call_iv = 0.15
        if put_iv <= 0:
            put_iv = 0.15

        chain_rows.append({
            "strikePrice": strike,
            "call_oi": call_oi,
            "put_oi": put_oi,
            "call_iv": call_iv,
            "put_iv": put_iv,
            "tte": tte,
        })

    if not chain_rows:
        raise ValueError(f"No option chain data available for near expiry: {target_expiry}")

    df = pd.DataFrame(chain_rows)
    return df, spot_price
