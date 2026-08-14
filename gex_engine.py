"""
gex_engine.py — Quantitative Option Gamma Exposure (GEX) Engine
Calculates strike-level Black-Scholes Gamma, Dealer GEX (in ₹ Crores),
Call/Put Walls, Zero Gamma Flip level, and Point B target trajectories.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import norm
from typing import Dict, Any


def calculate_bs_gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculates standard Black-Scholes Gamma for an option strike.
    
    Parameters:
        S : Spot Price
        K : Strike Price
        T : Time to Expiration in Years (tte)
        r : Risk-free Interest Rate
        sigma : Implied Volatility (decimal format, e.g., 0.15 for 15%)
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return gamma


def process_gex_analysis(df: pd.DataFrame, spot_price: float, lot_size: int = 25, r: float = 0.07) -> Dict[str, Any]:
    """
    Processes the option chain dataframe to calculate GEX metrics across strikes.
    
    Expected DataFrame Columns:
        - strikePrice (float)
        - call_oi (int/float)
        - put_oi (int/float)
        - call_iv (float)
        - put_iv (float)
        - tte (float, time to expiration in years)
    """
    df = df.copy()

    # 1. Compute Strike-Level Black-Scholes Gamma
    df["call_gamma"] = df.apply(
        lambda row: calculate_bs_gamma(spot_price, row["strikePrice"], row["tte"], r, row["call_iv"]),
        axis=1,
    )
    df["put_gamma"] = df.apply(
        lambda row: calculate_bs_gamma(spot_price, row["strikePrice"], row["tte"], r, row["put_iv"]),
        axis=1,
    )

    # 2. Compute Dealer GEX in ₹ Crores per Strike
    # SpotGamma Dealer Model:
    # Dealers are Short Calls -> Negative Gamma impact (trend amplifying on upside)
    # Dealers are Short Puts -> Positive Gamma impact (stabilizing / dampening)
    # GEX (₹ Cr) = (OI * Lot Size * Gamma * Spot^2 * 0.01) / 10,000,000
    df["call_gex_cr"] = -1.0 * (df["call_oi"] * lot_size * df["call_gamma"] * (spot_price**2) * 0.01) / 1e7
    df["put_gex_cr"] = (df["put_oi"] * lot_size * df["put_gamma"] * (spot_price**2) * 0.01) / 1e7
    df["net_gex_cr"] = df["call_gex_cr"] + df["put_gex_cr"]

    # 3. Aggregate Total Net Market GEX
    total_net_gex = df["net_gex_cr"].sum()

    # 4. Identify Structural Walls (Peak Open Interest Strikes)
    call_wall = float(df.loc[df["call_oi"].idxmax(), "strikePrice"])
    put_wall = float(df.loc[df["put_oi"].idxmax(), "strikePrice"])

    # 5. Calculate Zero Gamma Flip Level (Nearest Sign Crossing to Spot)
    df_sorted = df.sort_values("strikePrice").reset_index(drop=True)
    
    # Identify index rows where Net GEX changes sign
    df_sorted["sign"] = np.sign(df_sorted["net_gex_cr"])
    sign_changes = df_sorted[df_sorted["sign"].diff().fillna(0) != 0]

    if not sign_changes.empty:
        # Select the zero crossing strike closest to current spot price
        closest_idx = (sign_changes["strikePrice"] - spot_price).abs().idxmin()
        gamma_flip = float(sign_changes.loc[closest_idx, "strikePrice"])
    else:
        # Fallback to current spot if chain GEX is uniformly one sign
        gamma_flip = float(spot_price)

    # 6. Calculate Point B Target Trajectories
    # Point B projection based on 50% expansion of the Call-Put Wall structure
    wall_span = max(call_wall - put_wall, spot_price * 0.01)
    point_b_upside = float(call_wall + (wall_span * 0.5))
    point_b_downside = float(put_wall - (wall_span * 0.5))

    return {
        "spot_price": float(spot_price),
        "total_net_gex": float(total_net_gex),
        "call_wall": call_wall,
        "put_wall": put_wall,
        "gamma_flip": gamma_flip,
        "point_b_upside": point_b_upside,
        "point_b_downside": point_b_downside,
        "chain_data": df_sorted,
    }
