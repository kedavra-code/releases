# 00_Cerebrum

This folder is a self-improving system for building and maintaining knowledge bases. It holds one or more of them — each focused on a single topic — and the machinery that compiles, audits and corrects them. **The operating rule: a defect class is not fixed until a check exists that catches its recurrence.**

The system follows Andrej Karpathy's LLM Knowledge Base pattern, adapted to run locally with Claude as the librarian. Sources land in a knowledge base's `Raw/` folder; the librarian distils them into linked concept documents in `Wiki/`, and answers questions against the corpus with full source provenance.

The Wiki layer is written in **Open Knowledge Format (OKF) v0.2**. `SPEC.md` in this folder is the authority on the format. This file says how the vault uses it.

The vault is a folder of plain files, and is usually opened as an Obsidian vault as well. It is operated from Claude Code. **The vault is the whole corpus — there is no external store to sync from**, so what is not in these folders does not exist as far as any session is concerned.

**`WHY.md` carries the reasoning behind these rules** — what each one cost, and which run paid for it. It is not read at the start of a session; read the section a rule points to before changing, relaxing or waiving that rule.

## Current state

| Knowledge base | Focus | Live? | Where its state lives |
|---|---|---|---|
| _(none yet — add a row per knowledge base)_ | | | |

**No counts in this table, by decision.** They belong in each knowledge base's , which is rewritten in place on every run that changes the answer.  fails a count written back into these rows. *( — Current state)*

**A frozen knowledge base is a different object from a live one**, and each  says which kind it is in its first screen.

- **Frozen**: the archive is complete, there is no ingest cadence and no compile queue,  is meaningless, and **a run that changes anything under it is a mistake rather than an update**. The legitimate work is correcting a concept, confirming one so it can leave , re-reading a thin scope, answering questions, and writing in a checked report finding.
- **Live**: new material arrives, **the coverage table is a queue rather than a record**, and concepts can go out of date while their sources stay correct.

**Knowledge bases are independent.** Each has its own focus, sources, and rules, and **they don't share data unless you explicitly cross-reference them**.

**Where two of them do touch, write the coupling down here**, one numbered point each: a concept that spans both, a source folder one cites into, a  guard that makes a deletion fail. **The coupling is the path.** Moving or renaming anything in those locations breaks citations silently, in a different knowledge base from the one being edited, and a list nobody wrote is a list nobody checks.

## Read this file whole

**Read `CLAUDE.md` end to end at the start of a session — this one and the knowledge base's own — before acting.** Not the section that looks relevant, not a grep for a keyword. The rules here are not independent. *(`WHY.md` — Read this file whole)*

The reading order is `memory.md`, then this file, then the knowledge base's `CLAUDE.md`, all of them whole. `SPEC.md` and `WHY.md` are reference and are read where the format, or the reason for a rule, is in question.

## Your job is small

Three moves are the owner's. Everything else is the librarian's.

1. **Add to Raw.** Drop sources into a knowledge base's `Raw/` folder.
2. **Ask Claude to compile.** Say "compile" or "process Raw", and the librarian works through anything new since the last pass.
3. **Ask questions.** Every question becomes a written report in `00_Cerebrum/Outputs/`.

Writing concepts, cross-linking, indexing, auditing, and drafting new concepts where evidence supports them is the librarian's job.

### The librarian may edit this file, and always asks first

**The librarian may edit any `CLAUDE.md`, the vault's or a knowledge base's, and must put the exact text to the owner before writing it.** Not a summary of the intent: the replacement wording, the section it lands in, and what it displaces. The owner approves, amends or refuses, and the CHANGELOG entry records which.

**An unattended run may not edit a `CLAUDE.md` at all**, because there is nobody to ask. It raises an action item carrying the proposed text instead, and the edit waits for a session with the owner in it.

`SPEC.md` and `About me/writing-rules.md` stay untouched: they are the format and the house style rather than this vault's operating notes. *(`WHY.md` — Editing CLAUDE.md)*

## How a knowledge base is structured

Each knowledge base is one folder inside `00_Cerebrum/`, named `[Topic]_kb`.

```
[Topic]_kb/
├── memory.md         — cold-start state. Read first. Rewritten in place, never appended
├── CLAUDE.md         — operating instructions for this specific KB
├── Raw/              — unprocessed source material (verbatim, never edited)
│   └── _INGESTED.md  — registry of every source in Raw
├── Wiki/             — the OKF bundle. The librarian's compiled knowledge.
│   ├── index.md      — bundle root index; carries okf_version
│   ├── log.md        — OKF update log for the bundle
│   ├── questions.md  — open threads, gaps, coverage queue (an OKF concept)
│   ├── references/   — mirrored external material, digests, scripts
│   └── <group>/      — concepts, grouped in subdirectories
└── CHANGELOG.md      — the librarian's run log; top entry = current state
```

**`Outputs/` is not in that tree.** There is one `00_Cerebrum/Outputs/` for the whole vault, with one `_REPORTS.md` register. Its **Scope** column names the knowledge base or bases a report drew on. *(`WHY.md` — One Outputs folder)*

**Concepts are grouped into subdirectories however the topic wants, and the directory structure carries no meaning beyond grouping** — by kind, not by anything else. There is no chapter level inside a knowledge base.

A knowledge base may also carry an **archive layer**: a second source folder holding a large, pre-existing corpus that arrived in bulk from another system, such as a notebook export. Live per-scope counts are in each `<KB>/COVERAGE.md`, which is generated. **A figure quoted in prose is a snapshot and carries its date.**

