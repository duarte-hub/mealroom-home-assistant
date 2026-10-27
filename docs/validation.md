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

## Not yet verified

- A real Docker build: Docker is not installed on the development Mac.
- Installation or execution inside the user's Home Assistant OS instance.
- Actual aarch64 runtime behaviour, despite dependency-wheel availability.
- The GitHub Actions workflow: prepared but not run until the source is published.

The included CI builds and smoke-tests the amd64 production image. A Home
Assistant installation is still the final integration check. Native tests do
not substitute for these container and Supervisor checks.
