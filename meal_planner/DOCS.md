# Mealroom

Start the app, choose **Open Web UI**, then use **Preferences** to set up your
kitchen. Enable **Show in sidebar** on the Home Assistant App page for quick access.

## Configuration

`household`, `weekly_budget` and `shop` are first-run defaults. Change preferences
inside Mealroom after the first start. Costs are editable dinner estimates; the
shop label is not a connection to a retailer. The default currency is AUD.

## Persistence

Recipes, meal plans, favourites, notes and shopping progress live in
`/data/mealroom.sqlite3`. App restarts and updates preserve this data. Home
Assistant app backups include the app data. A portable JSON export and restore
are available in Mealroom's **Preferences** page.

## Shared household

Home Assistant authenticates access through Ingress. Everyone with access to
Mealroom can edit the same kitchen. The app does not ask for or store a Home
Assistant token and does not request any access to devices or other apps.

## Troubleshooting

- **No matching recipes:** increase the cooking-time limit, select the equipment
  you have, check dietary exclusions, or add more suitable recipes.
- **Budget cannot cover the week:** unlock expensive dinners, add cheaper
  recipes, or raise the dinner budget. Manual selections can exceed it.
- **403 when opening directly:** use **Open Web UI** or the sidebar. Direct
  network requests are blocked in Home Assistant mode.
- **Shopping checks cleared:** plan or recipe changes, including serving-size
  changes, reset checkmarks to prevent stale quantities appearing bought.
- **Install build fails:** check the App logs and Internet access to Docker Hub,
  the Alpine package repository and PyPI. The App builds on-device on amd64 or
  aarch64; its first build is slower than subsequent starts.

The running app needs no cloud account or Internet connection.
