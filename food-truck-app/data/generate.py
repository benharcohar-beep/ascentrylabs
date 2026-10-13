"""
Generate the FAKE dataset behind Truckboard.

Everything here is invented. Truck names are made up; the places are real
Milwaukee spots, but the numbers attached to them are not measurements of
anything. The point is to give the app a realistic shape (seasonality,
day-of-week, weather, events, fees, tips) so the screens have something
honest-looking to show until Eventini's real POS data replaces it.

Outputs
  food-truck-app/data/truckboard-data.xlsx   the workbook Benny asked for
  food-truck-app/src/data/data.json          the aggregates the app reads

Run:  python3 food-truck-app/data/generate.py
Needs: openpyxl (pip install openpyxl). No API keys, no network.

Every tunable number lives in the ASSUMPTIONS list near the top, each with a
source label: "estimate" (mine), "industry range" (widely quoted ranges for
US food trucks, to verify) or "assumed date" (an event date I could not
confirm for 2026).
"""

from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HERE = Path(__file__).resolve().parent
XLSX_OUT = HERE / "truckboard-data.xlsx"
JSON_OUT = HERE.parent / "src" / "data" / "data.json"

rng = random.Random(20261009)
# Separate streams so tuning the sales model never reshuffles the market or the weather.
rng_market = random.Random(7)
rng_weather = random.Random(11)

# The data ends on the day the generator runs, so the app's 'today' is today.
# Re-run the generator to bring the demo up to date.
END = date.today()
START = END - timedelta(days=364)

# ---------------------------------------------------------------------------
# Assumptions (also written to the Assumptions tab)
# ---------------------------------------------------------------------------

SALES_TAX = 0.079  # WI 5% + Milwaukee County 0.9% + City of Milwaukee 2%
CARD_FEE_PCT = 0.026
CARD_FEE_FIXED = 0.10

SEASON = {10: 0.9, 11: 0.7, 12: 0.6, 1: 0.5, 2: 0.5, 3: 0.6,
          4: 0.8, 5: 1.0, 6: 1.15, 7: 1.2, 8: 1.2, 9: 1.05}
DOW = {0: 0.8, 1: 0.85, 2: 0.9, 3: 1.0, 4: 1.2, 5: 1.3, 6: 1.0}  # Mon=0
HOUR_PROFILE = {10: 0.4, 11: 0.8, 12: 1.3, 13: 1.2, 14: 0.6, 15: 0.4,
                16: 0.5, 17: 0.9, 18: 1.2, 19: 1.2, 20: 0.9, 21: 0.6, 22: 0.4}
DEMAND_SCALE = 0.5       # scales every location's base orders/hour; tuned to hit the revenue target
RAIN_MULT = 0.5          # planted story: rain halves a day
COLD_MULT = 0.75         # below 35F
HOT_MULT = 0.9           # above 88F

MONTH_TEMP_F = {1: 24, 2: 27, 3: 38, 4: 50, 5: 61, 6: 71,
                7: 76, 8: 74, 9: 67, 10: 55, 11: 42, 12: 30}
MONTH_RAIN_P = {1: 0.25, 2: 0.22, 3: 0.3, 4: 0.33, 5: 0.35, 6: 0.33,
                7: 0.3, 8: 0.3, 9: 0.3, 10: 0.3, 11: 0.3, 12: 0.28}

ASSUMPTIONS = [
    ("Period", f"{START.isoformat()} to {END.isoformat()}", "estimate", "12 months ending on the day the generator ran"),
    ("Sales tax", f"{SALES_TAX:.1%}", "to verify", "WI 5% + Milwaukee County 0.9% + City of Milwaukee 2% on prepared food"),
    ("Card processing", f"{CARD_FEE_PCT:.1%} + ${CARD_FEE_FIXED:.2f} per card/tap order", "industry range", "Square-style flat rate; Eventini's own fee structure to be confirmed"),
    ("Demand scale", DEMAND_SCALE, "estimate", "multiplies base orders/hour at every location"),
    ("Opening cash balance", 6500, "estimate", "cash in the business account on day one; the app rolls it forward from sales and costs"),
    ("Sales tax remittance", "paid on the 20th of the following month", "to verify", "WI monthly filers; quarterly for small filers"),
    ("Target annual revenue", "$180k to $250k", "industry range", "single truck, one city, part-year"),
    ("Target average order", "$15 to $18", "industry range", ""),
    ("Target food cost", "28% to 33% of sales", "industry range", "driven by the Recipes tab"),
    ("Target labour cost", "25% to 30% of sales", "industry range", "paid staff only, owner hours tracked but unpaid"),
    ("Season multiplier", json.dumps(SEASON), "estimate", "month -> demand multiplier"),
    ("Day-of-week multiplier", json.dumps(DOW), "estimate", "0=Mon"),
    ("Hour profile", json.dumps(HOUR_PROFILE), "estimate", "lunch and dinner peaks"),
    ("Rain multiplier", RAIN_MULT, "estimate", "PLANTED STORY: a rainy day halves sales"),
    ("Cold multiplier (<35F)", COLD_MULT, "estimate", ""),
    ("Hot multiplier (>88F)", HOT_MULT, "estimate", ""),
    ("Monthly mean temp F", json.dumps(MONTH_TEMP_F), "estimate", "rough Milwaukee climatology"),
    ("Monthly rain probability", json.dumps(MONTH_RAIN_P), "estimate", ""),
    ("Winter schedule", "2 to 3 days a week Nov to Mar, breweries/office/indoor", "estimate", ""),
    ("Summerfest 2026", "Jun 18-20, Jun 25-27, Jul 2-4", "assumed date", "pattern of recent years"),
    ("Mexican Fiesta 2026", "Aug 21-23", "assumed date", ""),
    ("Wisconsin State Fair 2026", "Aug 6-16", "assumed date", ""),
    ("Bastille Days 2026", "Jul 9-12", "assumed date", ""),
    ("Brewers home games", "synthetic schedule, ~81 dates Apr-Sep", "estimate", "not the real 2026 schedule"),
    ("Bucks home games", "synthetic schedule, ~41 dates Oct-Apr", "estimate", "not the real 2025-26 schedule"),
    ("Farmers markets", "Saturdays mid-Jun to mid-Oct", "estimate", ""),
]

PLANTED_STORIES = [
    "Birria taco is priced $4.25 against a market median of about $5.10: underpriced by roughly 17%.",
    "Deer District (Bucks games) takes nearly $200 an hour at the till, but a 25% cut plus a $100 pitch fee leaves less per hour than a no-fee office lunch.",
    "A rainy day roughly halves sales; the worst Saturday of the summer is a rain day.",
    "Water St downtown office lunch is the best no-fee slot by net revenue per hour, and it is bookable any weekday.",
    "Quesabirria runs a 40%+ food cost (cheese and beef); al pastor runs under 30%. Same price band, very different margin.",
    "Tips run about 15% of sales at breweries, 10% on the street and under 8% at games and festivals.",
    "Veggie taco sales fall by three quarters from 7 September while the roasted veg prep stays the same: a slow seller the owner should prep less of.",
]

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

