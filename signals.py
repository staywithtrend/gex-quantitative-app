"""
signals.py — Generates strategic market insights based on GEX metrics.
"""

def generate_signal_report(metrics):
    spot = metrics["spot_price"]
    flip = metrics["gamma_flip"]
    c_wall = metrics["call_wall"]
    p_wall = metrics["put_wall"]

    regime = "Positive Gamma" if spot > flip else "Negative Gamma"
    dealer_action = "Mean Reverting (Buying Dips, Selling Rallies)" if spot > flip else "Momentum Accelerating (Selling Dips, Chasing Breakouts)"
    vol_state = "Suppressed / Low Volatility" if spot > flip else "Expanded / High Volatility"

    strategy = "Iron Condor / Range Bound Credit Spreads" if spot > flip else "Directional Breakout / Long Options"
    trade_type = "Sell Premium" if spot > flip else "Buy Premium"

    range_type = "Bounded Channel" if spot > flip else "Expansion Zone"
    description = f"Market is trading between Put Wall (₹{p_wall:,.0f}) and Call Wall (₹{c_wall:,.0f})."

    breakout_info = {
        "upside": {
            "trigger_level": c_wall,
            "target_point_a": c_wall + 150,
            "target_point_b": c_wall + 300,
            "point_b_upside": c_wall + 300, # Added for backward compatibility
            "reasoning": "Breaching the Call Wall forces dealers to short futures/buy calls rapidly to hedge short gamma, driving momentum upward."
        },
        "downside": {
            "trigger_level": p_wall,
            "target_point_a": p_wall - 150,
            "target_point_b": p_wall - 300,
            "point_b_downside": p_wall - 300, # Added for backward compatibility
            "reasoning": "Dropping below the Put Wall forces dealers to sell underlying index futures aggressively to cover delta exposure."
        }
    }

    return {
        "current_situation": {
            "regime": regime,
            "dealer_action": dealer_action,
            "volatility_state": vol_state
        },
        "strategy_info": {
            "suggested_strategy": strategy,
            "trade_type": trade_type
        },
        "range_info": {
            "range_type": range_type,
            "description": description
        },
        "breakout_info": breakout_info
    }
