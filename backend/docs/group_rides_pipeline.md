# Group Rides LLM Pipeline

This document describes how the group-rides feature turns a set of Discord
reactions into driver-by-driver pickup schedules, what each component is
responsible for, and why the pipeline is shaped the way it is.

Related code (all paths are relative to `backend/`):

- `bot/services/group_rides_service.py` — orchestrator
- `bot/services/llm_service.py` — Gemini client + repair loop
- `bot/services/assignment_validator.py` — semantic validation
- `bot/services/ride_grouping.py` — prompt-input formatters + final output
- `bot/utils/genai/prompt.py` — prompt templates
- `bot/utils/locations.py` — graph, Dijkstra, Markdown table rendering
- `bot/core/schemas.py` — Pydantic data model
- `bot/core/enums.py` — pickup / living location enums

---

## 1. High-level flow

```
 Discord reactions
        |
        v
 [GroupRidesService._process_ride_grouping]
   - filter Sunday-class attendees
   - resolve identities for reacted users
   - bucket by living location -> pickup location (plus flex alternatives)
   - validate total capacity
        |
        v
 [LLMService.generate_ride_groups]
   - render all-pairs distance matrix as Markdown
   - format pickups + drivers as text blocks
   - call Gemini (response_mime_type=application/json, seed=42)
   - JSON-decode response
   - shape validate (LLMOutputNominal / LLMOutputError)
   - semantic validate (assignment_validator)
   - on violation: append repair block + retry (up to MAX_REPAIR_ATTEMPTS)
        |
        v
 [ride_grouping.create_output]
   - resolve each LLM-chosen location back to a PickupLocations enum
   - group consecutive same-location riders per driver
   - walk pickups in reverse to compute leave times
   - format a Discord-friendly summary + per-driver message
        |
        v
 Discord channel
```

---

## 2. Component walkthrough

### 2.1 `GroupRidesService._process_ride_grouping`

Entry point. Responsibilities:

1. Determine which event type the message refers to (Sunday / Friday) and the
   corresponding end leave time.
2. Remove Sunday-class attendees from the reacted set so they aren't scheduled.
3. Call `LocationsService.list_locations` to resolve reacting users into
   `(name, username, living_location)` tuples.
4. `_split_on_off_campus` converts raw `(living_location, [(name, username), ...])`
   rows into two things:
   - `passengers_by_location: dict[PickupLocations, list[Passenger]]`
   - `off_campus: dict[str, list[(name, username)]]` (never sent to the LLM;
     the coordinator handles these manually).
5. `_validate_capacity` parses the comma-separated driver capacity string and
   ensures total capacity >= total passengers; fails fast otherwise.
6. `llm_input_pickups` and `llm_input_drivers` format the structured data as
   prompt text blocks.
7. Hand off to `LLMService.generate_ride_groups` in a thread (the Discord
   event loop must stay responsive).
8. Pass the LLM output to `create_output` for rendering and send the messages.

### 2.2 `_split_on_off_campus` + flex pickups

A passenger's `pickup_location` comes from the `living_to_pickup` mapping.
Some living locations (currently only Marshall) have entries in
`living_to_alt_pickups` mapping them to additional allowed pickups. Those
passengers are still keyed under their primary pickup so capacity math
treats them as a single pool, but each `Passenger` is annotated with
`alt_pickup_locations` so the LLM and validator can see the flex options.

This is the "alternative pickup locations" pattern: the decision isn't really
about Marshall, it's about which corridor the driver is already serving. If a
car serves Muir/Sixth/ERC/Seventh, Marshall Uppers is free; if it serves
Warren/Innovation, Geisel Loop is free. Splitting Marshall riders between the
two locations falls out automatically because each flex passenger is
independent.

### 2.3 `llm_input_pickups` — fixed vs flex rendering

Fixed passengers render in the traditional grouped form:

```
Sixth loop: alice, bob
ERC across from bamboo: carol
Innovation: dave
```

Flex passengers render in a dedicated section with the allowed set explicit:

```
Flex pickups (assign each passenger to exactly one allowed location):
- erin [allowed: Marshall uppers, Geisel Loop]
- frank [allowed: Marshall uppers, Geisel Loop]
```

This shape makes "split vs keep together" a natural output of the LLM instead
of a rule you have to remember to enforce.

### 2.4 `locations.py` — graph + distance table

`LOCATIONS_MATRIX` is an adjacency map of campus pickup points plus the
special `START` and `END` nodes. Two derived helpers:

