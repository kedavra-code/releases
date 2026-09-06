---
name: knowledge-base-health-check-skill
description: "Audits knowledge bases in the 00_Cerebrum vault, where each Wiki folder is an Open Knowledge Format (OKF) v0.2 bundle. Checks conformance (frontmatter, type, sources, footnote labels resolving to source ids, index accuracy, stale_after), verifies every citation resolves, applies writing-rules fixes, rewrites memory.md, reports archive coverage, and flags promotion candidates from Outputs. Auto-drafts up to three new concepts where evidence supports them, and files an Outputs report when a run raises action items or applies fixes. Use whenever the user says \"run a health check\", \"audit the [name] KB\", \"audit my knowledge base\", \"check the wiki\", or whenever a scheduled task fires it. A plural request — \"run the health checks\", \"health check all knowledge bases\", \"audit the vault\" — sweeps every knowledge base in the vault, one concurrent audit each, and asks nothing first. Singular audits the one named."
---

# Knowledge base health check

Audits a knowledge base, or every knowledge base in the vault when the request is plural. Auto-fixes routine drift, verifies OKF conformance, rewrites the cold-start state file, drafts the strongest new concept candidates, and flags only judgement calls. Same procedure every run, on demand or scheduled.

## When to invoke

- The user says "run a health check", "audit the [name] KB", "audit my knowledge base", "check the wiki" — one knowledge base, the one named. If a singular request names none and more than one exists, ask which.
- The user says "run the health checks", "health check all knowledge bases", "audit the vault", "run a health check on everything" — every knowledge base. See *The sweep* below.
- The user says "action the latest health check" — that is the `knowledge-base-action-skill`, not this one. Hand over to it.
  This line said to walk the items "using numbered options in chat" until 22.08.2026. The owner's standing instruction is the opposite: clickable options, one item at a time, every answer recorded before anything is implemented.
- A scheduled task fires it. The monthly task is a sweep and runs it the same way.

**The plural is load-bearing.** A singular request naming no knowledge base is a question to ask; a plural one is an instruction not to. Asking which base to audit after being told to audit all of them is the failure this distinction exists to prevent, and it was the behaviour of this skill until 22.08.2026: the sweep existed only inside the monthly scheduled task, so a request to check everything by hand hit "operates on one knowledge base per invocation" and stalled on a question the owner had already answered.

## The sweep: every knowledge base in one invocation

**Discover the list; never carry one.** Every immediate subfolder of `00_Cerebrum/` holding a `CLAUDE.md` is a knowledge base. Reading that off disk on each run is what makes a base added later get audited without anyone remembering to update this file, and it is why the monthly task discovers rather than enumerates.

**Frozen bases are swept too, and this is where the health check parts company with the compile skill.** "Compile the archives" deliberately skips a frozen base: there is no new material to read, and a run that changes one is a mistake. Freezing has the opposite bearing on an audit. What drifts in a closed bundle is not the corpus but the machinery around it — an index a regenerated script now writes differently, a citation broken by a source folder moving in another base, a finding that has stood long enough to escalate. That drift is caused from outside the base, and the archive being closed prevents none of it.

What freezing does change is what counts as a finding. There is no ingest cadence, so the coverage table is a record rather than a queue, `stale_after` is meaningless, and a scope that has grown is itself the defect. Say that in the entry rather than reporting an empty queue as progress.

**One sub-agent per knowledge base, all dispatched in a single message so they run concurrently.** The procedure below is unchanged and each agent runs the whole of it against its own base. The boundary that holds is one knowledge base per *audit*, not one per invocation.

### What the orchestrator keeps for itself

Agents share nothing inside their own knowledge base and would collide on everything above it. Four things belong to the vault rather than to any base, and a concurrent write to any of them loses whatever the other agent wrote:

| What | Why an agent may not write it |
|---|---|
| `00_Cerebrum/Outputs/_REPORTS.md` | One register for the whole vault since 21.08.2026. Two agents appending a row at once keep one row |
| `00_Cerebrum/_ACTION-ITEMS.md` | Derived from every base's table, so it is only correct once the last agent has finished |
| `okf-viewer.html` | Renders the whole vault, so regenerating it mid-sweep captures a half-audited state |
| `.git` | One commit for the sweep, opening on one CHANGELOG heading |

So each agent **writes its own report file and returns its register row as text**, and the orchestrator appends the rows serially once every agent is in. This is the pattern `merge-appends.py` uses on a compile, for the same reason and against the same failure: concurrent agents may create, and may not edit what they share.

### Closing a sweep

After the last agent reports, in this order:

1. `python3 _scripts/actionitems.py` — the roll-up, once, never per base.
2. Append the returned `_REPORTS.md` rows.
3. `python3 _scripts/visualize.py`, then `node _scripts/viewer-check.js` where node exists. Deliver nothing that fails the check.
4. `python3 _scripts/verify.py` — green before any commit. It covers every base, so it is the sweep's own audit.
5. Commit and push if the session can run git, with one message opening on the sweep's CHANGELOG heading. A device-bridge session leaves the tree clean and says a commit is pending.

Then print one summary: the per-base one-liners as bullets, then the vault totals. Do not restate each base's findings in prose. The entries and reports hold them, and a sweep summary that repeats four audits is longer than any of them.

### The sub-agent prompt

Passed to each agent with `<full path>` filled in:

```
Run the knowledge-base-health-check-skill against the knowledge base at <full path>. Audit that base only. Apply all auto-fixes, rewrite memory.md, auto-draft up to three new concepts where evidence supports them, and log to that knowledge base's CHANGELOG.md and Wiki/log.md. Write an Outputs report to 00_Cerebrum/Outputs/ if the run raises action items or applies fixes. Do not web search on any internal topic. Do not pause for input.

Four things are the orchestrator's and you must not write them: 00_Cerebrum/Outputs/_REPORTS.md, 00_Cerebrum/_ACTION-ITEMS.md, okf-viewer.html, and anything under .git. If you filed a report, return the register row you would have added as a final line prefixed ROW:, and leave the appending to the orchestrator.

Return one line:
KB: <name> | concepts: N machine-scanned, N read in full | citations broken: N | auto-fixed: N | new concepts: N | held: N | action items: N new, N carried | report: <path|none> | clean: <yes|no>

If the skip-if-no-changes precondition fires, return:
KB: <name> | skipped (no changes since last check)
```

### The interview is prepared once, not once per base

An interactive sweep still ends with the monthly interview, and three to five questions is the budget for the whole sweep. Four agents each asking five leaves the owner twenty questions, which is how a mechanism that works gets abandoned. Collect the candidates every agent raised, then choose across the vault by what is actually blocked: a contradiction waiting on a ruling outranks a thin concept a memory could thicken, whichever base each sits in.