HERO = {
    "truck_id": "T000",
    "name": "La Lumbre Taqueria",
    "concept": "Classic taqueria",
    "price_tier": "value",
    "home_neighbourhood": "Clarke Square",
    "years_trading": 3,
    "instagram_followers": 4100,
    "owner": "Marisol Ortega",
    "pos": "Eventini",
}

# Made-up rival trucks. Any resemblance to a real business is accidental.
RIVALS = [
    ("T001", "Taqueria El Jaripeo",        "Classic taqueria",  "value",   "Historic Mitchell St", 6, 2300),
    ("T002", "Humo y Birria",              "Birria specialist", "premium", "Walker's Point",       2, 9800),
    ("T003", "Dona Lupe's Tacos",          "Classic taqueria",  "value",   "Clarke Square",        9, 1500),
    ("T004", "Tacos del Sol MKE",          "Classic taqueria",  "mid",     "Bay View",             4, 5200),
    ("T005", "Cielo Street Kitchen",       "Mexican fusion",    "premium", "Third Ward",           3, 12400),
    ("T006", "La Reina Elotes y Mas",      "Street snacks",     "value",   "Lincoln Village",      5, 3100),
    ("T007", "Mariscos El Faro",           "Seafood",           "premium", "Lincoln Village",      4, 2700),
    ("T008", "Tortas Chido",               "Tortas",            "mid",     "Riverwest",            2, 1900),
    ("T009", "Guac Shack",                 "Fast casual",       "mid",     "East Side",            3, 6800),
    ("T010", "Taqueria Hermanos Ruiz",     "Classic taqueria",  "mid",     "Layton Blvd",          7, 2900),
    ("T011", "Chido Birria & Tacos",       "Birria specialist", "mid",     "Wauwatosa",            1, 4400),
    ("T012", "Pepe's Al Pastor",           "Classic taqueria",  "mid",     "Historic Mitchell St", 5, 3600),
]
TIER_MULT = {"value": 0.92, "mid": 1.0, "premium": 1.15}

# Standard items: the like-for-like buckets used for market comparison.
# (id, label, base market median $, which rival concepts carry it)
STANDARD_ITEMS = [
    ("taco_single",        "Street taco, single",           4.00, {"Classic taqueria", "Mexican fusion", "Fast casual", "Birria specialist", "Seafood"}),
    ("taco_birria_single", "Birria taco, single",           4.75, {"Classic taqueria", "Birria specialist", "Mexican fusion"}),
    ("taco_plate_3",       "Taco plate, 3 with rice/beans", 13.00, {"Classic taqueria", "Birria specialist", "Fast casual"}),
    ("quesabirria_3",      "Quesabirria, 3 with consome",   15.00, {"Classic taqueria", "Birria specialist", "Mexican fusion"}),
    ("burrito_std",        "Burrito, standard",             12.00, {"Classic taqueria", "Fast casual", "Mexican fusion"}),
    ("burrito_cali",       "California burrito",            13.50, {"Classic taqueria", "Fast casual"}),
    ("quesadilla",         "Quesadilla",                    10.00, {"Classic taqueria", "Fast casual", "Mexican fusion", "Birria specialist"}),
    ("torta",              "Torta",                         11.50, {"Classic taqueria", "Tortas"}),
    ("elote",              "Elote (street corn)",            5.50, {"Classic taqueria", "Street snacks", "Mexican fusion", "Fast casual"}),
    ("chips_salsa",        "Chips and salsa",                3.50, {"Classic taqueria", "Fast casual", "Mexican fusion", "Street snacks"}),
    ("chips_guac",         "Chips and guacamole",            6.50, {"Classic taqueria", "Fast casual", "Mexican fusion"}),
    ("nachos",             "Loaded nachos",                 11.00, {"Fast casual", "Mexican fusion", "Street snacks"}),
    ("agua_fresca",        "Agua fresca",                    3.75, {"Classic taqueria", "Street snacks", "Birria specialist", "Tortas", "Seafood"}),
    ("soda_bottle",        "Bottled soda (Jarritos etc.)",   2.50, {"Classic taqueria", "Street snacks", "Birria specialist", "Tortas", "Seafood", "Fast casual", "Mexican fusion"}),
    ("water",              "Bottled water",                  1.50, {"Classic taqueria", "Street snacks", "Birria specialist", "Tortas", "Seafood", "Fast casual", "Mexican fusion"}),
    ("churros",            "Churros",                        4.50, {"Classic taqueria", "Street snacks", "Mexican fusion"}),
]

# Ingredients: (id, name, unit, cost per unit $, shelf life in days once prepped/opened)
INGREDIENTS = {
    "tortilla_corn":  ("Corn tortilla", "each", 0.08, 7),
    "tortilla_flour": ("Flour tortilla, large", "each", 0.35, 10),
    "pork_pastor":    ("Pork, marinated al pastor", "oz", 0.22, 3),
    "beef_asada":     ("Beef, carne asada", "oz", 0.34, 3),
    "pork_carnitas":  ("Pork, carnitas", "oz", 0.20, 4),
    "chicken":        ("Chicken, marinated", "oz", 0.17, 2),
    "beef_birria":    ("Beef, birria braise", "oz", 0.35, 3),
    "veg_mix":        ("Roasted veg mix", "oz", 0.12, 2),
    "cheese":         ("Oaxaca/jack cheese", "oz", 0.28, 10),
    "rice_beans":     ("Rice and beans portion", "portion", 0.35, 2),
    "toppings":       ("Onion, cilantro, lime, salsa", "portion", 0.12, 1),
    "crema_guac":     ("Crema / guacamole", "oz", 0.30, 1),
    "consome":        ("Consome", "cup", 0.45, 3),
    "corn_cob":       ("Corn on the cob", "each", 0.60, 3),
    "elote_dress":    ("Mayo, cotija, chili", "portion", 0.35, 5),
    "chips":          ("Tortilla chips", "portion", 0.40, 14),
    "salsa_cup":      ("Salsa cup", "each", 0.20, 3),
    "agua_base":      ("Agua fresca base", "cup", 0.55, 2),
    "soda":           ("Bottled soda", "each", 1.10, 180),
    "water_btl":      ("Bottled water", "each", 0.25, 365),
    "churro":         ("Churro, fried", "each", 0.45, 1),
    "bread_torta":    ("Torta roll", "each", 0.55, 2),
    "packaging":      ("Packaging and napkins", "portion", 0.07, 365),
    "foil_box":       ("Foil / clamshell", "each", 0.18, 365),
}

