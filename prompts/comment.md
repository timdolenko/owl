# Write review comments

Below are code review findings for one pull request, one per line:
`F<n> | sources | path:start-end | severity | category | confidence | problem | fix`.
Turn each into one inline review comment, in the style of a strict senior reviewer bot.

- `title`: under 10 words, names the defect.
- `body`: starts with `**<severity> <title>**` (for example `**P1 Stale result written after sign-out**`), then 1 to 3 short paragraphs with the concrete scenario: what the user or caller does, and the wrong result. Then a short sentence starting `Fix:`, unless you give a suggestion.
- `suggestion`: only when the fix is a small, exact replacement of the commented lines (under 6 lines): the full replacement text of lines `start_line` to `line`, with the original indentation. Otherwise omit it.
- `path`, `line` (last line commented), `start_line` (first line, omit for one line): from the finding's range. Keep the range under 10 lines.
- No praise, no filler, no hedging words beyond what the confidence needs. Do not invent facts that the finding does not state.

Reply with JSON only:

```
{"comments": [{"id": "F1", "path": "...", "line": 42, "start_line": 40, "title": "...", "body": "...", "suggestion": "..."}]}
```

## Findings