## Orientation: what this vault looks like

Read this before touching anything. The structure is specific and several obvious assumptions are wrong here.

```
00_Cerebrum/
├── CLAUDE.md                  vault rules. Never modify.
├── SPEC.md                    OKF v0.2, normative on format. Never modify.
├── About me/writing-rules.md  house style. Never modify.
├── _scripts/                  verify.py (the canonical mechanical audit) and actionitems.py (the roll-up generator). Run them; extend verify.py.
└── <Topic>_kb/
    ├── memory.md              cold-start state. DERIVED — this check rewrites it.
    ├── assertions.yaml        settled facts with teeth. verify.py enforces them.
    ├── CLAUDE.md              per-KB manual. Never modify.
    ├── CHANGELOG.md           append-only run log.
    ├── Raw/_INGESTED.md       source register.
    ├── OneNote/               archive layer. READ ONLY, never write, never propose moving.
    └── Wiki/                  the OKF bundle.
        ├── index.md           reserved. Not a concept. Root carries okf_version.
        ├── log.md             reserved. Not a concept. Bundle history.
        ├── questions.md       IS a concept, type: Open Questions.
        └── <group>/<chapter>/<concept>.md
```

Filenames are lowercase: `questions.md`, `index.md`, `Raw/`. macOS filesystems are usually case-insensitive, so wrong casing appears to work locally and breaks on a case-sensitive one; use the real names anyway.

**Concepts are grouped by kind, and optionally by chapter below that.** A chapter is a subdirectory per era, employer, client or product inside a group, used where one knowledge base covers several clearly separate ones. A concept spanning chapters lives at the group root, not in a chapter directory. Under OKF the directory carries no meaning; `tags` and `sources` carry the chapter.

**Ten things that are correct here and look like defects:**

1. **Broken concept links are legitimate.** A link to a concept that doesn't exist marks knowledge worth writing. Report them, never repair them, never delete them.
2. **`[[wikilinks]]` are not used.** Links are relative markdown. Never introduce a wikilink.
3. **There is no `Status: established | emerging | speculative` field.** Lifecycle is `status: draft | stable | deprecated`; trust is *derived* from `verified` and never stored. Do not add a trust or confidence field.
4. **Cross-knowledge-base citations are deliberate.** Six concepts in `Combined_kb` cite `../../../Private_kb/OneNote/...`. Resolve and verify them; do not report them as broken.
5. **Fenced code blocks contain illustrative examples.** Strip them before checking citations and footnotes, or `Wiki/references/_build-brief.md` is flagged every run.
6. **`memory.md` is derived.** Never report it as drifted. Rewrite it.
7. **Nothing carries `verified`.** Only a human confirmation creates that key. Never write one.
8. **`Raw/` may be empty.** The real source is the archive layer. Absence of Raw files is not a finding.
9. **The `**Term:**` bullet pattern is banned** by the writing rules as an AI tell. Never convert toward it.
10. **Files cannot be deleted on this device.** To retire something, move it to `<KB>/Wiki/_to_delete/` and say so.

## Procedure

1. **Sync the repository first, if this session can run git.** `git status --short`, then `git pull --rebase --autostash` — unconditionally, because the vault is edited from more than one place. **A session working through the device bridge must not run that command, or any other bare git.** Use `00_Cerebrum/_scripts/git-read.sh status --short` instead, which forces `--no-optional-locks` and refuses anything that is not a read.

   The reason is narrower than "no writes" and was learned the hard way on 15.08.2026: **a bare `git status` is itself a write.** It refreshes the index and takes `.git/index.lock`. The bridge VM cannot delete files, so the lock survives the session, and the owner's next commit fails with *Unable to create '.git/index.lock'* — three and a half hours later, in that case, with no obvious connection to the run that caused it. This step used to say "bridge sessions may read history and nothing more", which named the right danger and then listed the dangerous command as safe. Recovery needs `rm .git/index.lock` from the owner's own machine, so a bridge session cannot even repair what it broke.
2. **Read `<KB>/memory.md`.** It is the cheapest way to load state: counts, compiled scopes, settled facts, hazards, next scope.
3. **Read the rest of the state files.** `<KB>/CLAUDE.md`, the top block of `<KB>/CHANGELOG.md`, `<KB>/Wiki/questions.md` **including its Action items table, which is the only place a past item's state lives**, `<KB>/Wiki/log.md`, `<KB>/Raw/_INGESTED.md`, `00_Cerebrum/Outputs/_REPORTS.md`. Then `00_Cerebrum/CLAUDE.md` for vault rules and `About me/writing-rules.md` for the banned list.
4. **Skip-if-no-changes.** If the top CHANGELOG entry is itself a health check, with no compile pass, manual edit or new output since, append `## YYYY-MM-DD — Health check skipped (no changes since last check)` to the top of CHANGELOG and stop.
5. **Machine-scan every concept, and read in full the set `_scripts/readset.py` derives.** There is one run type; what changed on 15.08.2026 is what a full read means. See *The read rule* below.
6. **Run `00_Cerebrum/_scripts/verify.py` first.** It is the mechanical half of Audits 1, 2, 4 and 6 in executable form, plus the `assertions.yaml` checks. Then run the audits below, applying auto-fixes as you go, and re-run the script after fixing. When a run finds a new mechanical defect class, extend the script before closing: **a defect class is not fixed until verify.py catches its recurrence.** On its first run, 09.08.2026, it caught two classes the hand-written checks had missed. Since 10.08.2026 findings carry a clock: one standing on three distinct run-days escalates to a DEFECT unless waived with a reason in `assertions.yaml` `finding_waivers`. When the escalation fires during a health check, either fix the finding, or waive it and say why in the CHANGELOG — never waive to make the run green.
7. **Reconcile the Action items table.** See *Action items* below. Do this before writing anything else, because it decides which of this run's findings are new.
8. **Rewrite `memory.md`.**
9. **Write the CHANGELOG entry and the `Wiki/log.md` entry.**
10. **Write a `00_Cerebrum/Outputs/` report if this run qualifies.** See *When a run writes a report* below.
11. **Regenerate `00_Cerebrum/_ACTION-ITEMS.md`** if this run touched any action item. In a multi-knowledge-base run, once at the end, after every sub-agent has reported.
12. **If the run regenerated `okf-viewer.html`** (a compile changed concepts, or `_scripts/visualize.py` changed), run `node 00_Cerebrum/_scripts/viewer-check.js` where node exists and deliver nothing that fails it. The delivery rule lives in `00_Cerebrum/CLAUDE.md`; on a machine without node, say in the summary that the viewer is regenerated but unchecked.
13. **Commit and push, if this session can run git.** `verify.py` must be green; the message opens with the CHANGELOG entry's heading; the entry and the changes travel together. A bridge session leaves the tree clean and states in its summary that a commit is pending.
14. **Print the summary**, ending with a `computer://` link. If interactive and pending items exist, follow it with a numbered list and wait.