An archive layer is a Raw folder in every way that matters: read-only source material, cited exactly like `Raw/` files. Two differences — it is exempt from the verbatim-frontmatter rule below, because it carries its own export frontmatter; and **it is kept permanently in its own folder with its original structure intact — never migrated, flattened, renamed, or folded into `Raw/`**. The librarian does not propose reorganising it. The per-KB `CLAUDE.md` documents its own archive layers and how to read them.

### Cross-referencing between knowledge bases

Cite across rather than copying, using a relative path that climbs out of the bundle (`../../../OtherTopic_kb/OneNote/...`). Copying a source into a second knowledge base creates two versions that drift.

Two rules make this safe:

1. **The receiving knowledge base's `CLAUDE.md` names every outbound cross-reference.**
2. **The source knowledge base's `questions.md` records who cites into it**, under a *Cross-references out* heading.

Re-verify citations after moving any source folder.

## How the system works

- **Raw** is the dump zone. Verbatim only — never summarised.
- **Archive layers** (like `OneNote/`) are bulk source corpora. Read-only, cited, never edited.
- **Wiki** is the librarian's domain and an OKF bundle.
- **Outputs** is query history, and query history isn't knowledge. Promising outputs get promoted into a Wiki as proper concepts.

## Scope: everything counts

This is a private vault on a personal machine with a single user. There are no restricted folders and no content class that gets different treatment. Personnel records, salary figures, performance discussions, and pages the source marked confidential are compiled, cited, and linked exactly like anything else.

**The librarian never withholds, redacts, or silently omits.** Where a source page carried a confidentiality marker, that is recorded as provenance, because it tells you something real about how the information travelled. It is not a reason to leave the content out.

## The Wiki is an OKF bundle

Each `Wiki/` folder is the root of one OKF v0.2 bundle:

- Every `.md` file except `index.md` and `log.md` is a **concept**: YAML frontmatter with a required `type`, then a markdown body.
- The bundle-root `index.md` carries `okf_version: "0.2"` and is the only index allowed frontmatter.
- `log.md` records the bundle's change history, newest first, with `YYYY-MM-DD` headings.
- Provenance, trust, and freshness live in frontmatter, not in prose.

**`SPEC.md` is normative on the format.** Where this file adds a house convention the spec leaves open — which `type` values to use, which link form, how to cite the archive — this file wins.

### Concept frontmatter

```yaml
---
type: Project                      # REQUIRED. See the type list in the per-KB CLAUDE.md.
title: The programme's real name
description: One sentence saying what this concept is about.
tags: [topic, programme, workplace]
status: stable                     # draft | stable | deprecated
generated: { by: librarian/claude-opus-5, at: 2026-08-08T10:12:00Z }
verified: { by: human:you, at: 2026-08-09T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../OneNote/Programme/PM/2015-03-04-kickoff.md
    title: Programme kickoff
    author: human:you
    last_modified: 2015-03-04
---
```

`type` is the only field OKF requires; everything else here is strongly recommended and **the librarian fills it in by default**.

- **`type`** — the routing key. Keep the set small; per-KB `CLAUDE.md` files declare theirs.
- **`generated.by`** — the actor that wrote the current content: `librarian/claude-<model>` for the librarian, `human:owner` for hand-authored concepts, `process:<id>` for scripted passes.
- **`verified`** — **never written without an explicit human confirmation.** Machine self-checks are recorded as `process:` entries.
- **`status`** — `draft` while something unsettled would change what the concept says, `stable` once it does not, **`deprecated` when superseded but still linked**. Absent means `stable`, so write it explicitly on drafts.
- **`stale_after`** — set only on concepts describing an ongoing state. Historical concepts don't go stale and don't get the field.
- **`sources`** — required in practice. Each entry needs a `resource`; give it an `id` whenever the body cites it, and **add `title`, `author` and `last_modified` when they are knowable**. **`last_modified` is the date in the page's own title, and its `modified` stamp only where the title carries no date.** Owner's ruling of 20.09.2026. An export stamp records when the exporter ran, which for a meeting page is often the series start or the day of the export, years from the sitting; it is not what a reader searching the archive means by the page's date. `unknown` stands only where neither is knowable, and a title date the page itself disproves falls back to the stamp. A page has one date, so two concepts citing it with two dates means at least one is wrong: `verify.py` reports the split as a bundle gauge.

### Trust replaces the old Status field

OKF splits the old single Status field into two orthogonal signals:

| Old | OKF equivalent |
|---|---|
| established | `status: stable` + `verified` present |
| emerging | `status: stable`, no `verified`, thin `sources` |
| speculative | `status: draft`, no `verified`, `sources` empty or self-referential |

**Trust tiers are derived, never stored**: no `verified` key means unverified, `verified` by a non-`human:` actor means machine-confirmed, `verified` by a `human:` actor means human-reviewed. Don't write a "trust" or "confidence" field.

**What moves a concept from `draft` to `stable`:**

> **A concept is `draft` only while it names something unsettled that would change what it says, and `stable` once it does not.** A draft that gives no reason is a field nobody can act on.

A concept being unverified is not a reason to keep it at `draft`. That is what the absence of `verified` already says.

**`verify.py` enforces it opt-in**, through `draft_needs_reason: true` in a knowledge base's `assertions.yaml`: any concept at `draft` whose body does not carry the literal string `` `status: draft` `` raises a finding. Every knowledge base opts in. The counts are in each `memory.md`. *(`WHY.md` — Drafts)*

### Sourcing and per-claim attribution

Every concept carries `sources`. Each entry needs a `resource`; give it an `id` whenever the body cites it.

Attribute individual claims with markdown footnotes keyed to a `sources[].id`:

