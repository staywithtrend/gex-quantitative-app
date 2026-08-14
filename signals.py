"""
signals.py — Quantitative GEX Signal, Breakout Level Engine & Strategy Matrix
Generates synchronized breakout trigger levels, market regime classification,
and context-aware option strategy recommendations.
"""

from __future__ import annotations
from typing import Any, Dict


class GexSignalEngine:
    """Quantitative breakout, range quantification, and strategy recommendation engine."""

    def __init__(self, metrics: Dict[str, Any]):
        self.spot = float(metrics["spot_price"])
        self.gamma_flip = float(metrics["gamma_flip"])
        self.call_wall = float(metrics["call_wall"])
        self.put_wall = float(metrics["put_wall"])
        self.net_gex = float(metrics["total_net_gex"])
        self.point_b_upside = float(metrics["point_b_upside"])
        self.point_b_downside = float(metrics["point_b_downside"])

    def evaluate_current_situation(self) -> Dict[str, str]:
        """Classifies the GEX Regime, Volatility State, and Dealer Market Mechanics."""
        if self.spot > self.gamma_flip and self.net_gex > 0:
            regime = "High Positive GEX (> ₹0 Cr)"
            volatility_state = "Low Volatility / Range-bound"
            dealer_action = (
                "Dealers are long gamma (mean-reverting). Market volatility is dampened "
                "as dealers sell rallies and buy dips to remain delta neutral."
            )
        elif abs(self.spot - self.gamma_flip) / self.spot <= 0.0075 or abs(self.net_gex) < 100:
            regime = "GEX Flip Zone / Neutral (~ ₹0 Cr)"
            volatility_state = "Transitioning / Indecisive"
            dealer_action = (
                "Market is trading near the Zero Gamma threshold. Dealer hedging behavior "
                "shifts rapidly between stabilizing and trend-accelerating."
            )
        else:
            regime = "Negative GEX / High Volatility (< ₹0 Cr)"
            volatility_state = "High Volatility / Trending"
            dealer_action = (
                "Dealers are short gamma (trend acceleration). Market moves are amplified "
                "as dealers hedge aggressively in the direction of spot movement."
            )

        return {
            "regime": regime,
            "volatility_state": volatility_state,
            "dealer_action": dealer_action,
        }

    def evaluate_range_quantification(self) -> Dict[str, str]:
        """Quantifies structural range bounds between Call and Put Walls."""
        wall_width_pct = ((self.call_wall - self.put_wall) / self.spot) * 100

        if wall_width_pct <= 2.5 and self.net_gex > 0:
            range_type = "Tight Range + Low Volatility"
            description = (
                f"Spot is bounded between narrow Call (₹{self.call_wall:,.0f}) and Put (₹{self.put_wall:,.0f}) "
                f"Walls with positive GEX. High probability of price pinning."
            )
        elif wall_width_pct > 2.5 and self.net_gex <= 0:
            range_type = "Wide Range + High Volatility"
            description = (
                f"Spot is positioned between distant Call (₹{self.call_wall:,.0f}) and Put (₹{self.put_wall:,.0f}) "
                f"Walls under Negative Net GEX. Expect expanding intraday swings."
            )
        else:
            range_type = "Moderate Structural Range"
            description = f"Market trading within structural bounds (₹{self.put_wall:,.0f} - ₹{self.call_wall:,.0f})."

        return {"range_type": range_type, "description": description}

    def evaluate_breakout_levels(self) -> Dict[str, Any]:
        """Quantifies Point A -> Point B breakout levels with synchronized anchor levels."""
        # Upside Breakout Trigger (Point A = Call Wall)
        upside_trigger_level = self.call_wall
        upside_target_point_a = upside_trigger_level
        upside_target_point_b = self.point_b_upside
        upside_trigger_met = self.spot >= upside_trigger_level

        upside_reasoning = (
            "Dealers are forced to buy underlying stock/futures to maintain delta neutrality "
            "as spot rises through low gamma territory, accelerating upside momentum. "
            f"Sustained trade above ₹{upside_trigger_level:,.0f} triggers a fast short-squeeze sweep "
            f"extending from Point A (₹{upside_target_point_a:,.0f}) toward target zone Point B (₹{upside_target_point_b:,.0f})."
        )

        # Downside Breakout Trigger (Point A = Put Wall)
        downside_trigger_level = self.put_wall
        downside_target_point_a = downside_trigger_level
        downside_target_point_b = self.point_b_downside
        downside_trigger_met = self.spot <= downside_trigger_level

        downside_reasoning = (
            "Put hedging cascade forces market makers to sell underlying assets aggressively into falling prices, "
            "creating a fast downward sweep. Breaching below ₹{downside_trigger_level:,.0f} unlocks rapid liquidations "
            f"extending from Point A (₹{downside_target_point_a:,.0f}) to Point B (₹{downside_target_point_b:,.0f})."
        )

        return {
            "upside": {
                "trigger_level": upside_trigger_level,
                "target_point_a": upside_target_point_a,
                "target_point_b": upside_target_point_b,
                "is_active": upside_trigger_met,
                "reasoning": upside_reasoning,
            },
            "downside": {
                "trigger_level": downside_trigger_level,
                "target_point_a": downside_target_point_a,
                "target_point_b": downside_target_point_b,
                "is_active": downside_trigger_met,
                "reasoning": downside_reasoning,
            },
        }

    def recommend_strategy(self, regime: str) -> Dict[str, str]:
        """Maps GEX Regime and Spot location directly to specific strategy setups."""
        dist_to_call_wall = abs(self.spot - self.call_wall)
        dist_to_put_wall = abs(self.spot - self.put_wall)

        if "High Positive GEX" in regime:
            return {
                "suggested_strategy": "Iron Condor / Short Straddle / Short Strangle",
                "trade_type": "Volatility Decay / Net Premium Collection",
            }
        elif "Flip Zone" in regime:
            return {
                "suggested_strategy": "Calendar Spread / Neutral Butterfly",
                "trade_type": "Pivot Zone / Low Gamma Risk",
            }
        else:  # Negative GEX / High Volatility Regime
            if dist_to_call_wall < dist_to_put_wall:
                return {
                    "suggested_strategy": "Bull Call Spread (Targeting Point B)",
                    "trade_type": "Upside Breakout / Gamma Squeeze",
                }
            else:
                return {
                    "suggested_strategy": "Bear Put Spread (Targeting Point B)",
                    "trade_type": "Downside Breakdown / Put Cascade",
                }


def generate_signal_report(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Generates the full quantitative signal report dictionary."""
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
