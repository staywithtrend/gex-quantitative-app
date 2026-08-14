"""
dashboard.py — Quantitative GEX Terminal with Safe Data Handling
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gex_engine import process_gex_analysis
from nse_fetcher import NseSession, SUPPORTED_SYMBOLS
from signals import generate_signal_report

st.set_page_config(
    page_title="Quantitative GEX Analytics Terminal",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_data(ttl=30, show_spinner="Fetching Live NSE Option Chain...")
def fetch_cached_option_chain(symbol: str, expiry: str | None = None):
    session = NseSession()
    return session.get_option_chain(symbol=symbol, expiry=expiry)

# Sidebar Controls
st.sidebar.title("⚡ Quantitative GEX Terminal")
symbol = st.sidebar.selectbox("Select Index", sorted(SUPPORTED_SYMBOLS), index=0)

if st.sidebar.button("🔄 Refresh Market Data"):
    st.cache_data.clear()

try:
    initial_data = fetch_cached_option_chain(symbol)
    expiries = initial_data["records"]["expiryDates"]
    
    selected_expiry = st.sidebar.selectbox("Select Expiry", expiries)
    
    if selected_expiry == expiries[0]:
        data = initial_data
    else:
        data = fetch_cached_option_chain(symbol, expiry=selected_expiry)

    # Process metrics and signals
    metrics = process_gex_analysis(data, symbol)
    signals = generate_signal_report(metrics)

    st.title(f"🎯 {symbol} GEX Quantitative Terminal ({selected_expiry})")
    
    # 1. Executive Key Metrics Bar
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Spot Price", f"₹{metrics['spot_price']:,.2f}")
    col2.metric("Zero Gamma (Flip)", f"₹{metrics['gamma_flip']:,.0f}")
    col3.metric("Call Wall (Resistance)", f"₹{metrics['call_wall']:,.0f}")
    col4.metric("Put Wall (Support)", f"₹{metrics['put_wall']:,.0f}")
    
    gex_in_cr = metrics['total_net_gex'] / 1e7
    col5.metric("Net Market GEX", f"₹{gex_in_cr:,.2f} Cr")

    st.markdown("---")

    # 2. Current Situation & Strategy Recommender Matrix
    curr = signals["current_situation"]
    strat = signals["strategy_info"]
    rng = signals["range_info"]

    st.subheader("📌 Current Situation & Quantitative Strategy Recommender")
    
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.markdown(f"**GEX Regime:**\n### `{curr['regime']}`")
        st.caption(f"**Dealer Mechanics:** {curr['dealer_action']}")
        
    with m_col2:
        st.markdown(f"**Volatility State:**\n### `{curr['volatility_state']}`")
        st.caption(f"**Structure:** {rng['range_type']} — {rng['description']}")

    with m_col3:
        st.markdown(f"**Suggested Strategy:**\n### `{strat['suggested_strategy']}`")
        st.caption(f"**Trade Execution:** {strat['trade_type']}")

    st.markdown("---")

    # 3. Quantitative Breakout & Level Engine
    st.subheader("🚀 Quantitative Breakout & Trending Level Engine")
    bk = signals["breakout_info"]

    b_col1, b_col2 = st.columns(2)

    with b_col1:
        st.markdown("### 🟢 Upside Trending Move Trigger")
        st.write(f"**Trigger Level (Above):** `₹{bk['upside']['trigger_level']:,.0f}`")
        st.write(f"**Target Trajectory:** Point A (`₹{bk['upside']['target_point_a']:,.0f}`) ➔ Point B (`₹{bk['upside']['target_point_b']:,.0f}`)")
        st.info(f"**Quantitative Reasoning:**\n\n{bk['upside']['reasoning']}")

    with b_col2:
        st.markdown("### 🔴 Downside Trending Move Trigger")
        st.write(f"**Trigger Level (Below):** `₹{bk['downside']['trigger_level']:,.0f}`")
        st.write(f"**Target Trajectory:** Point A (`₹{bk['downside']['target_point_a']:,.0f}`) ➔ Point B (`₹{bk['downside']['target_point_b']:,.0f}`)")
        st.error(f"**Quantitative Reasoning:**\n\n{bk['downside']['reasoning']}")

    st.markdown("---")

    # 4. GEX Tabular Display (Safe Iteration preventing dict/apply errors)
    st.subheader("📋 Strike-Level GEX Tabular Display")
    
    df_gex = metrics.get("gex_df")
    if not isinstance(df_gex, pd.DataFrame):
        df_gex = pd.DataFrame(df_gex if df_gex is not None else [])

    def safe_format(val, fmt="₹{:,.0f}", default="₹0"):
        try:
            if val is None or pd.isna(val):
                return default
            return fmt.format(float(val))
        except (ValueError, TypeError):
            return default

    display_data = []
    if not df_gex.empty:
        for _, row in df_gex.iterrows():
            display_data.append({
                "Strike Price": safe_format(row.get("strike"), "₹{:,.0f}"),
                "Call OI": safe_format(row.get("call_oi"), "{:,.0f}", "0"),
                "Put OI": safe_format(row.get("put_oi"), "{:,.0f}", "0"),
                "Call Gamma": safe_format(row.get("call_gamma"), "{:.6f}", "0.000000"),
                "Put Gamma": safe_format(row.get("put_gamma"), "{:.6f}", "0.000000"),
                "Call GEX (₹ Cr)": safe_format(row.get("call_gex", 0) / 1e7, "₹{:,.2f} Cr"),
                "Put GEX (₹ Cr)": safe_format(row.get("put_gex", 0) / 1e7, "₹{:,.2f} Cr"),
                "Net GEX (₹ Cr)": safe_format(row.get("net_gex", 0) / 1e7, "₹{:,.2f} Cr"),
                "GEX Dominance": str(row.get("dominance", "Neutral")),
            })

    display_df = pd.DataFrame(display_data)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    # 5. Interactive GEX Profile Chart
    st.subheader("📊 Net Gamma Exposure Profile")
    fig = go.Figure()
    
    if not df_gex.empty and 'net_gex' in df_gex.columns:
        colors = ['#16a34a' if g >= 0 else '#dc2626' for g in df_gex['net_gex']]
        
        fig.add_trace(go.Bar(
            x=df_gex['strike'],
            y=df_gex['net_gex'] / 1e7,
            marker_color=colors,
            name="Net GEX (₹ Cr)",
            hovertemplate="Strike: %{x}<br>Net GEX: ₹%{y:.2f} Cr<extra></extra>"
        ))

        fig.add_vline(x=metrics['spot_price'], line_width=2, line_dash="dash", line_color="#2563eb", annotation_text="Spot")
        fig.add_vline(x=metrics['gamma_flip'], line_width=2, line_color="#f59e0b", annotation_text="Gamma Flip")
        fig.add_vline(x=metrics['call_wall'], line_width=1.5, line_color="#16a34a", annotation_text="Call Wall")
        fig.add_vline(x=metrics['put_wall'], line_width=1.5, line_color="#dc2626", annotation_text="Put Wall")

    fig.update_layout(xaxis_title="Strike Price", yaxis_title="Net GEX (₹ Cr)", template="plotly_white", height=450)
    st.plotly_chart(fig, use_container_width=True)

except Exception as err:
    st.error(f"Error running dashboard terminal: {err}")
