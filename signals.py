"""
signals.py — Quantitative GEX Signal, Breakout Level Engine & Strategy Matrix
"""

from __future__ import annotations
from typing import Any, Dict


class GexSignalEngine:
    """Quantitative breakout, range quantification, and strategy recommendation engine."""

    def __init__(self, metrics: Dict[str, Any]):
        self.spot = metrics["spot_price"]
        self.gamma_flip = metrics["gamma_flip"]
        self.call_wall = metrics["call_wall"]
        self.put_wall = metrics["put_wall"]
        self.net_gex = metrics["total_net_gex"]
        self.point_b_upside = metrics["point_b_upside"]
        self.point_b_downside = metrics["point_b_downside"]

    def evaluate_current_situation(self) -> Dict[str, str]:
        """Classifies the GEX Regime, Volatility State, and Dealer Market Mechanics."""
        if self.spot > self.gamma_flip and self.net_gex > 0:
            regime = "High Positive GEX ($>\\$0$)"
            volatility_state = "Low Volatility / Range-bound"
            dealer_action = "Dealers are long gamma (mean-reverting). Market volatility is dampened as dealers sell rallies and buy dips."
        elif abs(self.spot - self.gamma_flip) / self.spot <= 0.0075 or abs(self.net_gex) < 1e6:
            regime = "GEX Flip Zone / Near 0"
            volatility_state = "Transitioning / Indecisive"
            dealer_action = "Market is near the pivot threshold. Dealer hedging shifts rapidly between stabilizing and accelerating."
        else:
            regime = "Negative GEX + Breakout ($<\\$0$)"
            volatility_state = "High Volatility / Trending"
            dealer_action = "Dealers are short gamma (trend acceleration). Market moves are amplified as dealers hedge in the direction of the trend."

        return {
            "regime": regime,
            "volatility_state": volatility_state,
            "dealer_action": dealer_action,
        }

    def evaluate_range_quantification(self) -> Dict[str, str]:
        """Quantifies structural range bounds (Tight vs Wide Range)."""
        wall_width_pct = ((self.call_wall - self.put_wall) / self.spot) * 100

        if wall_width_pct <= 2.5 and self.net_gex > 0:
            range_type = "Tight Range + Low Volatility"
            description = f"Spot is bounded between narrow Call ({self.call_wall:.0f}) and Put ({self.put_wall:.0f}) Walls with heavy Positive Net GEX. Active dealer pinning expected."
        elif wall_width_pct > 2.5 and self.net_gex <= 0:
            range_type = "Wide Range + High Volatility"
            description = f"Spot is trapped between distant Call ({self.call_wall:.0f}) and Put ({self.put_wall:.0f}) Walls under Negative/Low Net GEX. Expect large intraday swings."
        else:
            range_type = "Moderate Range"
            description = f"Market trading within normal structural bounds ({self.put_wall:.0f} - {self.call_wall:.0f})."

        return {"range_type": range_type, "description": description}

    def evaluate_breakout_levels(self) -> Dict[str, Any]:
        """Quantifies Point A -> Point B triggers with 2-line dealer mechanics reasoning."""
        # Upside Breakout Trigger Condition
        upside_trigger_level = max(self.call_wall, self.gamma_flip)
        upside_trigger_met = self.spot >= upside_trigger_level or (self.spot < self.gamma_flip and self.spot > self.call_wall)
        
        upside_reasoning = (
            "Dealers are forced to buy underlying stock/futures to maintain delta neutrality as spot rises through low gamma territory, accelerating upside momentum.\n"
            f"Sustained trade above ₹{upside_trigger_level:,.0f} triggers a fast short-squeeze sweep toward target zone Point B (₹{self.point_b_upside:,.0f})."
        )

        # Downside Breakout Trigger Condition
        downside_trigger_level = min(self.put_wall, self.gamma_flip)
        downside_trigger_met = self.spot <= downside_trigger_level

        downside_reasoning = (
            "Put hedging cascade forces market makers to sell underlying assets aggressively into falling prices, creating a fast downward sweep.\n"
            f"Breaching below ₹{downside_trigger_level:,.0f} unlocks rapid liquidations extending from Point A (₹{self.put_wall:,.0f}) to Point B (₹{self.point_b_downside:,.0f})."
        )

        return {
            "upside": {
                "trigger_level": upside_trigger_level,
                "target_point_a": self.call_wall,
                "target_point_b": self.point_b_upside,
                "is_active": upside_trigger_met,
                "reasoning": upside_reasoning,
            },
            "downside": {
                "trigger_level": downside_trigger_level,
                "target_point_a": self.put_wall,
                "target_point_b": self.point_b_downside,
                "is_active": downside_trigger_met,
                "reasoning": downside_reasoning,
            },
        }

    def recommend_strategy(self, regime: str) -> Dict[str, str]:
        """Maps GEX Regime directly to the Strategy Recommender Matrix."""
        if "High Positive GEX" in regime:
            return {
                "suggested_strategy": "Short Straddle / Short Strangle / Iron Condor (Sell Volatility)",
                "trade_type": "Net Premium Collection / Volatility Decay",
            }
        elif "Flip Zone" in regime:
            return {
                "suggested_strategy": "Calendar Spreads / Neutral Butterfly",
                "trade_type": "Low Volatility Risk / Pivot Positioning",
            }
        else: # Negative GEX + Breakout
            return {
                "suggested_strategy": "Bull Call Spread / Bear Put Spread or Long Gamma (Straddle/Strangle)",
                "trade_type": "Directional Momentum / Volatility Expansion",
            }


def generate_signal_report(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Generates the full quantitative signal report."""
    engine = GexSignalEngine(metrics)
    current_sit = engine.evaluate_current_situation()
    range_info = engine.evaluate_range_quantification()
    breakout_info = engine.evaluate_breakout_levels()
    strategy_info = engine.recommend_strategy(current_sit["regime"])

    return {
        "current_situation": current_sit,
        "range_info": range_info,
        "breakout_info": breakout_info,
        "strategy_info": strategy_info,
    }
