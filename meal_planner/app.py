import copy
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import secrets

from flask import Flask, abort, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from planner import eligible, empty_plan, generate, monday, normalise, price, shopping
from store import DEFAULT_SETTINGS, Store

CATEGORIES = ["Produce", "Meat & fish", "Chilled", "Pantry", "Frozen", "Other"]
ALLERGENS = ["gluten", "milk", "eggs", "fish", "shellfish", "peanuts", "nuts", "soy", "sesame"]
ARTS = ["tray", "curry", "pasta", "rice", "fish", "tacos", "salad", "soup"]
ID = re.compile(r"[a-zA-Z0-9_-]{1,100}\Z")


def text(value, name, maximum=200, optional=False):
    if not isinstance(value, str) or len(value.strip()) > maximum or (not optional and not value.strip()):
        raise ValueError(f"{name} must be text between {'0' if optional else '1'} and {maximum} characters.")
    return value.strip()


def number(value, name, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")
    if not low <= value <= high or (integer and int(value) != value):
        raise ValueError(f"{name} must be {'a whole number ' if integer else ''}between {low} and {high}.")
    return int(value) if integer else value


def choices(value, name, allowed, maximum=20):
    if not isinstance(value, list) or len(value) > maximum or any(v not in allowed for v in value):
        raise ValueError(f"Invalid {name}.")
    return list(dict.fromkeys(value))


def string_list(value, name, maximum=40):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"Invalid {name}.")
    return list(dict.fromkeys(text(v, name, 100) for v in value))


def valid_settings(raw):
    if not isinstance(raw, dict):
        raise ValueError("Preferences must be an object.")
    d = {**DEFAULT_SETTINGS, **raw}
    if d["diet"] not in ["omnivore", "vegetarian", "vegan", "pescatarian"]:
        raise ValueError("Choose a valid dietary preference.")
    if d["currency"] not in ["AUD", "NZD", "USD", "GBP", "EUR"]:
        raise ValueError("Unsupported currency.")
    return {"name": text(d["name"], "Kitchen name", 60),
            "household": number(d["household"], "Household size", 1, 12, True),
            "budget": number(d["budget"], "Weekly dinner budget in cents", 100, 1000000, True),
            "currency": d["currency"], "shop": text(d["shop"], "Shop", 60),
            "diet": d["diet"], "max_minutes": number(d["max_minutes"], "Cooking time", 10, 240, True),
            "allergens": choices(d["allergens"], "allergens", ALLERGENS),
            "equipment": choices(d["equipment"], "equipment", ["hob", "oven", "air fryer", "microwave"]),
            "dislikes": string_list(d["dislikes"], "ingredients to avoid")}


def ingredient(raw):
    if not isinstance(raw, dict):
        raise ValueError("Each ingredient must be an object.")
    if raw.get("category") not in CATEGORIES:
        raise ValueError("Choose a valid shopping category.")
    return {"name": text(raw.get("name"), "Ingredient", 100),
            "quantity": number(raw.get("quantity"), "Quantity", 0.001, 100000),
            "unit": text(raw.get("unit", "each"), "Unit", 20), "category": raw["category"]}


def valid_recipe(raw, recipe_id=None):
    if not isinstance(raw, dict):
        raise ValueError("Recipe must be an object.")
    recipe_id = recipe_id or raw.get("id") or secrets.token_hex(8)
    if not isinstance(recipe_id, str) or not ID.fullmatch(recipe_id):
        raise ValueError("Invalid recipe ID.")
    items = raw.get("ingredients")
    if not isinstance(items, list) or not 1 <= len(items) <= 80:
        raise ValueError("Add between 1 and 80 ingredients.")
    if not isinstance(raw.get("steps"), list) or not 1 <= len(raw["steps"]) <= 50:
        raise ValueError("Add between 1 and 50 cooking steps.")
    steps = [text(s, "Step", 3000) for s in raw["steps"]]
    if raw.get("protein_type") not in ["chicken", "beef", "pork", "fish", "vegetarian", "vegan", "other"]:
        raise ValueError("Choose a valid main protein.")
    if raw.get("art", "salad") not in ARTS:
        raise ValueError("Invalid recipe illustration.")
    return {"id": recipe_id, "title": text(raw.get("title"), "Recipe title", 120),
            "description": text(raw.get("description", ""), "Description", 500, True),
            "servings": number(raw.get("servings"), "Base servings", 1, 12, True),
            "minutes": number(raw.get("minutes"), "Cooking time", 1, 600, True),
            "cost": number(raw.get("cost"), "Cost per serving in cents", 1, 100000, True),
            "protein_type": raw["protein_type"], "art": raw.get("art", "salad"),
            "tags": string_list(raw.get("tags", []), "tags", 8),
            "allergens": choices(raw.get("allergens", []), "allergens", ALLERGENS),
            "equipment": choices(raw.get("equipment", []), "equipment", ["hob", "oven", "air fryer", "microwave"]),
            "ingredients": [ingredient(i) for i in items], "steps": steps}


