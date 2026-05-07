# Group Rides Eval Harness

A small CLI for manually inspecting what the group-rides LLM pipeline produces
on a hand-written scenario. By default there are no gold/expected assertions —
the harness prints the prompt, the raw LLM output, the validator findings, the
per-driver drive time, and the rendered Discord messages so you can judge
whether the assignment is good yourself. If you add an `expected` block to a
scenario, you also get a gold-comparison section that grades the run at three
strictness levels plus the drive-time delta.

Complements the unit-test suite (`tests/unit/test_flex_pickup.py`,
`tests/unit/test_assignment_validator.py`, etc.) which covers the
deterministic parts of the pipeline without calling Gemini.

## Quick start

Run every command from `backend/`.

```bash
# Inspect the prompt only — does not call Gemini. No GOOGLE_API_KEY needed.
uv run python -m evals.run_scenario evals/scenarios/basic.yaml --dry-run

# Full run (requires GOOGLE_API_KEY in the environment).
uv run python -m evals.run_scenario evals/scenarios/basic.yaml

# Compare against the legacy prompt.
uv run python -m evals.run_scenario evals/scenarios/basic.yaml --legacy-prompt
```

## What the output contains

In order:

1. **INPUT** — driver capacities, passenger count, event/end-leave time.
2. **PROMPT** — the exact string sent to Gemini (hard constraints, soft
   preferences, all-pairs distance table, pickups, drivers).
3. **RAW LLM OUTPUT** — the raw JSON object returned by Gemini.
4. **VALIDATOR** — any semantic violations from
   `assignment_validator.validate_assignment` (missing passengers,
   capacity violations, disallowed pickup locations, phantom names, etc.).
   "(all checks passed)" means the output satisfies every hard constraint.
5. **DRIVE TIME** — total minutes for each driver, computed by walking
   `START -> first pickup -> ... -> last pickup -> END` on the all-pairs
   shortest-path table. Consecutive same-location stops are collapsed.
6. **GOLD COMPARISON** — only printed when the scenario has an `expected`
   block. See the next section.
7. **RENDERED DISCORD MESSAGES** — exactly what the coordinator would
   paste into Discord.

On `--dry-run` only steps 1–2 are printed.

## Scenario file format

```yaml
name: human-readable name                  # optional
notes: |                                   # optional free-text context
  What's being tested here.
drivers: [4, 4]                            # driver capacities (seats per car)
event: sunday                              # optional: sunday (default) or friday
custom_prompt: |                           # optional extra instructions appended
  Extra instructions that override the main prompt.
passengers:
  - { name: alice, living: Sixth }
  - { name: bob,   living: Marshall }      # flex: Marshall OR Geisel Loop
  - { name: carol, living: Warren }
  - { name: dave,  living: PCE }           # PCE/PCW map to Innovation
```

Valid `living` values (case-insensitive, matched against
`CampusLivingLocations`):

- `Sixth`, `Seventh`, `Marshall`, `ERC`, `Muir`, `Eighth`, `Revelle`
- `Warren`, `PCE` (Pepper Canyon East), `PCW` (Pepper Canyon West)
- `Rita`, `Pangea`

`Marshall` is the only living location that produces flex passengers; they
can be assigned to either `Marshall uppers` or `Geisel Loop`.

## Optional: gold comparison

Add an `expected` block to any scenario and the harness will grade the run
at three strictness levels plus a drive-time delta:

```yaml
expected:
  cars:
    - passengers:
        - { name: alice,  location: Muir }
        - { name: bob,    location: Sixth }
        - { name: marsha, location: Marshall }     # or "Marshall uppers"
    - passengers:
        - { name: marley, location: Geisel Loop }
        - { name: iris,   location: Innovation }
        - { name: wendy,  location: Warren }
  max_time_delta_minutes: 2                        # optional
```

Matching rules:

1. **Partition** — does the actual assignment group passengers into the
   same *cars* as gold? Driver labels are ignored (actual `"Driver0"` can
   be matched to gold's car-1 if their passenger sets match).
2. **Location** — is every passenger's resolved pickup location equal to
   the gold location? Location strings are compared with the same
   normalization as the production pipeline — `"Geisel Loop"`,
   `"GeiselLoop"`, and `"Geisel"` all match `PickupLocations.GEISEL_LOOP`.
3. **Order** — within each matched car, is the pickup order identical?
   Only meaningful when partition matches.

If `max_time_delta_minutes` is set, the harness flags actual drive times
that exceed the gold total by more than that many minutes.

The output section looks like:

```
-- GOLD COMPARISON --
partition: PASS
locations: FAIL
  x marsha: expected 'Marshall uppers', got 'Geisel Loop'
order: PASS
drive time: gold=14 min, actual=15 min (delta +1 min, tolerance +2 min (within tolerance))
```

The harness still exits 0 — this is inspection, not CI.

## Starter scenarios

- `scenarios/basic.yaml` — Minimal two-driver upper-corridor scenario. Use
  as a template when writing your own.
- `scenarios/marshall_flex_split.yaml` — Two drivers on opposite corridors
  with two Marshall riders. Exercises the flex-pickup split.
- `scenarios/marshall_flex_split_with_gold.yaml` — Same input as the above
  with a full `expected` block; use it to see a populated gold-comparison
  section.
- `scenarios/warren_innovation_corridor.yaml` — Exercises the hard
  corridor-separation rule (Warren/Innovation must not be combined with
  Eighth/Muir/Sixth/Marshall/ERC).

## What to look for

Per the pipeline's lexicographic preferences:

1. **No hard violations.** The validator section should say
   "(all checks passed)".
2. **No overlapping routes.** For a chain A-B-C-D across two drivers,
   prefer AB + CD over AC + BD.
3. **Corridor coherence.** Upper campus (Muir/Sixth/Marshall/ERC/Seventh/
   Eighth) stays together; Warren/Innovation stays together.
4. **Flex placement.** Marshall riders should be at "Marshall uppers" when
   the car serves the upper corridor, and at "Geisel Loop" when the car
   also serves Warren/Innovation.
5. **Driver count.** The minimum drivers that keep each car under 4 stops
   and under 7 minutes of drive time.
6. **Rita on its own.** If a Rita rider appears and there's a spare
   driver, give them a dedicated car.

The total drive-time number is a single quality signal but not the only
one — sometimes a slightly longer total is correct because it keeps a
driver on a single corridor.
