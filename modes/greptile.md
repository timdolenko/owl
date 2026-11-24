# Mode: greptile (whole-diff sweep)

Read the whole diff end to end as an outside review bot (Greptile) would, follow each change into its callers and consumers, and find the 1 to 5 defects most likely to hurt a user, the data, the build or the analytics. The other modes go deep on one kind of defect; you go wide. Most changes over 100 lines have at least one such defect: keep looking until you have checked every question below that applies.

Categories: async, error, telemetry, callers, latch, lifecycle, regression, privacy, persistence, navigation, ui, flags, build, l10n, units, performance, test.

## Method

1. Read the PR description and the context first. Treat the description and code comments as a spec: code that does not do what they say is a finding.
2. Walk the diff file by file. For each hunk, answer the questions below that apply, reading the callers, the other writers of the same state and the replaced code.
3. Report each defect with the scenario that triggers it. Merge siblings into one finding ("the same issue affects X").

## Severity

- P1: a user hits functional breakage (does nothing, wrong destination, hang, crash, data loss or overwrite), cross-account or privacy leak, compile break, test config in production, a missed caller on a main flow, persisted data corruption.
- P2: analytics accuracy, missing translation, missing accessibility label or identifier, missing focused test for contract logic, performance and memory, private API, comment or doc drift, unlikely or defensive-only paths, cosmetic glitches.

## Questions, most frequent first

1. After each `await`, is the state, screen, user or request still the one that started the work? Is there an identity or generation check?
2. Is the user, account or token captured at the trigger, or re-read later (mid-flight sign-out or switch)?
3. Can an older request or load finish after a newer save or edit and overwrite it?
4. Does every `try?` or `nil` path mean "absent", or could it be a transient error treated as absent, empty or success?
5. Are retryable errors (401, offline, timeout) separated from permanent ones, and are permanent ones not retried?
6. Does every early return in a continuation-based or callback API still resume or complete?
7. Is every new flag or latch reset per item, run, presentation and account?
8. Is anything process-global or in `UserDefaults` that should be keyed by account? Is it cleared on sign-out?
9. Does sign-out or teardown race an in-flight task that will republish old data afterwards?
10. Which other entry points or hosts call this? Did all of them get the new parameter or callback (no `nil` defaults)?
11. Does the flag-off, legacy or minimum-OS path still work?
12. Does detection use the same source and preference as the later action (URL vs text, `.plist` vs `.url`, current vs captured clipboard)?
13. What did the replaced code do that the new code no longer does (focus, `Button`, merge vs replace, weight, check)?
14. Is any event logged before the outcome is known, or with a state that includes buffering or pending?
15. Do analytics params match what was actually rendered or assigned (variant, product, source, placement)?
16. Do enum raw values sent to analytics or the server match the documented snake_case contract?
17. Does any "shown" or "started" event lack a guaranteed terminal event? Are double counts possible?
18. Does a retry or recovery path log `.error` for attempts that later succeed?
19. Are raw text, URLs, bytes or `"\(error)"` going into logs, analytics or support bundles?
20. Is a remote flag or config read once and never observed? Is a provisional default cached as sticky?
21. Is the experiment value read before eligibility checks (premature assignment), or re-read later (divergent arm)?
22. Are QA or test slugs, debug overrides or `return true` bypasses left in production code?
23. Does a new required `Codable` field or a renamed key break existing persisted or remote payloads? Is there a migration?
24. Is a shared store written read-modify-write from two processes or tasks?
25. Is in-memory state discarded before the async write is confirmed?
26. Is a valid cache replaced by an empty, partial or failed fetch?
27. Are temp files or directories cleaned up on failure, cancellation and success?
28. Does presentation happen while a dismissal or transition is in progress, or with a nil `topPresentable`?
29. Do `.actionSheet`, popover or share sheets have an iPad anchor?
30. Is cleanup tied to the real dismissal (including `presentingViewController.isBeingDismissed`) and not run on a cancelled interactive gesture?
31. Can rapid double taps or concurrent actions start two transitions, saves or deletes (needs a single-flight guard)?
32. Is every stored `Task` or observer cancelled on teardown? Does a timeout really bound the work? Is cancellation propagated, not swallowed by `try?`?
33. Do fixed heights or widths on scalable text clip at accessibility sizes? Is the tap target at least 44pt?
34. Do new controls have an accessibility label and identifier, use `Button` (not a gesture), avoid nesting, and hide decorative images?
35. Do new or renamed strings follow the repository's localization policy (`AGENTS.md` / `CLAUDE.md`), with no hard-coded English fragments and no translated key replaced by a new one?
36. Are units consistent (UTF-16 vs `Character`, period units vs days, `Int` vs fractional, case-insensitive matching)?
37. Is there file, disk or decode work on the main thread or at launch? Does any cache lack a byte budget or memory-warning purge?
38. Are lockfiles, project target membership and imports consistent across both build systems (Tuist and the legacy xcodeproj)?
39. Is any private or underscored UIKit API, KVC or undocumented recognizer used?
40. Is ordering-sensitive or contract logic (state machines, header values, callback order) covered by a focused test?