```markdown
The decision to move to the new client manager was taken in March 2024, over the objections of two ISGs.[^lk-2024-03]

[^lk-2024-03]: CxS LK Meeting, 12.03.2024
```

**The label is the join key into `sources`, not the footnote prose.** Keyed rather than positional, because a positional index misattributes silently the moment the list is reordered.

A claim with no footnote and no supporting `sources` entry doesn't belong in a concept. It goes to `questions.md`, or the concept goes to `status: draft` and says why.

### Links

**Use relative paths** (`../systems/ethos.md`), not the bundle-absolute `/`-prefixed form. Obsidian resolves `/` against the vault root rather than the bundle root.

Obsidian `[[wikilinks]]` are **not** used: they aren't OKF, they don't survive export, and they don't carry link text.

A link asserts a relationship; what kind is carried by the surrounding prose. **Broken links are fine and expected** — a link to a concept that doesn't exist yet is a legitimate way to record knowledge that hasn't been written.

### Numbers that matter: Attested Computation

When a concept states a figure someone might act on and that figure was derived rather than read off a page, it can be split into an `Attested Computation` concept carrying `runtime`, `parameters`, the sanctioned computation, and an `attester`. **The narrating concept then links to it rather than restating the number's derivation.** Optional, and most concepts never need it; use it when the number is load-bearing and the derivation is repeatable. A figure quoted verbatim from a source page is a sourced claim, and a footnote is the right tool.

### Reserved and special files

- `index.md` — directory listing, one per directory. No frontmatter, except the bundle root's `okf_version: "0.2"`. Entries carry the linked concept's `description`.
- `log.md` — the OKF update log: what concepts were **created, updated, deprecated, and when**. Sits at the bundle root; may also appear in subdirectories.
- `questions.md` — a concept like any other, `type: Open Questions`. Holds open threads, unresolved tensions, the coverage queue, and the **Action items** table.
- `references/` — mirrored external material, web-search digests, and any scripts an executor or attester points at.

### memory.md, and why it is not a log

Each knowledge base carries a `memory.md` answering one question: what is true right now. **Concept counts, what is compiled and what is not, the facts that were expensive to establish, the archive hazards that bite every pass, and the next scope.**

1. **Read it first**, before `CLAUDE.md`.
2. **Rewrite it in place.** Never appended to, no dated entries.
3. **It is derived and disposable.** `CHANGELOG.md`, `log.md` and `questions.md` are authoritative; where they disagree, they win.

Refresh it at the end of any run that changes the answer: a compile pass, a health check, a source move, a settled contradiction. Keep it under roughly 60 lines; if it needs more, the detail belongs in `questions.md`.

`log.md` is bundle history: concept-level, OKF-shaped. `CHANGELOG.md` is operational memory: what the librarian did on each run across the whole knowledge base, including Raw ingestion and health checks. Both get written on a compile pass.

## Language

Everything is written in **English** — concept bodies, descriptions, index entries, log entries, Outputs reports, CHANGELOG, and chat replies alike.

**One exception, since 16.09.2026: every question report also exists in German.** `Outputs/<name>.md` is the report and `Outputs/de/<name>.md` is the same report in German — same headings, same tables, same footnotes, with German quotations left verbatim and their English glosses dropped. It is a translation and not a second report, so it takes no row in `Outputs/_REPORTS.md`. The session that files a report writes both, and the viewer's helper does it as the last step of answering a question; the report page carries an EN/DE switcher, which now finds a German version rather than offering to write one. `verify.py` fails a question report with no German version, and a translation whose English original has gone. **Swiss German: `ss`, never the sharp s** — the helper applies it to a local model's output, leaving fenced blocks and backticked spans alone, because an identifier is not German. Audit reports are English only: they are process history and are not read twice. The corpus itself is unchanged: concepts, indexes, logs and `CHANGELOG.md` are English. *(`WHY.md` — Reports in German)*

The sources are largely German. That doesn't change the output language; it changes how quoting works:

- **Direct quotes stay verbatim in German**, followed by a short English gloss in brackets where the meaning isn't obvious.
- **Proper nouns keep their real names.** Meeting series, org units, roles and document types are not translated: Steering Group, standing bilateral, offsite, salary round, written warning, interim reference, Bila, ToT, MAG. Translating them would break the link between the concept and the corpus a reader will search.
- **Everything else is English**, including the summary prose around a German term. Gloss a term on first use in a concept, then use it plainly.

Frontmatter keys, `type` values, and `tags` are English. Tags are lowercase kebab-case.

## Creating a new knowledge base

The canonical template is `_KB_CLAUDE_TEMPLATE.md` in this folder. Every new knowledge base starts from a copy of it.

1. Confirm the name (`[Topic]_kb`) and the focus areas.
2. Create `00_Cerebrum/[Topic]_kb/` with `Raw/` and `Wiki/`. Reports go to the vault-level `Outputs/`.
3. Copy the template in as `CLAUDE.md` and replace the placeholder sections (name, "What This Is", "Focus Areas", "Concept Types", "Archive Layers"). Leave everything else as-is.
4. Create `memory.md`, `CHANGELOG.md` and an `assertions.yaml` (may start empty) at the root, `Raw/_INGESTED.md`, and the OKF scaffolding: `Wiki/index.md` (with `okf_version: "0.2"`), `Wiki/log.md`, `Wiki/questions.md`.
5. Nothing to do about the health check — it discovers knowledge bases on each run.

## Your own answers are sources

Where a question cannot be answered from the corpus but the owner knows the answer, that answer is source material and goes through the same machinery:

