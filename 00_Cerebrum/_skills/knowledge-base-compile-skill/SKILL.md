---
name: knowledge-base-compile-skill
description: "Compiles an archive layer of a 00_Cerebrum knowledge base into OKF concepts by dispatching batches of ~55 archive pages to parallel sub-agents, then merging what they hand back. Plans batches, packs them, runs up to eight agents concurrently, merges append-requests, writes the compile ledger, and measures coverage as the share of archive pages actually cited rather than asserted. Use whenever the user says \"compile the archives\", \"compile the [name] archive\", \"run a compile\", \"continue the compile\", \"read the rest of the archive\", or asks how much of an archive has actually been read. Also covers the routine ingest of new material into a live knowledge base, from its Raw/ folder and from a weekly OneNote export delta. \"Compile the archives\", plural, means every live knowledge base in turn and never a frozen one."
---

# Knowledge base compile

Reads an archive layer end to end and turns it into cited OKF concepts, and keeps a live knowledge base current afterwards. Built for archives too large to read in one session: Gamma (1'625 pages, 23 batches) and Beta (2'341 pages, 34 batches) went from partial coverage to 100 per cent this way on 15.08.2026, and Alpha — the archive this was written for — was rebuilt from nothing to 100 per cent on 22.08.2026 in nine waves, after its export was replaced.

**All four bundles are now at 100 per cent, so the common invocation is no longer the bulk pass.** It is the delta: a handful of pages a week. The bulk procedure below still stands, because an archive can be replaced again, but read *Compiling a live knowledge base* first — that is what "compile the archives" now usually means.

**Coverage here means the share of archive pages some concept actually cites, plus pages a compile agent opened and recorded as carrying nothing citable.** It does not mean "a concept exists for this scope". That older question is about the bundle, and it reported Alpha as fully compiled while 10'122 of its 10'561 pages had never been cited by anything. Every rule below exists to keep the measurement honest.

## When to invoke

- **"compile the archives"**, plural — every live knowledge base in turn. See the next section; this is the routine command.
- "compile the Alpha archive", "run a compile", "continue the compile", "finish reading the archive" — one named knowledge base.
- The user asks what share of an archive has actually been read, and the answer is "less than all of it".
- A live knowledge base's routine ingest, from `Raw/` or from a weekly export delta. **This used to say the opposite** — that the skill was for bulk archive layers only and not for routine ingest. That split made sense while the archives were mostly unread; now that they are all at 100 per cent it left the frequent case with no home, so ingest is in scope and has its own section below.

## "Compile the archives", plural

**It means every live knowledge base, one at a time, and never a frozen one.**

Liveness is not hardcoded here, and must not be. Each `<KB>/memory.md` declares it in its first screen; read that. The vault `CLAUDE.md`'s *Current state* table lists the knowledge bases, and its `Live?` column is the summary — but `memory.md` is the authority, because it is rewritten by every run that changes the answer.

| Knowledge base | State | Compile it? |
|---|---|---|
| _(read each `memory.md`)_ | live | yes |
| | frozen | **no** |

**A frozen archive is complete and closed.** There is no ingest cadence, no queue, and nothing arrives. A run that changes anything under one is a mistake rather than an update — so a plural invocation must not touch them, and must not report them as "compiled, 0 pages" either, which invites the next run to check again.

Plural is a sequence, not a merge. The scripts take one knowledge base per invocation and the concept namespaces are separate; run one to completion, close it out, then start the next.

## Where new material comes from

Each live knowledge base has its own sources, and they are not interchangeable.

Each live knowledge base's `CLAUDE.md` names its own. Record them here as you add knowledge bases, because a run that guesses will plan batches over the wrong folder:

| Knowledge base | Sources |
|---|---|
| _(name each one and where its new material lands)_ | |

**Not every archive folder is a compile queue.** A folder of static pages that no exporter feeds — kept because other bundles cite across into it — reads as 0 per cent covered in `COVERAGE.md`, and that is not a backlog to clear. Note such folders here explicitly, and do not plan batches over one without asking the owner.