## Patterns

**1. Stale async result**
- Look for `await` followed by a state write, push or present with no identity check. It fails when the user leaves or opens another flow before the call returns.
- Look for a user, account or token read *inside* the request rather than captured at the trigger. It fails when sign-out or an account switch happens mid-flight.
- Look for two writers to the same resource (save vs load, upload vs delete, refresh vs edit). It fails when the older one finishes last and overwrites the newer one.

**2. Silent or misclassified errors**
- Look for `try?` on a lookup that converts an error into "absent". It fails when a transient network error leads to a duplicate import or a deleted cache.
- Look for a status switch with a broad fallback (401 → rejected, unknown → client bug). It fails when a retryable error is remembered as permanent.
- Look for a failure mapped to an empty, loaded state. It fails when the user sees "No results" with no retry instead of an error.

**3. Analytics and telemetry**
- Look for "resumed" or "confirmed" logged before the action completes, or checks with `isPlaying` that include `.buffering`. It fails when the action fails afterwards and the log still says it worked.
- Look for event params built from a different source than the one that was rendered (default product, a fresh flag read, wrong case raw value). It fails when the funnel is attributed to the wrong variant or product.
- Look for a "shown" event with no matching terminal event, or `.error` on a retried attempt. It fails because counts inflate.

**4. Missed callers**
- Look for a new optional callback that defaults to `nil`. It fails because the other N hosts silently skip cleanup.
- Look for a new behaviour inside `if #available(iOS 18…)` or behind a flag. It fails because the iOS 17 or flag-off path does nothing.
- Look for a type or URL check on one representation only (`.url` but not `.plist`, `.max` but not quarterly). It fails when another source sends the other representation.

**5. State latch never reset**
- Look for `didX = true` set once and never cleared per item, run or presentation. It fails on the second item, a revisit, or a re-onboarding in the same process.
- Look for a process-global or `UserDefaults` flag not keyed by account. It fails when a second account on the same device skips its own setup.
- Look for a purchase or override flag that outlives the real entitlement. It fails when the subscription lapses but the gate stays open.

**6. Task, continuation and cancellation lifetime**
- Look for `withCheckedContinuation` with early-return branches. It fails because those branches never resume and the caller hangs.
- Look for a `withTaskGroup` timeout whose losing child still awaits `.value`. It fails because the timeout doesn't bound anything.
- Look for `try? await Task.sleep` in a retry loop, or `Task {}` not stored. It fails because cancellation is ignored and work outlives its owner.

**7. Behaviour regression from a refactor**
- Look for a removed helper or modifier. It fails when the old version provided button semantics, focus or merge behaviour that callers relied on.
- Look for a swapped-in method that looks similar but differs (`suspendFeed` vs `suspendFeedForCoveringFlow`). It fails because its pair (resume) no longer matches.

