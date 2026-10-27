"""Independent constraint-based dinner planner and ingredient aggregation."""
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import random
import re
import unicodedata


def normalise(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def monday(value=None):
    day = date.fromisoformat(value) if value else date.today()
    return (day - timedelta(days=day.weekday())).isoformat()


def empty_plan(week):
    start = date.fromisoformat(week)
    return {"days": [{"date": (start + timedelta(days=i)).isoformat(),
                      "recipe_id": None, "locked": False} for i in range(7)], "warnings": []}


def eligible(recipe, settings):
    diet = settings["diet"]
    if diet == "vegetarian" and recipe["protein_type"] not in ("vegetarian", "vegan"):
        return False
    if diet == "vegan" and recipe["protein_type"] != "vegan":
        return False
    if diet == "pescatarian" and recipe["protein_type"] not in ("fish", "vegetarian", "vegan"):
        return False
    if recipe["minutes"] > settings["max_minutes"]:
        return False
    if set(recipe["allergens"]) & set(settings["allergens"]):
        return False
    if not set(recipe["equipment"]).issubset(settings["equipment"]):
        return False
    ingredients = [normalise(i["name"]) for i in recipe["ingredients"]]
    return not any(normalise(term) in ingredient for term in settings["dislikes"] for ingredient in ingredients)


def price(recipe, household):
    # Costs are integer cents per serving, so a saved plan cannot gain float drift.
    return recipe["cost"] * household


def generate(state, week, seed=None):
    settings = state["settings"]
    existing = state["plans"].get(week, empty_plan(week))
    by_id = {r["id"]: r for r in state["recipes"]}
    pool = [r for r in state["recipes"] if eligible(r, settings)]
    if not pool:
        raise ValueError("No recipes match these preferences. Add recipes or relax the time, equipment, dietary, or ingredient filters.")
    rng = random.Random(seed)
    locked = {i: by_id[d["recipe_id"]] for i, d in enumerate(existing["days"])
              if d.get("locked") and d.get("recipe_id") in by_id}
    locked_cost = sum(price(r, settings["household"]) for r in locked.values())
    free_count = 7 - len(locked)
    if locked_cost + free_count * min(price(r, settings["household"]) for r in pool) > settings["budget"]:
        raise ValueError("This budget cannot cover seven dinners with your current filters and locked meals. Increase the budget, unlock meals, or add cheaper recipes.")
    history = {d["recipe_id"] for key, plan in state["plans"].items() if key < week
               for d in plan["days"] if d.get("recipe_id")}
    best = None
    for _ in range(160):
        selected = dict(locked)
        used = Counter(r["id"] for r in locked.values())
        proteins = Counter(r["protein_type"] for r in locked.values())
        spent = locked_cost
        score_total = 0
        free_slots = [i for i in range(7) if i not in locked]
        for slot_index, slot in enumerate(free_slots):
            remaining = len(free_slots) - slot_index - 1
            cheapest = min(price(r, settings["household"]) for r in pool)
            affordable = [r for r in pool if spent + price(r, settings["household"]) + remaining * cheapest <= settings["budget"]]
            if not affordable:
                break
            def score(r):
                rating = state["ratings"].get(r["id"], {}).get("rating", 0)
                return (rng.random() * 5 + (2 if r["id"] in state["favourites"] else 0)
                        + rating / 3 - used[r["id"]] * 24 - proteins[r["protein_type"]] * 0.7
                        - (2 if r["id"] in history else 0))
            scored = [(score(r), r) for r in affordable]
            value, recipe = max(scored, key=lambda item: item[0])
            selected[slot] = recipe
            used[recipe["id"]] += 1
            proteins[recipe["protein_type"]] += 1
            spent += price(recipe, settings["household"])
            score_total += value
        if len(selected) == 7 and (best is None or score_total > best[0]):
            best = score_total, selected
    if best is None:
        raise ValueError("A complete plan could not be found. Try increasing the budget.")
    plan = empty_plan(week)
    warnings = []
    for i, recipe in best[1].items():
        plan["days"][i].update(recipe_id=recipe["id"], locked=i in locked)
    if len({r["id"] for r in best[1].values()}) < 7:
        warnings.append("Some dinners repeat so the full week fits your budget and preferences.")
    if any(not eligible(r, settings) for r in locked.values()):
        warnings.append("Locked meals were kept, including any that no longer match your preferences.")
    plan["warnings"] = warnings
    return plan


def shopping(state, week):
    by_id = {r["id"]: r for r in state["recipes"]}
    groups = {}
    household = state["settings"]["household"]
    entries = []
    for day in state["plans"].get(week, empty_plan(week))["days"]:
        recipe = by_id.get(day.get("recipe_id"))
        if recipe:
            scale = Decimal(household) / Decimal(recipe["servings"])
            entries.extend((i, scale, recipe["title"], None) for i in recipe["ingredients"])
    entries.extend((item, Decimal(1), "Extra groceries", item["id"]) for item in state["extras"].get(week, []))
    for item, scale, title, extra_id in entries:
        name, unit = normalise(item["name"]), normalise(item["unit"])
        # Combine common metric units, but never guess mass from volume or count.
        multiplier = {"kg": Decimal(1000), "l": Decimal(1000)}.get(unit, Decimal(1))
        unit = {"kg": "g", "l": "ml"}.get(unit, unit)
        canonical = name + "|" + unit
        key = hashlib.sha256(canonical.encode()).hexdigest()[:20]
        if key not in groups:
            groups[key] = {"key": key, "name": item["name"], "unit": unit,
                           "category": item["category"], "quantity": Decimal(0),
                           "recipes": [], "extra_ids": [], "pantry": name in state["pantry"],
                           "checked": bool(state["checked"].get(week, {}).get(key))}
        row = groups[key]
        row["quantity"] += Decimal(str(item["quantity"])) * scale * multiplier
        if title not in row["recipes"]:
            row["recipes"].append(title)
        if extra_id:
            row["extra_ids"].append(extra_id)
    for row in groups.values():
        row["quantity"] = float(row["quantity"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return sorted(groups.values(), key=lambda r: (r["category"], normalise(r["name"])))