## Before anything else

Read, in this order and whole: the knowledge base's `memory.md`, the vault `CLAUDE.md`, the knowledge base's `CLAUDE.md`. Then `00_Cerebrum/_COMPILE-RESUME.md`, which carries the current state of any paused run and the measured costs.

**Access note, and pass it to every sub-agent.** In some sandboxes the file tools return `EPERM` for the vault path and `Glob` returns nothing, while bash reads the same files cleanly — a filesystem-permission matter, and a property of the session rather than of the machine. Where that is the case, use bash for all vault access and say so to every sub-agent: an `EPERM` or an empty `Glob` is not evidence a file is missing, and only bash failing means the vault is unreachable. **Never run `git`** from a bridge or sandbox session; a bare `git status` takes `.git/index.lock`, which such a session cannot remove, and it wedges the owner's next commit. Read history only through `_scripts/git-read.sh`.

## Compiling a live knowledge base

The bulk pass reads an archive nobody has read. This is the other job: keeping a bundle current when a few pages a week arrive. It is cheap — usually one agent, sometimes none — and the whole risk is in *noticing* what arrived.

### New pages the planner finds by itself

`plan-batches.py` derives unread as *every page on disk minus (pages some concept cites ∪ pages the ledger records)*. It walks the filesystem fresh every run, so **a page that did not exist last week appears as unread with no bookkeeping**. Nothing needs to be told it arrived.

**Coverage falling after a sync is correct.** New pages enlarge the denominator, so `COVERAGE.md` drops below 100 per cent whenever the archive grows. That is the queue working, not a regression.

### Changed pages the planner cannot find

This is the gap, and it is the reason to read the export reports rather than just running the planner.

A page that a concept already cites counts as covered **whatever its content now says**. Rewrite it in OneNote and the planner stays silent. Only the exporter knows, and it says so in `<archive>/_CHANGELOG.md` and `_CHANGES-YYYY-MM-DD.json`:

```
rebuild        status in (new, modified) AND contentChanged
remove         status == archived
investigate    status == moved-or-deleted
ignore         everything else
```

**Key off `contentChanged`, not `status`.** OneNote bumps a timestamp for edits that leave the text identical; `contentChanged` hashes the prose alone, with frontmatter and asset names excluded.

**`_CHANGELOG.md` is the authority, not the JSON.** It gains exactly one line per run. A same-day re-run overwrites `_CHANGES-YYYY-MM-DD.*`, so a run's findings can vanish from the JSON while the changelog still records them — this has already happened once. Where the two disagree, trust the changelog and find the pages by frontmatter `modified`.

**Distinguish a quiet week from a dead job.** From inside the vault they look identical: nothing to compile either way. A new changelog line with all zeros means the job ran and found nothing. **No line for the expected sync means the job did not run** — say so plainly and do not report the archive as current. The per-knowledge-base `CLAUDE.md` carries the schedule and where the failure marker lives.

### What the pipeline cannot do to a changed page

**It appends and never edits.** Given a page whose content changed, an agent can add what the page now says. It cannot revise a sentence in an existing concept that the change made wrong, and appending beneath a wrong claim leaves both standing, with the wrong one first.

So a `modified` page with `contentChanged` needs a judgement the bulk pass never needs: does the new content *extend* the concept, or *contradict* it? Extension is an ordinary APPEND. **Contradiction goes to the owner** — named concept, named page, both readings — and is not resolved by appending over it. This limitation is why Alpha was rebuilt from nothing in August 2026 rather than patched: 98 concepts written from a twentieth of an archive could not be corrected by adding to them.

### Raw ingest

`Raw/` is the drop zone for anything that is not an archive layer: articles, PDFs, transcripts, testimony, screenshots.