def valid_backup(raw):
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("This is not a Mealroom version 1 backup.")
    recipes = raw.get("recipes")
    if not isinstance(recipes, list) or not 1 <= len(recipes) <= 2000:
        raise ValueError("Backup must contain 1–2000 recipes.")
    clean = {"schema_version": 1, "settings": valid_settings(raw.get("settings")),
             "recipes": [valid_recipe(r) for r in recipes], "plans": {}, "ratings": {},
             "checked": {}, "extras": {}, "favourites": [], "pantry": []}
    ids = {r["id"] for r in clean["recipes"]}
    if len(ids) != len(recipes):
        raise ValueError("Backup contains duplicate recipe IDs.")
    clean["favourites"] = string_list(raw.get("favourites", []), "favourites", 2000)
    if not set(clean["favourites"]).issubset(ids):
        raise ValueError("Favourite recipe is missing from backup.")
    plans = raw.get("plans", {})
    if not isinstance(plans, dict) or len(plans) > 2000:
        raise ValueError("Invalid plan history.")
    for week, plan in plans.items():
        if monday(week) != week or not isinstance(plan, dict) or not isinstance(plan.get("days"), list) or len(plan["days"]) != 7:
            raise ValueError("Invalid week in backup.")
        target = empty_plan(week)
        for slot, day in zip(target["days"], plan["days"]):
            if (not isinstance(day, dict) or day.get("date") != slot["date"]
                    or not isinstance(day.get("recipe_id"), (str, type(None)))
                    or day.get("recipe_id") not in ids | {None}
                    or not isinstance(day.get("locked"), bool)):
                raise ValueError("Invalid meal in backup.")
            slot.update(recipe_id=day["recipe_id"], locked=day["locked"])
        clean["plans"][week] = target
    ratings = raw.get("ratings", {})
    if not isinstance(ratings, dict):
        raise ValueError("Invalid recipe notes.")
    for key, value in ratings.items():
        if key not in ids or not isinstance(value, dict) or not isinstance(value.get("cooked", False), bool):
            raise ValueError("Invalid recipe notes.")
        clean["ratings"][key] = {"rating": number(value.get("rating", 0), "Rating", 0, 5, True),
                                 "note": text(value.get("note", ""), "Note", 3000, True),
                                 "cooked": value.get("cooked", False)}
    clean["pantry"] = [normalise(v) for v in string_list(raw.get("pantry", []), "pantry", 2000)]
    for field in ["checked", "extras"]:
        source = raw.get(field, {})
        if not isinstance(source, dict) or len(source) > 2000:
            raise ValueError(f"Invalid {field} in backup.")
        for week, value in source.items():
            if monday(week) != week:
                raise ValueError("Invalid shopping-list week.")
            if field == "checked":
                if not isinstance(value, dict) or len(value) > 10000 or any(not re.fullmatch(r"[0-9a-f]{20}", key) or not isinstance(checked, bool) for key, checked in value.items()):
                    raise ValueError("Invalid shopping progress.")
                clean[field][week] = value
            else:
                if not isinstance(value, list) or len(value) > 500:
                    raise ValueError("Invalid extra groceries.")
                clean[field][week] = []
                for item in value:
                    row = ingredient(item)
                    row["id"] = text(item.get("id"), "Grocery ID", 100)
                    clean[field][week].append(row)
    return clean


