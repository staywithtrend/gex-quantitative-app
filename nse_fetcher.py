"""
nse_fetcher.py — Robust NSE option-chain adapter powered by PNSEA.
"""

from __future__ import annotations

import time
from typing import Any, Tuple, Optional
import pandas as pd

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
        "PNSEA is not installed. Ensure 'pnsea>=1.1' is in requirements.txt"
    ) from exc


SUPPORTED_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}


class NseSession:
    """Persistent PNSEA-backed NSE session used by the dashboard."""

    def __init__(self):
        self.nse = NSE()
        self._last_fetch = 0.0
        self._min_interval = 3.0

    @staticmethod
    def _clean_number(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            if value != value:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _respect_rate_limit(self):
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def _fetch_once(self, symbol: str, expiry: str | None = None):
        self._respect_rate_limit()

        if expiry:
            result = self.nse.options.option_chain(
                symbol,
                expiry_date=expiry,
            )
        else:
            result = self.nse.options.option_chain(symbol)

        self._last_fetch = time.monotonic()

        if not isinstance(result, (tuple, list)) or len(result) < 3:
            raise RuntimeError(
                f"Unexpected PNSEA option-chain response for {symbol}."
            )

        df, expiries, underlying = result[0], result[1], result[2]

        if df is None or getattr(df, "empty", True):
            suffix = f" for expiry {expiry}" if expiry else ""
            raise RuntimeError(
                f"NSE returned an empty option chain for {symbol}{suffix}."
            )

        if not expiries:
            raise RuntimeError(f"NSE returned no expiry dates for {symbol}.")

        return df, list(expiries), self._clean_number(underlying)

    def get_option_chain(
        self,
        symbol="NIFTY",
        retries=3,
        expiry: str | None = None,
    ):
        symbol = str(symbol).upper().strip()

        if symbol not in SUPPORTED_SYMBOLS:
            raise RuntimeError(
                f"Unsupported index '{symbol}'. "
                f"Use one of: {', '.join(sorted(SUPPORTED_SYMBOLS))}"
            )

        last_error = None

        for attempt in range(1, retries + 1):
            try:
                df, expiries, underlying = self._fetch_once(
                    symbol,
                    expiry=expiry,
                )

                selected_expiry = str(expiry) if expiry else str(expiries[0])

                rows = []

                for _, row in df.iterrows():
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

                    rows.append(
                        {
                            "expiryDate": selected_expiry,
                            "strikePrice": strike,
                            "CE": ce,
                            "PE": pe,
                        }
                    )

                if not rows:
                    raise RuntimeError(
                        f"NSE returned no usable strike rows for "
                        f"{symbol} / {selected_expiry}."
                    )

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
        raise RuntimeError(
            f"Failed to fetch NSE option chain for {symbol}{suffix}: {last_error}"
        )


def fetch_nse_option_chain(symbol: str = "NIFTY", expiry: Optional[str] = None) -> Tuple[pd.DataFrame, float]:
    """Helper function for dashboard compatibility."""
    session = NseSession()
    raw_data = session.get_option_chain(symbol=symbol, expiry=expiry)

    records = raw_data["records"]
    spot_price = float(records.get("underlyingValue", 0.0))
    expiry_dates = records.get("expiryDates", [])
    data_list = records.get("data", [])

    target_expiry = expiry if expiry else expiry_dates[0]

    today = pd.Timestamp.now().normalize()
    try:
        exp_date = pd.to_datetime(target_expiry, format="%d-%b-%Y")
        dte = max((exp_date - today).days, 0.5)
    except Exception:
        dte = 1.0

    tte = dte / 365.0

    chain_rows = []
    for item in data_list:
        strike = float(item.get("strikePrice", 0))
        ce = item.get("CE", {}) or {}
        pe = item.get("PE", {}) or {}

        call_oi = float(ce.get("openInterest", 0))
        put_oi = float(pe.get("openInterest", 0))

        call_iv = float(ce.get("impliedVolatility", 0.0) or 0.0) / 100.0
        put_iv = float(pe.get("impliedVolatility", 0.0) or 0.0) / 100.0

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

    df = pd.DataFrame(chain_rows)
    return df, spot_price