1. **Register it in `Raw/_INGESTED.md` before citing it.** A source the register does not name is invisible to the next session.
2. **Raw is verbatim.** Never summarise, reword or translate on ingest; distillation happens at the Wiki layer.
3. **Do not reach for the batch machinery.** A handful of files is a direct read and a concept written or appended to. The eight-agent pipeline earns its overhead somewhere above fifty pages; below that it costs more to orchestrate than to do.
4. Owner testimony is a source like any other — `author: human:owner`, cited normally, and **it never licenses a `verified:` key**.

### The short loop

```bash
V=/path/to/00_Cerebrum; cd "$V"
tail -5 "<KB>/OneNote/<layer>/_CHANGELOG.md"   # did the sync run? did it find anything?
python3 _scripts/plan-batches.py <KB> --dry-run # new pages, found without being told
ls <KB>/Raw/                                    # anything dropped by hand
```

Zero unread, a changelog line of all zeros, and nothing new in `Raw/` means there is nothing to do. **Say that and stop.** Manufacturing a pass over a bundle that has not changed is how a corpus acquires concepts nobody needed.

## The bulk loop

**For an archive nobody has read**, or one that has been replaced. For a live knowledge base's weekly delta use the short loop above; this machinery costs more to orchestrate than a few pages are worth.

One wave is: plan, refresh inventory, pack, dispatch, merge, ledger, measure, verify. Then repeat until the planner reports zero pages unread.

```bash
V=/path/to/00_Cerebrum; cd "$V"
python3 _scripts/plan-batches.py <KB>              # what is unread, cut into batches
python3 _scripts/inventory.py  <KB>                # the concept list agents read
python3 _scripts/prepare-batch.py <KB> ID1 ID2 …   # pack up to 8; NEVER --no-collapse
#   … dispatch one agent per batch, concurrently …
python3 _scripts/merge-appends.py <KB>             # applies + archives + LOST WRITE check
#   … append each batch's nothing-citable pages to <KB>/_COMPILE-LEDGER.md …
python3 _scripts/coverage.py <KB>
python3 _scripts/verify.py <KB>                    # must be 0 defects
```

**Then the linking pass, before the wave is closed.** Count concepts with no inbound link and divide by the bundle size. Every mature bundle in this vault sits at or under 2 per cent — Alpha 2, Gamma 1, Beta 0, Delta 0. **Above about 5 per cent, run a linking pass**: one agent, no concurrency, editing existing concepts directly, adding links where a real relationship exists and cross-KB links where a sibling bundle covers the same subject from another side. `verify.py` already reports each such concept as a finding, so the measurement is free:

```bash
python3 _scripts/verify.py <KB> | grep -c 'no inbound link'
```

At the end of a run that changed concepts: `python3 _scripts/visualize.py` and `bash _scripts/viewer-check-sandbox.sh` green, then rewrite `memory.md` in place and prepend a `CHANGELOG.md` entry.

**Eight agents per wave.** More gains little and multiplies collisions. Four scopes across eight batches is better than eight batches of one scope: it spreads the concept namespace.

## What it costs

Measured 15.08.2026 with opus agents, one batch each:

| | Tokens | Pages |
|---|---:|---:|
| One batch alone | 160k | 55 |
| A wave of eight | 1.55–1.65M | ~440 |
| Whole Gamma archive, 23 batches | 4.71M | 1'625 |
| Whole Beta archive, 34 batches | 7.26M | 2'341 |

Alpha was rebuilt greenfield on 22.08.2026 — 2'596 pages, 9 waves, ~9M tokens. Greenfield runs dearer per batch, around 250k against 200k: with an empty bundle an agent writes many concepts instead of appending to existing ones.

About 200k per batch almost regardless of pack size — roughly a third is fixed orientation cost, so a bigger pack is cheaper per page. **A full re-read of any archive is a decision to put to the owner, not an assumption to act on.** A weekly delta is not: it is one agent or none, and needs no approval.

**Sleep is the binding constraint on a long run, not tokens.** Two Alpha waves were destroyed mid-flight when the machine slept, at roughly 200k per killed agent. Nothing already written was lost — concepts go down as `set -C` heredocs and are atomic, so re-planning shrank the remaining work rather than repeating it — but the reading was paid for twice. Before dispatching more than a wave or two, tell the owner to keep the machine awake.

