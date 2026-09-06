---
name: knowledge-base-action-skill
description: "Walks the open action items across every knowledge base in the 00_Cerebrum vault and turns them into applied changes. Gathers and reconciles the item tables, groups items into decisions, interviews the owner one decision at a time using clickable options, records every answer verbatim as testimony, and only then implements everything in one pass, closing with the full regeneration and a green verify.py. Use whenever the user says \"action the health checks\", \"action the latest health check\", \"action the action items\", \"walk me through the open items\", or asks what is still open across the vault."
---

# Action the health checks

The health check *finds*. This skill *decides and applies*. Run it after a health check, or any time open items have accumulated.

Derived from the sitting of 22.08.2026, which walked 21 items across four knowledge bases and then a further five raised by the work itself.

## The four rules the owner set

These are standing instructions, not defaults to re-derive each time.

1. **All of them, one by one.** Not a summary, not a batch. Every open item gets its own turn.
2. **Clickable options.** Use `AskUserQuestion`, never numbered text. This overrides the health-check skill's own wording, which predates the instruction.
3. **Record every answer first, implement at the end.** Interview to completion, then apply everything in one pass. Do not implement between questions.
4. **Answers are testimony.** They go verbatim into `_testimony/YYYY-MM-DD_testimony-action-items.md` and are cited like any other source.

## Procedure

### 1. Gather, and reconcile before you count

Read the `# Action items` table in every `<KB>/Wiki/questions.md`. That table is the only place an item's state lives; `_ACTION-ITEMS.md` is generated and must never be read as a source.

Before deciding what is open, check each item against reality rather than against its own row. **Items go stale in both directions**: on 22.08.2026 two were still marked `open` after the same session had implemented them, and one marked `open` had been fixed by an unrelated repair earlier the same evening. Verify, then count.

A `withdrawn` item is never raised again. If the same condition trips the same check, the check is wrong and gets fixed.

### 2. Group items into decisions

Several items are usually one problem seen from three bundles at once. Group them. Twenty-one items became seven decisions on 22.08.2026, and the grouping is what made the sitting finishable.

Order the decisions so that anything blocking other work comes first.

### 3. Read the evidence before writing the options

**This is the step that decides whether the sitting is any good.** Open the files, count the instances, look at the actual lines. An option written from an item's description will be abstract, and an abstract option gets a guessed answer.

Three times on 22.08.2026 reading first changed the question itself:

- "28 concepts need per-case judgement" turned out to be 26 concepts of one mechanical shape plus 2 of another, and 209 of the 212 rows were repairable by script.
- "Rotate a credential in a read-only archive" turned out to be a credential committed to git and pushed to GitHub, because a fingerprint script wrote page text into a tracked file.
- "Two table faults" turned out to be one fault plus one class that a repair earlier the same evening had already cleared.

Measure before you offer. Say the real number.

### 4. Ask, one decision at a time

`AskUserQuestion`, two to four options. Put the recommended option first and mark it `(Recommended)`.

- **Every option must be one you would actually implement.** No straw men.
- **Always include the honest do-nothing option**, with its real consequence stated — "escalates to a DEFECT on the third run-day and blocks commits".
- **State what each option costs**, not just what it does.
- The owner regularly takes an option nobody offered. `AI-2026-08-22-4` was answered with a fourth route — repair, keep the `verified` key, and record what changed — which became `_REPAIR-LEDGER.md`. Leave room for that and treat it as a good outcome.

Do not implement anything yet. Do not summarise the previous answer at length. Ask the next question.

### 5. Record the testimony

Write `_testimony/YYYY-MM-DD_testimony-action-items.md` with the standard Raw frontmatter and `type: Testimony`. Questions paraphrased, **answers verbatim**. Register it in the relevant `Raw/_INGESTED.md`. Cite it from the item rows.

### 6. Implement, all at once

Now apply everything. Task list first, one task per decision.

Where the work splits cleanly across knowledge bases, parallel sub-agents are the documented pattern. Give each the no-clobber rule and the access note.

Two constraints that bite here:

- **Where the file tools cannot read the vault, bash can.** In some sandboxes `Read` returns `EPERM` for the vault path while bash reads it cleanly. Where that happens, use bash for everything and tell every sub-agent the same.
- **Never run bare `git status`.** It takes `.git/index.lock`, which a bridge session cannot delete, and the owner's next commit then fails. `_scripts/git-read.sh` is the only git a session may run.

### 7. Close out

Every one of these, every time:

```
python3 _scripts/actionitems.py      # the roll-up
python3 _scripts/reindex.py          # indexes from frontmatter
python3 _scripts/inventory.py        # the concept list agents read
python3 _scripts/coverage.py         # archive coverage
python3 _scripts/visualize.py        # okf-viewer.html
bash    _scripts/viewer-check-sandbox.sh
python3 _scripts/verify.py           # must end green
```

Plus: a CHANGELOG entry per file that changed (vault-level in `00_Cerebrum/CHANGELOG.md`, bundle work in `<KB>/CHANGELOG.md`), a `log.md` entry per bundle, `_REPAIR-LEDGER.md` for any body touched in a `verified` bundle, and every item row updated where it lives.

The commit is the owner's: a bridge session must not write git. Give the exact commands and stop.

## What the sitting keeps getting wrong

Encoded because each of these cost a correction on 22.08.2026.

**A closed item is not a queue.** Anything deliberately held during a pass needs its **own item, raised at the moment the pass closes**. Recording it inside the item being closed hides it, because an actioned item stops being read. This is the shape that left five duplicate pairs unread for a week under a heading called *Owner decisions waiting*.

**Check before answering "is it done".** Asked that question directly, the honest answer came only from re-reading the tables and the registers, and it was no — three loose ends lived only in closed items or in chat.

**Calibrate a new check before trusting it.** The first secret scan raised 33 hits and one was real; the other 32 were German CamelCase page titles and base64 Outlook ids. A check that reports 32 false positives to find one real hit teaches the reader to skip the block. Measure the false-positive rate, then tighten, then ship.

**A guard against a leak must not be the leak.** Asserting that a particular passphrase never appears would put the passphrase into `assertions.yaml`, which is tracked. Match on shape, never on the value.

**A defect class is not fixed until a check catches its recurrence** — the vault's own rule, and the one most often half-done. Fixing instances and leaving the script unchanged is how a class comes back. Twice on 22.08.2026 a guard written against the instance in front of someone caught that instance and nothing adjacent: a first-person check that enumerated twelve phrases and missed every past tense, and a counts-in-prose rule that matched one phrasing of a percentage and missed the rest. **Both fixes replaced an enumeration with a shape.** Prefer a shape.

**Some items cannot be closed by any run.** A credential to rotate, a git history to purge, a `CLAUDE.md` edit in an unattended run. Say so plainly, give the exact commands, and leave the item open. Do not mark it actioned because the vault's half is done.

**`SPEC.md` and `About me/writing-rules.md` are outside the consultation rule.** A `CLAUDE.md` may be edited after putting the exact text to the owner. Those two may not be edited at all without his explicit instruction — and when he gives it, the edit does not become a standing permission.

**Keep the chat short.** The reasoning belongs in the files. The owner asked twice on 22.08.2026 for less text. One or two sentences on the outcome, then the commands.
