"""
gex_engine.py — Quantitative Gamma Exposure calculation engine (Pure Loop Implementation)
"""

import pandas as pd
import numpy as np

def calculate_gamma(S, K, T, sigma):
    """Black-Scholes Gamma approximation."""
    try:
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0.0
        d1 = (np.log(S / K) + (0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        norm_pdf = np.exp(-0.5 * d1 ** 2) / np.sqrt(2 * np.pi)
        gamma = norm_pdf / (S * sigma * np.sqrt(T))
        return float(gamma)
    except Exception:
        return 0.0

def process_gex_analysis(raw_data, symbol):
    records = raw_data.get("records", {})
    spot_price = float(records.get("underlyingValue", 0.0))
    data_list = records.get("data", [])

    rows = []
    for item in data_list:
        strike = float(item.get("strikePrice", 0))
        ce = item.get("CE", {}) or {}
        pe = item.get("PE", {}) or {}

        call_oi = float(ce.get("openInterest", 0))
        put_oi = float(pe.get("openInterest", 0))
        call_iv = float(ce.get("impliedVolatility", 0.0) or 15.0) / 100.0
        put_iv = float(pe.get("impliedVolatility", 0.0) or 15.0) / 100.0

        tte = 7.0 / 365.0

        call_gamma = calculate_gamma(spot_price, strike, tte, call_iv)
        put_gamma = calculate_gamma(spot_price, strike, tte, put_iv)

        multiplier = 50 if "NIFTY" in symbol else 25
        call_gex = call_oi * call_gamma * (spot_price ** 2) * 0.01 * multiplier
        put_gex = -1 * (put_oi * put_gamma * (spot_price ** 2) * 0.01 * multiplier)
        net_gex = call_gex + put_gex

        dominance = "Bullish (Put Heavy)" if net_gex < 0 else "Bearish (Call Heavy)"

        rows.append({
            "strike": strike,
            "call_oi": call_oi,
            "put_oi": put_oi,
            "call_gamma": call_gamma,
            "put_gamma": put_gamma,
            "call_gex": call_gex,
            "put_gex": put_gex,
            "net_gex": net_gex,
            "dominance": dominance
        })

    df_gex = pd.DataFrame(rows)

    if not df_gex.empty:
        call_wall_idx = df_gex['call_oi'].idxmax()
        put_wall_idx = df_gex['put_oi'].idxmax()
        call_wall = float(df_gex.loc[call_wall_idx, 'strike']) if call_wall_idx in df_gex.index else spot_price
        put_wall = float(df_gex.loc[put_wall_idx, 'strike']) if put_wall_idx in df_gex.index else spot_price
        
        df_gex['cum_gex'] = df_gex['net_gex'].cumsum()
        flip_mask = df_gex['cum_gex'] * df_gex['cum_gex'].shift(1) < 0
        flip_indices = df_gex.index[flip_mask].tolist()
        gamma_flip = float(df_gex.loc[flip_indices[0], 'strike']) if flip_indices else spot_price
    else:
        call_wall, put_wall, gamma_flip = spot_price, spot_price, spot_price

    total_net_gex = float(df_gex['net_gex'].sum()) if not df_gex.empty else 0.0

    return {
        "spot_price": spot_price,
        "gamma_flip": gamma_flip,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "total_net_gex": total_net_gex,
        "gex_df": df_gex
    }