- `lookup_time(LocationQuery)` runs Dijkstra and is used by `create_output`
  when computing when each driver needs to leave to hit a pickup on time.
- `compute_all_pairs_shortest_paths()` runs Dijkstra from every node and
  caches the result. `render_distance_markdown()` turns that into a
  Markdown table that looks like:

```
| from / to | START | Muir | Sixth | ... | END |
| --- | --- | --- | --- | --- | --- |
| START | 0 | 12 | 13 | ... | 30 |
| Muir  | 12 | 0 | 1 | ... | 24 |
...
```

The table is injected into the prompt instead of the raw adjacency dict. This
is the single largest accuracy win in the pipeline — the LLM used to be
handed sparse adjacency and had to do multi-hop graph reasoning on its own,
which free-tier Flash is not reliable at.

### 2.5 `LLMService.generate_ride_groups` — call + repair

The Gemini client is constructed with `response_mime_type="application/json"`,
so the API always returns a raw JSON string in `ai_response.content` and no
codefence stripping is required. `temperature=0` + `seed=42` reduce per-call
variance; the seed also sets up a clean foundation for future best-of-N
sampling.

Around the API call is a two-layer retry scheme:

- `@tenacity.retry(stop=stop_after_attempt(NUM_RETRY_ATTEMPTS))` handles
  transient / network / JSON-decode failures. It re-issues the identical
  prompt.
- Inside that, a **repair loop** of up to `MAX_REPAIR_ATTEMPTS + 1` attempts
  runs semantic validation via `assignment_validator.validate_assignment`
  and, on violation, appends a repair block to the base prompt with the
  previous output and the specific violations. This gives the model the
  signal to actually fix its mistakes instead of re-rolling the same
  prompt hoping for a different answer.

If the LLM explicitly returns `{"error": "..."}`, the pipeline returns that
as-is (handled upstream by the coordinator).

### 2.6 `assignment_validator.validate_assignment`

Shape-only Pydantic validation (`LLMOutputNominal`) catches JSON structure
problems but lets through the common real bugs:

- A passenger omitted entirely.
- A passenger assigned to two drivers.
- A phantom name that was never in the input.
- A passenger sent to the wrong location (e.g. Marshall rider to Rita).
- More passengers on a driver than the driver's capacity.

`validate_assignment` enforces all of these against the structured
`passengers_by_location` and `driver_capacity_list` passed through from
the service. Location comparison is lenient about whitespace and short vs
long forms ("Sixth" vs "Sixth loop") because the LLM legitimately uses both.

Each violation is formatted as a one-line human-readable string. Those
strings are what the repair loop feeds back to the LLM.

### 2.7 `ride_grouping.resolve_chosen_pickup` + `create_output`

When the LLM returns `{"name": "erin", "location": "Geisel Loop"}`, the
service has to turn "Geisel Loop" back into a `PickupLocations` enum so
downstream code (Dijkstra for leave-time math, Google Maps URL lookup, etc.)
can work with it.

`resolve_chosen_pickup` matches on three normalized forms simultaneously:
full ("geisel loop"), first word ("geisel"), and run-together ("geiselloop").
This means a Marshall rider assigned to any of `"Geisel Loop"`,
`"GeiselLoop"`, or `"Geisel"` all resolve to `PickupLocations.GEISEL_LOOP`.

`create_output` then:

1. Builds `passenger_lookup` by name for O(1) resolution.
2. For each driver's list, resolves the chosen pickup, uses
   `passenger.model_copy(update={"pickup_location": chosen})` so the
   Passenger object downstream reflects the resolved location (this is the
   "thread the chosen location through" step required for Marshall flex to
   work end to end).
3. Groups consecutive same-location passengers (the LLM returns pickup order,
   so adjacent same-location passengers form a single stop).
4. Walks the groups in reverse from `end_leave_time` using Dijkstra on
   `LOCATIONS_MATRIX` to compute per-stop leave times.
5. Produces a human-readable summary plus a per-driver copy-paste message
   with Google Maps links.

---

## 3. Design decisions

### 3.1 Why keep the LLM at all?

The combinatorial core of this task (assign passengers to drivers, order
stops, minimize time) is a small Vehicle Routing Problem. A deterministic
solver (OR-tools) would be more reliable for the hard constraints. However:

- The coordinator wants a single deployment with a Discord front-end, not a
  separate solver service.
