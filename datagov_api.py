# datagov_api.py

import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DATAGOV_API_KEY = os.getenv("DATAGOV_API_KEY")
BASE_URL = "https://api.data.gov.in/resource"


def fetch_datagov_resource(resource_id, params=None, limit=1000):
    """
    Generic fetch for a data.gov.in resource.
    """
    if DATAGOV_API_KEY is None:
        raise RuntimeError("DATAGOV_API_KEY not set in environment")

    if params is None:
        params = {}

    query_params = {
        "api-key": DATAGOV_API_KEY,
        "format": "json",
        "limit": limit,
    }
    query_params.update(params)

    url = f"{BASE_URL}/{resource_id}"
    resp = requests.get(url, params=query_params)
    resp.raise_for_status()
    return resp.json()


def get_sample_state_demand(resource_id, state_name, date_str):
    """
    Example: fetch state-level hourly demand from a dataset.

    You MUST adjust 'state' and 'date' filter keys and column names
    according to your chosen dataset.
    """
    raw = fetch_datagov_resource(
        resource_id,
        params={
            # Example; replace with real filter names from the dataset
            "filters[state]": state_name,
            "filters[date]": date_str,
        },
        limit=500,
    )

    records = raw.get("records", [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # You must update this part with the actual column names
    # from your dataset. For example:
    # df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"])
    # df["demand_mw"] = df["demand_mw"].astype(float)
    # df = df.sort_values("datetime").set_index("datetime")

    return df


def build_home_load_profile(hours=24, total_daily_kwh=10.0):
    """
    Simple synthetic household load profile (kWh per hour).
    Morning + evening peaks.
    """
    import numpy as np

    base = []
    for h in range(hours):
        if 6 <= h <= 9:
            base.append(1.2)  # morning peak
        elif 18 <= h <= 22:
            base.append(1.5)  # evening peak
        elif 10 <= h <= 16:
            base.append(0.6)  # daytime
        else:
            base.append(0.2)  # night
    base = np.array(base, dtype=float)
    # scale to total_daily_kwh
    scale = total_daily_kwh / base.sum()
    return list(base * scale)
