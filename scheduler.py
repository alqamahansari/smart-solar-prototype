# scheduler.py

import pandas as pd

def plan_day(
    times,
    solar_kwh,
    load_kwh,
    price_per_kwh,
    battery_capacity_kwh=5.0,
    max_charge_kwh_per_slot=1.0,
    max_discharge_kwh_per_slot=1.0,
    round_trip_efficiency=0.9,
    high_price_threshold=7.0,
    low_price_threshold=4.0,
    initial_soc_kwh=0.0,
):
    """
    Simple rule-based scheduler.

    times: list-like of timestamps
    solar_kwh: list-like of predicted solar energy per slot (kWh)
    load_kwh: list-like of house load per slot (kWh)
    price_per_kwh: list-like of grid price per slot (₹/kWh)

    Returns:
        schedule_df: pandas DataFrame with per-slot decisions
        summary: dict with total cost, savings, etc.
    """
    n = len(times)
    soc = initial_soc_kwh  # state of charge (kWh)

    records = []

    for i in range(n):
        t = times[i]
        solar = float(solar_kwh[i])
        demand = float(load_kwh[i])
        price = float(price_per_kwh[i])

        solar_used = 0.0
        grid_used = 0.0
        battery_charge = 0.0
        battery_discharge = 0.0

        # 1) Use solar to meet current load
        solar_to_load = min(solar, demand)
        solar_used += solar_to_load
        demand -= solar_to_load
        solar -= solar_to_load

        # 2) Use extra solar to charge battery
        if solar > 0:
            can_store = min(
                battery_capacity_kwh - soc,
                max_charge_kwh_per_slot
            )
            charge = min(solar, can_store)
            battery_charge = charge
            soc += charge * round_trip_efficiency
            solar -= charge
            # remaining solar (if any) is spilled/exported

        # 3) If still demand: decide between battery and grid
        if demand > 0:
            # If price is high, try to use battery first
            if price >= high_price_threshold and soc > 0:
                can_discharge = min(soc, max_discharge_kwh_per_slot)
                discharge = min(demand, can_discharge)
                battery_discharge = discharge
                demand -= discharge
                soc -= discharge / round_trip_efficiency

            # Remaining demand from grid
            if demand > 0:
                grid_used = demand
                demand = 0.0

        # Optional: cheap-price charging from grid (off-peak)
        # Uncomment this block if you want that behavior.
        # if price <= low_price_threshold and soc < battery_capacity_kwh:
        #     can_store = min(battery_capacity_kwh - soc, max_charge_kwh_per_slot)
        #     grid_for_charge = can_store
        #     soc += grid_for_charge * round_trip_efficiency
        #     grid_used += grid_for_charge

        # Decide dominant source label for UI
        if solar_used > 0 and grid_used == 0 and battery_discharge == 0:
            source = "SOLAR"
        elif grid_used > 0 and solar_used == 0 and battery_discharge == 0:
            source = "GRID"
        elif battery_discharge > 0 and grid_used == 0:
            source = "BATTERY"
        else:
            source = "MIXED"

        records.append({
            "time": t,
            "load_kwh": load_kwh[i],
            "solar_pred_kwh": solar_kwh[i],
            "price": price,
            "solar_used_kwh": solar_used,
            "battery_charge_kwh": battery_charge,
            "battery_discharge_kwh": battery_discharge,
            "grid_used_kwh": grid_used,
            "battery_soc_kwh": soc,
            "main_source": source,
        })

    schedule_df = pd.DataFrame(records)

    # Summary metrics
    total_grid_energy = schedule_df["grid_used_kwh"].sum()
    total_cost = (schedule_df["grid_used_kwh"] * schedule_df["price"]).sum()

    # Cost if grid only (no solar, no battery)
    grid_only_energy = sum(load_kwh)
    grid_only_cost = (grid_only_energy * pd.Series(price_per_kwh)).sum()

    # Solar utilization
    total_solar_available = sum(solar_kwh)
    total_solar_used = schedule_df["solar_used_kwh"].sum()
    solar_utilization_pct = 0.0
    if total_solar_available > 0:
        solar_utilization_pct = 100 * total_solar_used / total_solar_available

    summary = {
        "total_cost": total_cost,
        "grid_only_cost": grid_only_cost,
        "cost_savings": grid_only_cost - total_cost,
        "savings_pct": 100 * (grid_only_cost - total_cost) / grid_only_cost
        if grid_only_cost > 0 else 0.0,
        "total_grid_energy_kwh": total_grid_energy,
        "solar_utilization_pct": solar_utilization_pct,
    }

    return schedule_df, summary