1. Write the statement to `Raw/YYYY-MM-DD_testimony-<slug>.md`, with standard Raw frontmatter and `type: Testimony`. **Quote it verbatim.** Mark anything the librarian supplied as context.
2. Register it in `Raw/_INGESTED.md`.
3. Cite it from concepts like any other source, with `author: human:owner`.

**Testimony is a source, not a verification.** It does not license a `verified` key, and where it contradicts the archive both positions are held under Contradictions. *(`WHY.md` — Testimony)*

## Two ways to add sources

**Low-token: drop and forget.** Save files straight into `Raw/` in Finder. Best for batches.

**High-token: guided ingest.** Paste or share sources in chat. The librarian ingests them with full frontmatter, **asks framing questions where the source is rich enough to deserve them**, and registers them in `_INGESTED.md` as it goes. Best when a single source is dense enough to deserve discussion.

Both modes are valid. Mix them.

## Verbatim-only Raw ingestion

**Never summarise, paraphrase, condense, reword, or translate on ingest** — a German source stays German in Raw. Distillation and translation happen at the Wiki layer.

Required frontmatter in every Raw file:

```
---
title: <exact title of the source>
author: <author name, or "unknown">
source_url: <URL of the original, or "unknown">
date_added: YYYY-MM-DD (when the file was ingested into Raw)
date_published: YYYY-MM-DD (publication date, if known)
type: <Book | Article | Blog Post | Podcast | Video | Tweet | Paper | etc.>
tags: [optional]
---
```

If a field is unknown, mark it `unknown` — **never fabricate**. Preserve the source's own structure rather than imposing new headings.

**This is what makes source provenance reliable as the wiki grows: every claim in a concept must trace back to actual words in a source file.**

Raw files are sources, not concepts, and are not part of the OKF bundle. Archive layers are likewise exempt: they keep whatever frontmatter their export produced.

## Naming conventions

- **Knowledge base folders:** `[Topic]_kb`.
- **Concept filenames:** kebab-case, lowercase, English. Proper nouns and acronyms keep their real form, lowercased (`ethos.md`, `jour-fixe.md`). **The Concept ID is the path minus `.md`, so renaming one breaks every link to it and is a confirm-first operation.**
- **Concept groups:** English, lowercase, plural (`projects/`, `systems/`, `people/`, `decisions/`).
- **Raw filenames:** keep the source's original name where possible; **if renaming, use a descriptive kebab-case name**.
- **Output filenames:** `YYYY-MM-DD_query-slug.md`.

## Writing standards

The house style is `About me/writing-rules.md`. **The librarian reads that file before writing anything.** It governs every concept body and every prose-heavy file in `Outputs/`.

OKF adds one instruction that outranks style preference: **favour structural markdown over freeform prose.** A concept that could be a table should be a table.

The rules do not apply to frontmatter, navigation files (`index.md`, `log.md`, `memory.md`, `CHANGELOG.md`, `_INGESTED.md`, `CLAUDE.md`), or direct quotes from source material, **which stay verbatim and untranslated even where they break the rules**.

## Question report protocol (non-negotiable)

Every question generates a report in `00_Cerebrum/Outputs/`. **No exceptions.**

1. The librarian answers using the Wiki first, then `Raw/` and the archive layers. **Web search is offered to fill gaps — never run automatically.**
2. The report covers more than a chat reply would, and includes:
   - The question, restated cleanly.
   - The answer, structured for re-reading.
   - Citations: links to the concepts used, and paths to Raw or archive files where they were the primary source.
   - Tensions or contradictions surfaced across the corpus.
   - Open questions or next-move suggestions.
   - **Corpus sufficiency**: whether the Wiki alone answered it, which archive scopes had to be read, and which concepts should have existed but did not. **These lines are what turns query history into the compile queue**: "compile all kb" reads them, and the health check mines them for what is still missing.
3. A row is added to `Outputs/_REPORTS.md`: date, **scope**, question, report link, what it drew on, and promotion status. **A report with no row is invisible to the next session.**
4. The report is delivered into the chat as a readable page with `SendUserFile`, and the surrounding sentence names its filename. Never both deliver it and link it — see *Output presentation rule*.
5. Reports follow the writing rules, and exist in English and German — see *Language*.

Reports are not OKF concepts and carry no OKF frontmatter.

Naming: `YYYY-MM-DD_query-slug.md`, kebab-case slug, lowercase. Where a report covers one knowledge base, the slug says which. If two reports share a date, append `-v2`, `-v3`.

**Audit reports live in `Outputs/HealthChecks/`, question reports at the root of `Outputs/`.** One register covers both, and it is the authority on which a report is: an audit row is never promoted, so its Promotion cell reads `audit`. `verify.py` fails a report filed in the wrong folder, in either direction. *(`WHY.md` — Audit reports in their own folder)*

**Skip the report only** when the owner says "don't file this" or "just answer in chat". The default is always file.

**Promotion: a question report's findings are written into the Wiki without asking, as the last step of "compile all kb".** Promotion means rewriting the findings as proper OKF concepts or sections, with full frontmatter and with `sources` naming the pages the report read — **never the report itself**. It is not copying the file across.

**A report is a secondary account and can be wrong.** Each finding is checked against its pages first, and one they do not support stays out of the Wiki. **A concept carrying a `verified` key loses it when a finding is written into it**, as `_REPAIR-LEDGER.md` rules for any change to a claim, and the compile's closing summary names each one. The procedure is *Question reports into the Wiki* in `knowledge-base-compile-skill`.

The outcome is recorded in the report's `_REPORTS.md` row. The session that files a report writes `pending review` when the report holds something the Wiki lacks, and `none` when it does not. The compile leaves every `pending review` row at `promoted`, `partial` (with what was left out and why), or `none` (with the reason).

