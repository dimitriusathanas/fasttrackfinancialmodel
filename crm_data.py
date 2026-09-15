"""Receivables CRM dataset: schema, seed data generation, and CSV persistence."""
from __future__ import annotations

import os
import random
from datetime import date, timedelta

import pandas as pd

_DIR = os.path.dirname(os.path.abspath(__file__))
CUSTOMERS_CSV = os.path.join(_DIR, "crm_customers.csv")

SEED = 20260915
N_CUSTOMERS = 60

COLUMNS = [
    "customer_id",
    "customer",
    "phone",
    "email",
    "city",
    "country",
    "region",
    "business_area",
    "times_hired",
    "last_work_date",
    "cash_received",
    "receivables_outstanding",
]

# (city, country, region, dialling code, tld, legal suffix)
_LOCATIONS = [
    ("Munich", "Germany", "Europe", "+49", "de", "GmbH"),
    ("Hamburg", "Germany", "Europe", "+49", "de", "GmbH"),
    ("Rotterdam", "Netherlands", "Europe", "+31", "nl", "B.V."),
    ("Amsterdam", "Netherlands", "Europe", "+31", "nl", "B.V."),
    ("Paris", "France", "Europe", "+33", "fr", "S.A."),
    ("Lyon", "France", "Europe", "+33", "fr", "SARL"),
    ("Milan", "Italy", "Europe", "+39", "it", "S.p.A."),
    ("Madrid", "Spain", "Europe", "+34", "es", "S.L."),
    ("Barcelona", "Spain", "Europe", "+34", "es", "S.L."),
    ("Lisbon", "Portugal", "Europe", "+351", "pt", "Lda."),
    ("Stockholm", "Sweden", "Europe", "+46", "se", "AB"),
    ("Copenhagen", "Denmark", "Europe", "+45", "dk", "A/S"),
    ("Warsaw", "Poland", "Europe", "+48", "pl", "Sp. z o.o."),
    ("Vienna", "Austria", "Europe", "+43", "at", "GmbH"),
    ("Zurich", "Switzerland", "Europe", "+41", "ch", "AG"),
    ("Dublin", "Ireland", "Europe", "+353", "ie", "Ltd"),
    ("London", "United Kingdom", "Europe", "+44", "co.uk", "Ltd"),
    ("Manchester", "United Kingdom", "Europe", "+44", "co.uk", "Ltd"),
    ("New York", "United States", "North America", "+1", "com", "LLC"),
    ("Chicago", "United States", "North America", "+1", "com", "Inc."),
    ("Austin", "United States", "North America", "+1", "com", "LLC"),
    ("Toronto", "Canada", "North America", "+1", "ca", "Inc."),
    ("Vancouver", "Canada", "North America", "+1", "ca", "Inc."),
    ("Mexico City", "Mexico", "Latin America", "+52", "mx", "S.A. de C.V."),
    ("Sao Paulo", "Brazil", "Latin America", "+55", "br", "Ltda."),
    ("Santiago", "Chile", "Latin America", "+56", "cl", "SpA"),
    ("Bogota", "Colombia", "Latin America", "+57", "co", "S.A.S."),
    ("Singapore", "Singapore", "Asia Pacific", "+65", "sg", "Pte Ltd"),
    ("Tokyo", "Japan", "Asia Pacific", "+81", "jp", "K.K."),
    ("Osaka", "Japan", "Asia Pacific", "+81", "jp", "K.K."),
    ("Seoul", "South Korea", "Asia Pacific", "+82", "kr", "Co., Ltd."),
    ("Sydney", "Australia", "Asia Pacific", "+61", "au", "Pty Ltd"),
    ("Melbourne", "Australia", "Asia Pacific", "+61", "au", "Pty Ltd"),
    ("Auckland", "New Zealand", "Asia Pacific", "+64", "nz", "Ltd"),
    ("Mumbai", "India", "Asia Pacific", "+91", "in", "Pvt Ltd"),
    ("Bengaluru", "India", "Asia Pacific", "+91", "in", "Pvt Ltd"),
    ("Dubai", "United Arab Emirates", "Middle East", "+971", "ae", "LLC"),
    ("Riyadh", "Saudi Arabia", "Middle East", "+966", "sa", "LLC"),
    ("Tel Aviv", "Israel", "Middle East", "+972", "il", "Ltd"),
    ("Johannesburg", "South Africa", "Africa", "+27", "za", "Pty Ltd"),
    ("Nairobi", "Kenya", "Africa", "+254", "ke", "Ltd"),
    ("Casablanca", "Morocco", "Africa", "+212", "ma", "S.A."),
]

