"""One household, persisted transactionally in SQLite. No cloud services."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3


DEFAULT_SETTINGS = {
    "name": "Our kitchen", "household": 2, "budget": 12000,
    "currency": "AUD", "shop": "Coles", "diet": "omnivore",
    "max_minutes": 45, "allergens": [], "dislikes": [],
    "equipment": ["hob", "oven"],
}


def initial_state():
    recipes = json.loads(Path(__file__).with_name("recipes.json").read_text())
    return {"schema_version": 1, "settings": copy.deepcopy(DEFAULT_SETTINGS),
            "recipes": recipes, "favourites": [], "ratings": {}, "plans": {},
            "checked": {}, "extras": {}, "pantry": []}


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS household (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO household VALUES (1, ?)", (json.dumps(initial_state()),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def read(self):
        with self.connect() as db:
            return json.loads(db.execute("SELECT data FROM household WHERE id=1").fetchone()[0])

    def update(self, change):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = json.loads(db.execute("SELECT data FROM household WHERE id=1").fetchone()[0])
            result = change(state)
            db.execute("UPDATE household SET data=? WHERE id=1", (json.dumps(state, allow_nan=False),))
            return result