- Several soft preferences are fuzzy ("Rita gets its own driver if drivers
  permit"; "don't combine unrelated stops") that LLMs handle well in natural
  language.
- The free-tier Gemini quota is cheap, and the problem sizes are small
  (typically <20 riders, <6 drivers).

The current architecture compromises: the LLM does the assignment, and
deterministic code enforces every hard constraint around it.

### 3.2 Why a distance table instead of an adjacency dict?

Passing raw adjacency forced the LLM to do graph search in its head, which
Flash is unreliable at beyond 1-2 hops. An all-pairs shortest-path Markdown
table makes every driver's total route time a trivial lookup: the LLM just
sums three numbers (START -> first pickup, pickup-to-pickup, last pickup ->
END).

### 3.3 Why `response_mime_type="application/json"` instead of
`with_structured_output`?

`with_structured_output` in `langchain-google-genai` translates a Pydantic
model to a Gemini response schema. The current output is
`dict[str, list[LLMPassenger]]` with dynamic driver keys; schema translation
for dynamic-key objects is inconsistent across LangChain versions. Forcing
JSON output via `response_mime_type` is a smaller, more portable change
that already eliminates the entire codefence-stripping fallback. A future
commit can migrate to full schema enforcement by reshaping the output into a
list of drivers.

### 3.4 Why a repair loop on top of tenacity?

Tenacity's retry_if_exception_type(Exception) re-issues the identical
prompt. When the LLM's output is *shape-valid but semantically wrong* (wrong
capacity, missing passenger, phantom name) the same prompt is overwhelmingly
likely to produce the same wrong answer again. The repair loop gives the
model two pieces of new information on each retry:

1. Its previous (wrong) output.
2. The specific list of constraints that were violated.

Both are surfaced in plain language, which is the representation LLMs are
best at. Tenacity is still useful for network flakiness and the (rare)
non-JSON response.

### 3.5 Why split hard vs soft constraints in the prompt?

The previous prompt mixed capacity rules (hard) with "prefer non-overlapping
routes" (soft) in two overlapping numbered lists, including at least one
outright contradiction. Small models degrade quickly from ambiguous or
contradictory rules. The new prompt has a single `<hard_constraints>` block
(never to be violated) and a single `<soft_preferences>` block with
lexicographic priorities (S1 dominates S2 dominates ...). This mirrors how
the validator actually thinks about the problem, so any disagreement between
prompt and validator is now localised and obvious.

### 3.6 Why are Marshall residents keyed under the primary location in
`passengers_by_location`?

Because capacity math (`_validate_capacity`, `is_enough_capacity`) counts
passengers independent of pickup location — a Marshall rider still consumes
one seat regardless of whether they're picked up at the uppers or at Geisel
Loop. Keying them under a single primary location keeps that math trivial.
The flex decision is purely about *where* to pick them up, not *whether*
they need a seat.

### 3.7 Why keep `GROUP_RIDES_PROMPT_LEGACY` around?

Prompt engineering is empirically evaluated. Until there's an offline eval
harness with 20+ historical inputs + coordinator-approved outputs, we cannot
prove the new prompt is strictly better than the old one in production.
Keeping the legacy prompt behind a flag gives the coordinator a one-click
rollback if the new one regresses.

---

## 4. Known trade-offs and next steps

- **No offline eval.** Every prompt change today is vibes-based. A small
  eval harness over historical inputs is the single highest-leverage thing
  to add next.
- **LLM still chooses driver count.** This is actually the subtlest source
  of sub-optimal routes. A small helper that deterministically proposes the
  top-k driver count choices by total time — and lets the LLM pick among
  them — would be the next architectural step.
- **No best-of-N.** With `seed=42` and `temperature=0` outputs are
  near-deterministic, so naive sampling gives near-duplicates. Varying the
  seed + scoring by `(hard_violations, soft_violations, total_time)` would
  be cheap on free tier and catch the occasional bad answer.
- **Off-campus passengers bypass the LLM.** They're surfaced in the summary
  as "TODO: off campus" for the coordinator to handle. If off-campus routing
  is ever automated, the driver capacity passed to the LLM will need to be
  reduced by off-campus headcount first.
- **Flex pickups are hard-coded to Marshall.** The `living_to_alt_pickups`
  map is the single point of extension; adding Revelle ↔ Muir or similar is
  a one-line change, though the corridor-preference text in the prompt
  would need a corresponding update.
