# Mise investigation and Mealroom implementation map

Investigated 27 October 2026. Selected artifact:
`/Applications/Mise.app/Wrapper/Mise.app`, version **1.1.24**, build **222**,
bundle identifier `com.gregorytaylor.shopping`.

## Evidence boundaries

REA was used through its 6.8.0 CLI while the active chat lacked connected REA
tools. Complete records remain locally in `mise-analysis/evidence`, excluded
from Git and the release archive. No installed application files were modified.

| Evidence | File | Finding |
| --- | --- | --- |
| `ev_9f49836e1b1eb1c896a7b6e71b1fc101a1e51082ec81f13d60f13a5a0d8707f7` | `plist.json` | Version, bundle ID, iOS platform and URL schemes |
| `ev_e7d26f78ef94c0a7510fb76ea0678b62d3f923571562a94e141087681354178d` | `macho.json` | ARM64, iOS load metadata, native dependencies and encryption declaration |
| `ev_2412b83b77736323e62da941184e29a47fc8968703e6b98dddd42b4c5ce2db4f` | `signature.json` | Apple signing declarations, Apple sign-in and production APNs entitlements |
| `ev_6bce9ff6eb6ad9e8ff499629012395ece12d8083523ca35622883321af02ec36` | `artifact.json` | Bounded static app/package inspection, not observed execution |

The native executable SHA-256 is
`e191c5664944d9a7e0bc73d2675ec92e3e2a574a67ca76aef47d8dc1e0255955`.
Its load commands declare `cryptid=1`; native code decompilation was not
attempted. REA's source analyzer rejected the `.jsbundle` selection because it
was not an eligible JavaScript source file. This was retained as an explicit
limitation, not reported as successful JavaScript decompilation.

A supplemental, read-only Python string-table parser inspected the Hermes
bytecode. It verified the file length, all selected string ranges and the
Hermes footer SHA-1. It is **not REA Evidence** and does not recover original
JavaScript or establish control flow. Its output records each string's ID,
offset, encoding and byte length. The bundle SHA-256 is
`63723182e96580d78f53d836479d72d5301c9b861bbdf3d85768dd5b5bea5d57`.
It declares Hermes bytecode version 98, 18,178 functions and 40,053 strings.
The parser's string-table layout follows Meta's
[BytecodeFileFormat.h](https://github.com/facebook/hermes/blob/static_h/include/hermes/BCGen/HBC/BytecodeFileFormat.h)
Git blob `f2f8b1ea5ecbc74baaf66b13c71939ba3168cb78`; the layout is compatible
with the inspected v98 string table. No function bytecode was decoded.

## Observed and inferred app structure

**Observed in package metadata:** an iPhone/iPad app usable on Apple silicon,
ARM64 native executable, React and Hermes frameworks, Expo module frameworks,
GoogleSignIn, Singular and Superwall resource bundles. The app contains a
12,995,190-byte `main.jsbundle`, not a web/Electron ASAR. There are 940 image
files under its `assets` tree. Image counts do not establish a recipe count.

**Inferred from string-table names and literals:** screens for meal plans,
recipe detail, shopping lists, favourites, settings and onboarding. Onboarding
names include region, shop, budget, household size, dietary needs, allergens,
protein likes, dislikes, kitchen equipment and cooking days. Language
identifiers include English, Portuguese, Spanish, German, French, Dutch and
Swedish; runtime translation coverage was not verified.

Planner-related identifiers include `generateWeeklyMealPlan`, `buildGreedyPlan`,
`calculateRecipeScore`, `resolveWeeklyMealPlanFallback`, variety retry helpers,
protein/format repetition limits, recent-plan penalties and preferred-protein
bonuses. These support a hypothesis of constrained local recipe selection,
but do not establish scoring weights, execution order or the exact algorithm.

Shopping-related identifiers include `buildWeeklyShoppingList`,
`buildWeeklyShoppingListSections`, `scaleIngredientsForHousehold` and
ingredient normalisation/quantity formatting. Persisted-key literals reference
favourites, meal feedback, notes, ratings, shopping progress, current and
previous plans, recently viewed meals and household context.

Service literals and shipped SDK resources indicate Supabase authentication/
database calls, Superwall subscriptions, PostHog analytics and Singular
attribution. Candidate database names include `user_meal_plans`,
`user_preferences`, `user_saved_meals`, `user_recipe_notes`,
`user_recipe_ratings` and `user_meal_feedback`. Household RPC names include
`create_household`, `create_household_invite`, `join_household`,
`leave_household` and `get_household_context`. These are candidate interfaces
from shipped strings; schema, access policies and live behaviour remain unknown.

No backend endpoint was contacted, no personal app database was read, no
subscription checks were changed, and no runtime/UI observations were completed
before the user steered the task toward building a Docker app.

## Independent recreation

| Mise feature hypothesis | Mealroom implementation |
| --- | --- |
| Local constrained plan generation | Independently written budget-limited randomised planner |
| Dietary, ingredient and equipment preferences | Explicit metadata and ingredient-name filters |
| Recipe shopping lists | Decimal quantity aggregation, metric normalisation and household scaling |
| Saved recipes and feedback | Favourites, ratings, notes and cooked marker |
| Household/cloud sharing | One persistent local household, protected by Home Assistant Ingress |
| Subscription access | All implemented features available locally |
| Regional recipes and retailer cost data | 24 original editable starter recipes, estimated AUD costs |
| Native screens | Independently designed responsive web interface |

Mise's source code, compiled code, original recipes, imagery, brand and embedded
service configuration are not included in Mealroom. The exact original
algorithm, backend and runtime workflows were not recovered. This is a
functional recreation of the planning/recipe/shopping workflow, not a complete
or byte-for-byte clone.