# Menu: (item_id, name, category, standard_item, price, daypart weight, popularity, recipe)
MENU = [
    ("M01", "Taco al pastor",      "Tacos",   "taco_single",        3.50, 18, {"tortilla_corn": 2, "pork_pastor": 3, "toppings": 1, "packaging": 1}),
    ("M02", "Taco carne asada",    "Tacos",   "taco_single",        3.75, 16, {"tortilla_corn": 2, "beef_asada": 3, "toppings": 1, "packaging": 1}),
    ("M03", "Taco carnitas",       "Tacos",   "taco_single",        3.50, 12, {"tortilla_corn": 2, "pork_carnitas": 3, "toppings": 1, "packaging": 1}),
    ("M04", "Taco pollo",          "Tacos",   "taco_single",        3.25,  9, {"tortilla_corn": 2, "chicken": 3, "toppings": 1, "packaging": 1}),
    ("M05", "Taco birria",         "Tacos",   "taco_birria_single", 4.25, 14, {"tortilla_corn": 2, "beef_birria": 3, "cheese": 0.75, "toppings": 1, "packaging": 1}),
    ("M06", "Taco veggie",         "Tacos",   "taco_single",        3.25,  4, {"tortilla_corn": 2, "veg_mix": 3, "toppings": 1, "packaging": 1}),
    ("M07", "Taco plate (3)",      "Plates",  "taco_plate_3",      12.50,  9, {"tortilla_corn": 6, "pork_pastor": 9, "rice_beans": 1, "toppings": 2, "foil_box": 1}),
    ("M08", "Quesabirria (3)",     "Plates",  "quesabirria_3",     14.00, 10, {"tortilla_corn": 6, "beef_birria": 10, "cheese": 4, "consome": 1, "toppings": 1, "foil_box": 1}),
    ("M09", "Burrito",             "Burritos","burrito_std",       11.50, 11, {"tortilla_flour": 1, "beef_asada": 5, "rice_beans": 1, "cheese": 1, "crema_guac": 0.5, "packaging": 1}),
    ("M10", "California burrito",  "Burritos","burrito_cali",      13.00,  6, {"tortilla_flour": 1, "beef_asada": 5, "rice_beans": 1, "cheese": 1.5, "crema_guac": 1, "packaging": 1}),
    ("M11", "Quesadilla",          "Plates",  "quesadilla",         9.50,  7, {"tortilla_flour": 1, "cheese": 3, "chicken": 3, "toppings": 1, "packaging": 1}),
    ("M12", "Torta",               "Tortas",  "torta",             11.00,  5, {"bread_torta": 1, "pork_carnitas": 5, "cheese": 1, "crema_guac": 1, "toppings": 1, "packaging": 1}),
    ("M13", "Elote",               "Sides",   "elote",              5.00,  9, {"corn_cob": 1, "elote_dress": 1, "packaging": 1}),
    ("M14", "Chips and salsa",     "Sides",   "chips_salsa",        3.50,  6, {"chips": 1, "salsa_cup": 1, "packaging": 1}),
    ("M15", "Chips and guac",      "Sides",   "chips_guac",         6.50,  5, {"chips": 1, "crema_guac": 3, "packaging": 1}),
    ("M16", "Agua fresca",         "Drinks",  "agua_fresca",        3.50, 12, {"agua_base": 1, "packaging": 1}),
    ("M17", "Jarritos",            "Drinks",  "soda_bottle",        2.50, 10, {"soda": 1}),
    ("M18", "Bottled water",       "Drinks",  "water",              1.50,  8, {"water_btl": 1}),
    ("M19", "Churros (3)",         "Dessert", "churros",            4.50,  4, {"churro": 3, "packaging": 1}),
]
TACO_IDS = {"M01", "M02", "M03", "M04", "M05", "M06"}


def key_ingredient(recipe: dict):
    """The ingredient that carries most of the item's cost, and its quantity."""
    k = max(recipe, key=lambda i: INGREDIENTS[i][2] * recipe[i])
    return k, recipe[k]


def item_cost(recipe: dict) -> float:
    return round(sum(INGREDIENTS[k][2] * q for k, q in recipe.items()), 2)


# Locations: real Milwaukee places; every number attached is invented.
# (id, name, type, neighbourhood, lat, lon, flat_fee, pct_fee, base orders/hr, allowed dows, hours, season)
# season: "all" | "warm" (Apr-Oct) | "winter_ok"
LOCATIONS = [
    ("L01", "Zocalo Food Park",                 "food_park", "Walker's Point",  43.0243, -87.9189, 150,  0.00, 18, {2, 3, 4, 5, 6}, (11, 21), "all"),
    ("L02", "Third Ward, Broadway & Menomonee", "street",    "Third Ward",      43.0334, -87.9075,   0,  0.00, 15, {3, 4, 5},       (11, 21), "warm"),
    ("L03", "Bay View, KK Ave",                 "street",    "Bay View",        43.0035, -87.9029,   0,  0.00, 14, {2, 3, 4, 5, 6}, (11, 20), "warm"),
    ("L04", "Cesar Chavez Dr",                  "street",    "Clarke Square",   43.0202, -87.9323,   0,  0.00, 13, {0, 1, 2, 3, 4, 5, 6}, (11, 20), "all"),
    ("L05", "Deer District (Bucks games)",      "event",     "Westown",         43.0451, -87.9174, 100,  0.25, 46, {0, 1, 2, 3, 4, 5, 6}, (16, 22), "all"),
    ("L06", "Brewers tailgate lot",             "event",     "Story Hill",      43.0280, -87.9712, 250,  0.00, 32, {0, 1, 2, 3, 4, 5, 6}, (16, 21), "warm"),
    ("L07", "Lakefront Brewery",                "brewery",   "Brewers Hill",    43.0528, -87.9057,   0,  0.00, 17, {3, 4, 5, 6},    (16, 21), "all"),
    ("L08", "Third Space Brewing",              "brewery",   "Menomonee Valley",43.0291, -87.9290,   0,  0.00, 15, {3, 4, 5},       (16, 21), "all"),
    ("L09", "Gathering Place Brewing",          "brewery",   "Riverwest",       43.0696, -87.9007,   0,  0.00, 13, {4, 5, 6},       (16, 21), "all"),
    ("L10", "1840 Brewing",                     "brewery",   "Bay View",        43.0067, -87.9087,   0,  0.00, 14, {4, 5, 6},       (16, 21), "all"),
    ("L11", "Schlitz Park (office lunch)",      "office",    "Brewers Hill",    43.0493, -87.9139,   0,  0.00, 22, {0, 1, 2, 3, 4}, (11, 14), "all"),
    ("L12", "Water St downtown (office lunch)", "office",    "Downtown",        43.0415, -87.9103,   0,  0.00, 24, {0, 1, 2, 3, 4}, (11, 14), "all"),
    ("L13", "Milwaukee Regional Medical Center","hospital",  "Wauwatosa",       43.0423, -88.0224,   0,  0.00, 19, {0, 1, 2, 3, 4}, (11, 14), "all"),
    ("L14", "South Shore Farmers Market",       "market",    "Bay View",        42.9965, -87.8812,  60,  0.00, 20, {5},             (8, 13),  "warm"),
    ("L15", "Tosa Farmers Market",              "market",    "Wauwatosa",       43.0466, -88.0075,  50,  0.00, 19, {5},             (8, 13),  "warm"),
    ("L16", "Summerfest grounds",               "festival",  "Lakefront",       43.0301, -87.8996, 300,  0.20, 32, {0, 1, 2, 3, 4, 5, 6}, (12, 22), "warm"),
    ("L17", "Mexican Fiesta",                   "festival",  "Lakefront",       43.0301, -87.8996, 250,  0.20, 34, {0, 1, 2, 3, 4, 5, 6}, (12, 22), "warm"),
    ("L18", "Wisconsin State Fair",             "festival",  "West Allis",      43.0186, -88.0100, 300,  0.18, 28, {0, 1, 2, 3, 4, 5, 6}, (11, 21), "warm"),
    ("L19", "UWM campus, Kenwood Blvd",         "campus",    "East Side",       43.0760, -87.8820,  75,  0.00, 15, {1, 2, 3},       (11, 15), "all"),
    ("L20", "Bastille Days, Cathedral Square",  "festival",  "East Town",       43.0412, -87.9044, 200,  0.15, 30, {0, 1, 2, 3, 4, 5, 6}, (12, 22), "warm"),
]
LOC = {l[0]: l for l in LOCATIONS}
TIP_MEAN = {"brewery": 0.20, "street": 0.12, "food_park": 0.15, "event": 0.09,
            "festival": 0.08, "office": 0.14, "hospital": 0.13, "market": 0.16, "campus": 0.10}