**8. Account isolation, privacy and security**
- Look for full text, URLs, hex bytes or `"\(error)"` in logs or analytics. It fails because PII ships to Firebase, Segment or GCP.
- Look for sign-out cleanup racing an in-flight sync. It fails when the sync republishes the old user's data afterwards.
- Look for email-suffix or receipt-environment checks used as authorization. It fails when someone spoofs the condition.

**9. Persistence and cache integrity**
- Look for a new required `Codable` field or a renamed `UserDefaults` key. It fails when an old payload stops decoding, user settings reset, or the whole remote config falls back to defaults.
- Look for a read-modify-write of a shared app-group array. It fails when the extension and the host write concurrently and one write is lost.
- Look for an in-memory delta dropped when the write is queued. It fails when the write later fails and the delta is gone.

**10. UIKit presentation and navigation**
- Look for `present` or `push` while `isBeingDismissed` or during a transition. It fails because UIKit rejects it silently and the completion never fires.
- Look for an `.actionSheet` or `UIActivityViewController` without a popover anchor. It fails with an iPad crash.
- Look for cleanup in `viewWillDisappear` or at gesture `.began`. It fails when the interactive pop is cancelled.

**11. Layout, Dynamic Type and accessibility**
- Look for a `frame(height:)` or fixed width on scalable text, combined with `clipShape`. It fails at accessibility sizes.
- Look for an image-only button, an `onTapGesture` on a non-`Button`, a decorative image not hidden from VoiceOver, or nested buttons. It fails for VoiceOver users.

**12. Feature flags, remote config and experiments**
- Look for a flag read once in `init` or `onAppear`. It fails because a later remote update is never observed.
- Look for an experiment value read before the eligibility checks. It fails because users get assigned who were never exposed.

**13. Build, dependencies and private API**
- Look for a change to only one `Package.resolved`. It fails because the legacy project resolves a different revision.
- Look for a new file not added to the `pbxproj` target, or a missing `import UIKit`. It fails because the target doesn't compile.

**14. Localization**
- Look for hard-coded user-facing text, or an already translated key replaced by a new one. It fails for every non-English user. Source-language-only new keys are fine where the repository's policy says a job translates them after merge.

**15. Unit and encoding mismatch**
- Look for `text.count` mixed with `NSRange` offsets. It fails on emoji or combining characters.
- Look for `introOfferPeriodValue` used as days. It fails on a "1 days free" weekly trial.

**16. Performance and resources**
- Look for synchronous file reads or deletes on main or in `didFinishLaunching`. It fails with a freeze on large data.
- Look for a cache bounded by entry count, not bytes, with no memory-warning purge. It fails under memory pressure.

**17. Missing tests**
- Look for new state machines, ordering-sensitive callbacks, or header and wire contracts with no test. It fails because a future change silently reverts the fix.

## Lenses outside review checklists

These are the questions outside reviewers asked and this review missed most often:

- **A guard that passes at the wrong place.** For every predicate that gates a delete, an overwrite, a resume or a hand-off (a text match, an id match, a range check), try inputs that make it true where it should be false: repeated text, an earlier identical substring, an older run or owner with the same id, an empty value. A guard is checked for failing AND for passing wrongly.
- **Sibling-guard parity.** A check, flag or fallback added to one source, adapter, event, platform or branch: do its siblings (the other event that reaches the same end state, the other side of a stack, the other host) need it too?
- **Claims against behaviour.** User-facing copy, privacy and permission text, the PR description, doc comments and public API names promise something: does the code do exactly that, on every path?
- **Re-implemented host path.** When the diff re-implements a flow that exists elsewhere (another host, the app vs an extension, the legacy path), compare timeouts, retries, failure handling, telemetry and analytics with the original line by line.
- **Test strength.** For every test the diff adds or changes: would it fail on the base, or with the new production line removed? A test that passes for a reason other than its name (a default flag, a spy that records nothing) is a P2 finding.
- **Synthesized conformances.** A synthesized `Codable`, `Equatable` or `Hashable` is a constructor and a comparison that ignores the type's own init, validation and invariants.
- **Teardown during an await.** A new `await`, callback or queued work must recheck every way its owner can end meanwhile: cancel, invalidate, teardown, release, a newer request or a replaced owner.

