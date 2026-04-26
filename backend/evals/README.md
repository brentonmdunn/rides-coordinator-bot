# Group Rides Eval Harness

A small CLI for manually inspecting what the group-rides LLM pipeline produces
on a hand-written scenario. There are no gold/expected assertions here — the
harness prints the prompt, the raw LLM output, the validator findings, the
per-driver drive time, and the rendered Discord messages so you can judge
whether the assignment is good yourself.

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
6. **RENDERED DISCORD MESSAGES** — exactly what the coordinator would
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

## Starter scenarios

- `scenarios/basic.yaml` — Minimal two-driver upper-corridor scenario. Use
  as a template when writing your own.
- `scenarios/marshall_flex_split.yaml` — Two drivers on opposite corridors
  with two Marshall riders. Exercises the flex-pickup split.
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