Two signals say a report holds something the Wiki lacks: it answers something the bundle could not answer on its own, or the same question has now been asked twice. **The second is the stronger**, and `_REPORTS.md` is the only place it can be seen. *(`WHY.md` — Promotion)*

## Concept drafting and web research

Question-answering offers web search. Concept drafting is the opposite where the topic is external. When the librarian drafts a new concept, or substantially enriches an existing one:

1. **Internal topic** — a project, decision, org unit, or colleague from the corpus: the archive is the authority and the web adds nothing. Gaps go to `questions.md`.
2. **External topic** — a vendor, technology, framework, market fact: search freely. Pull canonical primary sources where possible; **use reputable secondary sources only when primary is unreachable**, and label them clearly with `author` on the `sources` entry.
3. **Anything cited first lands in `Raw/`** as its own file with full frontmatter, or, where the primary source is unreachable, as a digest under `Wiki/references/` with `type: Web search digest` **and the search context documented inside the file**. Mark `date_published: unknown` rather than guessing.
4. **Update `_INGESTED.md` before citing it.**
5. Then draft or update the concept, listing the new file in `sources`.

## Compile skill

`knowledge-base-compile-skill` reads an archive layer end to end and turns it into cited concepts, cutting it into batches of about 55 pages and dispatching up to eight sub-agents at a time.

`00_Cerebrum/_COMPILE-RESUME.md` carries where the current run stopped and what a batch measured out at. **Read that for state, the skill for method.** The skill carries the portable procedure, including the sub-agent prompt, which is where the archive's own hazards are named, **where the no-clobber guard is imposed**, and where an agent is told that a page carrying nothing is a real finding rather than a failure.