STAFF = [
    ("S00", "Marisol Ortega", "Owner", 0.0),
    ("S01", "Diego Ramos", "Cook", 18.0),
    ("S02", "Yesenia Cruz", "Cashier", 15.5),
    ("S03", "Luis Mendoza", "Cook", 17.0),
    ("S04", "Ana Villanueva", "Cashier", 15.0),
]

FIXED_MONTHLY = [
    ("Commissary kitchen rent", 900, False),
    ("Truck loan", 750, False),
    ("Insurance (liability + auto)", 350, False),
    ("Licences and permits (annualised)", 180, False),
    ("Phone, POS software, website", 80, False),
    ("Marketing", 100, False),
    ("Maintenance reserve", 200, False),
    ("Propane", 220, True),   # scaled by activity
    ("Fuel", 300, True),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def poisson(lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 60:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def r2(x: float) -> float:
    return round(x + 1e-9, 2)


def quarter(x: float) -> float:
    return round(round(x * 4) / 4, 2)


# ---------------------------------------------------------------------------
# Weather and events
# ---------------------------------------------------------------------------

def make_weather():
    rows = []
    for d in daterange(START, END):
        m = d.month
        temp = round(min(95, max(-15, rng_weather.gauss(MONTH_TEMP_F[m], 9))))
        rain = rng_weather.random() < MONTH_RAIN_P[m]
        mm = r2(rng_weather.expovariate(1 / 6)) if rain else 0.0
        rows.append({"date": d.isoformat(), "temp_f": temp, "rain": rain, "rain_mm": mm,
                     "condition": "rain" if rain and temp > 34 else "snow" if rain else "clear" if rng_weather.random() < 0.6 else "cloudy"})
    # Planted story: make two July/August Saturdays rain days
    by = {r["date"]: r for r in rows}
    for ds in ("2026-07-18", "2026-08-15"):
        by[ds].update(rain=True, rain_mm=14.2, condition="rain")
    for ds in ("2026-06-27", "2026-07-04"):  # keep the festival weekends dry
        by[ds].update(rain=False, rain_mm=0.0, condition="clear")
    return rows


def make_events():
    ev = []

    def add(name, d, loc, mult, kind, source):
        ev.append({"event_id": f"E{len(ev)+1:03d}", "name": name, "date": d.isoformat(),
                   "location_id": loc, "boost": mult, "kind": kind, "source": source})

    # Bucks: ~41 home games Oct-Apr (synthetic)
    bucks_days = []
    for d in daterange(date(2025, 10, 22), date(2026, 4, 12)):
        if rng.random() < 0.235:
            bucks_days.append(d)
    for d in bucks_days:
        add("Bucks home game", d, "L05", 1.0, "sport", "synthetic schedule")
    # Brewers: ~81 home games Apr-Sep (synthetic), mostly in homestands
    d = date(2026, 4, 2)
    while d <= date(2026, 9, 27):
        stand = rng.choice([3, 3, 4, 6])
        for i in range(stand):
            dd = d + timedelta(days=i)
            if dd <= date(2026, 9, 27):
                add("Brewers home game", dd, "L06", 1.0, "sport", "synthetic schedule")
        d += timedelta(days=stand + rng.choice([3, 4, 6, 7]))
    # Festivals (assumed dates)
    for d in [date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 20),
              date(2026, 6, 25), date(2026, 6, 26), date(2026, 6, 27),
              date(2026, 7, 2), date(2026, 7, 3), date(2026, 7, 4)]:
        add("Summerfest", d, "L16", 1.0, "festival", "assumed date")
    for d in daterange(date(2026, 8, 21), date(2026, 8, 23)):
        add("Mexican Fiesta", d, "L17", 1.15, "festival", "assumed date")
    for d in daterange(date(2026, 8, 6), date(2026, 8, 16)):
        add("Wisconsin State Fair", d, "L18", 1.0, "festival", "assumed date")
    for d in daterange(date(2026, 7, 9), date(2026, 7, 12)):
        add("Bastille Days", d, "L20", 1.0, "festival", "assumed date")
    # Farmers markets: Saturdays mid-Jun to mid-Oct
    for d in daterange(START, END):
        if d.weekday() == 5 and ((d.month == 6 and d.day >= 13) or d.month in (7, 8, 9) or (d.month == 10 and d.day <= 17)):
            add("South Shore Farmers Market", d, "L14", 1.0, "market", "estimate")
            add("Tosa Farmers Market", d, "L15", 1.0, "market", "estimate")
    return ev


# ---------------------------------------------------------------------------
# Schedule: which days the truck trades, and where
# ---------------------------------------------------------------------------

def make_schedule(events):
    ev_by_date = defaultdict(list)
    for e in events:
        ev_by_date[e["date"]].append(e)

    rows = []
    for d in daterange(START, END):
        m, dow = d.month, d.weekday()
        winter = m in (11, 12, 1, 2, 3)
        shoulder = m in (4, 10)
        todays = ev_by_date[d.isoformat()]

        # Festivals and sport events first (the truck takes the booking)
        fest = [e for e in todays if e["kind"] == "festival"]
        sport = [e for e in todays if e["kind"] == "sport"]
        market = [e for e in todays if e["kind"] == "market"]

        loc = None
        if fest:
            e = fest[0]
            loc = e["location_id"]
        elif sport and rng.random() < (0.4 if not winter else 0.45):
            loc = sport[0]["location_id"]
        elif market and rng.random() < 0.7:
            loc = rng.choice(market)["location_id"]
        else:
            # Probability of trading at all
            p = 0.25 if winter else 0.5 if shoulder else 0.68
            if dow in (4, 5):
                p += 0.12
            if rng.random() > p:
                rows.append({"date": d.isoformat(), "trading": False, "location_id": None, "reason": "day off"})
                continue
            cands = []
            for l in LOCATIONS:
                lid, _, ltype, *_rest = l
                dows, hours, season = l[9], l[10], l[11]
                if ltype in ("event", "festival", "market"):
                    continue
                if dow not in dows:
                    continue
                if season == "warm" and (winter or m in (11, 3)):
                    continue
                w = 1.0
                if winter and ltype in ("brewery", "office", "hospital", "campus"):
                    w = 2.0
                if ltype == "street":
                    w = 2.0 if dow in (4, 5) else 1.4
                if lid == "L01":
                    w = 3.0 if dow in (4, 5, 6) else 1.8
                cands.append((lid, w))
            if not cands:
                rows.append({"date": d.isoformat(), "trading": False, "location_id": None, "reason": "no slot"})
                continue
            loc = rng.choices([c[0] for c in cands], weights=[c[1] for c in cands])[0]

        l = LOC[loc]
        start_h, end_h = l[10]
        ltype = l[2]
        staff_n = 2 if (ltype in ("event", "festival") or not winter) else 1
        rows.append({"date": d.isoformat(), "trading": True, "location_id": loc, "start_hour": start_h,
                     "end_hour": end_h, "paid_staff": staff_n,
                     "event_id": next((e["event_id"] for e in todays if e["location_id"] == loc), None),
                     "reason": ""})
    return rows


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def make_orders(schedule, weather, events):
    w_by = {w["date"]: w for w in weather}
    ev_by = {(e["date"], e["location_id"]): e for e in events}
    def menu_weights(d: date):
        # PLANTED STORY: veggie taco falls off a cliff from 7 Sep 2026 (students back, lunch crowd changes);
        # churros fade from mid-August. The owner keeps prepping the same amount.
        ws = []
        for m in MENU:
            w = m[5]
            if m[0] == "M06" and d >= date(2026, 9, 7):
                w *= 0.25
            if m[0] == "M19" and d >= date(2026, 8, 15):
                w *= 0.45
            ws.append(w)
        return ws
    orders, lines = [], []
    oid = 0
    for s in schedule:
        if not s["trading"]:
            continue
        d = date.fromisoformat(s["date"])
        l = LOC[s["location_id"]]
        ltype, base = l[2], l[8] * DEMAND_SCALE
        w = w_by[s["date"]]
        mult = SEASON[d.month] * DOW[d.weekday()]
        if w["rain"]:
            mult *= RAIN_MULT
        if w["temp_f"] < 35:
            mult *= COLD_MULT
        if w["temp_f"] > 88:
            mult *= HOT_MULT
        e = ev_by.get((s["date"], s["location_id"]))
        if e:
            mult *= e["boost"]
        if ltype in ("event", "festival", "office", "hospital", "market", "campus"):
            mult *= 1.0 / SEASON[d.month] ** 0.5  # bookings are less seasonal than walk-up
        day_noise = rng.lognormvariate(0, 0.12)
        menu_w = menu_weights(d)
        for h in range(s["start_hour"], s["end_hour"]):
            lam = base * HOUR_PROFILE.get(h, 0.5) * mult * day_noise
            if ltype in ("office", "hospital", "market", "campus"):
                lam = base * {11: 0.8, 12: 1.4, 13: 1.1, 8: 0.5, 9: 0.9, 10: 1.1, 14: 0.5}.get(h, 0.6) * mult * day_noise
            n = poisson(lam)
            for _ in range(n):
                oid += 1
                order_id = f"O{oid:06d}"
                ts = datetime(d.year, d.month, d.day, h, rng.randrange(60), rng.randrange(60))
                n_lines = rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
                picked = {}
                for _k in range(n_lines):
                    m = rng.choices(MENU, weights=menu_w)[0]
                    if m[0] in TACO_IDS:
                        q = rng.choices([1, 2, 3, 4], weights=[20, 35, 30, 15])[0]
                    else:
                        q = 1 if rng.random() < 0.85 else 2
                    picked[m[0]] = picked.get(m[0], 0) + q
                subtotal = 0.0
                for mid, q in picked.items():
                    m = next(x for x in MENU if x[0] == mid)
                    lt = r2(m[4] * q)
                    subtotal += lt
                    lines.append({"order_id": order_id, "item_id": mid, "item": m[1], "qty": q,
                                  "unit_price": m[4], "line_total": lt})
                subtotal = r2(subtotal)
                discount = r2(rng.choice([1, 2, 3])) if rng.random() < 0.05 else 0.0
                discount = min(discount, subtotal)
                taxable = r2(subtotal - discount)
                tax = r2(taxable * SALES_TAX)
                pay = rng.choices(["card", "tap", "cash"], weights=[58, 24, 18])[0]
                tip = 0.0
                if rng.random() < (0.85 if pay != "cash" else 0.45):
                    pct = rng.gauss(TIP_MEAN[ltype], 0.05)
                    pct = min(max(pct, 0.05), 0.32)
                    tip = r2(taxable * pct)
                    if pay == "cash":
                        tip = r2(round(tip))  # whole dollars in the jar
                total = r2(taxable + tax + tip)
                fee = r2(total * CARD_FEE_PCT + CARD_FEE_FIXED) if pay != "cash" else 0.0
                orders.append({"order_id": order_id, "datetime": ts.isoformat(sep=" "), "date": s["date"],
                               "hour": h, "location_id": s["location_id"], "event_id": s["event_id"],
                               "payment": pay, "subtotal": subtotal, "discount": discount, "tax": tax,
                               "tip": tip, "total": total, "processing_fee": fee, "lines": len(picked)})
    return orders, lines


# ---------------------------------------------------------------------------
# Shifts, costs, catering
# ---------------------------------------------------------------------------

def make_shifts(schedule):
    rows = []
    pool = STAFF[1:]
    for s in schedule:
        if not s["trading"]:
            continue
        hours = (s["end_hour"] - s["start_hour"]) + 2.0  # prep, drive, clean-down
        rows.append({"date": s["date"], "staff_id": "S00", "name": STAFF[0][1], "role": "Owner",
                     "hours": hours, "wage": 0.0, "cost": 0.0})
        for st in rng.sample(pool, s["paid_staff"]):
            rows.append({"date": s["date"], "staff_id": st[0], "name": st[1], "role": st[2],
                         "hours": hours, "wage": st[3], "cost": r2(hours * st[3])})
    return rows


def make_catering(schedule):
    trading = {s["date"] for s in schedule if s["trading"]}
    rows = []
    n = 0
    for d in daterange(START, END):
        if d.isoformat() in trading:
            continue
        m = d.month
        p = {12: 0.14, 5: 0.12, 6: 0.15, 7: 0.13, 8: 0.15, 9: 0.13, 10: 0.08}.get(m, 0.03)
        if d.weekday() in (4, 5, 6) and rng.random() < p * 2.4:
            n += 1
            heads = rng.choice([40, 50, 60, 75, 80, 100, 120, 150])
            per_head = rng.choice([18, 20, 22, 25])
            kind = rng.choice(["Wedding", "Office lunch", "Birthday", "Holiday party" if m == 12 else "Graduation" if m in (5, 6) else "Block party"])
            rows.append({"booking_id": f"C{n:03d}", "date": d.isoformat(), "type": kind, "heads": heads,
                         "price_per_head": per_head, "revenue": heads * per_head,
                         "food_cost": r2(heads * per_head * 0.30), "staff_cost": r2(4.5 * 2 * 17),
                         "source": rng.choice(["Eventini booking", "Eventini booking", "Direct"])})
    return rows


def make_fixed_costs(orders):
    by_month = defaultdict(float)
    for o in orders:
        by_month[o["date"][:7]] += o["subtotal"] - o["discount"]
    peak = max(by_month.values())
    rows = []
    for ym in sorted(by_month):
        for name, amt, scaled in FIXED_MONTHLY:
            v = amt * (0.4 + 0.6 * by_month[ym] / peak) if scaled else amt
            rows.append({"month": ym, "cost": name, "amount": r2(v), "scaled_by_activity": scaled})
    return rows


# ---------------------------------------------------------------------------
# Market prices and benchmarks
# ---------------------------------------------------------------------------

def make_market():
    rows = []
    sources = ["menu photo", "Instagram", "truck website", "Eventini POS", "Eventini POS"]
    for r in RIVALS:
        tid, name, concept, tier, *_ = r
        for sid, label, med, concepts in STANDARD_ITEMS:
            if concept not in concepts:
                continue
            if concept == "Birria specialist" and sid in ("taco_single", "burrito_std", "burrito_cali"):
                if rng_market.random() < 0.5:
                    continue
            if rng_market.random() < 0.12:
                continue
            price = quarter(med * TIER_MULT[tier] * rng_market.lognormvariate(0, 0.07))
            seen = START + timedelta(days=rng_market.randrange(0, (END - START).days))
            rows.append({"truck_id": tid, "truck": name, "standard_item": sid, "item_label": label,
                         "price": price, "date_seen": seen.isoformat(), "source": rng_market.choice(sources)})
    return rows


def make_benchmarks(market):
    by = defaultdict(list)
    for m in market:
        by[m["standard_item"]].append(m["price"])
    hero_by = {}
    for m in MENU:
        hero_by.setdefault(m[3], []).append(m[4])
    rows = []
    for sid, label, med, _ in STANDARD_ITEMS:
        ps = sorted(by[sid])
        hero = statistics.mean(hero_by[sid]) if sid in hero_by else None
        rows.append({"standard_item": sid, "item_label": label, "n_trucks": len(ps),
                     "min": ps[0], "p25": ps[len(ps) // 4], "median": statistics.median(ps),
                     "p75": ps[(3 * len(ps)) // 4], "max": ps[-1],
                     "hero_price": r2(hero) if hero else None,
                     "hero_vs_median": r2(hero / statistics.median(ps) - 1) if hero else None})
    return rows


INDUSTRY_KPIS = [
    ("Food cost % of sales", "28% to 35%", "industry range", "to verify against Eventini vendor data"),
    ("Labour cost % of sales", "25% to 35%", "industry range", ""),
    ("Average ticket, Mexican truck", "$14 to $19", "estimate", ""),
    ("Tip rate on card", "10% to 20%", "estimate", "varies strongly by venue"),
    ("Event / food park fee", "10% to 25% of sales, or $50 to $300 flat", "estimate", ""),
    ("Trading days per year, Wisconsin", "150 to 220", "estimate", "weather-limited"),
    ("Annual revenue, single truck", "$150k to $300k", "industry range", ""),
]


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

def aggregate(schedule, orders, lines, shifts, weather, events, fixed, catering):
    cost_by_item = {m[0]: item_cost(m[6]) for m in MENU}
    w_by = {w["date"]: w for w in weather}
    ev_by_id = {e["event_id"]: e for e in events}
    o_by_date = defaultdict(list)
    for o in orders:
        o_by_date[o["date"]].append(o)
    cogs_by_order = defaultdict(float)
    item_day = defaultdict(lambda: [0, 0.0, 0.0])
    o_date = {o["order_id"]: o["date"] for o in orders}
    for ln in lines:
        cogs_by_order[ln["order_id"]] += cost_by_item[ln["item_id"]] * ln["qty"]
        k = (o_date[ln["order_id"]], ln["item_id"])
        item_day[k][0] += ln["qty"]
        item_day[k][1] += ln["line_total"]
        item_day[k][2] += cost_by_item[ln["item_id"]] * ln["qty"]
    labour_by_date = defaultdict(float)
    for s in shifts:
        labour_by_date[s["date"]] += s["cost"]

    days = []
    for s in schedule:
        w = w_by[s["date"]]
        row = {"date": s["date"], "trading": s["trading"], "location_id": s["location_id"],
               "event": ev_by_id[s["event_id"]]["name"] if s.get("event_id") else None,
               "temp_f": w["temp_f"], "rain": w["rain"], "condition": w["condition"]}
        if s["trading"]:
            os_ = o_by_date[s["date"]]
            l = LOC[s["location_id"]]
            hours = s["end_hour"] - s["start_hour"]
            gross = r2(sum(o["subtotal"] - o["discount"] for o in os_))
            tips = r2(sum(o["tip"] for o in os_))
            fees = r2(sum(o["processing_fee"] for o in os_))
            loc_fee = r2(l[6] + l[7] * gross)
            cogs = r2(sum(cogs_by_order[o["order_id"]] for o in os_))
            labour = r2(labour_by_date[s["date"]])
            row.update({"hours": hours, "paid_staff": s["paid_staff"], "orders": len(os_), "gross_sales": gross,
                        "tips": tips, "tax_collected": r2(sum(o["tax"] for o in os_)),
                        "processing_fees": fees, "location_fee": loc_fee, "cogs": cogs, "labour": labour,
                        "net_after_fees": r2(gross - fees - loc_fee),
                        "contribution": r2(gross - fees - loc_fee - cogs - labour),
                        "gross_per_hour": r2(gross / hours), "net_per_hour": r2((gross - fees - loc_fee) / hours),
                        "avg_order": r2(gross / len(os_)) if os_ else 0.0})
        days.append(row)

    hourly = defaultdict(lambda: [0, 0.0, 0])
    for o in orders:
        k = (o["location_id"], o["hour"])
        hourly[k][0] += 1
        hourly[k][1] += o["subtotal"] - o["discount"]
    for s in schedule:
        if s["trading"]:
            for h in range(s["start_hour"], s["end_hour"]):
                hourly[(s["location_id"], h)][2] += 1
    hourly_rows = [{"location_id": k[0], "hour": k[1], "orders": v[0], "gross_sales": r2(v[1]), "days": v[2]}
                   for k, v in sorted(hourly.items())]
    item_rows = [{"date": k[0], "item_id": k[1], "qty": v[0], "revenue": r2(v[1]), "cogs": r2(v[2])}
                 for k, v in sorted(item_day.items())]
    return days, hourly_rows, item_rows, cost_by_item


def monthly_pnl(days, fixed, catering):
    months = sorted({d["date"][:7] for d in days})
    rows = []
    for ym in months:
        ds = [d for d in days if d["date"].startswith(ym) and d["trading"]]
        cat = [c for c in catering if c["date"].startswith(ym)]
        fx = sum(f["amount"] for f in fixed if f["month"] == ym)
        gross = sum(d["gross_sales"] for d in ds)
        cat_rev = sum(c["revenue"] for c in cat)
        cogs = sum(d["cogs"] for d in ds) + sum(c["food_cost"] for c in cat)
        labour = sum(d["labour"] for d in ds) + sum(c["staff_cost"] for c in cat)
        fees = sum(d["processing_fees"] + d["location_fee"] for d in ds)
        tips = sum(d["tips"] for d in ds)
        rows.append({"month": ym, "trading_days": len(ds), "orders": sum(d["orders"] for d in ds),
                     "truck_sales": r2(gross), "catering_sales": r2(cat_rev), "total_sales": r2(gross + cat_rev),
                     "tips_collected": r2(tips), "cogs": r2(cogs), "labour": r2(labour), "fees": r2(fees),
                     "fixed_costs": r2(fx), "operating_profit": r2(gross + cat_rev - cogs - labour - fees - fx),
                     "food_cost_pct": r2(cogs / (gross + cat_rev)) if gross else 0,
                     "labour_pct": r2(labour / (gross + cat_rev)) if gross else 0})
    return rows


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

HEAD = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="1F1F1F")
WARN_FILL = PatternFill("solid", fgColor="FFF2CC")


def sheet(wb, title, rows, headers=None, widths=None, money=()):
    ws = wb.create_sheet(title)
    if not rows:
        ws.append(["(empty)"])
        return ws
    headers = headers or list(rows[0].keys())
    ws.append(headers)
    for c in ws[1]:
        c.font, c.fill = HEAD, HEAD_FILL
    for r in rows:
        ws.append([r.get(h) for h in headers])
    ws.freeze_panes = "A2"
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(h, max(12, min(34, len(str(h)) + 4)))
        if h in money:
            for cell in ws.iter_cols(min_col=i, max_col=i, min_row=2):
                for c in cell:
                    c.number_format = '"$"#,##0.00'
    return ws


def write_xlsx(data):
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    intro = [
        ["TRUCKBOARD FAKE DATASET"],
        ["Everything in this workbook is invented. Truck names are made up. Places are real Milwaukee locations but no number here is a measurement of anything."],
        ["Generated by food-truck-app/data/generate.py on " + date.today().isoformat() + ". Change the assumptions in that script and rerun; do not edit numbers here by hand."],
        [],
        ["Tab", "What it is", "Replaces with real data from"],
        ["Assumptions", "Every driver, with its source label", "n/a"],
        ["Trucks", "Hero truck plus 12 made-up rivals", "Eventini vendor list"],
        ["Locations", "Real Milwaukee spots; fees and traffic are invented", "Eventini event/venue bookings"],
        ["Standard_Items", "Like-for-like buckets for price comparison", "n/a (fixed list)"],
        ["Menu", "Hero menu, price, ingredient cost, margin", "Eventini POS catalogue"],
        ["Recipes", "Ingredients per item, drives Menu costs", "owner entry"],
        ["Schedule", "One row per day: trading or not, where, hours, staff", "Eventini bookings"],
        ["Orders", "One row per order, like a POS export", "Eventini POS transactions"],
        ["Order_Items", "One row per item sold", "Eventini POS line items"],
        ["Shifts", "Who worked, hours, wage", "owner entry / payroll"],
        ["Fixed_Costs", "Monthly overheads", "owner entry"],
        ["Catering", "Private bookings", "Eventini bookings"],
        ["Weather", "Daily Milwaukee weather, invented", "Open-Meteo (free)"],
        ["Events", "Games, festivals, markets with assumed dates", "Eventini event calendar"],
        ["Market_Prices", "Rival prices per standard item", "Eventini POS catalogues (pooled, anonymised)"],
        ["Benchmarks", "Min/median/max per item and hero vs median; industry KPIs", "computed"],
        ["Daily_Summary", "Per trading day: sales, tips, fees, COGS, labour, net per hour", "computed"],
        ["Monthly_PnL", "Month by month P&L", "computed"],
        [],
        ["PLANTED STORIES (so the dashboard has something to find)"],
    ] + [[s] for s in PLANTED_STORIES]
    for r in intro:
        ws.append(r)
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"].fill = WARN_FILL
    for c in ws[5]:
        c.font = Font(bold=True)
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 70
    ws.column_dimensions["C"].width = 48

    sheet(wb, "Assumptions", [{"assumption": a, "value": v, "source": s, "note": n} for a, v, s, n in ASSUMPTIONS],
          widths={"value": 60, "note": 60})
    trucks = [dict(truck_id=HERO["truck_id"], name=HERO["name"], concept=HERO["concept"], price_tier=HERO["price_tier"],
                   home_neighbourhood=HERO["home_neighbourhood"], years_trading=HERO["years_trading"],
                   instagram_followers=HERO["instagram_followers"], is_hero=True)]
    trucks += [dict(truck_id=r[0], name=r[1], concept=r[2], price_tier=r[3], home_neighbourhood=r[4],
                    years_trading=r[5], instagram_followers=r[6], is_hero=False) for r in RIVALS]
    sheet(wb, "Trucks", trucks)
    sheet(wb, "Locations", [dict(location_id=l[0], name=l[1], type=l[2], neighbourhood=l[3], lat=l[4], lon=l[5],
                                 flat_fee=l[6], pct_fee=l[7], base_orders_per_hour=l[8],
                                 days=",".join(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d] for d in sorted(l[9])), open_hour=l[10][0],
                                 close_hour=l[10][1], season=l[11]) for l in LOCATIONS], widths={"name": 36})
    sheet(wb, "Standard_Items", [dict(standard_item=s[0], label=s[1], assumed_market_median=s[2]) for s in STANDARD_ITEMS],
          widths={"label": 34})
    menu_rows = []
    for m in MENU:
        c = data["cost_by_item"][m[0]]
        menu_rows.append(dict(item_id=m[0], name=m[1], category=m[2], standard_item=m[3], price=m[4],
                              ingredient_cost=c, gross_margin=r2(m[4] - c), food_cost_pct=r2(c / m[4])))
    sheet(wb, "Menu", menu_rows, money=("price", "ingredient_cost", "gross_margin"))
    recipe_rows = []
    for m in MENU:
        for k, q in m[6].items():
            nm, unit, cost, shelf = INGREDIENTS[k]
            recipe_rows.append(dict(item_id=m[0], item=m[1], ingredient=nm, unit=unit, qty=q, unit_cost=cost, cost=r2(q * cost), shelf_life_days=shelf))
    sheet(wb, "Recipes", recipe_rows, money=("unit_cost", "cost"))
    sheet(wb, "Schedule", data["schedule"])
    sheet(wb, "Orders", data["orders"], money=("subtotal", "discount", "tax", "tip", "total", "processing_fee"))
    sheet(wb, "Order_Items", data["lines"], money=("unit_price", "line_total"))
    sheet(wb, "Shifts", data["shifts"], money=("wage", "cost"))
    sheet(wb, "Fixed_Costs", data["fixed"], money=("amount",))
    sheet(wb, "Catering", data["catering"], money=("price_per_head", "revenue", "food_cost", "staff_cost"))
    sheet(wb, "Weather", data["weather"])
    sheet(wb, "Events", data["events"])
    sheet(wb, "Market_Prices", data["market"], money=("price",))
    bm = sheet(wb, "Benchmarks", data["benchmarks"], money=("min", "p25", "median", "p75", "max", "hero_price"))
    bm.append([])
    bm.append(["Industry KPIs", "value", "source", "note"])
    for c in bm[bm.max_row]:
        c.font = Font(bold=True)
    for k in INDUSTRY_KPIS:
        bm.append(list(k))
    sheet(wb, "Daily_Summary", data["days"],
          money=("gross_sales", "tips", "tax_collected", "processing_fees", "location_fee", "cogs", "labour",
                 "net_after_fees", "contribution", "gross_per_hour", "net_per_hour", "avg_order"))
    sheet(wb, "Monthly_PnL", data["pnl"],
          money=("truck_sales", "catering_sales", "total_sales", "tips_collected", "cogs", "labour", "fees",
                 "fixed_costs", "operating_profit"))
    wb.save(XLSX_OUT)


# ---------------------------------------------------------------------------
# JSON for the app
# ---------------------------------------------------------------------------

def write_json(data):
    out = {
        "meta": {"generated": date.today().isoformat(), "start": START.isoformat(), "end": END.isoformat(),
                 "fake": True, "sales_tax": SALES_TAX, "planted_stories": PLANTED_STORIES,
                 "opening_cash": 6500, "tax_remit_day": 20},
        "truck": HERO,
        "locations": [dict(id=l[0], name=l[1], type=l[2], neighbourhood=l[3], lat=l[4], lon=l[5],
                           flatFee=l[6], pctFee=l[7]) for l in LOCATIONS],
        "menu": [dict(id=m[0], name=m[1], category=m[2], standardItem=m[3], price=m[4],
                      cost=data["cost_by_item"][m[0]], keyIngredient=key_ingredient(m[6])[0],
                      keyIngredientQty=key_ingredient(m[6])[1], keyIngredientUnit=INGREDIENTS[key_ingredient(m[6])[0]][1],
                      shelfLifeDays=INGREDIENTS[key_ingredient(m[6])[0]][3]) for m in MENU],
        "standardItems": [dict(id=s[0], label=s[1]) for s in STANDARD_ITEMS],
        "rivals": [dict(id=r[0], name=r[1], concept=r[2], tier=r[3], neighbourhood=r[4]) for r in RIVALS],
        "marketPrices": [dict(truckId=m["truck_id"], item=m["standard_item"], price=m["price"],
                              seen=m["date_seen"], source=m["source"]) for m in data["market"]],
        "benchmarks": data["benchmarks"],
        "days": data["days"],
        "hourly": data["hourly"],
        "itemDays": data["item_days"],
        "events": data["events"],
        "fixedCosts": data["fixed"],
        "catering": data["catering"],
        "monthly": data["pnl"],
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(out, separators=(",", ":")))


# ---------------------------------------------------------------------------

def main():
    weather = make_weather()
    events = make_events()
    schedule = make_schedule(events)
    orders, lines = make_orders(schedule, weather, events)
    shifts = make_shifts(schedule)
    catering = make_catering(schedule)
    fixed = make_fixed_costs(orders)
    market = make_market()
    benchmarks = make_benchmarks(market)
    days, hourly, item_days, cost_by_item = aggregate(schedule, orders, lines, shifts, weather, events, fixed, catering)
    pnl = monthly_pnl(days, fixed, catering)

    data = dict(weather=weather, events=events, schedule=schedule, orders=orders, lines=lines, shifts=shifts,
                catering=catering, fixed=fixed, market=market, benchmarks=benchmarks, days=days, hourly=hourly,
                item_days=item_days, cost_by_item=cost_by_item, pnl=pnl)
    write_xlsx(data)
    write_json(data)

    # Sanity print
    gross = sum(p["truck_sales"] for p in pnl)
    cat = sum(p["catering_sales"] for p in pnl)
    cogs = sum(p["cogs"] for p in pnl)
    lab = sum(p["labour"] for p in pnl)
    tdays = sum(1 for s in schedule if s["trading"])
    print(f"trading days {tdays}  orders {len(orders)}  lines {len(lines)}")
    print(f"truck sales ${gross:,.0f}  catering ${cat:,.0f}  avg order ${gross/len(orders):.2f}")
    print(f"food cost {cogs/(gross+cat):.1%}  labour {lab/(gross+cat):.1%}  op profit ${sum(p['operating_profit'] for p in pnl):,.0f}")
    print(f"tips ${sum(p['tips_collected'] for p in pnl):,.0f}")
    print(f"xlsx -> {XLSX_OUT}\njson -> {JSON_OUT} ({JSON_OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
