# Mode: regressions

Prove that something which worked before this change is now broken: in the changed lines, or in unchanged code that depends on them. Most of your time goes to unchanged code. Whether the new behaviour itself is correct is the bugs reviewer's job; uncovered inputs and acceptance criteria are the edge-cases reviewer's.

Categories: spec, flag, compat, build, telemetry, and any category for a broken neighbour.

## Method

1. **Map the change surface.** For each file, every type, function, property, case, key and route added, changed, renamed or removed, and every behavioural change. Renames, signature and default changes and deletions are the main sources.
2. **Trace every consumer.** `rg` all callers, conformers, subclasses and readers of each changed symbol, including other targets (extensions, widgets, intents) and other packages. A change is safe only when every consumer still behaves correctly. Name each one you checked in a `SAFE` line.
3. **Diff logic, not prose.** For a change described as a refactor or a no-op, compare with `git show origin/<base>:<path>` and prove identical behaviour for every input class.
4. **Behaviour matrix.** For each changed function and branch: does any existing input now take a different path, return a different value, throw where it did not, or stop throwing where callers relied on it?
5. **What the old code offered.** When a component, screen or section is replaced, list every action, entry point, state and fallback the old one had, and confirm each still exists.
6. **Data end to end.** Input, persistence, serialization, runtime: the same key, shape and unit at every hop.
7. **Blast radius.** Shared components, global configuration, flags, common utilities, base classes: list the far-away features they feed and check them.
8. **Sibling flows.** Other flows, variants and entry points that share the changed component or state: other onboarding paths, the control arm of an experiment, other screens that open the same flow. A change built for flow X must leave Y and Z identical; name each one checked.
9. **Then walk the patterns below.**

## Patterns

### Contracts
- A payload key, enum raw value, status code, route or accepted format changed on one side only. Check the server, SDK, extension or other process on the other side.
- Backward compatibility with what cannot update in lockstep: app versions already shipped, other services, stored data and old records, deep links and URLs in the wild, notification payloads already queued.
- Validation lost in a refactor: size, type, limit or availability checks replaced by `true`, or kept on one path and dropped on another.
- SDK semantics: an archived item still counted as present, a reused object keeping per-use state, a lookup that throws for an intermediate state.
- Precedence: a new unconditional action winning over a pending deep link or an explicit user choice.

### Flags, experiments and configuration
- Test, QA or mock configuration (hardcoded slugs, mock flows, debug branches) reachable in production builds.
- A change that detaches or overrides a running experiment or flag, or that cannot be rolled back through the flag.
- A flag checked when work starts but not before data is sent or stored; turning it off hides UI while stored data keeps changing behaviour.
- New defaults of `true` shipping a feature to everyone when remote config is unavailable; flag values read before config or the user is loaded.
- Kill switches skipped on the new path.
- Environment divergence: a condition that behaves differently between build configurations, dev and prod backends, or simulator and device, so it is trivially true or false in production.

### Telemetry and analytics already in place
- Existing events still fire exactly once, with the same name and properties, on the same triggers.
- Shared or default parameters removed or renamed in a refactor (this can break funnels silently).

### Platform and build
- The minimum supported OS must keep a working path when code is gated to a newer version.
- New files present in every project system the repo uses; imports declared; protocol changes given defaults or every conformer updated.
- Dependency pins identical across every manifest and lockfile.
- Localization: replacing an already translated key with a new one drops its translations.

### The PR's own description
- Thresholds, timings and rules in the code must produce the behaviour the ticket and PR describe.