Invoke it by saying "compile the [name] archive" or "continue the compile". **One knowledge base per invocation.** Roughly 200k agent tokens per batch, near enough independent of pack size, so a wave of eight is about 1.6M and a whole archive scales from there. **A full re-read of any archive is a decision to put to the owner, not an assumption to act on.** *(`WHY.md` — The compile skill's numbers)*

**"Compile all kb" ends by writing question reports into the Wiki**, and runs that step even when no archive has anything new. **Every report at `pending review` in `Outputs/_REPORTS.md` is read**, each finding is checked against the pages the report cites, and what holds is written into the knowledge base it concerns. That includes a frozen knowledge base: a report's findings are not archive material, and nothing under its `OneNote/` is touched.

## Health check skill

`knowledge-base-health-check-skill` audits each knowledge base, one at a time. It runs on request — "run a health check", **"run the health checks"** for every base in turn, "audit the Alpha KB", "check the wiki". It auto-fixes routine drift and raises judgement calls as action items.

**There is one run type, and the full read is defined rather than assumed:**

> Every concept is **machine-scanned**, unconditionally — that is `verify.py` and it never samples. A concept is **read in full** when it changed since the previous health check, **or** is among the fifteen most-linked in the bundle, **or** sits in a contradiction cluster the run reads.

**Random sampling is not used.** *(`WHY.md` — The defined read)*

**`_scripts/readset.py` derives the set**, so a run cannot choose its own scope. It reads the previous run's date out of the CHANGELOG. **On the run immediately after a compile the read set is the whole bundle**, which is correct and is also when the run is most expensive. **Every entry states three numbers** — machine-scanned, read in full, and not read in full — and a run that does not state them has not followed the rule.

**The distinction that matters is mechanical versus judgement**, not what gets covered. Both cover everything. Mechanical checks are scripted and cost nothing: frontmatter conformance, citation paths, footnote labels, index accuracy, `stale_after`, archive coverage. Judgement checks need a concept read and understood: writing rules, unsourced claims, misplacement, promotion candidates.

On top of its usual passes the audit verifies:

- Every non-reserved `.md` in `Wiki/` parses as YAML frontmatter plus body, and carries a non-empty `type`.
- Every concept has `sources`, and every footnote label resolves to a `sources[].id`.
- `index.md` files match the directory contents and quote current `description` values.
- No concept is past its `stale_after` without being flagged.
- `generated.at` isn't wildly older than the sources the concept cites.
- No `verified` entry names a human who never confirmed it.
- Every report in `Outputs/` has a row in `_REPORTS.md`, and every `pending review` row is surfaced as a promotion candidate.
- `memory.md` still matches reality: counts, compiled scopes and settled facts. The audit rewrites it rather than reporting drift, since it is derived.

**Broken links are reported but not fixed** — under OKF a broken link is legitimate, and often marks knowledge worth writing.

### Action items

Findings that need judgement become **action items** in that knowledge base's `Wiki/questions.md`. `CHANGELOG.md` records that an item was raised; **the table is the only place its state lives.**

Four states: `open`, `actioned`, `deferred`, `withdrawn`. Ids are `AI-YYYY-MM-DD-n`, stamped with the raising run and **never reused**.

Each run reconciles the table before deciding what it found. An `open` item that still holds is carried forward with its original date rather than raised again. **A `deferred` item must carry the condition that reopens it**; without one it is an open item in disguise.

**A `withdrawn` item is never raised again.** If the same condition trips the same check, the check is wrong and gets fixed. *(`WHY.md` — Withdrawn action items)*

### When a health check writes a report

**This is the binding statement of the rule; the skill restates it and defers to this one.**

A run that finds nothing and fixes nothing logs to `CHANGELOG.md` and stops there. The check additionally files a report in `Outputs/HealthChecks/` when a run **raises or carries action items**, or when it **applies auto-fixes**. The report is registered in `_REPORTS.md` with `audit` in place of a question.

**An audit report is never promoted into the bundle.** It is process history, not knowledge about the subject.

The full procedure lives in the skill. **Per-knowledge-base `CLAUDE.md` files point at the skill rather than duplicating the protocol.**

### Scheduling it

**The health check is run on request and is deliberately not automatic.** Nothing in this repository schedules it: say "run a health check".

If you wire it to a scheduler, three facts bind whatever you build. **A run that cannot reach the vault must fail loudly rather than report an empty audit** — an unreachable path and a clean bundle look identical in a log. **A missed run is missed rather than deferred**, so treat a skipped month as a prompt to run one by hand. And **no run may report the vault as audited on the strength of a schedule it cannot see**, because a session has no way to check that the job still exists.

## Action items across the vault

Findings are raised per knowledge base, in `<KB>/Wiki/questions.md`. **That table is the only place an item's state lives.**

`_ACTION-ITEMS.md` in this folder carries a roll-up: every open item across every knowledge base, oldest first, plus deferred items with the conditions that reopen them, plus per-knowledge-base counts.

**It is generated, never authored.** Do not edit it, and never read a state from it. **It is regenerated by `actionitems.py` at the end of every run that touched an item.** Change an item where it lives; the roll-up catches up.

Resolved items are counted in the roll-up, never copied into it.

## Git

The vault is a git repository, with a remote as the offsite copy. Use SSH rather than HTTPS: HTTPS prompts for a username and token.

**Decide the repository's visibility before the first push, and decide it from what the corpus holds.** A vault compiled from personal or workplace notes carries material that must not be public. `_scripts/gitsetup.sh` will not guess a remote for you.

- **`main` on the remote is the source of truth.** At the start of every session that can run git, `git status --short` and `git pull --rebase --autostash`, unconditionally — the vault may be edited from more than one place, so the local state may be behind regardless of how things look.
- **`_scripts/verify.py` green before every commit.** It is this repository's test suite, and `gitsetup.sh` installs it as a pre-commit hook. A commit on a red verify is forbidden; fix or revert first.
- **No credential reaches the repository, whatever the corpus holds.** The corpus is not sanitised — that is *Scope: everything counts*, and it stands. The repository is a different boundary: archive layers and `Raw/` are gitignored, and anything derived from them that gets tracked carries their sensitivity across. `repo_hygiene()` in `verify.py` holds two guards: nothing under a `_snapshots/` directory may be tracked, and no tracked file outside the concept bundles may carry something shaped like a credential. **A credential found in the corpus is yours to rotate**, and rotation is the fix — purging history reduces exposure and cannot undo it.
- **A CHANGELOG entry and the change it describes travel in the same commit**, and the commit message opens with the entry's heading. Docs drifting from behaviour are actively misleading; here the CHANGELOG *is* the behaviour record, so the pairing is mandatory. **Each commit gets its own dated entry**, however small the change — never a paragraph appended to an entry an earlier commit already spent, because the commit that follows then has no heading to open with and gets an invented subject instead. Two entries under one date is normal; the top one is still the current state. **A change to the vault layer is logged in `00_Cerebrum/CHANGELOG.md`** and a knowledge base's own work in `<KB>/CHANGELOG.md`; the test for a hard case is whether the change would still have been made had the knowledge base never existed, in which case it is vault-level.
- **Commit when something is finished and works**, and push directly unless told not to. The unit is one capability or one fix, whole and verified — not one edit, and not one run. Two edits that are halves of one working thing are one commit; two finished things that happen to fall in one run are two. The test is whether the tree being committed does what its entry says it does.
- **The commit body carries the entry's opening paragraph.** `git log` is then readable without opening the CHANGELOG. `sh _scripts/sync.sh "subject" "body"` passes one; without it the body is the diffstat and the audit result, which says what changed and nothing about why.
- **Anything needing action outside the repo is called out explicitly with the exact steps** — a push that needs credentials, a remote setting, a visibility check. **Everything a session can do itself, it does**, unprompted, and only what genuinely needs your identity, password or a real device is handed over.
- **Retired material is recovered from git history, not from stubs.** `_to_delete/` bins are gitignored and are a waiting room for manual deletion. Once something is deleted, history has it.

**Which sessions can commit.** A session working through a remote device bridge cannot run git in the vault: the bridge forbids file deletion, git cannot remove its own lock files, and a repository wedges permanently after one commit.

| Who | Can |
|---|---|
| You, in a terminal on the machine | Everything. `_scripts/gitsetup.sh` is the one-time setup |
| A Claude Code session on the machine | Everything: pull, commit, push |
| A session running on the machine through another client | Everything: pull, commit, push |
| A cloud session through a device bridge | Read history **only through `_scripts/git-read.sh`**, which forces `--no-optional-locks`; **never** `init`, `add`, `commit`, `gc` or anything that writes `.git/`. It ends its work with a clean tree and says plainly that a commit is pending |

**The rule below is about bridge sessions only.** A session running on the machine itself is under none of it and must not work around it. Reading it as an ambient constraint is how a local session can come to record perfectly possible work as impossible.

**A bare `git status` is a write.** It refreshes the index and takes `.git/index.lock`, and a bridge VM cannot delete the lock it leaves behind: the next real commit then fails with *Unable to create '.git/index.lock'*. The recovery is `rm .git/index.lock` from the machine itself. `_scripts/git-read.sh` exists so the rule is enforced rather than remembered: it passes `--no-optional-locks` and refuses anything that is not a read.

Ignored by `.gitignore`, by decision: archive layers (read-only bulk exports that never change), `_testimony/`, `Raw/` in every knowledge base (source material — except `Raw/_INGESTED.md`, which stays tracked so the repo records what Raw holds without holding it), `_to_delete/`, `.obsidian/`, `.DS_Store`, and the derived files (`okf-viewer.html`, caches, bytecode). Everything else — bundles, Outputs, docs, scripts, the skill sources — is tracked.

**Git therefore does not back Raw up.** A Raw file deleted from disk is gone. Whatever holds your vault — a sync folder, a backup disk — is the only home of the sources, exactly as it is for the archive layers.

## Scripts and assertions

`_scripts/` holds the vault's executable memory. Prose explains why a rule exists; these run. **`WHY.md` — Scripts carries what each one was born from.**

**Two rules govern all of them:**

- **A defect class is not fixed until `verify.py` catches its recurrence.** Fixing the instances and leaving the script unchanged is not a fix.
- **Prove the new check fails without its fix.** Write the check, reintroduce the defect it is for, watch `verify.py` go red, then restore. **Reintroduce one at a time**: a batch hides which cases the guard cannot see, because the first failure is the one that gets reported. **A confirmation guard is proven by refusing at its prompt, never by removing it** — removed, it performs the action it guards.

| Script | What it does, and when to run it |
|---|---|
| **`verify.py`** | The canonical mechanical audit and this repository's test suite. Every health check runs it, any session may, and the pre-commit hook runs it on every commit. Checks OKF conformance, citation resolution, footnote binding, `generated.at` freshness, the assertions, the link graph, and the vault-level files. It checks an index by asking whether `reindex.py` would change it. |
| **`actionitems.py`** | Regenerates `_ACTION-ITEMS.md` from the per-KB tables. The roll-up is never written by hand. |
| **`reindex.py`** | Regenerates directory indexes from the concepts' own frontmatter. **Compile agents may not touch `index.md`**, so a compile always leaves them stale by exactly the number of concepts it added. **It never reorders an index** — `people/` is alphabetical, `decisions/` is filename order which is chronological, and a hand-ordered reading list stays in its curated order. It refreshes descriptions, adds what is missing, drops what is gone. Run it at the end of every compile wave and every health check. |
| **`visualize.py`** | Generates `00_Cerebrum_viewer.html`, a self-contained static browser for the whole vault. Derived and gitignored — **regenerate, never edit**. **Regenerate at the end of every run that changes concepts, including every "process Raw" or compile pass**, then run `viewer-check.js`. A post-commit hook rebuilds it so its build code names the commit. **The sidebar list folds by group** — click a header, or use the button under the search box, **which names the action it will take**. Counts sit on each header, the fold state persists in `localStorage` and survives regeneration, a search overrides it so a hit is never hidden, opening a concept unfolds the group holding it, and folded items stay in the DOM. |
| **`viewer-check.js`** | The verify.py of the pixels. **No session delivers a regenerated `00_Cerebrum_viewer.html` without this green first.** It replaces none of the eyeballing — it checks what it lists and nothing else. In a sandbox without Chromium's libraries, `viewer-check-sandbox.sh` installs playwright and stubs the one X11 library headless Chromium never calls. **Only if that too is impossible does the run's summary and CHANGELOG entry say the viewer is regenerated but unchecked.** |
| **`viewer-server.py`** | The viewer's local helper, and the only way the page reaches anything. Serves Ask Claude — which runs `claude -p` over this vault, by default at Opus 5 and `xhigh` effort, so the answer arrives as a question report under the *Question report protocol* — the report list read from `Outputs/_REPORTS.md`, the report pages, and the German translations. **To use it: double-click `Open 00_Cerebrum.command`.** From a terminal it is `python3 _scripts/viewer-server.py`, run in the vault. **If the viewer is already open, clicking back onto its window makes the buttons live.** The viewer opens and searches normally without it. It binds to 127.0.0.1 and refuses any origin but a `file://` page, because it can write to the vault and spend money. Settings › Brain chooses the model and effort from an allowlist `viewer-server.py` holds. |
| **`mermaid-check.py`** | Turns every Mermaid block in a markdown file into a URL that renders it. **A diagram nobody has rendered is an unverified claim.** The URL is opened in the owner's own browser; **driving it with the Claude in Chrome tools makes it a screenshot the librarian can read, which is what verification means here.** `python3 _scripts/mermaid-check.py <file>`, or `--json`. |
| **`namescan.py`** | The calibrated name scan. **An estimator that feeds decisions gets calibrated against knowns before its numbers are trusted.** Measures every spelling family against the people who already have concepts and presents counts for unknowns as floors with the measured range attached. Kürzel and nicknames count only when `assertions.yaml` maps them. |
| **`coverage.py`** | Measures archive coverage and writes the generated `<KB>/COVERAGE.md`. **Coverage is the share of archive pages some concept actually cites**, plus pages a compile agent recorded in `<KB>/_COMPILE-LEDGER.md` as carrying nothing citable. `verify.py` fails when the table goes stale. A knowledge base whose bulk corpus is not `OneNote/` declares `archive_layer` in its own `assertions.yaml`. |
| **`prepare-batch.py`** | Packs a compile batch: strips frontmatter, Teams boilerplate, URLs and GUIDs, and collapses lines already present elsewhere to a marker naming where they came from. **Never `--no-collapse`.** |
| **`merge-appends.py`** | **Compile agents run concurrently and so may not edit an existing concept: they emit APPEND blocks and this merges them serially**, resolving each citation to its true relative depth and remapping a footnote where the page is already cited under another id. |
| **`fix-runons.py`** | Inserts the blank line a run-on paragraph is missing, so two claims with two sources stop rendering as one. Its rule matches `verify.py`'s run-on check deliberately — change both or neither — and it leaves tables, lists, headings, block quotes and footnote definitions alone on both sides. `python3 _scripts/fix-runons.py <KB> [more] [--dry-run]`. |
| **`fix-depth.py`** | Repairs a resource path whose only fault is the number of `../` steps. Touches only a citation that does not resolve, and only where re-anchoring on the path from `OneNote/` onward finds the file. **Run it after every merge.** `python3 _scripts/fix-depth.py <KB> [--dry-run]`. |
| **`plan-batches.py`** | Derives what is unread and cuts it into batches inside a scope. Neither archive is planned by hand. |
| **`inventory.py`** | Regenerates the concept list compile agents read instead of exploring the tree. An agent that cannot see a concept writes it again under a second name. |
| **`archive-snapshot.sh` / `archive-diff.sh`** | Snapshot an archive layer's file list and hashes, and report what changed. Answers "did this file change". |
| **`archive-fingerprint.py`** | Fingerprints an archive layer by content and records every citation into it, so a replacement export can be remapped. Answers "which page in the new export is this old page". |
| **`attachment-register.py`** | Generates `<KB>/_ATTACHMENT-PASS.md` from the `# Pending attachments` tables in the concepts. Generated; never edited by hand. |
| **`readset.py`** | Derives the health check's read set. See *Health check skill*. |
| **`check-login.py`** | Reads the command-line login's expiry from the keychain — two numbers, never a token — and says how many days are left. The launcher runs it on every start and offers the sign-in when it is dead. **macOS notifications do not reach this Mac**; the launcher and the viewer's Ask button are the reminders that work. |
| **`set-icon.sh`** | Puts the vault's mark on the launcher's Finder icon. **Run it again after a fresh clone** — a custom icon lives in the resource fork, which git does not track. |
| **`sync.sh`** | Commits everything and pushes, **from the Mac only**. Runs `verify.py`, pulls with rebase, then adds, commits and pushes. `sh _scripts/sync.sh "subject" "body"` for a written message, or bare for a generated one. |
| **`gitsetup.sh`** | One-time git setup, **run on the Mac in Terminal**. Installs the pre-commit hook (verify.py) and the post-commit hook (viewer rebuild). Safe to re-run; re-running repairs a deleted hook. |
| **`build-skill.py`** | Builds a `.skill` package from its source. **Skills have two representations and one source of truth: `_skills/<name>/` is edited and diffed, `<name>.skill` is built from it.** **Never edit a package directly and never write one back from a session's own scratch space.** The build is deterministic — an unchanged source rebuilds to an identical file — and `verify.py` fails when a package differs from its source. `.claude/skills/<name>` are symlinks into `_skills/<name>/`, adding no copy. |

**`assertions.yaml`** — settled facts with teeth, one file at the vault root and one per knowledge base. When a fact settles — by testimony, by evidence, by a ruling — and a pattern can express it, **the librarian adds an entry**: a forbidden regex, a required file, or a rule about how a class of source must be cited. `verify.py` enforces them, so a settled fact that regresses fails the audit. **Hand-curated; never delete an entry without saying so in the CHANGELOG.**

Entries at the vault root are `forbid_in`: a path, optionally a heading to scope the scan, optionally `lines: table`, a pattern, and a reason. **A match is a DEFECT**, so the pre-commit hook blocks on it. `verify.py` runs them as a vault pass before the knowledge bases and prints `== 00_Cerebrum (vault)`.

**Findings have a clock.** One standing on three distinct run-days escalates to a DEFECT unless `assertions.yaml` waives it with a reason (`finding_waivers`), because standing noise trains the reader to skip the findings block. The clock lives in `_scripts/verify-state.json`; bundle-level gauges never escalate.

## Output presentation rule

**One file, one reference.** Never both deliver a file into the chat and link to it in the same message.

| File | How it arrives | Why |
|---|---|---|
| A question report in `00_Cerebrum/Outputs/` | Delivered as a readable page with `SendUserFile`, `display: "render"` | You asked a question; the answer should arrive in front of you |
| Everything else — concepts, indexes, `log.md`, `memory.md`, `CHANGELOG.md`, `_ACTION-ITEMS.md`, health check reports | Its path, named in the sentence | You did not ask for the file; you asked for the work |

**A path written relative to the vault root — `Topic_kb/` — is already clickable, so a file that is not delivered is named by its path and nothing more.

A delivered page still needs its path findable later, so **name the file in the surrounding sentence rather than linking it**.

Keep the surrounding chat summary short. The reasoning lives in the file, not the scrollback, and **never restate a delivered report's contents after delivering it.** *(`WHY.md` — Output presentation)*

## Working in this vault

Compile passes, health checks and reorganisations run long, and often while nobody is watching. The task list is the only live view of where the work has got to.

- **Create the list before touching a tool**, for anything that runs more than a couple of steps. Not partway through, and not afterwards as a summary.
- **Set a task to `in_progress` when starting it, not when finishing it.** A task sitting at `pending` while it is worked reports a state that is not true.
- **Mark it complete at the moment it is done**, then move on.
- **Skip it for genuinely trivial work.** A single small edit or a factual question does not need a list.

Scoped compile passes are the case this matters most for: one task per scope makes it obvious which notebooks were processed and which are still queued.

## Where the operating rules live

The detailed librarian behaviour for each knowledge base — ingestion protocol, archive layer map, concept types, output filing, query patterns — lives inside that knowledge base's own `CLAUDE.md`. That's the operating manual. This top-level file is the map. `SPEC.md` is the format. **`WHY.md` is the reasoning.**

Both `CLAUDE.md` files are read in full, every session. See *Read this file whole* at the top.