Prefer a script over reading files one by one. Audits 1, 2, 4 and the clustering half of 6 are mechanical and should be done with a single pass that parses frontmatter and bodies, not by eye.

## The read rule

There is one run type. What a full read means was redefined on 15.08.2026, and the history matters because this is the second correction to the same rule.

**First correction, 09.08.2026.** Earlier versions ran a delta audit most months and a full one quarterly, to save the cost of reading every concept. That was removed for three reasons. It had caused a real defect: the scope was written as though it governed everything, so a delta run would have verified citations only in changed files and a moved source folder could have gone undetected for a quarter. The saving was small and the sampling was weak — "three concepts sampled at random" was a poor substitute for reading and never had a principled basis. And some findings only appear across concepts, since duplication, overlapping coverage and misplacement are invisible when looking at a handful of changed files. The replacement rule was every run reads every concept, with the trigger for revisiting it stated as roughly 500 concepts.

**Second correction, 15.08.2026.** The trigger arrived early, and by size rather than count. `Gamma_kb` passed it at 219 concepts and 1.8 MB of body text, because a compile writes long concepts. The health check of that day read 21 concepts end to end and machine-scanned all 219 — so the run was already truncating, and the only thing making it visible was a CHANGELOG line naming what had been read. That is the honest version of the wrong thing, and it stays wrong until the rule changes.

So:

> Every concept is **machine-scanned**, unconditionally — that is `verify.py`, and it never samples. A concept is **read in full** when it changed since the previous health check, **or** is among the fifteen most-linked in the bundle, **or** sits in a contradiction cluster the run reads.

The three arms do different jobs. Changed-since catches new work, which is where fresh error lives. Most-linked catches the concepts where a wrong claim propagates furthest — a claim in a concept with 53 inbound links is one the bundle leans on. The cluster arm is the sweep Audit 6 already requires. None of them samples at random; that practice was withdrawn in August 2026 and is not coming back.

**`_scripts/readset.py` derives the set**, and exists so a run cannot choose its own scope: a run that picks will always pick what it had budget for. It reads the previous run's date out of the CHANGELOG, so the arithmetic is not a matter of memory. Every CHANGELOG entry states three numbers — machine-scanned, read in full, not read in full — and a run that does not state them has not followed the rule.

On the run immediately after a compile the read set is the whole bundle, because everything changed. That is correct, and it is also when the run is most expensive; budget for it rather than trimming it.

**Revisit this again if the machine scan itself stops completing.** The read arms are bounded by design; `verify.py` is the part that scales with the bundle.

**The distinction that still matters is mechanical versus judgement**, because it explains why some checks are scripted and some are read.

**Mechanical audits** are scripted, cost a second, and need no comprehension:

- Audit 1, frontmatter and conformance, including `stale_after` expiry and `generated.at` against source dates
- Audit 2, citation paths and footnote labels
- Audit 4, index accuracy, link resolution, inbound links and orphans, and the mentioned-but-never-written scan
- Audit 6, the shared-source clustering that produces the contradiction candidate set
- the `assertions.yaml` checks: settled facts expressed as forbidden patterns, required files and source rules, so a settled fact that regresses fails the audit

Run them with a single pass that parses frontmatter and bodies. Never do them by eye.

**Judgement audits** need a concept read and understood, so they cost real effort:

- Audit 3, writing rules
- unsourced claims that read as factual
- concepts misplaced across chapters
- Audit 6, reading each clustered pair for actual disagreement
- Audit 7, promotion candidates
- concept drafting

Both now cover the whole bundle. Report one number, the concept count, and say if anything was skipped and why.

## Audit 1 — OKF conformance

**Mechanical, scripted.** The primary audit. Every non-reserved `.md` under `Wiki/` is a concept.

- Frontmatter parses as YAML between `---` delimiters, followed by a body. **Parse it with a real YAML parser** (`yaml.safe_load` in Python), never with a regex over the lines. A regex reports a malformed block as fine, and worse, it reports every later check on that concept as fine too. Two defects survived four clean-looking runs this way: a `sources:` key deleted so its list dangled under `generated:`, and an unquoted `description` containing `: ` that ended the value early. Both are invisible line by line and obvious to a parser.
- A concept whose frontmatter fails to parse is a defect in its own right, and every other mechanical check on that concept is unreliable until it is fixed. Fix it, then re-run the whole audit rather than continuing past it.
- `type` present and non-empty. Unknown values are tolerated; a missing one is a defect.
- `status` present. Absent means `stable` per the spec, but this vault writes it explicitly.
- `sources` present and non-empty. `questions.md` is the only exemption.
- No `verified` key unless a prior CHANGELOG entry records the human confirmation that produced it. An unexplained `verified` is a serious finding: report it, never add one.
- `index.md` and `log.md` carry no frontmatter, except the bundle-root `index.md` which carries `okf_version: "0.2"` and nothing else.
- `generated.by` follows the actor convention: `librarian/claude-<model>`, `human:<id>` or `process:<id>`.
- Any concept past its `stale_after` is flagged. In a knowledge base holding financial positions, treat this as high priority: a stale rate is worse than no rate.
- **`generated.at` older than the newest `last_modified` in its own `sources`. Script this; do not eyeball it.** It means evidence was added to a concept without the concept being restamped, so every downstream freshness judgement is made against a date that is not true. Nine concepts carried this defect on 09.08.2026, all from the same cause: testimony sources dated that day were appended to concepts still stamped the day before. Auto-fix by restamping to the time of the edit that added the source.
- **A concept making a present-tense claim about an ongoing state, with no `stale_after`.** Search bodies for `currently`, `at present`, `to date`, `remains`, `still in use`, `as of today`. The house rule sets `stale_after` only on concepts describing a live state, so the absence of the field is a claim in itself: it asserts the concept is historical. A present-tense sentence contradicts that. Either the tense is wrong, and the claim should be pinned to its date, or the field is missing. Flag, do not guess which.

## Audit 2 — sourcing and provenance

**Mechanical, scripted.**

- Every `sources[].resource` path resolves on disk. Resolve relative to the concept's own directory. This is the check that catches a moved source folder, and it is the most valuable single check in the skill.
- Every footnote label used in the body has a definition, and every label resolves to a `sources[].id`. Strip fenced blocks first.
- Report `sources` entries whose `id` is never cited. Usually harmless, sometimes a dropped claim.
- Report claims that read as factual but carry no footnote, within the sampled set.

