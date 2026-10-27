# Validation · 27 October 2026

## Passed

- 16 Python behaviour tests: full-week budget limits, dietary/allergen/time
  constraints, locks, impossible-plan errors, shopping aggregation and scaling,
  persistent state across server recreation, recipe edits, favourites and notes,
  shopping progress, pantry and extra grocery export, valid backup restore,
  atomic rejection of corrupt backups, malformed prices, CSRF requirements and
  Home Assistant Ingress peer restrictions.
- Tests also pass with SQLite resource warnings treated as errors.
- JavaScript syntax (`node --check`) and entrypoint shell syntax (`sh -n`).
- YAML metadata and packaging checks: both architecture declarations, no host
  ports or privileged access in HA config, Ingress enabled, local assets present
  and valid SVG XML, relative frontend requests.
- Runtime dependency consistency (`pip check`).
- All pinned production dependencies resolve as binary wheels for Python 3.13
  on Alpine/musllinux **aarch64** and **x86_64**.
- Source archive CRC verification and explicit exclusion of data, virtual
  environments, Git internals and the raw Mise investigation.

## Browser verification

The local app was run with Waitress, using a dedicated development data folder.
The in-app browser successfully:

1. Opened the initial kitchen.
2. Generated seven dinners within the displayed dinner budget.
3. Opened the combined shopping list and persisted a checkbox change.
4. Searched recipes by ingredient.
5. Opened a recipe, displayed scaled ingredients and entered cooking mode.
6. Advanced between cooking steps.

Screenshots are in `mealroom-preview.png` and `mealroom-dinners.png`.
The visible preview was approximately 671 pixels wide, exercising the responsive
bottom navigation and two-column cards. Other viewport sizes were not browser
verified during this pass.

## Docker verified in GitHub Actions

[The initial verification run](https://github.com/duarte-hub/mealroom-home-assistant/actions/runs/40450568206)
completed successfully for source commit
`750fb772ed8d16fe94154edd02aefc75a7bd6953`.

- All 16 tests passed on Linux with Python 3.13.
- The production amd64 Docker image built successfully.
- Its entrypoint started the application with a persistent Docker volume.
- HTTP health and application-state requests succeeded, returning 24 recipes.
- The application process ran as UID 1000 and created its SQLite database in
  the persistent volume.

## Not yet verified

- Installation or execution inside the user's Home Assistant OS instance.
- Actual aarch64 runtime behaviour, despite dependency-wheel availability.

A Home Assistant installation is still the final Supervisor/Ingress integration
check. Docker is not installed on the development Mac; the container build and
smoke test ran on GitHub's Linux runner.
