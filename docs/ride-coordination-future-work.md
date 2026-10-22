# Deferred ride coordination features

These ideas are future work, not part of the database persistence and recovery PR.
They require a separate product decision before implementation. The current work
preserves existing signup, grouping, and coverage behavior.

## Possible coordinator tools

- A dated Ride Events page for inspecting requests and custom details.
- Manual request editing from that page, in addition to the existing non-Discord
  rider interface.
- Explicit confirmation of driver availability, offered legs, and passenger seats.
- Separate pickup and return assignments saved as a structured plan.
- Validation for duplicate riders, event membership, self-assignment, capacity,
  and return destinations.

## Decisions before implementation

Decide whether generated grouping text is a suggestion or a confirmed plan, who
can confirm or edit a plan, and how edits interact with later rider withdrawals.
Determine how confirmed driver capacity differs from the capacity already entered
in the existing grouping tool. Preserve existing coverage behavior until there is
an explicit migration plan for it.

The removed prototype is available in commits `700a336f` (backend) and `4819ae5e`
(dashboard) for reference. Reassess it against agreed requirements before reuse.