## Audit 3 — writing rules

**Judgement, read.** Load `00_Cerebrum/About me/writing-rules.md` and apply it. It is derived from Wikipedia's *Signs of AI writing* and is a hard constraint.

Check for: the banned vocabulary list, the banned phrase list, negative parallelism, the rule of three, trailing `-ing` analysis, false ranges, vague attribution, hedging used as cover, summary openers, title-case headings, curly quotes, emoji, more than one em dash in a prose paragraph, and the `**Term:** restatement` bullet pattern.

British English, not American. Swiss conventions: `1'500`, `CHF 4,500`, prose dates `12.03.2024`, ISO in frontmatter and tables.

Exempt: frontmatter, direct quotes from sources, and the navigation files `memory.md`, `index.md`, `log.md`, `CHANGELOG.md`, `_INGESTED.md`, `_REPORTS.md`, `CLAUDE.md`.

## Audit 4 — structure and navigation

**Mechanical, except the misplacement check, which is judgement.**

- Every `index.md` matches its directory's actual contents, and quotes each concept's current `description`.
- Concept filenames are kebab-case, lowercase, with umlauts transliterated.
- **Placement follows what a concept is about, not what it cites.** A concept belongs at the group root when its subject genuinely spans chapters. Citing another chapter's archive incidentally does not make it cross-chapter: a concept about one chapter's org unit may legitimately cite another chapter's page describing the role someone was moving to. Judge the subject, then check the citation mix as corroboration, never the reverse. A naive "cites more than one chapter" test produces false positives and was withdrawn after flagging a correctly placed concept.
- Flag genuine misplacements; do not move a concept without asking, because the path is the Concept ID and moving it breaks every inbound link.
- Broken concept links: count and list. Never fix.
- **Once per run, sweep the instruction files** — `00_Cerebrum/CLAUDE.md`, the template, each `<KB>/CLAUDE.md` — for restated rules. A rule living in two places with detail in both is the duplication-plus-edit hazard in the governance layer: the delivery rule needed five edits in one day because of it. Report restatements; the fix is one home and pointers.

### Inbound links and orphans

Outbound links have always been counted. Inbound links are the more informative direction and were not checked before 09.08.2026.

Build the link graph from concept bodies and report every concept with **zero inbound links from another concept**. **Exclude `index.md` files from the graph.** An index links to everything in its directory, so counting it makes every concept reachable and the check returns nothing, always.

An orphan is a finding, not a defect. Under OKF a concept stands on its own. But a concept nothing points at is usually one of three things, and they need different responses:

| Shape | What it usually means | Response |
|---|---|---|
| Rich outbound, no inbound | Written in a batch, never woven in | Propose the inbound links; the linking concepts exist |
| No links either way | Written from one source and left | Check whether it duplicates something, then propose links |
| A timeline or index-like concept | Correctly a hub; hubs point outward | Note and leave |

Nine of 108 concepts were orphaned on 09.08.2026. Report the list with its shape, propose links, and do not add them silently: a link asserts a relationship, and asserting one is a content decision.

### Mentioned but never written

The check that most reliably says what to write next. Concepts that exist but are unlinked are one problem; entities the corpus talks about that have no concept at all are a bigger one.

Scan concept bodies, excluding headings, table rows, footnote definitions and fenced blocks, for capitalised two-word name shapes. Drop any candidate already matching a `people/` filename after transliteration, and drop candidates where either word is a section word — `The`, `Outcome`, `Notes`, `Purpose`, `Participants`, a month name — since those come from sentence boundaries, not names. Report anything appearing in **three or more distinct concepts**.

**Count with `00_Cerebrum/_scripts/namescan.py`, or the counts lie.** The grep procedure this paragraph used to describe was wrong by an order of magnitude twice — Alex Fischer 153 reported against 198 standing (09.08.2026), Mila Roth 11 against roughly 200 (10.08.2026) — because each fix taught it one spelling family and each family revealed the next. The script measures instead: every family (full name, `Surname, Firstname`, `F. Surname`, first-name-only, mapped aliases) against the people who already have concepts, so every archive count for an unknown is presented as a floor with the calibrated range attached (10.08.2026: median 2.1x, p90 7.5x). Three rules ride along. **Aliases and Kürzel count only when the `aliases` section of `<KB>/assertions.yaml` maps them** — an unmapped shorthand is an interview question for the owner, never a count and never a silent attribution. **Aliases are chapter-scoped**: "Robin" is Robin Moser in one bundle and Robin Vogel in another. **First-name-only counts are ceilings, not floors**: unknown people share first names too.

Three or more concepts is the threshold that matters. A name in one concept is a passing mention. A name in four, with no page, is a person the corpus keeps needing and cannot link to.

The same scan surfaces systems and vendors alongside people. Separate the two buckets by hand; `Chris Keller` and `Exchange Online` have the same shape and different answers. Write the candidates into the *Concepts worth writing next* section of `questions.md` with their mention counts, and never auto-draft a person concept from mentions alone: a name appearing four times is evidence someone matters, not evidence of who they are.

## Audit 5 — archive coverage

**Mechanical, scripted.**

The archive layer is the real corpus. Report, do not modify.

- Compare the coverage table in `Wiki/questions.md` against the archive on disk. Report scopes that are uncompiled, partially compiled, or have grown since the last check.
- Give the largest uncompiled scope by page count. That is usually the single most useful line in the whole report.
- Never propose reorganising, migrating or renaming anything under the archive layer.

## Audit 6 — contradictions

**Clustering is mechanical; the comparison is judgement.**

Before 09.08.2026 the skill said what to do *when* two concepts disagreed and never went looking. Handling without detection finds only the contradictions that happen to be noticed while reading for something else.

Comparing every concept against every other is not affordable and not necessary. Two concepts can only contradict each other about something they both describe, and shared evidence is the cheap proxy for that.

1. **Cluster mechanically.** For every pair of concepts, count shared `sources[].resource` values. Pairs sharing **three or more** are the candidate set. On a 108-concept bundle this gave 94 pairs, which is readable; on a larger one, raise the threshold rather than sampling, and say in the report that you did.
2. **Read each pair for disagreement**, looking specifically at: dates for the same event, who held a role and when, whether something happened at all, sequence, and outcomes. These are where a corpus of meeting minutes actually contradicts itself.
3. **Do not harmonise.** Two well-sourced concepts disagreeing is a finding worth keeping. Add a line to each pointing at the other, and record the tension in the Contradictions table in `questions.md` with both positions and the evidence for each.
4. **Do not resolve from inference.** A contradiction between two sourced claims is resolved by evidence or by the vault owner, never by whichever reading seems more plausible. The MFA contradiction of 09.08.2026 was resolved against the position the owner initially asserted, because post numbering fixed the date, and the correction produced a better account than either side held.

