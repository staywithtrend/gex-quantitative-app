"""
nse_fetcher.py — Robust NSE Option-Chain Adapter for Quantitative Systems
"""

from __future__ import annotations

import math
import time
from typing import Any

# Compatibility patch for PNSEA and curl_cffi
try:
    import curl_cffi.requests
    if not hasattr(curl_cffi.requests, "RequestException"):
        try:
            from curl_cffi.requests.errors import RequestsError
            curl_cffi.requests.RequestException = RequestsError
        except Exception:
            curl_cffi.requests.RequestException = Exception
except Exception:
    pass

try:
    from pnsea import NSE
except ImportError as exc:
    raise ImportError(
        "PNSEA is not installed. Run: pip install -r requirements.txt"
    ) from exc


SUPPORTED_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}


class NseSession:
    """Persistent PNSEA-backed NSE session used by dashboard.py."""

    def __init__(self, min_interval: float = 3.0):
        self.nse = NSE()
        self._last_fetch = 0.0
        self._min_interval = min_interval

    @staticmethod
    def _clean_number(value: Any, default: float = 0.0) -> float:
        """Safely convert API values to float, handling None, NaN, and str."""
        if value is None:
            return default
        try:
            val = float(value)
            return default if math.isnan(val) else val
        except (TypeError, ValueError):
            return default

    def _respect_rate_limit(self):
        """Enforce minimum delay between requests to avoid IP bans."""
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def _fetch_once(self, symbol: str, expiry: str | None = None):
        self._respect_rate_limit()

        if expiry:
            result = self.nse.options.option_chain(symbol, expiry_date=expiry)
        else:
            result = self.nse.options.option_chain(symbol)

        self._last_fetch = time.monotonic()

        if not isinstance(result, (tuple, list)) or len(result) < 3:
            raise RuntimeError(f"Unexpected response structure for {symbol}.")

        df, expiries, underlying = result[0], result[1], result[2]

        if df is None or getattr(df, "empty", True):
            suffix = f" for expiry {expiry}" if expiry else ""
            raise RuntimeError(f"Empty option chain returned for {symbol}{suffix}.")

        if not expiries:
            raise RuntimeError(f"No expiry dates returned for {symbol}.")

        return df, list(expiries), self._clean_number(underlying)

    def get_option_chain(
        self,
        symbol: str = "NIFTY",
        retries: int = 3,
        expiry: str | None = None,
    ) -> dict[str, Any]:
        """Returns structured JSON dictionary with option chain data."""
        symbol = str(symbol).upper().strip()

        if symbol not in SUPPORTED_SYMBOLS:
            raise RuntimeError(f"Unsupported symbol '{symbol}'. Use: {sorted(SUPPORTED_SYMBOLS)}")

        last_error = None

        for attempt in range(1, retries + 1):
            try:
                df, expiries, underlying = self._fetch_once(symbol, expiry=expiry)
                selected_expiry = str(expiry) if expiry else str(expiries[0])

                if "expiryDate" in df.columns:
                    df_filtered = df[df["expiryDate"] == selected_expiry]
                    if not df_filtered.empty:
                        df = df_filtered

                rows = []
                for row in df.to_dict(orient="records"):
                    strike = self._clean_number(row.get("strikePrice"))
                    if strike <= 0:
                        continue

                    ce = {
                        "openInterest": self._clean_number(row.get("CE_openInterest")),
                        "changeinOpenInterest": self._clean_number(row.get("CE_changeinOpenInterest")),
                        "totalTradedVolume": self._clean_number(row.get("CE_totalTradedVolume")),
                        "impliedVolatility": self._clean_number(row.get("CE_impliedVolatility")),
                        "lastPrice": self._clean_number(row.get("CE_lastPrice")),
                    }

                    pe = {
                        "openInterest": self._clean_number(row.get("PE_openInterest")),
                        "changeinOpenInterest": self._clean_number(row.get("PE_changeinOpenInterest")),
                        "totalTradedVolume": self._clean_number(row.get("PE_totalTradedVolume")),
                        "impliedVolatility": self._clean_number(row.get("PE_impliedVolatility")),
                        "lastPrice": self._clean_number(row.get("PE_lastPrice")),
                    }

                    rows.append({
                        "expiryDate": selected_expiry,
                        "strikePrice": strike,
                        "CE": ce,
                        "PE": pe,
                    })

                if not rows:
                    raise RuntimeError(f"No usable strike data for {symbol} / {selected_expiry}.")

                return {
                    "records": {
                        "underlyingValue": underlying,
                        "expiryDates": expiries,
                        "data": rows,
                    }
                }

            except Exception as exc:
                last_error = str(exc)
                if attempt < retries:
                    time.sleep(2.0 * attempt)

        suffix = f" / {expiry}" if expiry else ""
        raise RuntimeError(f"Failed to fetch NSE chain for {symbol}{suffix}: {last_error}")