def create_app(data_dir=None, ingress_only=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=5 * 1024 * 1024)
    app.store = Store(Path(data_dir or os.environ.get("DATA_DIR", "./data")) / "mealroom.sqlite3")
    app.csrf_token = secrets.token_urlsafe(32)
    ingress = ingress_only if ingress_only is not None else os.environ.get("INGRESS_ONLY", "false").lower() == "true"

    @app.before_request
    def guard():
        if request.path == "/healthz" and request.remote_addr in ("127.0.0.1", "::1"):
            return None
        if ingress and request.remote_addr != "172.30.32.2":
            abort(403, "Open Mealroom through Home Assistant Ingress.")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), app.csrf_token):
                abort(403, "Refresh the page before saving changes.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
        if request.path.startswith("/api/") or request.path == "/":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    def body():
        value = request.get_json()
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object.")
        return value

    def week_arg(raw=None):
        value = (raw or request.args).get("week")
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
            raise ValueError("Choose a valid week.")
        return monday(value)

    def recipe_by_id(state, recipe_id):
        result = next((r for r in state["recipes"] if r["id"] == recipe_id), None)
        if result is None:
            abort(404, "Recipe not found.")
        return result

    @app.get("/")
    def index():
        return render_template("index.html", csrf=app.csrf_token)

    @app.get("/healthz")
    def health():
        return jsonify(status="ok", version="0.1.0")

    @app.get("/api/state")
    def get_state():
        state = app.store.read()
        week = week_arg()
        plan = state["plans"].get(week, empty_plan(week))
        ids = {r["id"]: r for r in state["recipes"]}
        total = sum(price(ids[d["recipe_id"]], state["settings"]["household"])
                    for d in plan["days"] if d.get("recipe_id") in ids)
        return jsonify(**state, week=week, plan=plan, shopping=shopping(state, week),
                       total=total, eligible_ids=[r["id"] for r in state["recipes"] if eligible(r, state["settings"])],
                       categories=CATEGORIES, allergens_available=ALLERGENS)

    @app.put("/api/settings")
    def settings():
        clean = valid_settings(body())
        def update(s):
            if s["settings"]["household"] != clean["household"]:
                s["checked"] = {}
            s["settings"] = clean
        app.store.update(update)
        return jsonify(ok=True)

    @app.post("/api/plan/generate")
    def generate_plan():
        raw = body()
        week = week_arg(raw)
        def update(s):
            plan = generate(s, week)
            plan["generated_at"] = datetime.now(timezone.utc).isoformat()
            s["plans"][week] = plan
            # Progress applies to the previous exact ingredient totals; start fresh.
            s["checked"][week] = {}
            return plan
        return jsonify(plan=app.store.update(update))

    @app.patch("/api/plan/day")
    def edit_day():
        raw = body()
        week = week_arg(raw)
        day_index = number(raw.get("day"), "Day", 0, 6, True)
        def change(s):
            plan = s["plans"].setdefault(week, empty_plan(week))
            day = plan["days"][day_index]
            if "recipe_id" in raw:
                recipe_id = raw["recipe_id"]
                if recipe_id is not None:
                    recipe_by_id(s, recipe_id)
                day["recipe_id"] = recipe_id
                day["locked"] = False
                s["checked"][week] = {}
                plan["warnings"] = []
            if "locked" in raw:
                if not isinstance(raw["locked"], bool):
                    raise ValueError("Lock must be true or false.")
                day["locked"] = raw["locked"] and bool(day["recipe_id"])
        app.store.update(change)
        return jsonify(ok=True)

    @app.post("/api/plan/swap")
    def swap_day():
        raw = body()
        week = week_arg(raw)
        i = number(raw.get("day"), "Day", 0, 6, True)
        def change(s):
            plan = s["plans"].setdefault(week, empty_plan(week))
            if plan["days"][i]["locked"]:
                raise ValueError("Unlock this dinner before swapping it.")
            ids = {r["id"]: r for r in s["recipes"]}
            other = [d["recipe_id"] for j, d in enumerate(plan["days"]) if j != i and d["recipe_id"]]
            spent = sum(price(ids[r], s["settings"]["household"]) for r in other)
            candidates = [r for r in s["recipes"] if eligible(r, s["settings"])
                          and r["id"] != plan["days"][i]["recipe_id"]
                          and spent + price(r, s["settings"]["household"]) <= s["settings"]["budget"]]
            if not candidates:
                raise ValueError("No other dinner fits the remaining budget and preferences.")
            import random
            fresh = [r for r in candidates if r["id"] not in other]
            plan["days"][i]["recipe_id"] = random.choice(fresh or candidates)["id"]
            plan["warnings"] = []
            s["checked"][week] = {}
        app.store.update(change)
        return jsonify(ok=True)

    @app.post("/api/recipes")
    def add_recipe():
        recipe = valid_recipe(body(), secrets.token_hex(8))
        def update(s):
            if len(s["recipes"]) >= 2000:
                raise ValueError("Recipe limit reached (2000).")
            s["recipes"].append(recipe)
        app.store.update(update)
        return jsonify(recipe=recipe), 201

    @app.put("/api/recipes/<recipe_id>")
    def edit_recipe(recipe_id):
        clean = valid_recipe(body(), recipe_id)
        def update(s):
            old = recipe_by_id(s, recipe_id)
            s["recipes"][s["recipes"].index(old)] = clean
            s["checked"] = {}
        app.store.update(update)
        return jsonify(recipe=clean)

    @app.delete("/api/recipes/<recipe_id>")
    def delete_recipe(recipe_id):
        def update(s):
            old = recipe_by_id(s, recipe_id)
            s["recipes"].remove(old)
            s["favourites"] = [r for r in s["favourites"] if r != recipe_id]
            s["ratings"].pop(recipe_id, None)
            for plan in s["plans"].values():
                for day in plan["days"]:
                    if day["recipe_id"] == recipe_id:
                        day.update(recipe_id=None, locked=False)
            s["checked"] = {}
        app.store.update(update)
        return jsonify(ok=True)

    @app.patch("/api/recipes/<recipe_id>/personal")
    def personal(recipe_id):
        raw = body()
        def update(s):
            recipe_by_id(s, recipe_id)
            if "favourite" in raw:
                if not isinstance(raw["favourite"], bool):
                    raise ValueError("Favourite must be true or false.")
                s["favourites"] = [r for r in s["favourites"] if r != recipe_id]
                if raw["favourite"]:
                    s["favourites"].append(recipe_id)
            rating = s["ratings"].setdefault(recipe_id, {"rating": 0, "note": "", "cooked": False})
            if "rating" in raw:
                rating["rating"] = number(raw["rating"], "Rating", 0, 5, True)
            if "note" in raw:
                rating["note"] = text(raw["note"], "Note", 3000, True)
            if "cooked" in raw:
                if not isinstance(raw["cooked"], bool):
                    raise ValueError("Cooked must be true or false.")
                rating["cooked"] = raw["cooked"]
        app.store.update(update)
        return jsonify(ok=True)

    @app.patch("/api/shopping/check")
    def check_item():
        raw = body()
        week = week_arg(raw)
        if not isinstance(raw.get("checked"), bool):
            raise ValueError("Checked must be true or false.")
        def update(s):
            if raw.get("key") not in {r["key"] for r in shopping(s, week)}:
                raise ValueError("Shopping item no longer exists. Refresh the list.")
            s["checked"].setdefault(week, {})[raw["key"]] = raw["checked"]
        app.store.update(update)
        return jsonify(ok=True)

    @app.post("/api/shopping/extras")
    def extra_item():
        raw = body()
        week = week_arg(raw)
        item = ingredient(raw)
        item["id"] = secrets.token_hex(8)
        def update(s):
            extras = s["extras"].setdefault(week, [])
            if len(extras) >= 500:
                raise ValueError("This list has reached 500 extra groceries.")
            extras.append(item)
            s["checked"][week] = {}
        app.store.update(update)
        return jsonify(ok=True), 201

    @app.delete("/api/shopping/extras/<item_id>")
    def delete_extra(item_id):
        week = week_arg()
        def update(s):
            s["extras"][week] = [r for r in s["extras"].get(week, []) if r["id"] != item_id]
            s["checked"][week] = {}
        app.store.update(update)
        return jsonify(ok=True)

    @app.put("/api/pantry")
    def pantry():
        values = [normalise(v) for v in string_list(body().get("items"), "pantry items", 2000)]
        app.store.update(lambda s: s.update(pantry=values))
        return jsonify(ok=True)

    @app.get("/api/backup")
    def backup():
        response = jsonify(app.store.read())
        response.headers["Content-Disposition"] = 'attachment; filename="mealroom-backup.json"'
        return response

    @app.post("/api/restore")
    def restore():
        clean = valid_backup(body())
        # Validation completes before the transaction touches the current household.
        def update(s):
            s.clear()
            s.update(clean)
        app.store.update(update)
        return jsonify(ok=True)

    return app