Expect the top of the cluster list to be project-versus-timeline and person-versus-timeline pairs. Those are the concepts most likely to restate the same fact in two places, which is exactly where drift appears.

### A concept can contradict itself, and clustering will never find it

Self-contradiction needs no second document, so it does not appear in any pair. One instance was found only because a reader happened to have two concepts open and noticed one handling a claim more carefully than the other: a project concept asserted in one section that a board had demanded a control, and recorded four sections later that the claim was false.

So read each concept in the cluster **against itself** as well as against its pair. The shape to look for is a confident claim in a narrative section that a later *Open questions*, *Notes on dating* or *Contradictions* section corrects. Long concepts written in several passes are where this lives.

Fix by attribution, not deletion. "X said Y, and Y was false" carries more than either the false claim alone or its removal. In the case above, attributing it surfaced the actual finding: the Beta standard was set on an authority that did not exist.

### The reading queue, carried across runs

The candidate set is too large to read in one pass and will grow. Do not sample it, and do not silently read the top few. Keep an explicit queue.

- Record the full candidate list, the clusters already read, and the date each was read, in `questions.md`.
- Read the **next five highest-overlap unread pairs at minimum, every run**. "As many as the run can afford" turned out to mean zero: the backlog grew from 94 to 238 pairs across two days while nobody was scheduled to read cluster six (fixed 10.08.2026). Five per run is the floor, not the ambition.
- **State the arithmetic in the report every time**: clusters read this run, concepts covered, pairs still unread. On 09.08.2026 that was 5 clusters, 14 concepts, 89 of 94 pairs unread. A clean result on fourteen concepts is not a clean result on the bundle, and a report that does not say so is misleading.
- A pair once read is not read forever. Re-queue any pair where either concept has changed since the reading date.

### After any correction, check the coupled concepts

This is the rule that would have prevented both findings of 09.08.2026, and it applies to compile passes and question reports as much as to health checks.

**When a correction lands on a concept, immediately list every concept sharing three or more sources with it, and check whether the correction applies there too.** The MFA record was corrected on 09.08.2026 by the vault owner's own testimony. The project concept was rewritten. The decision concept, sharing fifteen sources with it, was not, and kept the disproven reading plus an inference built on top of it for the rest of the day.

A correction applied to one of a coupled pair does not half-fix the bundle. It converts a single error into a contradiction, which is harder to see and reads as two sourced positions rather than one mistake.

**While you are there, check verbatim duplication — but only then.** Alongside the coupled concepts, list the passages the corrected concept shares word for word with any other, and check each against the correction.

Duplication is not a defect and is not reported on its own. Concepts are meant to stand alone, so restating a fact in three places is correct under OKF, and a standing list of every repeated passage would be long, almost always harmless, and quickly ignored. It was ruled out as a standing audit on 09.08.2026 for exactly that reason.

What makes it dangerous is duplication plus an edit. One such cluster restated whole passages — a kickoff meeting described in four concepts, one licence figure in three, five people entries word for word between a programme concept and its successor. Each is a place a correction has to land more than once. So the check fires when a correction lands and at no other time.

## Audit 7 — outputs and promotion

**Register check is mechanical; promotion judgement is read.**

- Every report in `00_Cerebrum/Outputs/` has a row in `Outputs/_REPORTS.md`. Add missing rows. The register covers the whole vault, so filter to rows whose **Scope** names the knowledge base under audit.
- Rows marked `pending review` or `partial` are surfaced as promotion candidates in the pending bucket.
- A report whose synthesis exists nowhere in the bundle is a candidate. So is any question asked twice — the strongest available signal that a concept is missing.
- Mine each report's **Corpus sufficiency** lines. A question the Wiki could not answer alone names the concepts to write and the scopes to compile next; that is the compile queue, ordered by actual use rather than by guess.

## Auto-fixes, applied in place

- **Writing rules.** Unambiguous banned-word swaps. American to British spelling. Title-case headings to sentence case. Curly quotes to straight. Never introduce the `**Term:**` pattern; if a bullet uses it, rewrite as a table row or prose.
- **Index files.** Run `python3 _scripts/reindex.py <KB>`. It refreshes every description from the concept's own frontmatter, adds what is missing and drops what is gone, and **never reorders**: `people/` is alphabetical, `decisions/` is filename order which is chronological, and one bundle uses a curated reading order. `verify.py` checks an index by asking whether `reindex.py` would change it, which is stronger than the filename test it replaced on 15.08.2026 — that test passed seven truncated descriptions sitting in one index while reporting the bundle clean.
- **`_REPORTS.md` rows.** Add a row for any unregistered report.
- **`_INGESTED.md`.** Register orphan files in `Raw/` that carry valid frontmatter and fit the focus areas.
- **Footnote labels.** Where a label is an obvious typo of an existing `sources[].id`, correct it. Where it has no plausible match, flag it.
- **Contradictions.** Detection is Audit 6. When a pair disagrees, do not harmonise them. Add a line to each pointing at the other, and record the tension in the Contradictions table in `questions.md` without duplicating an existing row. Two well-sourced concepts disagreeing is a feature.
- **`generated.at` restamping.** Where a concept's `generated.at` predates the newest `last_modified` in its own `sources`, restamp it to the edit that added the source. Safe to apply without asking; the field records when the content was written and the older value is simply wrong.
- **Gap mirroring.** New gaps go into `questions.md`, without duplicating existing entries.

## Rewrite memory.md

`memory.md` is a compression of the authoritative files, so drift in it is not a finding: it is a stale derivation. Rewrite it in place at the end of every run, keeping it under roughly 60 lines and preserving these sections:

- What the knowledge base is, in two or three lines.
- Where it stands: concept counts by type, citations, compiled and uncompiled scopes, trust tiers.
- Settled facts. **Carry these forward. Never drop one without evidence that it was wrong** — each represents work already done, and losing one means a future session re-derives it or repeats the error.
- Archive hazards.
- Coupling: cross-knowledge-base citations.
- Conventions that are easy to get wrong.
- Next scope.

## Auto-drafted concepts

Up to three per run, from three streams: entities referenced by three or more concepts but never written, syntheses sitting unpromoted in `Outputs/`, and contradictions substantial enough to deserve their own concept.

For each:

