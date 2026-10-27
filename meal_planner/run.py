import json
import logging
import os
from pathlib import Path

from waitress import serve
from app import create_app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    app = create_app()
    options = Path("/data/options.json")
    if options.is_file():
        # Supervisor options provide first-run defaults; the UI owns them afterward.
        settings_file = Path(os.environ.get("DATA_DIR", "/data")) / ".options_applied"
        if not settings_file.exists():
            from app import valid_settings
            raw = json.loads(options.read_text())
            def initialise(s):
                s["settings"] = valid_settings({**s["settings"],
                    "household": raw.get("household", 2),
                    "budget": round(raw.get("weekly_budget", 120) * 100),
                    "shop": raw.get("shop", "Coles")})
            app.store.update(initialise)
            settings_file.touch()
    port = int(os.environ.get("PORT", "8099"))
    print(f"Mealroom is listening on port {port}", flush=True)
    serve(app, host=os.environ.get("HOST", "0.0.0.0"), port=port, threads=6,
          max_request_body_size=5 * 1024 * 1024, clear_untrusted_proxy_headers=True)
