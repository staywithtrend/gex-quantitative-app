"""
gex_engine.py — Quantitative GEX & Level Analytics Engine
"""

from __future__ import annotations

from datetime import datetime
import numpy as np
import pandas as pd
from scipy.stats import norm

LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
}


def black_scholes_gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculates Black-Scholes Option Gamma."""
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return float(gamma)


def calculate_days_to_expiry(expiry_str: str) -> float:
    """Parses NSE date format to time-to-expiry in years (T)."""
    try:
        exp_date = datetime.strptime(expiry_str, "%d-%b-%Y")
        now = datetime.now()
        days = (exp_date - now).days + ((15.5 - now.hour) / 24.0)
        return max(days / 365.0, 0.001)
    except Exception:
        return 0.007


def process_gex_analysis(raw_data: dict, symbol: str, risk_free_rate: float = 0.07) -> dict:
    """
    Computes strike-level metrics, GEX Dominance, Call/Put Walls, Zero Gamma,
    and Point A -> Point B breakout extension targets.
    """
    records = raw_data.get("records", {})
    spot_price = float(records.get("underlyingValue", 0.0))
    strikes_data = records.get("data", [])
    lot_size = LOT_SIZES.get(symbol.upper(), 50)

    if not strikes_data or spot_price <= 0:
        raise ValueError("Invalid option chain or spot price data.")

    rows = []
    for item in strikes_data:
        strike = float(item["strikePrice"])
        expiry_str = item["expiryDate"]
        T = calculate_days_to_expiry(expiry_str)

        # Call Metrics
        ce_oi = float(item["CE"]["openInterest"])
        ce_iv = float(item["CE"]["impliedVolatility"]) / 100.0
        ce_gamma = black_scholes_gamma(spot_price, strike, T, risk_free_rate, ce_iv)
        call_gex = ce_oi * lot_size * ce_gamma * (spot_price**2) * 0.01

        # Put Metrics
        pe_oi = float(item["PE"]["openInterest"])
        pe_iv = float(item["PE"]["impliedVolatility"]) / 100.0
        pe_gamma = black_scholes_gamma(spot_price, strike, T, risk_free_rate, pe_iv)
        put_gex = -1.0 * (pe_oi * lot_size * pe_gamma * (spot_price**2) * 0.01)

        net_gex = call_gex + put_gex

        # Dominance Classification
        if call_gex > abs(put_gex) * 1.3:
            dominance = "Call Heavy 🟢"
        elif abs(put_gex) > call_gex * 1.3:
            dominance = "Put Heavy 🔴"
        else:
            dominance = "Neutral ⚪"

        rows.append({
            "strike": strike,
            "call_oi": ce_oi,
            "put_oi": pe_oi,
            "call_gamma": ce_gamma,
            "put_gamma": pe_gamma,
            "call_gex": call_gex,
            "put_gex": put_gex,
            "net_gex": net_gex,
            "dominance": dominance,
        })

    df = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)

    # Filter for active trading band (±12% around spot)
    lower_bound = spot_price * 0.88
    upper_bound = spot_price * 1.12
    df_filtered = df[(df["strike"] >= lower_bound) & (df["strike"] <= upper_bound)].copy()

    # Identify Key Walls
    call_wall = float(df_filtered.loc[df_filtered["call_gex"].idxmax()]["strike"])
    put_wall = float(df_filtered.loc[df_filtered["put_gex"].idxmin()]["strike"])

    # Zero Gamma / Gamma Flip Level
    df_filtered["cum_gex"] = df_filtered["net_gex"].cumsum()
    zero_crossings = df_filtered[np.sign(df_filtered["cum_gex"]).diff() != 0]

    if not zero_crossings.empty:
        gamma_flip = float(zero_crossings.iloc[0]["strike"])
    else:
        gamma_flip = spot_price

    # Point B Target Calculations (Next high-volume/GEX concentration strikes)
    upside_candidates = df_filtered[df_filtered["strike"] > call_wall]
    if not upside_candidates.empty:
        point_b_upside = float(upside_candidates.loc[upside_candidates["call_gex"].idxmax()]["strike"])
    else:
        point_b_upside = call_wall + (call_wall - put_wall) * 0.5

    downside_candidates = df_filtered[df_filtered["strike"] < put_wall]
    if not downside_candidates.empty:
        point_b_downside = float(downside_candidates.loc[downside_candidates["put_gex"].idxmin()]["strike"])
    else:
        point_b_downside = put_wall - (call_wall - put_wall) * 0.5

    return {
        "spot_price": spot_price,
        "total_net_gex": float(df_filtered["net_gex"].sum()),
        "gamma_flip": gamma_flip,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "point_b_upside": point_b_upside,
        "point_b_downside": point_b_downside,
        "gex_df": df_filtered,
    }