1. Draft from the archive layer and `Raw/`. **If the topic is internal — a project, decision, org unit or colleague from the corpus — do not web search.** The archive is the authority; gaps go to `questions.md`.
2. If the topic is external — a vendor, a technology, a market fact — web search is expected. Save each source to `Raw/` verbatim with full frontmatter, or as a digest under `Wiki/references/digests/<chapter>/`, and register it before citing.
3. Write full OKF frontmatter: `type`, `title`, `description`, `tags`, `status: draft`, `generated`, `sources`. Never `verified`.
4. File it in the correct chapter directory, or at the group root if it spans chapters. Follow the concept shapes in the KB's `CLAUDE.md`.
5. Footnote every claim to a `sources[].id`.
6. Add the concept to the relevant `index.md` files and to `Wiki/log.md`.

If evidence is thin, do not fabricate. Log `Concept candidate held: <name> (insufficient evidence)` and move on. Surfacing a gap beats writing filler.

## Action items

Every finding that needs judgement becomes an action item with a state, recorded in the `# Action items` table in `<KB>/Wiki/questions.md`. `CHANGELOG.md` records that an item was raised; the table records what became of it. Without the table, an item raised in one run is invisible to the next, because the run only reads the top CHANGELOG block.

**States:** `open`, `actioned`, `deferred`, `withdrawn`.

**When the owner catches a defect between runs, the CHANGELOG entry recording it opens with "Caught by the owner."** The next health check counts those entries against its own findings. If the owner is finding more than the audit, the checks are pointed at the wrong layer — no amount of adding checks reveals that; only this ratio does.

**On the quarterly runs (January, April, July, October), aggregate the tags instead of only counting them.** Group every "Caught by the owner." entry since the last quarterly run by defect class — content, interface, process — and answer one question in the report: **which recurring class still has no executable check?** The tags are write-only memory otherwise. The first aggregation would have shown interface defects at owner four, audit nil, two weeks before that gap was noticed by hand (10.08.2026); the class that keeps appearing under the owner's name is the class the next check gets built for.

**Ids** are `AI-YYYY-MM-DD-n`, stamped with the run that raised the item, never reused.

### Reconciling, on every run

Before deciding what this run found:

1. **Read every existing row.**
2. **An `open` item that still holds is not a new finding.** Carry it forward unchanged and report it as carried, with the date it was first raised. Raising it again as new hides how long it has been outstanding, which is usually the most interesting thing about it.
3. **An `open` item that no longer holds becomes `withdrawn`**, with the reason.
4. **A `withdrawn` item is never raised again.** If the same condition trips the same check, the check is wrong. Fix the check and say so in the row.
5. **A `deferred` item reopens only when its stated condition is met.** Every deferred row must carry that condition; a deferral without one is an `open` item wearing a disguise.
6. **Only findings that survive this pass are new items.**

### Writing a row

Each row: id, raising run, the item in one sentence, state, and resolution. A resolution is not "done" — it says what was done, or why the item was withdrawn, or what condition reopens it.

**Withdrawn rows are the most valuable entries in the table.** They record what the audit got wrong, not what the corpus got wrong. A false positive that is not written down is rediscovered every quarter, and each rediscovery costs the same effort as the first.

### The vault roll-up, regenerated at the end of every run

Items are raised per knowledge base and acted on by one person with one queue. Both facts have to hold, so `00_Cerebrum/_ACTION-ITEMS.md` carries a vault-wide view.

**It is derived. Regenerate it; never edit it, and never read a state from it.** The state of an item lives in its own `<KB>/Wiki/questions.md` and nowhere else. A second file recording the same state is the drift this table was built to prevent — the same failure that made an item raised in one run invisible to the next.

Regenerate it at the end of every run that touched any action item, and whenever an item changes state outside a run. In a multi-knowledge-base run, regenerate once at the end, after every sub-agent has reported, not per knowledge base.

What it holds:

| Section | Contents |
|---|---|
| Needing you now | Every `open` item across all knowledge bases, oldest first, with age in days, the knowledge base, and one line on why it needs judgement |
| Waiting on a condition | Every `deferred` item with the condition that reopens it |
| Closed, counted only | Per-knowledge-base counts of open, deferred, actioned, withdrawn, and total raised |

Resolved items are counted, never copied. Their reasoning belongs beside the corpus it concerns, and a roll-up of everything ever decided is an archive rather than a queue.

Sort open items by age, oldest first. Age is the point of the file: an item raised four months ago and carried silently through four runs is the one worth seeing, and it is exactly the one a per-knowledge-base table buried in a long questions.md hides.

The header must say it is generated, say where to edit instead, and carry the generation timestamp and the list of knowledge bases covered. A derived file with no timestamp is indistinguishable from a stale one.

**Generate it from the tables, with a script. Never hand-write it, and never hand-write the timestamp.** On 09.08.2026 a hand-written roll-up carried a stamp of 14:30 against an actual write time of 14:06, in a file whose only safety property is that a reader can tell when it went stale. Parse the `# Action items` table in each knowledge base, derive every row and every count, and stamp the file with the real write time.

### A contradiction only the vault owner can settle is an action item

This is the failure that made the roll-up wrong on 09.08.2026, and it is worse than a stale file. A compile raised five contradictions, all correctly recorded in the Contradictions table of `questions.md`. None became an action item, so the roll-up reported "Needing you now: nothing" while three rulings were outstanding.

The Contradictions table records that two positions disagree. The Action items table records that somebody has to do something. **A contradiction needs both rows when resolving it requires a decision the corpus cannot supply** — the owner's memory, a ruling between two sourced readings, or a choice about which version the bundle should carry.

Not every contradiction qualifies. Two sourced accounts of a colleague's conduct can sit in the table indefinitely, because holding both is the honest answer and nothing is waiting on a decision. The test is whether anything is blocked. If the answer is "this stays open until someone says which is right", raise the item.

## Flag-only, pending judgement

Log in the pending bucket **and open an action item row**, unless reconciliation showed the item already exists. Do not auto-action.

- Raw material that looks out of scope or malformed.
- Promotion candidates from `00_Cerebrum/Outputs/`.
- Concepts whose sources have grown but where a rewrite would change voice or structure.
- Banned-word violations where the right replacement isn't obvious.
- Concepts that appear misplaced across chapters, since moving one changes its Concept ID.
- Any `verified` key with no recorded confirmation.
- Concepts past `stale_after`.

## When a run writes a report

**For the 00_Cerebrum vault the binding statement of this rule is `00_Cerebrum/CLAUDE.md`,** under *When a health check writes a report*. What follows is the same rule with the reasoning behind it, and it is what a vault carrying no such section should follow. Keep the two in step; where they differ, the vault file governs and this one is corrected.

