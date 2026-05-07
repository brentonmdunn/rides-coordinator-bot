# Eval Harness: How It Works

This doc is the long-form companion to `README.md`. It walks through what
`evals/run_scenario.py` does step by step, shows complete worked examples
(including a flex scenario and a gold-dataset scenario), and documents every
CLI flag.

Run every command in this doc from `backend/`.

## Contents

- [1. What the harness does](#1-what-the-harness-does)
- [2. CLI flags](#2-cli-flags)
- [3. Scenario YAML reference](#3-scenario-yaml-reference)
- [4. Example A — basic two-driver run](#4-example-a--basic-two-driver-run)
- [5. Example B — Marshall flex pickups](#5-example-b--marshall-flex-pickups)
- [6. Example C — gold-dataset comparison](#6-example-c--gold-dataset-comparison)
- [7. Output section reference](#7-output-section-reference)
- [8. Troubleshooting](#8-troubleshooting)

---

## 1. What the harness does

```
  scenario.yaml
       │
       ▼
  parse passengers + drivers  ──►  build PassengersByLocation
       │                            (Marshall → alt_pickup_locations=[Geisel Loop])
       │
       ▼
  render prompt  (pickups + drivers + all-pairs distance matrix)
       │
       ▼              ──dry-run──►  stop here, print prompt, exit 0
       │
       ▼
  Gemini call  (LLMService.generate_ride_groups, with repair loop)
       │
       ▼
  validate + compute drive times + (optional) compare to gold
       │
       ▼
  pretty-print every section for manual inspection
```

Everything upstream of the Gemini call is deterministic. `--dry-run` exercises
exactly that deterministic path so you can iterate on scenarios and prompt
text without spending API quota.

---

## 2. CLI flags

```
uv run python -m evals.run_scenario SCENARIO [--dry-run] [--legacy-prompt]
```

| Flag | Purpose |
| --- | --- |
| `SCENARIO` (positional) | Path to a YAML scenario file. Required. |
| `--dry-run` | Build the `PassengersByLocation`, render the full prompt, print it, and exit before calling Gemini. No `GOOGLE_API_KEY` required. Use this when iterating on prompt wording, the `<pickups>` block, or the distance matrix. |
| `--legacy-prompt` | Use `GROUP_RIDES_PROMPT_LEGACY` instead of the current `GROUP_RIDES_PROMPT`. Useful for A/B comparisons against the pre-refactor baseline. |
| `-h` / `--help` | Argparse help. |

Exit codes:

- `0` — scenario ran to completion (even if validator found violations or
  the gold comparison failed — this is inspection, not CI).
- `1` — Gemini call raised (network, auth, etc.).
- `2` — scenario file is not a YAML mapping.

---

## 3. Scenario YAML reference

### Required fields

| Field | Type | Meaning |
| --- | --- | --- |
| `drivers` | list of ints | Seat capacity of each driver. The harness builds driver keys `Driver0`, `Driver1`, … in order. |
| `passengers` | list of mappings | Each has `name` and `living`. Optional `username` defaults to `name`. |

`living` is matched case-insensitively against `CampusLivingLocations`. Valid
values: `Sixth`, `Seventh`, `Marshall`, `ERC`, `Muir`, `Eighth`, `Revelle`,
`Warren`, `PCE` (Pepper Canyon East), `PCW` (Pepper Canyon West), `Rita`,
`Pangea`.

### Optional fields

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | Display name printed in the banner. Falls back to the file stem. |
| `notes` | string | Free-form context; printed verbatim after the banner. |
| `event` | `"sunday"` or `"friday"` | Selects the default end-leave time (10:10 vs 19:10). Defaults to `sunday`. |
| `custom_prompt` | string | Appended to the main prompt inside `<custom_instructions>`. Same field the production bot exposes. |
| `expected` | mapping | Enables gold-dataset comparison; see §6. |

### Flex semantics

A passenger with `living: Marshall` is automatically given
`alt_pickup_locations=[PickupLocations.GEISEL_LOOP]` by reusing the
production `living_to_alt_pickups` map. Nothing extra needs to appear in the
YAML.

You will see the flex passenger rendered in a dedicated `Flex pickups`
section of the `<pickups>` block in the prompt:

```
Flex pickups (assign each passenger to exactly one allowed location):
- marsha [allowed: Marshall uppers, Geisel Loop]
```

The validator accepts either allowed location; `resolve_chosen_pickup`
matches the LLM's chosen string (`"Marshall"`, `"Marshall uppers"`,
`"Geisel"`, `"GeiselLoop"`, `"Geisel Loop"`) back to the `PickupLocations`
enum so downstream drive-time math uses the correct node.

---

## 4. Example A — basic two-driver run

`evals/scenarios/basic.yaml`:

```yaml
name: basic two-driver mixed corridor
drivers: [4, 4]
event: sunday
passengers:
  - { name: alice, living: Muir }
  - { name: bob,   living: Sixth }
  - { name: carol, living: ERC }
  - { name: dave,  living: Seventh }
  - { name: erin,  living: Eighth }
```

Dry-run first, just to sanity-check the prompt:

```bash
uv run python -m evals.run_scenario evals/scenarios/basic.yaml --dry-run
```

Representative output (trimmed):

```
======================================================================
SCENARIO: basic two-driver mixed corridor
======================================================================

-- INPUT --
drivers: [4, 4]
passengers: 5
event: sunday  end_leave_time: 10:10

-- PROMPT --
You are a logistics coordinator. Assign every passenger ...
<hard_constraints>
H1. Every passenger in the <pickups> block is assigned to exactly one driver.
...
</hard_constraints>
<soft_preferences>
S1. Minimize total driving time ...
...
</soft_preferences>
<pickups>
Muir tennis courts: alice
Sixth loop: bob
ERC across from bamboo: carol
Seventh mail room: dave
Eighth basketball courts: erin
</pickups>
<drivers>
Driver0 has capacity 4, Driver1 has capacity 4
</drivers>
<matrix>
| from / to | START | Muir | Sixth | ... | END |
...
</matrix>

(dry-run: skipping Gemini call)
```

Remove `--dry-run` to do a full run. The important new sections you'll see
in the full run are:

```
-- RAW LLM OUTPUT --
{
  "Driver0": [
    {"name": "alice", "location": "Muir tennis courts"},
    {"name": "bob",   "location": "Sixth loop"},
    {"name": "carol", "location": "ERC across from bamboo"}
  ],
  "Driver1": [
    {"name": "dave", "location": "Seventh mail room"},
    {"name": "erin", "location": "Eighth basketball courts"}
  ]
}

-- VALIDATOR --
  (all checks passed)

-- DRIVE TIME (minutes, includes START->first and last->END) --
  Driver0: 18 min across 3 passenger(s)
  Driver1: 16 min across 2 passenger(s)
  total: 34 min

-- RENDERED DISCORD MESSAGES --
@alice @bob @carol — Driver0 will leave at ...
```

---

## 5. Example B — Marshall flex pickups

`evals/scenarios/marshall_flex_split.yaml`:

```yaml
name: Marshall flex split across corridors
drivers: [4, 4]
passengers:
  - { name: alice,  living: Muir }
  - { name: bob,    living: Sixth }
  - { name: marsha, living: Marshall }
  - { name: marley, living: Marshall }
  - { name: wendy,  living: Warren }
  - { name: iris,   living: PCE }
```

Two details to watch:

1. **Prompt rendering.** The `<pickups>` block puts the two Marshall
   riders in a separate `Flex pickups` section and the Warren/PCE riders
   in the fixed-location section. With `--dry-run` you can see it
   directly:

   ```
   <pickups>
   Muir tennis courts: alice
   Sixth loop: bob
   Warren Equality Ln: wendy
   Innovation: iris
   Flex pickups (assign each passenger to exactly one allowed location):
   - marsha [allowed: Marshall uppers, Geisel Loop]
   - marley [allowed: Marshall uppers, Geisel Loop]
   </pickups>
   ```

2. **LLM output.** Each flex passenger's `"location"` will be one of the
   two allowed strings. A good answer splits them — marsha to
   `"Marshall uppers"` (joining the Muir/Sixth car) and marley to
   `"Geisel Loop"` (joining the Warren/Innovation car). An equally valid
   answer could put both at the same location if the car compositions
   change. The validator enforces that the chosen location is allowed;
   the drive-time totals then show whether the split was actually the
   better choice.

Inspecting the output manually is the whole point here — there's no single
"correct" answer, and the flex decision is precisely what you want to
eyeball.

---

## 6. Example C — gold-dataset comparison

Add an `expected` block to grade the run against a coordinator-approved
answer. Manual mode still prints everything it normally does; the gold
comparison is an extra section at the end.

`evals/scenarios/marshall_flex_split_with_gold.yaml`:

```yaml
name: Marshall flex split across corridors (with gold)
drivers: [4, 4]
passengers:
  - { name: alice,  living: Muir }
  - { name: bob,    living: Sixth }
  - { name: marsha, living: Marshall }
  - { name: marley, living: Marshall }
  - { name: wendy,  living: Warren }
  - { name: iris,   living: PCE }

expected:
  cars:
    - passengers:
        - { name: alice,  location: Muir }
        - { name: bob,    location: Sixth }
        - { name: marsha, location: Marshall }
    - passengers:
        - { name: marley, location: Geisel Loop }
        - { name: iris,   location: Innovation }
        - { name: wendy,  location: Warren }
  max_time_delta_minutes: 2
```

### `expected` block schema

| Field | Type | Meaning |
| --- | --- | --- |
| `cars` | list | One entry per car the coordinator would have assigned. Driver labels are ignored on comparison — actual cars are matched to gold cars by passenger set. |
| `cars[].passengers` | list | Ordered list of `{name, location}`. The order matters for the strictest comparison level; see below. |
| `cars[].passengers[].name` | string | Must match a `name` in the top-level `passengers` list. Each name may appear in exactly one expected car. |
| `cars[].passengers[].location` | string | Any spelling `resolve_chosen_pickup` understands (`"Sixth"`, `"Sixth loop"`, `"GeiselLoop"`, …). |
| `max_time_delta_minutes` | int (optional) | If set, the comparison flags actual drive time exceeding gold by more than this many minutes. |

### What gets compared

Three levels, printed in order from loosest to strictest:

1. **Partition** — do the *sets* of passengers per car match? Driver
   labels are ignored.
2. **Location** — for every passenger, does the actual chosen pickup
   location match the gold location? Compared after the same
   normalization the pipeline uses for `resolve_chosen_pickup`, so
   `"GeiselLoop"` and `"Geisel Loop"` compare equal.
3. **Order** — within each matched car, is the pickup order identical?
   Only reported when partition matches (otherwise comparing orders
   across different passenger sets is meaningless).

Plus the **drive-time delta** between gold and actual, with the optional
tolerance check.

### Example gold output

```
-- GOLD COMPARISON --
partition: PASS
locations: FAIL
  x marsha: expected 'Marshall uppers', got 'Geisel Loop'
order: PASS
drive time: gold=14 min, actual=15 min (delta +1 min, tolerance +2 min (within tolerance))
```

The harness still exits 0. If you want a CI-style regression check, wrap
the command in your own script and parse `FAIL` out of the output — but
for the intended use case (inspect the output yourself) this is what you
want.

---

## 7. Output section reference

| Section | Printed when | Meaning |
| --- | --- | --- |
| banner + notes | always | Scenario name and free-form `notes` text. |
| `-- INPUT --` | always | Driver capacities, passenger count, event, end-leave time. |
| `-- PROMPT --` | always | The full prompt string sent to Gemini. |
| `(dry-run: skipping Gemini call)` | `--dry-run` | Harness exits immediately after. |
| `-- LLM CALL FAILED --` | Gemini raised | Exception type + message; harness exits 1. |
| `-- RAW LLM OUTPUT --` | full run | The raw JSON object returned by Gemini. |
| `-- LLM REPORTED NO VALID ASSIGNMENT --` | LLM returned `{"error": "..."}` | Harness stops processing and exits 0. |
| `-- VALIDATOR --` | full run | Either `(all checks passed)` or a list of semantic violations from `assignment_validator.validate_assignment`. |
| `-- DRIVE TIME ... --` | full run | Per-driver and total minutes via the all-pairs shortest-path table. Consecutive same-location stops are collapsed before walking the path, matching the drive-time logic used for gold comparison. |
| `-- GOLD COMPARISON --` | `expected` present | `partition` / `locations` / `order` PASS/FAIL plus drive-time delta. |
| `-- RENDERED DISCORD MESSAGES --` | full run | Exactly what the coordinator would paste into Discord. |

---

## 8. Troubleshooting

**`ValueError: Unknown living location: '…'`** — The `living` value didn't
match any `CampusLivingLocations` enum. Valid values are listed in §3.

**`ValueError: Unknown pickup location in gold scenario: '…'`** — The
`expected.cars[].passengers[].location` value didn't match any
`PickupLocations` enum spelling. Use `"Sixth"`, `"Sixth loop"`,
`"Warren"`, `"Warren Equality Ln"`, `"Innovation"`, `"Marshall"`,
`"Marshall uppers"`, `"Geisel"`, `"Geisel Loop"`, `"GeiselLoop"`, etc.

**`LLM CALL FAILED: AuthenticationError`** — `GOOGLE_API_KEY` isn't set or
is invalid. Use `--dry-run` to iterate without a key.

**Validator reports `Driver0 exceeds capacity …`** — the model violated a
hard constraint and the repair loop hit its limit. This is the kind of
thing the harness is built to surface; inspect the prompt and consider
whether wording changes would help.

**Partition mismatch but the assignment looks fine** — check that your
`expected` block spells every passenger name exactly as it appears in
`passengers`. Comparison is case-sensitive on names (unlike
`living` / `location`, which are normalized).