_BUSINESS_AREAS = [
    "Renewable Energy",
    "Logistics & Freight",
    "Pharmaceuticals",
    "Construction",
    "Financial Services",
    "Retail & E-commerce",
    "Automotive",
    "Hospitality",
    "Telecommunications",
    "Food & Beverage",
    "Industrial Manufacturing",
    "Software & IT Services",
    "Media & Publishing",
    "Commercial Real Estate",
    "Agriculture",
    "Maritime Services",
]

_NAMES = [
    "Meridian", "Northgate", "Kestrel", "Aldermark", "Brightwater", "Cobalt",
    "Drakemoor", "Evercrest", "Fairlane", "Granite", "Harborview", "Ironwood",
    "Juniper", "Keystone", "Lumen", "Marbleton", "Northstar", "Oakfield",
    "Pinnacle", "Quarrystone", "Ridgeline", "Silverpine", "Tamarack", "Umbra",
    "Vanguard", "Westbrook", "Yarrow", "Zenith", "Ambervale", "Blackthorn",
    "Clearwater", "Dunmore", "Eastgate", "Falconridge", "Greystone", "Highmoor",
    "Ivyrock", "Jadewing", "Kingsford", "Lanternhill", "Moorfield", "Nightingale",
    "Opaline", "Portside", "Quicksilver", "Redwood", "Stonebridge", "Thornfield",
    "Ultramar", "Verdant", "Whitecliff", "Xenon", "Yellowridge", "Zephyr",
    "Amberline", "Beacon", "Cardinal", "Delphi", "Elmwood", "Foxglove",
]

_MAILBOXES = ["accounts", "finance", "ap", "billing", "accounting", "controller"]

# Bucket mix at generation time: healthy majority, meaningful delinquent tail.
_BUCKETS = ["current"] * 34 + ["collections"] * 15 + ["legal"] * 11


def _phone(rng: random.Random, dial: str) -> str:
    return f"{dial} {rng.randint(10, 99)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}"


def generate_customers(as_of: date | None = None) -> pd.DataFrame:
    """Build the 60-customer seed dataset. Deterministic for a given `as_of` date."""
    as_of = as_of or date.today()
    rng = random.Random(SEED)

    buckets = list(_BUCKETS)
    rng.shuffle(buckets)

    records = []
    for i, (word, bucket) in enumerate(zip(_NAMES, buckets), start=1):
        city, country, region, dial, tld, suffix = rng.choice(_LOCATIONS)
        name = f"{word} {rng.choice(['Group', 'Industries', 'Partners', 'Holdings', 'Solutions', 'Works'])} {suffix}"
        email = f"{rng.choice(_MAILBOXES)}@{word.lower()}.{tld}"

        times_hired = rng.randint(1, 26)
        cash_received = round(times_hired * rng.uniform(1_800, 9_500), 2)

        if bucket == "current":
            if rng.random() < 0.55:
                days = rng.randint(2, 29)
                receivables = round(rng.uniform(0, 26_000), 2)
            else:
                days = rng.randint(31, 260)
                receivables = round(rng.uniform(0, 1_950), 2)
        elif bucket == "collections":
            days = rng.randint(32, 89)
            receivables = round(rng.uniform(2_400, 46_000), 2)
        else:
            # A share of the legal bucket sits just past the 90-day line so the
            # action-items view shows recent collections-to-legal escalations.
            days = rng.randint(91, 103) if rng.random() < 0.4 else rng.randint(110, 340)
            receivables = round(rng.uniform(3_200, 98_000), 2)

        records.append(
            {
                "customer_id": f"C{i:03d}",
                "customer": name,
                "phone": _phone(rng, dial),
                "email": email,
                "city": city,
                "country": country,
                "region": region,
                "business_area": rng.choice(_BUSINESS_AREAS),
                "times_hired": times_hired,
                "last_work_date": (as_of - timedelta(days=days)).isoformat(),
                "cash_received": cash_received,
                "receivables_outstanding": receivables,
            }
        )

    return pd.DataFrame(records, columns=COLUMNS)


def load_customers() -> pd.DataFrame:
    """Read the customer file, generating and saving the seed dataset on first run."""
    if not os.path.exists(CUSTOMERS_CSV):
        df = generate_customers()
        save_customers(df)
        return df
    df = pd.read_csv(CUSTOMERS_CSV, dtype={"customer_id": str})
    return df[COLUMNS]


def save_customers(df: pd.DataFrame) -> None:
    df[COLUMNS].to_csv(CUSTOMERS_CSV, index=False)


def reset_customers() -> pd.DataFrame:
    df = generate_customers()
    save_customers(df)
    return df