**One report per run, never one per audit.** The report follows the run, not the finding. A health check that reads every concept and runs all seven audits produces a single report with a section per audit that found something — contradictions included. Seven audits do not make seven reports; that would scatter one run's reasoning across `Outputs/` and leave `_REPORTS.md` unreadable.

The exception is a run of one audit. When an audit is invoked on its own — "sweep for contradictions", "check the archive coverage" — that is its own run and gets its own report, named for what it was rather than for the health check it was not. The contradiction sweep of 09.08.2026 is one: it was asked for directly, so it filed `2026-08-09_contradiction-sweep.md` rather than appearing inside a health check report that never ran.

Either way the audit's own state lives in `questions.md`, not in the report. The contradiction reading queue, the action items table and the coverage table all survive independently of which report happened to mention them. A report is a snapshot; `questions.md` is the running state.

Not every run writes one. `CHANGELOG.md` is the audit trail and is enough for a run that finds and fixes nothing; duplicating it into `00_Cerebrum/Outputs/` would create two places to look for the same thing.

Write a report to `00_Cerebrum/Outputs/YYYY-MM-DD_health-check-<kb-slug>.md` when **either** condition holds. The folder is shared by the whole vault, so the `<kb-slug>` in the filename is what says which knowledge base was audited:

- the run raised or carried **one or more action items**, or
- the run **applied auto-fixes**.

Those are the runs carrying reasoning a CHANGELOG block would flatten: what a finding actually means, what the options are, why a fix was safe to apply. A run that finds nothing and fixes nothing has none of that and stays CHANGELOG-only.

The report is not an OKF concept and carries no OKF frontmatter. `Outputs/` is history, not knowledge. Structure it as:

- The run, restated: knowledge base, date, which audits ran, scope covered.
- Findings by audit, with the concrete evidence rather than counts alone. Audit 6 always states its arithmetic here: clusters read, concepts covered, pairs still unread.
- Each action item: its id, what it is, how long it has been open, why it needs judgement, and the realistic options.
- What changed, and what was deliberately left alone.
- What the next run should watch.

Then add a row to `00_Cerebrum/Outputs/_REPORTS.md` with the knowledge base in **Scope**, `audit` in place of a question, and promotion status `none` unless a finding warrants a concept.

Two rules that catch people out. A health check report is never promoted into the bundle just for existing: an audit is process history, not knowledge about the subject. And the writing rules apply to it, because it is prose in `Outputs/`.

## CHANGELOG entry format

Append at the top of `<KB>/CHANGELOG.md`:

```
## YYYY-MM-DD — Health check

Audit: N concepts machine-scanned, N read in full by the read rule, N not read in full. Citations checked: N, broken: N. Outputs reviewed: N.

Conformance:
- frontmatter: N concepts, N missing type, N missing sources, N unexplained verified
- footnotes: N unresolved labels, N unused source ids
- stale_after: N concepts past date
- broken concept links: N (reported, not fixed)

Auto-fixed:
- writing rules: N fixes across N files
- indexes: N regenerated
- _REPORTS.md: N rows added
- contradictions: cross-references added in <concept-a> and <concept-b>
- new concepts drafted: <path-a>, <path-b>

Coverage:
- compiled: <scopes>. Largest uncompiled: <scope>, N pages.

memory.md rewritten.
Report: <path, or "none — nothing found, nothing fixed">

Action items:
- new: <id> <one-line description>
- carried: <id>, open since <date>
- actioned: <id> <what was done>
- withdrawn: <id> <why>
```

If both buckets are empty, replace them with `Clean — no fixes, no pending items.`

## Wiki/log.md entry

Append at the top, under a `## YYYY-MM-DD` heading, one line per concept created, updated or deprecated by the run. Prefix `**New**`, `**Update**`, `**Deprecation**`. If the run created no concepts, add a single `**Update**` line naming the health check and the fixes applied.

## Summary format

```
Health check — <KB name>, <YYYY-MM-DD>

- Audit: N machine-scanned, N read in full, N not read in full
- Conformance: N citations checked, N broken | N unresolved footnotes | N past stale_after
- Auto-fixed: N | new concepts drafted: N | candidates held: N
- Coverage: largest uncompiled scope is <scope>, N pages
- Action items: N new, N carried, N actioned, N withdrawn
- Found since last run — by the owner: N, by this audit: N
- Vault roll-up: regenerated / unchanged (by `_scripts/actionitems.py`, never by hand)
- Git: committed <short-sha> and pushed / commit pending (bridge session)
- See CHANGELOG: <path>

[View the health check entry](computer:///absolute/path/to/CHANGELOG.md)
```

The `computer://` link is required by the vault's output presentation rule, and it points at the report when one was written, otherwise at the CHANGELOG. A summary with a bare path is the rule broken.

**One file, one reference.** Never link a file and also deliver it into the chat with `SendUserFile` in the same message. A `computer://` link renders as its own file card, so doing both shows one file twice, and the second card carries a save-destination prompt unrelated to the vault. A health check report and everything else this skill writes is **link-only**; only a question report is delivered as a page, and when it is, its filename is named in the surrounding sentence rather than linked.

If interactive and pending items exist:

```
Which action items would you like to walk through?
1. <category-a> (N items)
2. <category-b> (N items)
N+1. None — close out the review
```

Use `AskUserQuestion` with clickable options. This said the opposite until 22.08.2026 — plain numbered text, on the reasoning that it works reliably everywhere — and the owner's standing instruction replaces it: clickable options, one item at a time.

## The monthly interview

The highest-yield mechanism this vault has is the owner answering prepared questions one at a time: on 09.08.2026 it took seventeen open questions to zero and produced corrections no archive page held. So elicitation is scheduled, not incidental.

Every interactive run, and every monthly run's summary, ends by preparing **three to five questions only the owner can answer**, drawn in this order: contradictions waiting on a ruling, open action items, hypotheses in `questions.md`, and thin concepts that a memory could thicken. Ask one at a time with `AskUserQuestion`, clickable options, and room for a free answer. Skip the section only when nothing qualifies, and say so.

Handling the answers:

- Every answer is captured as testimony in `Raw/`, registered in `_INGESTED.md`, and cited like any other source. Testimony is a source, not a verification.
- **Harvest confirmations.** When an answer confirms a concept's content — the owner heard it restated and said it holds — ask explicitly: "mark it human-reviewed?" A yes sets `verified: { by: human:owner, at: ... }` and the CHANGELOG records the confirmation, which is exactly the recorded evidence Audit 1 demands before tolerating a `verified` key. Never infer the yes. 195 of 196 concepts are unverified drafts not because nothing is confirmed but because confirmations were being thrown away.
- **When a fact settles and a pattern can express it, add it to `assertions.yaml` in the same pass.** A settlement that is only remembered is one rewrite away from regressing; an asserted one fails the next audit instead.