## The agent prompt

This is the part that cannot be reconstructed from the scripts. Every clause below was paid for. Substitute the bracketed parts.

> You are a compile agent for the **[KB]** knowledge base. You compile ONE batch: **[BATCH-ID]**, [N] pages from `[SCOPE PATH]`. [Seven] other agents are running other batches concurrently right now.
>
> **ACCESS NOTE.** Include this line only where the file tools actually fail for the vault path: the Read/Write/Edit/Glob/Grep tools return EPERM here. **Use bash for ALL vault access.** Vault root: `[VAULT]`. An EPERM is not evidence a file is missing. Never run `git`.
>
> **Step 1 — the bulk reads, then work.** Read exactly these four and nothing else exploratory:
> `_extractions/_packed-[BATCH-ID].txt`, `_extractions/_INVENTORY.md` (the [N] concepts that already exist), `[KB]/CLAUDE.md`, `About me/writing-rules.md`.
> Reading a specific named concept you intend to append to is expected and is not exploration. **No `ls` sweeps, no `find` over the archive, no opening individual OneNote pages.** If the pack overflows the bash output cap, read it in `sed -n '1,400p'` windows rather than one truncating `cat`.
> One `=== PAGE <relative path>` header per page — **cite that path exactly as given**. `[+N lines carried, first in <file>]` means that content already appears elsewhere in the corpus: an item carried forward again, not missing information. A page that is almost entirely such markers is a duplicate, and the marker names its source.
>
> **[ARCHIVE HAZARDS — from the KB's CLAUDE.md and memory.md: date fields that lie, Kürzel maps, homonyms, redaction relationships, settled facts that must not be re-litigated. Name them explicitly. This section is what separates a good batch from a plausible one.]**
>
> **Step 2 — write, without clobbering.** [N] concepts exist and the bundle is [X] per cent compiled, so **[APPEND is often / usually the right answer]**. Check `_INVENTORY.md` before creating anything.
> Every concept file you create must be written with the no-clobber guard:
> ```
> ( set -C; cat > "$V/[KB]/Wiki/people/example-name.md" <<'EOF'
> ---
> ...
> EOF
> ) || echo "EXISTS — file an APPEND instead"
> ```
> If the guarded write fails the concept already exists: **do not remove it, do not retry without the guard, do not invent a variant filename.** Read the existing file and file an APPEND against it. **If you list such a concept under `## Concepts created`, also list it under `## Collisions`** — the merge preflight uses that to tell a guard working from a lost write.
> Frontmatter: `type`, `title`, `description`, `tags`, `status: draft`, `generated: { by: librarian/claude-opus-5, at: <now> }`, `sources` with `id` / `resource` / `title` / `author` / `last_modified`.
> **Quote any `title:` containing `": "` or that is a bare `YYYY-MM-DD`** — both break the concept's YAML.
> `../../OneNote/…` is right from `Wiki/<group>/x.md`; from `Wiki/systems/vendors/x.md` or `Wiki/references/digests/x.md`, one level deeper, it is `../../../OneNote/…`. Cross-KB links are `../../../Alpha_kb/Wiki/…` from `Wiki/<group>/x.md`, and **`verify.py` fails the run on a cross-KB link that resolves nowhere.** Inside APPEND blocks always write `../../OneNote/…`; the merge script re-resolves the depth.
> Every claim carries a footnote whose label equals a `sources[].id`. A label defined but never referenced is a defect; so is a reference with no definition. No `verified:` key, ever. No `stale_after` on a frozen archive. English prose, German quotes verbatim, proper nouns never translated.
>
> **Link every concept you write to its neighbours.** A bundle that is a list is worth less than one that is a graph, and links are cheapest to write while the pages are in front of you. A `Procedure` links to the system it operates on; a system links to what it depends on, replaces or configures; a person links to the projects and decisions they appear in. **Aim for roughly three links per concept**, in the body prose and never in frontmatter. A link to a concept that does not exist yet is legitimate under OKF and is a good way to mark what should be written next — but a **cross-KB** link that resolves nowhere is a defect, so check those with `test -f` before writing them. Do not invent a relationship to reach a number: a subject the archive genuinely documents in isolation may stay thin, and saying so in the body is better than a false link.
> **Never edit an existing concept.** Two writers in one file is a lost write.
>
> **Step 3 — the handback.** Write `_extractions/[BATCH-ID].md` in one heredoc with headings `# Batch [BATCH-ID]`, a one-paragraph summary, `## Concepts created`, `## Collisions`, `## Pages read, nothing citable`, `## Append-requests`.
> **Nothing-citable entries must be `- ` bullets with the path in backticks**, optionally with a reason after the closing backtick. The leading `- ` is load-bearing: the ledger and `coverage.py` both key on it, and a wave that wrote bare backticks had 27 honest reads extract as zero.
> ```
> ### APPEND Wiki/people/example.md
> #### SOURCES
> - id: kt-2017-03-14
>   resource: ../../OneNote/…/2017-03-14-….md
>   title: …
>   author: human:owner
>   last_modified: 2017-03-14
> #### SECTION Record
> | … | [^kt-2017-03-14] |
> #### FOOTNOTES
> [^kt-2017-03-14]: …
> ```
> `#### SECTION <name>` must name a heading that exists **verbatim in the target file** — check it, do not trust the type's declared shape; several concepts do not follow theirs, and at least one Timeline has no headings at all and cannot be appended to by section. Multiple SECTION blocks in one APPEND are supported. Every footnote label used must be defined in the same block and equal a `sources[].id` there. No APPEND for a concept you created in this batch.
>
> **Prohibitions.** Do not edit an existing concept. Do not touch `index.md`, `log.md`, `questions.md`, `memory.md`, `CHANGELOG.md`, `COVERAGE.md`, `_INVENTORY.md`, `_COMPILE-LEDGER.md` or `_extractions/_merged/`. Do not write under `OneNote/` or `Raw/`. Do not write into any knowledge base other than **[KB]**. No `verified` key. Do not repair a broken concept link — under OKF a broken link is legitimate. Do not run git. Do not regenerate the viewer. Do not run `verify.py` — the dispatcher runs it once for the wave.
>
> **Report back**, under 30 lines: pages read and their date window, concepts created, collisions, append-requests and targets, pages carrying nothing citable, names or shorthands you could not resolve, and anything the pipeline should know.

## The rules that cost something

Each of these was a real failure. Do not relearn them.

- **Compile agents do not link unless told to, and the graph is where it shows.** `Epsilon_kb` came out of ten batches with 100 concepts and 100 edges — 1.0 per concept against 4.4 in its sibling `Delta_kb`, which covers the same institution's Confluence from the other side — and 21 per cent of its concepts had nothing pointing at them, against 0 to 2 per cent everywhere else. It rendered as a wide empty disc with the links buried, because the layout is a force simulation and edges are what pull structure out of it. **Worse, the dispatcher had told every agent not to write cross-KB links "because the dispatcher adds those afterwards" and then never did**, so the bundle had not one link to any sibling. Owner's instruction of 31.08.2026: always do the linking, it is essential when compiling new data. If a prompt defers a step to the dispatcher, the dispatcher's checklist has to carry it.
- **Concurrency loses writes.** Two agents deciding the same person deserves a concept write the same canonical filename, and the second destroys the first. Six went that way before the `set -C` guard existed; none since. `merge-appends.py` prints `LOST WRITE` as a backstop, and ignores anything the agent declared a collision — a check that cries wolf gets skipped.
- **A page must never reach an agent empty.** Collapsing can strip every line, and the agent then honestly records the page as carrying nothing citable, which the ledger counts as covered. That is coverage-by-assertion wearing the pipeline's own vocabulary. `prepare-batch.py` sends a page whole below the novelty floor and prints how many; a large count means the batch overlaps something already compiled and wants re-planning.
- **Never pass `--no-collapse` on a real run.** It writes its own `-nocollapse` file precisely so a comparison cannot clobber the pack an agent is about to read.
- **Archive a merged batch in the same breath as merging it.** Left in place it re-applies: sources dedupe, SECTION prose does not. `merge-appends.py` does this now; it was a documented manual step and was skipped the same afternoon by the person who documented it.
- **Batch ids repeat across waves**, because the planner renumbers from what is still unread. Archived handbacks are suffixed, and **never pick one with `sorted(glob(…))[-1]`** — `NBeta-01.md` sorts after `NBeta-01-w4.md` because `.` is above `-`. Pick on mtime.
- **A manifest from a superseded plan is invisible and expensive.** The bridge cannot delete, so it sits there looking usable; packing one re-reads compiled pages. `prepare-batch.py` refuses an id absent from the current `_BATCHES.json`.
- **Refresh `_INVENTORY.md` before every dispatch.** An agent that cannot see a concept writes it again under a second name — the same failure as a lost write, arriving from the other direction.
- **A fix that nothing calls is a comment.** `resolve_resource()` sat written and unwired while nine citations landed unresolvable. Wire it, then prove it fires.
- **A ledgered page is invisible to the planner.** `plan-batches.py` counts *cited ∪ ledgered* as done, so a page recorded as read-with-nothing-citable will never be offered again — correctly, but it means a page wrongly ledgered is gone for good. When an export report names a page explicitly, include it by manifest rather than expecting the planner to raise it.
- **Indexes and the inventory are generated; regenerate, never hand-edit.** `reindex.py` also *creates* an index for a directory that has none — five Alpha directories holding 182 concepts had no `index.md` at all, and the staleness check could not see them because it only compares indexes that exist.
- **Watch for a settled fact regressing.** An append reintroduced a superseded claim and `assertions.yaml` failed the run. That is the system working; correct in place and keep going.

## Closing an archive honestly

The last batches are where the temptation is. Guard against it explicitly in the prompt.

- Pool the leftover tails of several scopes into one final `TAIL-01` batch rather than running batches of four pages.
- Tell the closing agent plainly: **its job is to close the archive honestly, not to reach a number.** A page that duplicates one already cited, or carries nothing, is a real finding. Gamma's closing batch created zero concepts and said so — on a closing batch that is the result, not a failure.
- When 100 per cent is reached, say in `memory.md` what it means: how many pages are cited against how many were opened and ledgered, and what the ledgered ones are (duplicates across sections, redacted copies, year dividers). **Coverage is a statement about reading, not about depth.** A page cited once counts the same as a page that produced a Decision.
- **Run the linking pass before the wave is closed**, and state the before-and-after in the CHANGELOG entry: concepts, edges, edges per concept, and the share with no inbound link. A compile that reports coverage without reporting connectedness is describing half the result.
- **Run `python3 _scripts/reindex.py <KB>` before the wave is closed.** Compile agents may not touch `index.md`, so a finished compile leaves every concept it added absent from its directory index — 116 stale entries in `Gamma_kb` and 149 in `Beta_kb` on 15.08.2026. The agent prohibition stays; the script does it afterwards, from the concepts' own frontmatter. Until that day the repair was manual and the guidance here was "a health check clears it in one pass", which is how 265 entries accumulated: a repair nobody automated is a repair that gets skipped. `reindex.py` never reorders an index — it refreshes descriptions, adds what is missing and drops what is gone — because three different orders are in use and each is deliberate.

## Replacing an archive under a compiled bundle

If the archive layer itself is to be swapped for a better export, run `_scripts/archive-fingerprint.py <KB>` **before** the old one is gone: it records a content fingerprint per page and every citation with the resource string as written. Afterwards `--match <old fingerprint> <new dir>` reports SAME / EDITED / MOVED / AMBIGUOUS / GONE per page, cited pages first. Keep both archives on disk until `verify.py` is green. Folder-level citations have no content to hash and must be checked by hand.
