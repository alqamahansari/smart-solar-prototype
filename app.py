# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone

from openweather_api import get_coordinates_for_city, get_hourly_forecast, estimate_solar_from_weather
from datagov_api import build_home_load_profile
from scheduler import plan_day


st.set_page_config(page_title="Smart Solar Prototype", layout="wide")

st.title("Smart Solar Energy Planner (Prototype)")
st.markdown(
    "Decide when to use **Solar**, **Grid**, and **Battery** based on "
    "weather (OpenWeather API) and time-based pricing."
)

# --- Sidebar inputs ---
st.sidebar.header("House & System Configuration")

city = st.sidebar.text_input("City", value="Kakinada")
country_code = st.sidebar.text_input("Country Code", value="IN")
solar_capacity_kw = st.sidebar.number_input("Solar Capacity (kW)", min_value=0.5, max_value=20.0, value=3.0, step=0.5)
battery_capacity_kwh = st.sidebar.number_input("Battery Capacity (kWh)", min_value=0.0, max_value=50.0, value=5.0, step=0.5)
max_charge = st.sidebar.number_input("Max Charge per Hour (kWh)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)
max_discharge = st.sidebar.number_input("Max Discharge per Hour (kWh)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)

st.sidebar.header("Tariff (₹/kWh)")
off_peak_price = st.sidebar.number_input("Off-peak price (0–6h, 23–24h)", min_value=0.0, max_value=20.0, value=4.0, step=0.5)
normal_price = st.sidebar.number_input("Normal price (6–18h)", min_value=0.0, max_value=20.0, value=6.0, step=0.5)
peak_price = st.sidebar.number_input("Peak price (18–23h)", min_value=0.0, max_value=20.0, value=8.0, step=0.5)

total_daily_kwh = st.sidebar.number_input("Total Daily Load (kWh)", min_value=1.0, max_value=50.0, value=12.0, step=1.0)

hours = 24

if st.button("Generate 24-hour Plan"):
    try:
        # 1) Get coordinates from city name
        lat, lon = get_coordinates_for_city(city, country_code)

        # 2) Get hourly weather forecast
        weather = get_hourly_forecast(lat, lon, hours=hours)

        # Build time index
        times = [w["time"].astimezone(timezone.utc) for w in weather]

        # 3) Estimate solar from weather
        solar_kwh = estimate_solar_from_weather(weather, solar_capacity_kw)

        # 4) Build synthetic home load profile (can later replace with Data.gov-based)
        load_kwh = build_home_load_profile(hours=hours, total_daily_kwh=total_daily_kwh)

        # 5) Build price per hour
        prices = []
        for t in times:
            local_hour = t.hour  # in UTC; ideally convert to local IST
            # For prototype, treat this as local hour or adjust later
            if 0 <= local_hour < 6 or local_hour == 23:
                prices.append(off_peak_price)
            elif 6 <= local_hour < 18:
                prices.append(normal_price)
            else:  # 18–23
                prices.append(peak_price)

        # 6) Run scheduler
        schedule_df, summary = plan_day(
            times=times,
            solar_kwh=solar_kwh,
            load_kwh=load_kwh,
            price_per_kwh=prices,
            battery_capacity_kwh=battery_capacity_kwh,
            max_charge_kwh_per_slot=max_charge,
            max_discharge_kwh_per_slot=max_discharge,
            round_trip_efficiency=0.9,
            high_price_threshold=peak_price - 0.1,  # treat peak as "high"
            low_price_threshold=off_peak_price + 0.1,
            initial_soc_kwh=0.0,
        )

        st.success("Plan generated successfully!")

        # --- Summary metrics ---
        st.subheader("Daily Summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Cost (₹)", f"{summary['total_cost']:.2f}")
        col2.metric("Grid-Only Cost (₹)", f"{summary['grid_only_cost']:.2f}")
        col3.metric("Savings (₹)", f"{summary['cost_savings']:.2f}")
        col4.metric("Solar Utilization (%)", f"{summary['solar_utilization_pct']:.1f}")

        # --- Charts ---
        st.subheader("Energy Flows Over Time")

        schedule_df_display = schedule_df.copy()
        schedule_df_display["time_local"] = schedule_df_display["time"].dt.tz_convert("Asia/Kolkata")

        # 1. Load vs Solar Prediction
        fig1 = px.line(
            schedule_df_display,
            x="time_local",
            y=["load_kwh", "solar_pred_kwh"],
            labels={"value": "kWh", "time_local": "Time", "variable": "Signal"},
            title="Load vs Predicted Solar (kWh)",
        )
        st.plotly_chart(fig1, use_container_width=True)

        # 2. Source usage stacked
        st.subheader("Energy Source Usage")
        fig2 = px.bar(
            schedule_df_display,
            x="time_local",
            y=["solar_used_kwh", "battery_discharge_kwh", "grid_used_kwh"],
            labels={"value": "kWh", "time_local": "Time", "variable": "Source"},
            title="Solar vs Battery vs Grid (kWh per hour)",
        )
        st.plotly_chart(fig2, use_container_width=True)

        # 3. Battery SoC
        st.subheader("Battery State of Charge")
        fig3 = px.line(
            schedule_df_display,
            x="time_local",
            y="battery_soc_kwh",
            labels={"battery_soc_kwh": "Battery SoC (kWh)", "time_local": "Time"},
            title="Battery Charge Level Over Time",
        )
        st.plotly_chart(fig3, use_container_width=True)

        # 4. Price vs Time
        schedule_df_display["price"] = schedule_df["price"]
        fig4 = px.line(
            schedule_df_display,
            x="time_local",
            y="price",
            labels={"price": "Price (₹/kWh)", "time_local": "Time"},
            title="Grid Price vs Time",
        )
        st.plotly_chart(fig4, use_container_width=True)

        # --- Detailed table ---
        st.subheader("Detailed Schedule (per hour)")
        st.dataframe(
            schedule_df_display[[
                "time_local",
                "load_kwh",
                "solar_pred_kwh",
                "price",
                "solar_used_kwh",
                "battery_charge_kwh",
                "battery_discharge_kwh",
                "grid_used_kwh",
                "battery_soc_kwh",
                "main_source",
            ]],
            use_container_width=True,
        )

    except Exception as e:
        st.error(f"Error: {e}")