## Boundaries

- **One knowledge base per audit.** A sweep runs several audits at once and is still bound by this: an agent auditing one base does not touch another, and the vault-level files stay with the orchestrator. See *The sweep* above. The bullet read "one knowledge base per invocation" until 22.08.2026, which was the right rule stated one level too high, and it blocked the sweep it was never meant to forbid.
- **`CLAUDE.md` is editable, and never without asking first.** Put the exact replacement text to the owner — the wording, the section it lands in, and what it displaces — then write it. An unattended run may not edit one at all, because there is nobody to ask; it raises an action item carrying the proposed text instead. Settled 15.08.2026, after a blanket ban produced three hand-overs in one evening and left the vault's only outstanding defect sitting in a file the librarian was forbidden to fix. `SPEC.md` and `writing-rules.md` stay untouched: they are the format and the house style, not this vault's operating notes.
- Never write into the archive layer or `Raw/`.
- Never write a `verified` key.
- Never repair a broken concept link.
- Never delete. Move to `<KB>/Wiki/_to_delete/` and report it.
- Never move a concept between directories without asking, since the path is its Concept ID.
- Never fabricate when evidence is thin.
- Direct quotes stay verbatim, in their original language, even when they breach the writing rules.

## Setting up the monthly scheduled task

First-time setup only. Once the task exists, this section is irrelevant: the task discovers active knowledge bases on each run, so adding more later needs no change.

### Schedule it from a session running on the user's computer, never from a cloud session

**This was tested on 09.08.2026 and the result is structural.** A scheduled task created from a cloud session was fired on demand. The session it opened had no `mcp__remote-devices__*` tools registered at all — not denied, not unauthorised, absent. A tool search returned no matches, so `get_device_info` could not even be called. It reported:

```
device bridge tools present: no
00_Cerebrum reachable: no
VERDICT: a scheduled run on this account CANNOT reach the vault unattended.
```

The reason is structural: a vault on a local machine is reachable from a cloud session only through a device bridge, and scheduled cloud runs do not get one. Retrying, rescheduling or moving the hour changes nothing; the folder is not merely disconnected, the whole mechanism for connecting it is missing. Create such a task from a session running on the machine itself, with the vault connected, and prove it runs before trusting it.

So: **do not create this task with `create_trigger` from a cloud session.** If you are reading this in a cloud session and the user asks for the monthly schedule, tell them what this section says and stop. Creating it anyway produces a task that fails identically every month and writes nothing, which is worse than no task, because the vault then looks audited and is not.

The working setup is a task running on the user's computer:

1. In the Claude desktop app, start a new Cowork task and set the **Run this task** picker, top right, to run on the computer rather than in the cloud.
2. Connect the vault folder in that session.
3. Ask for the monthly health check to be scheduled from there. That session reaches the vault directly, with no bridge in between.

The machine has to be awake at the firing time. A schedule cannot wake a sleeping Mac, so a run whose slot passes while the machine is off is simply missed. Pick an hour the machine is normally on, and treat a missed month as a prompt to run the check by hand rather than as a failure.

Parameters, once you are in a session that can actually do this:

- **Name:** `Monthly knowledge base health check`
- **Cron:** check which timezone the scheduler evaluates before choosing a value, and do not assume UTC. **On the 00_Cerebrum vault it is local time**, so `0 9 1 * *` means 09:00 Zurich and stays 09:00 through both halves of the year, with nothing to adjust twice a year. Earlier versions of this section gave `0 7 1 * *` as the UTC equivalent of 09:00 Zurich; entered into a local-time scheduler that fires at 07:00. If the scheduler is genuinely UTC, `0 7 1 * *` is 09:00 Zurich in summer and `0 8 1 * *` in winter, and the hour drifts.
- **The value in force for 00_Cerebrum is recorded in `00_Cerebrum/CLAUDE.md`,** under *The monthly scheduled task*, together with the evidence that the task was proven to run. That file is the single home for this vault's scheduling facts; this section is the portable procedure. When they disagree, `CLAUDE.md` is describing what actually exists and wins.
- **Notifications:** push on completion.

Prompt, passed verbatim. Every firing starts a fresh session with no memory of this one:

```
Your working folder is the vault at [VAULT].

First, confirm you can reach it: list the folder and check that 00_Cerebrum/CLAUDE.md exists. If it does not, stop immediately. Do not search for the vault elsewhere, do not troubleshoot, and do not write anything. Report one line — "Health check did not run: the vault was not reachable from this session" — and end. A run that cannot read the vault has nothing to audit, and a silent failure is worse than a loud one because the vault then looks audited and is not.

Once you have confirmed it, read 00_Cerebrum/CLAUDE.md so you understand how the knowledge base system works, and 00_Cerebrum/SPEC.md for the Open Knowledge Format the Wiki folders use. Scheduled runs open a fresh session with no folder context, so this re-anchoring matters.

Then run the knowledge-base-health-check-skill as a sweep across every active knowledge base, following its section "The sweep: every knowledge base in one invocation". That section carries the discovery rule, the sub-agent prompt, the files an agent must not write, and the closing sequence.

This is an unattended run, so two things differ from an interactive sweep: do not pause for input at any point, and edit no CLAUDE.md — raise an action item carrying the proposed text instead, because there is nobody to ask.

Collect the one-line summaries.

Then print one completion comment in chat. This is the only report; nothing is pushed anywhere else.

**Monthly knowledge base health check ran.**

<total> knowledge base(s) audited, <skipped> skipped. <broken> broken citations found across all. Auto-fixed <total> items. Drafted <total> new concepts. <P> knowledge base(s) have pending judgement items.

Per knowledge base:
- <each sub-agent's one-line summary as a bullet>

CHANGELOGs:
- <path to each CHANGELOG.md>

Say "action the latest health check" to walk through any pending items.
```

**The task stored in the scheduler predates this rewrite and does not need re-creating.** Its prompt restated the orchestration inline; this one points at the skill instead. Both open the same skill in the same vault and reach the same procedure, so the stored copy is verbose rather than wrong. Replace it only if the task is being rebuilt anyway. The reason for the change is the vault's own rule about a rule living in two places: the inline copy and *The sweep* would have had to be edited together, and the one nobody was looking at is the one that would have gone stale.

Broken citations are the number to watch in that summary. The bundle held 0 across 958 citations on 09.08.2026, so any non-zero figure means a source moved or a path was written by hand.
