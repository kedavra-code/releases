# 00_Cerebrum

This folder is a self-improving system for building and maintaining knowledge bases. It holds one or more of them — each focused on a single topic — and the machinery that compiles, audits and corrects them. The knowledge bases get better the longer they are used. The machinery gets better every time it fails, because the operating rule is that a defect class is not fixed until a check exists that catches its recurrence.

The system follows Andrej Karpathy's LLM Knowledge Base pattern, adapted to run locally with Claude as the librarian. Sources land in a knowledge base's `Raw/` folder; the librarian reads them, distils them into linked concept documents in `Wiki/`, and answers questions against the corpus with full source provenance.

The Wiki layer is written in **Open Knowledge Format (OKF) v0.2**. The full spec lives at `SPEC.md` in this folder and is the authority on the format. This file says how the vault uses it.

The vault is a folder on disk, and is normally opened as an Obsidian vault as well. It is operated from Claude Code. The vault is the whole corpus — there is no external store to sync from.

**This is the template.** It carries the machinery and none of the corpus. Nothing here has read a source yet: there are no knowledge bases, `Outputs/` is empty, and the *Current state* table below is waiting for its first row. See `README.md` for how to start one.

## Current state

| Knowledge base | Focus | Live? | Where its state lives |
|---|---|---|---|
| _(none yet)_ | | | |

Add a row per knowledge base as you create it. `Live?` is **live** for a base that still ingests new material, **frozen** for a closed archive.

**No counts here, deliberately.** This table must never carry concept counts, page counts or compile status. Those go stale, nothing keeps them true, and this is the one file every session reads end to end — so a wrong number here is read more often than anywhere else. The counts live in each knowledge base's `memory.md`, which is rewritten in place on every run that changes the answer, and in the generated `COVERAGE.md`. Same reasoning as `_ACTION-ITEMS.md` being generated rather than authored: two files holding one state drift, and the drift is invisible because both look authoritative. `assertions.yaml` at the vault root enforces it.

**A frozen knowledge base is a different object from a live one**, and the difference changes what a run is allowed to do. In a frozen base the archive is complete, there is no ingest cadence and no compile queue, `stale_after` is meaningless, and the legitimate work is correcting a concept, confirming one so it can leave `draft`, re-reading a thin scope, and answering questions. In a live base new material arrives, the coverage table is a queue rather than a record, and concepts can go out of date while their sources stay correct. Each `memory.md` says which kind it is in its first screen.

## Read this file whole

**Read `CLAUDE.md` end to end at the start of a session — this one and the knowledge base's own — before acting.** Not the section that looks relevant, not a grep for a keyword. The rules here are not independent: the ones that get missed are the ones a task-shaped search does not think to look for, and they are exactly the ones written down because they were missed before.

The reading order is `memory.md`, then this file, then the knowledge base's `CLAUDE.md`, all of them whole. `SPEC.md` is reference and is read where the format is in question.

## Your job is small

Three moves are yours. Everything else is the librarian's.

1. **Add to Raw.** Drop sources (articles, transcripts, screenshots, notes, links, PDFs) into a knowledge base's `Raw/` folder. See *Two ways to add sources* below.
2. **Ask Claude to compile.** Say "compile" or "process Raw" and the librarian works through anything new since the last pass.
3. **Ask questions.** Pose questions against the corpus. Every question becomes a written report in `00_Cerebrum/Outputs/`, citing the concepts and raw sources it drew on.

Writing concept documents, cross-linking, indexing, auditing, and drafting new concepts where evidence supports them — that's the librarian's job. You only get involved when judgement is needed.

### The librarian may edit this file, and always asks first

An earlier version of this rule forbade the librarian to touch `CLAUDE.md` at all. That cost more than it protected: every hand-over stalled until the owner said "please do the edit". A rule that is suspended every time it binds is not a safeguard; it is a delay with a ritual attached.

**The librarian may edit any `CLAUDE.md`, the vault's or a knowledge base's, and must put the exact text to the owner before writing it.** Not a summary of the intent: the replacement wording, the section it lands in, and what it displaces. The owner approves, amends or refuses, and the CHANGELOG entry records which.

**An unattended run may not edit a `CLAUDE.md` at all**, because there is nobody to ask. It raises an action item carrying the proposed text instead, and the edit waits for a session with the owner in it. Consultation that nobody answers is not consultation.

`SPEC.md` and `About me/writing-rules.md` stay untouched. They are the format and the house style rather than this vault's operating notes.

What makes this file matter is that it is the one file every session reads end to end, so a wrong line here is read more often than a wrong line anywhere else. Consultation is the check this file gets instead of a script.

## How a knowledge base is structured

Each knowledge base is one folder inside `00_Cerebrum/`. The naming convention is `[Topic]_kb`, ending in `_kb`.

Inside each knowledge base:

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
├── assertions.yaml   — settled facts with teeth, enforced by _scripts/verify.py
└── CHANGELOG.md      — the librarian's run log; top entry = current state
```

**`Outputs/` is not in that tree.** There is one `00_Cerebrum/Outputs/` for the whole vault, with one `_REPORTS.md` register. A per-knowledge-base split answers a question the corpus does not ask: a report drawing on two knowledge bases then has no correct home. The register's **Scope** column carries what a folder would.

**Concepts are grouped by kind, not by anything else.** `people/`, `systems/`, `projects/`, `decisions/`. Resist adding a level above that — a vestigial directory level is worse than none, because every later run has to remember it exists.

A knowledge base may also carry an **archive layer**: a second source folder holding a large, pre-existing corpus that arrived in bulk from another system, such as a notebook export. Keep it permanently in its own folder with its original structure intact.

An archive layer is a Raw folder in every way that matters. It is read-only source material, it is cited exactly like `Raw/` files, and concept claims trace back to it the same way. Two differences: it is exempt from the verbatim-frontmatter rule below, because it carries its own export frontmatter; and it is never migrated, flattened, renamed, or folded into `Raw/`. The librarian does not propose reorganising it. `Raw/` stays the drop zone for anything new; the archive stays as it is. The per-KB `CLAUDE.md` documents its own archive layers and how to read them.

Knowledge bases are independent. Each has its own focus, sources, and rules. They don't share data unless you explicitly cross-reference them.

### Cross-referencing between knowledge bases

Explicit cross-referencing is allowed and sometimes right: a source can only live in one knowledge base, but a claim in another may genuinely rest on it. Cite across rather than copying, using a relative path that climbs out of the bundle (`../../../OtherTopic_kb/OneNote/...`). Copying a source into a second knowledge base creates two versions that drift.

Three rules make this safe:

1. **The receiving knowledge base's `CLAUDE.md` names every outbound cross-reference**, so the coupling is written down rather than discovered when it breaks.
2. **The source knowledge base's `questions.md` records who cites into it**, under a *Cross-references out* heading, so a reorganisation there is known to be a breaking change.
3. **`assertions.yaml` carries a `require_file` entry for every cross-referenced target**, so deleting or moving one fails the audit instead of silently breaking another bundle. Declare the guard when you declare the coupling, before there is a link to exercise it.

**The coupling is the path**, and paths break silently, in a different knowledge base from the one being edited. Re-verify citations after moving any source folder.

## How the system works

- **Raw** is the dump zone. Articles, papers, transcripts, screenshots, datasets, links. Verbatim only — never summarised.
- **Archive layers** are bulk source corpora. Read-only, cited, never edited.
- **Wiki** is the librarian's domain and an OKF bundle. Claude reads Raw and the archive layers, compiles concept documents, maintains links and indexes. You rarely edit Wiki files directly.
- **Outputs** is where queries land. Reports, answers, charts. One folder at the vault root, shared by every knowledge base. Not part of any OKF bundle — Outputs is query history, and query history isn't knowledge. Promising outputs get promoted into a Wiki as proper concepts.

## Scope: everything counts

This is a private vault on a personal machine with a single user. There are no restricted folders, no material the librarian works around, and no content class that gets different treatment. If it's in the corpus, it's fair game.

The librarian never withholds, redacts, or silently omits. Where a source page carried a confidentiality marker in its original context, that's recorded as provenance, because it tells you something real about how the information travelled. It is not a reason to leave the content out.

This is about the *corpus*. The *repository* is a different boundary — see *Git* below.

## The Wiki is an OKF bundle

Each knowledge base's `Wiki/` folder is the root of one OKF v0.2 bundle. That means:

- Every `.md` file in `Wiki/` except `index.md` and `log.md` is a **concept**: YAML frontmatter with a required `type`, then a markdown body.
- Concepts are grouped into subdirectories however the topic wants. The directory structure carries no meaning beyond grouping.
- `index.md` files provide progressive disclosure: a reader sees what exists before opening anything. The bundle-root `index.md` carries `okf_version: "0.2"` and is the only index allowed to have frontmatter.
- `log.md` records the bundle's change history, newest first, with `YYYY-MM-DD` headings.
- Provenance, trust, and freshness live in frontmatter, not in prose.

`SPEC.md` in this folder is normative. Where this file and `SPEC.md` disagree on the format, `SPEC.md` wins. Where this file adds a house convention the spec leaves open — which `type` values to use, which link form, how to cite the archive — this file wins.

### Concept frontmatter

The house profile. `type` is the only field OKF requires; everything else here is strongly recommended and the librarian fills it in by default.

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

Field notes specific to this vault:

- **`type`** — the routing key. Keep the set small; per-KB `CLAUDE.md` files declare theirs.
- **`generated.by`** — the actor that wrote the current content. `librarian/claude-<model>` for the librarian, `human:<id>` for hand-authored concepts, `process:<id>` for scripted passes.
- **`verified`** — only ever set from an explicit confirmation. The librarian never writes a `verified` key on its own initiative; a human-reviewed tier has to come from someone actually saying so. Machine self-checks are recorded as `process:` entries.
- **`status`** — `draft` while a concept is thin or mid-compile, `stable` once it holds up, `deprecated` when superseded but still linked. Absent means `stable`, so write it explicitly on drafts.
- **`stale_after`** — set only on concepts describing an ongoing state (a current org chart, an active project, a live contract). Historical concepts about closed matters don't go stale and don't get the field.
- **`sources`** — required in practice, even though OKF makes it optional. This is the field that replaces a "every claim traces to a source" rule written as prose, and it does the job better.

### Trust replaces a Status field

An obvious first design uses a single `Status: established | emerging | speculative` line in the body. OKF splits that into two orthogonal signals, and the split is the point:

| Naive | OKF equivalent |
|---|---|
| established | `status: stable` + `verified` present |
| emerging | `status: stable`, no `verified`, thin `sources` |
| speculative | `status: draft`, no `verified`, `sources` empty or self-referential |

Trust tiers are derived, never stored: no `verified` key means unverified, `verified` by non-`human:` actors means machine-confirmed, `verified` by a `human:` actor means human-reviewed. Don't write a "trust" or "confidence" field; the tier falls out of the frontmatter.

**What moves a concept from `draft` to `stable`.** `status` is lifecycle and `verified` is trust, and they answer different questions. So the rule is not about whether a concept's facts have been confirmed:

> **A concept is `draft` only while it names something unsettled that would change what it says, and `stable` once it does not.** A draft that gives no reason is a field nobody can act on.

A concept being unverified is not a reason to keep it at `draft`. That is what the absence of `verified` already says, and saying it twice in two fields is duplication.

**`verify.py` enforces it opt-in**, through `draft_needs_reason: true` in a knowledge base's `assertions.yaml`: any concept at `draft` whose body does not carry the literal string `` `status: draft` `` raises a finding. Turn it on for a bundle from the start; turning it on later, over a pile of drafts that predate the rule, makes promoting them a decision rather than a cleanup.

### Sourcing and per-claim attribution

Every concept carries `sources`. Each entry needs a `resource`; give it an `id` whenever the body cites it, and add `title`, `author`, and `last_modified` when they're knowable.

Attribute individual claims with markdown footnotes keyed to a `sources[].id`:

```markdown
The decision was taken in March 2024, over the objections of two units.[^lk-2024-03]

[^lk-2024-03]: Steering group meeting, 12.03.2024
```

The label is the join key into `sources` — not the footnote prose. Keyed rather than positional, because the librarian rewrites these documents constantly and a positional index misattributes silently the moment the list is reordered.

A claim with no footnote and no supporting `sources` entry doesn't belong in a concept. It goes to `questions.md` instead, or the concept goes to `status: draft` and says why.

### Links

Concepts link to each other with standard markdown links. **Use relative paths** (`../systems/thing.md`), not the bundle-absolute `/`-prefixed form OKF recommends. The spec permits both; relative wins here because Obsidian resolves `/` against the vault root rather than the bundle root, and the vault root is one level above `Wiki/`.

Obsidian `[[wikilinks]]` are **not** used. They aren't OKF, they don't survive export, and they don't carry link text.

A link asserts a relationship; what kind is carried by the surrounding prose, not by the link. Broken links are fine and expected — a link to a concept that doesn't exist yet is a legitimate way to record knowledge that hasn't been written.

### Numbers that matter: Attested Computation

When a concept states a figure that someone might act on — a headcount, a budget line, a page count, an SLA volume — and that figure was derived rather than read off a page, it can be split into an `Attested Computation` concept: a standalone document carrying `runtime`, `parameters`, the sanctioned computation, and an `attester`. The narrating concept then links to it rather than restating the number's derivation.

This is optional and most concepts never need it. Use it when the number is load-bearing and the derivation is repeatable. A figure quoted verbatim from a source page is not a computation — it's a sourced claim, and a footnote is the right tool.

### Reserved and special files

- `index.md` — directory listing, one per directory. No frontmatter, except the bundle root's `okf_version: "0.2"`. Entries carry the linked concept's `description`.
- `log.md` — the OKF update log for the bundle: what concepts were created, updated, deprecated, and when. Sits at the bundle root; may also appear in subdirectories.
- `questions.md` — not an OKF reserved name, so it's a concept like any other, with `type: Open Questions`. Holds open threads, unresolved tensions, the coverage queue, and the **Action items** table.
- `references/` — mirrored external material, web-search digests, and any scripts an executor or attester points at.

### memory.md, and why it is not a log

Each knowledge base carries a `memory.md` at its root. It answers one question: what is true right now. Concept counts, what is compiled and what is not, the facts that were expensive to establish, the archive hazards that bite every pass, and the next scope.

Three rules make it work:

1. **Read it first**, before `CLAUDE.md`. It is the cheapest way to load state.
2. **Rewrite it in place.** It is never appended to and holds no dated entries. A `memory.md` that grows is a changelog with the wrong name.
3. **It is derived and disposable.** `CHANGELOG.md`, `log.md` and `questions.md` are authoritative; `memory.md` is a compression of them. Where they disagree, they win, and `memory.md` gets corrected.

Refresh it at the end of any run that changes the answer: a compile pass, a health check, a source move, a settled contradiction. Keep it under roughly 60 lines. If it needs more, the detail belongs in `questions.md`.

`log.md` and the KB-root `CHANGELOG.md` are different files with different jobs. `log.md` is bundle history: concept-level, OKF-shaped, for anyone reading the bundle. `CHANGELOG.md` is operational memory: what the librarian did on each run across the whole KB, including Raw ingestion and health checks. Both get written on a compile pass.

## Language

Pick one output language for the vault and write everything in it — concept bodies, descriptions, index entries, log entries, Outputs reports, CHANGELOG, and chat replies alike. This template assumes **English**.

Where the sources are in another language, that doesn't change the output language; it changes how quoting works:

- **Direct quotes stay verbatim in the source language**, followed by a short gloss in brackets where the meaning isn't obvious from context.
- **Proper nouns keep their real names.** Meeting series, org units, roles, and document types are not translated. Translating them would break the link between the concept and the corpus a reader will search.
- **Everything else is the output language**, including the summary prose around a foreign term. Gloss a term on first use in a concept, then use it plainly.

Frontmatter keys, `type` values, and `tags` are English. Tags are lowercase kebab-case.

## Creating a new knowledge base

The canonical template lives at `_KB_CLAUDE_TEMPLATE.md`, here in the vault root beside this file. Every new knowledge base starts from a copy of it. It sits at vault level rather than inside a knowledge base because it belongs to no single one: it governs how any of them is created.

When you ask the librarian to spin up a new knowledge base, it should:

1. Confirm the name (`[Topic]_kb` format) and the focus areas.
2. Create the folder `00_Cerebrum/[Topic]_kb/` with two subfolders: `Raw/` and `Wiki/`. Reports go to the vault-level `00_Cerebrum/Outputs/`, which already exists.
3. Copy `00_Cerebrum/_KB_CLAUDE_TEMPLATE.md` into the new knowledge base's root and rename it to `CLAUDE.md`. Replace the placeholder sections (name, "What This Is", "Focus Areas", "Concept Types", "Archive Layers") with content specific to the new knowledge base. Leave everything else as-is.
4. Create `memory.md`, `CHANGELOG.md` and an `assertions.yaml` (may start empty) at the knowledge base root, `Raw/_INGESTED.md`, and the OKF scaffolding: `Wiki/index.md` (with `okf_version: "0.2"`), `Wiki/log.md`, `Wiki/questions.md`.
5. Add a row to the *Current state* table above.
6. Run `python3 _scripts/verify.py` and expect it green.

## Your own answers are sources

The archive is not the only primary source in this vault. You are. Where a question cannot be answered from the corpus but you know the answer, that answer is source material and goes through the same machinery as everything else.

The pattern:

1. Write the statement to `Raw/YYYY-MM-DD_testimony-<slug>.md`, with the standard Raw frontmatter and `type: Testimony`. **Quote it verbatim.** Mark anything the librarian supplied as context, so the testimony and the framing stay separable.
2. Register it in `Raw/_INGESTED.md`.
3. Cite it from concepts like any other source, with `author: human:<id>`.

This matters more than it sounds. A large share of the open questions in `questions.md` are not research tasks at all: what an acronym expanded to, who initials belong to, whether a contract was signed, what a folder was for. The archive cannot answer them and never will. You can, in seconds, and the answer is worth more than the pages around it because nothing else records it.

Testimony carries the same trust rules as anything else. It is a source, not a verification: it does not license a `verified` key, and where it contradicts the archive both positions are held under Contradictions.

## Two ways to add sources

**Low-token: drop and forget.** Save files straight into the knowledge base's `Raw/` folder. No chat tokens spent. Best for batches. Ask Claude to compile when you're ready and it processes everything new in one pass.

**High-token: guided ingest.** Paste or share sources in chat. Claude ingests them with full frontmatter, asks framing questions if the source is rich enough to deserve them, and registers them in `_INGESTED.md` as it goes. Best when a single source is dense enough to deserve discussion before it gets compiled.

Both modes are valid. Mix them.

## Verbatim-only Raw ingestion

When material lands in a knowledge base's `Raw/` folder, the librarian preserves it word-for-word. Raw is for unprocessed source material. Never summarise, paraphrase, condense, reword, or translate on ingest. Distillation and translation happen at the Wiki layer.

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

If a field is unknown, mark it `unknown` — never fabricate. Preserve the source's own structure rather than imposing new headings.

Raw files are sources, not concepts. They're not part of the OKF bundle and don't follow OKF frontmatter. Archive layers are likewise exempt: they keep whatever frontmatter their export produced, and the per-KB `CLAUDE.md` documents how to read it.

This rule is what makes source provenance reliable as the wiki grows. Every claim in a concept must trace back to actual words in a source file.

## Naming conventions

- **Knowledge base folders:** `[Topic]_kb`.
- **Concept filenames:** kebab-case, lowercase, English. Proper nouns and acronyms keep their real form, lowercased. The Concept ID is the path minus `.md`, so filenames are effectively permanent — renaming one breaks every link to it and is a confirm-first operation.
- **Concept groups:** English, lowercase, plural (`projects/`, `systems/`, `people/`, `decisions/`).
- **Raw filenames:** keep the source's original name where possible; if renaming, use a descriptive kebab-case name.
- **Output filenames:** `YYYY-MM-DD_query-slug.md`.

## Writing standards

The house style lives at `About me/writing-rules.md`. The librarian reads that file before writing anything, and it governs every concept body and every prose-heavy file in `Outputs/`.

It is derived from Wikipedia's *Signs of AI writing* essay, inverted into instructions: a banned vocabulary list, banned constructions (negative parallelism, the rule of three, trailing `-ing` analysis, false ranges, vague attribution), punctuation limits, and formatting rules. Read it rather than relying on the summary here.

OKF adds one instruction that outranks style preference: **favour structural markdown over freeform prose**. Headings, lists, tables, and fenced blocks aid both human reading and agent retrieval. A concept that could be a table should be a table.

The rules apply to concept bodies and to prose-heavy files inside `Outputs/`. They don't apply to frontmatter, navigation files (`index.md`, `log.md`, `memory.md`, `CHANGELOG.md`, `_INGESTED.md`, `CLAUDE.md`), or direct quotes from source material.

`About me/` is also where a profile of the vault owner belongs, if the corpus is about their own work. The librarian reads it for context the archive assumes and never states.

## Question report protocol (non-negotiable)

Every question you ask generates a report in `00_Cerebrum/Outputs/`, one folder for the whole vault. No exceptions. The point is to compound insight over time, not just answer in chat and lose the reasoning.

When you ask a question:

1. The librarian answers using the Wiki first, then `Raw/` and the archive layers. Web search is offered to fill gaps when answering a question — never run automatically.
2. The librarian writes a report to `00_Cerebrum/Outputs/` covering more than a chat reply would. The report includes:
   - The question, restated cleanly.
   - The answer, structured for re-reading.
   - Citations: links to the concepts used, and paths to Raw or archive files where they were the primary source.
   - Tensions or contradictions surfaced across the corpus.
   - Open questions or next-move suggestions that follow from the answer.
   - **Corpus sufficiency**: whether the Wiki alone answered it, which archive scopes had to be read, and which concepts should have existed but did not. These lines are what turns query history into the compile queue — the health check mines them.
3. The librarian adds a row to `Outputs/_REPORTS.md`: date, **scope**, question, report link, what it drew on, and promotion status. Scope names the knowledge base or bases the report drew on. A report with no row is invisible to the next session, which defeats the point of filing it.
4. The report is delivered into the chat as a readable page with `SendUserFile`, and the surrounding sentence names its filename so it can be found again. Never both deliver it and link it — see *Output presentation rule* below.
5. Reports follow the writing rules.

Reports are not OKF concepts and don't carry OKF frontmatter. Outputs is query history; the bundle is knowledge.

Naming convention: `YYYY-MM-DD_query-slug.md`, kebab-case slug, lowercase. Where a report covers one knowledge base, the slug says which, since the folder no longer does. If two reports share a date, append `-v2`, `-v3`, etc.

When to skip the report: only when you explicitly say "don't file this" or "just answer in chat." The default is always file.

Promotion: a report containing foundational synthesis can be proposed for promotion into the Wiki. Promotion means rewriting it as a proper OKF concept with full frontmatter and sourcing, not copying the file across. The outcome is recorded in the report's `_REPORTS.md` row, so an unpromoted candidate stays visible rather than being forgotten.

Two signals say a report should be promoted. It answers something the bundle could not answer on its own, or the same question has now been asked twice. The second is the stronger of the two, and `_REPORTS.md` is the only place it can be seen.

## Concept drafting and web research

The question-answering rule above says web search is offered, not run automatically. Concept drafting is the opposite where the topic is external. New concepts about outside knowledge exist to bring fresh material into the corpus, so web research is part of the job.

When the librarian drafts a new concept (or substantially enriches an existing one):

1. If the topic is internal — a project, decision, org unit, or colleague from the corpus — the archive is the authority and the web adds nothing. Gaps go to `questions.md`.
2. If the topic is external — a vendor, a technology, a framework, a market fact — search freely. Pull canonical primary sources where possible; use reputable secondary sources only when primary is unreachable, and label them clearly with `author` on the `sources` entry.
3. Anything cited first lands in `Raw/` as its own file, with the full required frontmatter, or as a digest under `Wiki/references/`. If the primary source is unreachable, save a digest with `type: Web search digest` and document the search context inside the file. Mark `date_published: unknown` rather than guessing.
4. Update `_INGESTED.md` to register the new Raw file before citing it.
5. Then draft or update the concept, listing the new file in `sources`.

## Compile skill

The `knowledge-base-compile-skill` reads an archive layer end to end and turns it into cited concepts, by cutting it into batches of about 55 pages and dispatching up to eight sub-agents at a time.

**The skill carries the portable procedure, including the sub-agent prompt.** That prompt is the part the scripts cannot hold: it is where the archive's own hazards get named, where the no-clobber guard is imposed, and where an agent is told that a page carrying nothing is a real finding rather than a failure. `_COMPILE-RESUME.md` records where the current run stopped and what a batch measured out at.

Invoke it by saying "compile the [name] archive" or "continue the compile". One knowledge base per invocation. Budget roughly 200k agent tokens per batch, near enough independent of pack size, so a wave of eight is about 1.6M and a whole archive scales from there.

## Health check skill

The `knowledge-base-health-check-skill` audits one knowledge base per invocation. It runs on demand when you ask ("run a health check", "audit the [name] KB", "check the wiki"). It auto-fixes routine drift and raises judgement calls as action items.

**There is one run type, and the full read is defined rather than assumed.** An earlier design had a cheap delta most months and a full audit quarterly. That was removed: it let a moved source folder go unnoticed for a quarter, and "three concepts sampled at random" had no principled basis. Its replacement, "every run reads every concept", survived only until a bundle got large enough that runs quietly truncated instead.

So the full read means:

> Every concept is **machine-scanned**, unconditionally — that is `verify.py` and it never samples. A concept is **read in full** when it changed since the previous health check, **or** is among the fifteen most-linked in the bundle, **or** sits in a contradiction cluster the run reads.

The three arms do different jobs. Changed-since catches new work, which is where fresh error lives. Most-linked catches the concepts where a wrong claim propagates furthest — a claim in a concept with fifty inbound links is a claim the bundle leans on. The cluster arm is the sweep the skill already required. What none of them does is sample at random.

**`_scripts/readset.py` derives the set**, and it exists so a run cannot choose its own scope: a run that picks will always pick what it had budget for. It reads the previous run's date out of the CHANGELOG, so the arithmetic is not a matter of memory. Every entry states three numbers — machine-scanned, read in full, and not read in full — and a run that does not state them has not followed the rule. On the run immediately after a compile the read set is the whole bundle, which is correct and is also when the run is most expensive.

**The distinction that still matters is mechanical versus judgement.** Mechanical checks are scripted and cost nothing: frontmatter conformance, citation paths, footnote labels, index accuracy, `stale_after`, archive coverage. Judgement checks need a concept read and understood: writing rules, unsourced claims, misplacement, promotion candidates. The split explains why some checks run as a script and some as a read, not what gets covered. Both cover everything.

With the Wiki as an OKF bundle, the audit has a concrete conformance surface to check. On top of its usual passes it verifies:

- Every non-reserved `.md` in `Wiki/` parses as YAML frontmatter plus body, and carries a non-empty `type`.
- Every concept has `sources`, and every footnote label resolves to a `sources[].id`.
- `index.md` files match the directory contents and quote current `description` values.
- No concept is past its `stale_after` without being flagged.
- `generated.at` isn't wildly older than the sources the concept cites.
- No `verified` entry names a human who never confirmed it.
- Every report in `00_Cerebrum/Outputs/` has a row in `Outputs/_REPORTS.md`, and every row marked `pending review` is surfaced as a promotion candidate.
- `memory.md` still matches reality: counts, compiled scopes and settled facts. The audit rewrites it rather than reporting drift, since it is derived.

Broken links are reported but not fixed — under OKF a broken link is legitimate, and often marks knowledge worth writing.

### Action items

Findings from a health check that need judgement become **action items**, recorded in the `# Action items` table in that knowledge base's `Wiki/questions.md`. `CHANGELOG.md` records that an item was raised; the table is the only place its state lives.

Four states: `open`, `actioned`, `deferred`, `withdrawn`. Ids are `AI-YYYY-MM-DD-n`, stamped with the raising run and never reused.

Each run reconciles the table before deciding what it found. An `open` item that still holds is carried forward with its original date rather than raised again, so how long it has been outstanding stays visible. A `deferred` item must carry the condition that reopens it; without one it is an open item in disguise.

**A `withdrawn` item is never raised again.** If the same condition trips the same check, the check is wrong and gets fixed. These rows are memory about the audit rather than the corpus, and they are the reason the same false positive is not rediscovered every quarter.

### When a health check writes a report

**This is the binding statement of the rule; the skill restates it with the reasoning and defers to this one.**

A run that finds nothing and fixes nothing logs to `CHANGELOG.md` and stops there. The check additionally files a report in `00_Cerebrum/Outputs/` when a run **raises or carries action items**, or when it **applies auto-fixes** — the runs carrying reasoning a CHANGELOG block would flatten. The report is registered in `_REPORTS.md` with `audit` in place of a question.

An audit report is never promoted into the bundle. It is process history, not knowledge about the subject.

The full procedure lives in the skill itself. Per-knowledge-base `CLAUDE.md` files point at the skill rather than duplicating the protocol.

### Running it on a schedule

**The health check is run on request by default.** Say "run a health check" or "run the health checks". Nothing in this template schedules it.

If you do schedule it, three things are worth knowing, each of which cost a wasted run to learn:

- **Check which timezone the scheduler evaluates cron in.** A cron written for UTC and entered into a local-time scheduler fires two hours early. A local-time cron has the compensation that it stays at the intended hour through both halves of the year.
- **A scheduled run must be able to reach the vault.** Test it: fire a one-time read-only task from a fresh session with no memory of the one that created it, and have it report whether it can read `CLAUDE.md` and count files. A task that fails every month is worse than no task, because the vault then looks audited and is not.
- **File tools and bash can disagree.** In some sandboxes `Read` returns `EPERM` and `Glob` returns nothing for a path that bash reads cleanly — a filesystem-permission matter, and a property of the session rather than of the machine. If that is your situation, the stored task prompt needs an access note instructing the run to use bash for all vault access, to pass that on to every sub-agent, and to treat an `EPERM` as a tool limitation rather than proof the vault is unreachable. Without the last part the run aborts and reports a false failure.
- **A machine that is asleep at the firing hour misses the run** rather than deferring it. Treat a missed slot as a prompt to run one by hand.

## Action items across the vault

Findings that need your judgement are raised per knowledge base, in `<KB>/Wiki/questions.md` under *Action items*, with a state of `open`, `actioned`, `deferred` or `withdrawn`. **That table is the only place an item's state lives.**

You act across the vault, though, not one knowledge base at a time. So `_ACTION-ITEMS.md` in this folder carries a roll-up: every open item across every knowledge base, oldest first, plus deferred items with the conditions that reopen them, plus per-knowledge-base counts.

**It is generated, never authored.** Do not edit it, and never read a state from it. It is regenerated by `_scripts/actionitems.py` at the end of every health check run that touched an item. Change an item where it lives; the roll-up catches up.

The reason for the split is the one this vault keeps relearning: two files recording the same state drift, and the drift is invisible because both look authoritative. A derived file is safe precisely because nobody is allowed to trust it as a source.

Resolved items are counted in the roll-up, never copied into it. Their reasoning belongs beside the corpus it concerns, and a list of everything ever decided is an archive rather than a queue.

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

`_scripts/` holds the vault's executable memory. Prose explains why a rule exists; these run.

- **`_scripts/verify.py`** — the canonical mechanical audit. Every health check runs it, any session may, and the pre-commit hook runs it on every commit. It checks OKF conformance, citation resolution, footnote binding, `generated.at` freshness, the assertions below, and the link graph, across every knowledge base, and the vault-level files too, driven by the vault-root `assertions.yaml`. **The operating rule: a defect class is not fixed until this script catches its recurrence.** Fixing the instances and leaving the script unchanged is how a documented check can sit unexecuted through several clean-looking runs. Findings have a clock: one standing on three distinct run-days escalates to a DEFECT unless `assertions.yaml` waives it with a reason (`finding_waivers`), because standing noise trains the reader to skip the findings block. The script keeps that clock in `_scripts/verify-state.json`; bundle-level gauges never escalate. It checks an index by asking whether `reindex.py` would change it, rather than by looking for the concept's filename — the weaker test passes truncated descriptions and cannot see an entry left behind by a concept that no longer exists.
- **Prove the new check fails without its fix.** A guard that has never failed is not known to guard anything. Write the check, reintroduce the defect it is for, watch `verify.py` go red, then restore. **Reintroduce one at a time**: a batch hides which cases the guard cannot see, because the first failure is the one that gets reported.
- **`_scripts/actionitems.py`** — regenerates `_ACTION-ITEMS.md` from the per-KB tables, with the real write time. The roll-up is never written by hand.
- **`_scripts/reindex.py`** — regenerates the directory indexes from the concepts' own frontmatter. Compile agents may not touch `index.md`, so a compile always leaves them stale by exactly the number of concepts it added. **It never reorders an index**, because more than one order is legitimate — alphabetical, chronological by dated filename, or a curated reading order. So it refreshes descriptions, adds what is missing, drops what is gone, and leaves the sequence to whoever wrote it. Run it at the end of every compile wave and every health check.
- **`_scripts/visualize.py`** — generates `okf-viewer.html`, a self-contained static browser for the whole vault: every concept rendered, concept links resolved in-app, dead links marked as the legitimate placeholders they are, trust tiers derived, inbound links shown. SPEC.md defines no viewer; this is the house one. Derived and gitignored — regenerate, never edit. **Regenerate it at the end of every run that changes concepts, including every compile pass.** Then run `viewer-check.js` where a browser can launch. Its layout gives each knowledge base a corner on a circle and its categories come from `CATS`; both are meant to be replaced once your vault has a shape worth stating. The list folds by group, and the fold state persists in `localStorage` without hiding a search hit.
- **`_scripts/viewer-check.js`** — the verify.py of the pixels. A generator can run clean while the page renders wrong, so this is the render-and-look habit made executable: boots the page in headless Chromium, opens a concept, checks for leaked HTML entities, searches, and requires the graph to draw saturated nodes rather than only grey edges. **The delivery rule: no session delivers a regenerated `okf-viewer.html` without this green first.** It replaces none of the eyeballing — it checks what it lists and nothing else. `_scripts/viewer-check-sandbox.sh` gets it running in a container without Chromium's system libraries.
- **`_scripts/mermaid-check.py`** — turns every Mermaid block in a markdown file into a URL that renders it. A diagram nobody has rendered is an unverified claim, the same as a figure nobody checked. Where no local renderer is reachable, the way through is a real browser: the Mermaid live editor carries the whole diagram in the URL fragment, so the URL is built here and opened there, and the render either succeeds or shows a parse error. `python3 _scripts/mermaid-check.py <file>`, or `--json` for tooling.
- **`_scripts/namescan.py`** — the calibrated name scan, for finding people in an archive who have no concept yet. It replaces a grep procedure that was wrong by an order of magnitude twice. It measures every spelling family against the people who already have concepts and presents counts for unknowns as floors with the measured range attached. Nicknames and initials count only when `assertions.yaml` maps them. The rule it encodes: an estimator that feeds decisions gets calibrated against knowns before its numbers are trusted.
- **`assertions.yaml`** (vault root) — the same idea one level up. The per-KB files guard concepts; this one guards the files above them: `CLAUDE.md`, `SPEC.md`, the KB template, `_ACTION-ITEMS.md`. Entries are `forbid_in`: a path, optionally a heading to scope the scan to, optionally `lines: table` to scan only table rows, a pattern, and a reason. `verify.py` runs them as a vault pass before the knowledge bases and prints `== 00_Cerebrum (vault)`. A match is a DEFECT, so the pre-commit hook blocks on it.
- **`_scripts/coverage.py`** — measures archive coverage instead of asserting it, and writes the generated `<KB>/COVERAGE.md`. Coverage is the share of archive pages some concept actually cites, plus pages a compile agent opened and recorded in `<KB>/_COMPILE-LEDGER.md` as carrying nothing citable. A weaker measure asks whether a concept exists for a scope, which is a question about the bundle rather than the archive, and can report a bundle fully compiled while most of its pages have never been cited. `verify.py` fails when the table goes stale. A knowledge base whose bulk corpus did not arrive as `OneNote/` declares its own `archive_layer` in its `assertions.yaml`.
- **`_scripts/linkcheck.py`** — measures how isolated a bundle's concepts are from each other. A compile that produces well-formed concepts nobody links to has produced a pile rather than a bundle, and nothing else catches that.
- **`_scripts/prepare-batch.py`** — packs a compile batch for an agent: strips frontmatter, boilerplate, URLs and GUIDs, and collapses lines already present elsewhere in the corpus to a marker naming where they came from. Rolling notes repeat themselves heavily, so reading every page whole means reading the same line several times over. A packed batch runs about a third the size of the raw pages.
- **`_scripts/merge-appends.py`** — applies the append-requests compile agents hand back. Agents run concurrently and so may not edit an existing concept; they emit APPEND blocks and this script merges them serially, resolving each citation to its true relative depth and remapping a footnote when the page is already cited under another id. Its historical bugs are documented in the code.
- **`_scripts/fix-runons.py`** — inserts the blank line a run-on paragraph is missing. A line ending in a footnote reference followed straight by a new sentence renders as one paragraph, so two claims with two different sources read as one claim. Because it is a rendering fault rather than a truth fault it is a finding rather than a defect, which is how these accumulate in the hundreds before anyone repairs any. `python3 _scripts/fix-runons.py <KB> [more KBs...] [--dry-run]`.
- **`_scripts/fix-depth.py`** — repairs a resource path whose only fault is the number of `../` steps. `merge-appends.py` re-resolves depth for the citations it merges, but a concept an agent writes directly never passes through it, so every wave produces a few. It touches only a citation that does not resolve, and only where re-anchoring on the path from the archive root onward finds the file. Run it after every merge.
- **`_scripts/fix-glosses.py`** and **`_scripts/fix-tablebreaks.py`** — two more repairs of the same class, for glosses and for tables broken across a paragraph boundary.
- **`_scripts/plan-batches.py`** — derives what is unread the way `coverage.py` derives what is covered, and cuts it into batches inside a scope. Planning batches by hand gets the count wrong.
- **`_scripts/inventory.py`** — regenerates the concept list compile agents read instead of exploring the tree. An agent that cannot see a concept writes it again under a second name.
- **`_scripts/readset.py`** and **`_scripts/readblocks.py`** — derive which concepts a health check reads in full, and cut them into blocks a run can work through. See *Health check skill* above for why a run may not choose its own scope.
- **`_scripts/archive-snapshot.sh`** and **`_scripts/archive-diff.sh`** — snapshot an archive layer's file list and hashes, and report what changed since.
- **`_scripts/archive-fingerprint.py`** — fingerprints an archive layer by content, and records every citation into it, so a replacement export can be remapped. `archive-snapshot.sh` answers "did this file change"; this answers "which page in the new export is this old page", which is the question a re-export actually poses.
- **`_scripts/attachment-register.py`** — generates `<KB>/_ATTACHMENT-PASS.md` from the `# Pending attachments` tables in the concepts themselves, so the queue of claims waiting on a missing image is derived rather than maintained.
- **`_scripts/sync.sh`** — runs `verify.py`, then `git pull --rebase --autostash`, then add, commit and push, and prints the resulting commit. It exists because a commit step pasted into a terminal fails silently and leaves you comparing hashes; a script fails in one place and says why. `sh _scripts/sync.sh "subject line"` for a written message, or bare for a generated one.
- **`_scripts/gitsetup.sh`** — one-time git setup: installs PyYAML if missing, runs `verify.py`, sets the remote from `CEREBRUM_REMOTE`, installs the pre-commit hook, and makes the first commit. Safe to re-run.
- **`_scripts/git-read.sh`** — the only git a bridge session may run. See *Git* above.
- **`_scripts/build-skill.py`** — builds a `.skill` package from its source. **Skills have two representations and one source of truth: `_skills/<name>/` is edited and diffed, `<name>.skill` is built from it and installed by the app.** Never edit a package directly. `verify.py` fails when a package differs from its source, and the build is deterministic so rebuilding an unchanged source produces an identical file. `.claude/skills/<name>` are symlinks into `_skills/<name>/`, which is how a Claude Code session opened on this folder reaches the skills; the symlinks add no copy.
- **`<KB>/assertions.yaml`** — settled facts with teeth. When a fact settles — by testimony, by evidence, by a ruling — and a pattern can express it, it gets an entry: a forbidden regex, a required file, or a rule about how a class of source must be cited. `verify.py` enforces them, so a settled fact that regresses fails the audit instead of waiting to be noticed. Hand-curated; the librarian adds entries as facts settle and never deletes one without saying so in the CHANGELOG.

## Output presentation rule

**One file, one reference.** Never both deliver a file into the chat and link to it in the same message. Both render as a file card, so doing both produces two cards for one file.

Which of the two depends on what the file is.

| File | How it arrives | Why |
|---|---|---|
| A question report in `00_Cerebrum/Outputs/` | Delivered as a readable page with `SendUserFile`, `display: "render"` | You asked a question; the answer should arrive in front of you |
| Everything else — concepts, indexes, `log.md`, `memory.md`, `CHANGELOG.md`, `_ACTION-ITEMS.md`, health check reports | Its path, named in the sentence | You did not ask for the file; you asked for the work. Knowing where it landed is enough |

In Claude Code a path written relative to the vault root — a knowledge base's memory.md, say — is already clickable, so a file that is not delivered is named by its path and nothing more.

A delivered page still needs its path findable later, so name the file in the surrounding sentence rather than linking it. The page is for reading now; the filename is what you search for in six months.

Keep the surrounding chat summary short. The reasoning lives in the file, not the scrollback, and never restate a delivered report's contents after delivering it.

## Working in this vault

Compile passes, health checks and reorganisations run long, and often while nobody is watching. The task list is the only live view of where the work has got to, so it is part of the job rather than decoration.

- **Create the list before touching a tool**, for anything that runs more than a couple of steps. Not partway through, and not afterwards as a summary.
- **Set a task to `in_progress` when starting it, not when finishing it.** A task that sits at `pending` while it is being worked makes the panel stale, which is worse than an empty one: it reports a state that is not true.
- **Mark it complete at the moment it is done**, then move on to the next.
- **Skip it for genuinely trivial work.** A single small edit or a factual question does not need a list. Over-applying it is its own kind of noise.

Scoped compile passes are the case this matters most for. One task per scope makes it obvious, on returning to a long run, which scopes were processed and which are still queued.

## Where the operating rules live

The detailed librarian behaviour for each knowledge base — ingestion protocol, archive layer map, concept types, output filing, query patterns — lives inside that knowledge base's own `CLAUDE.md`. That's the operating manual. This top-level file is the map. `SPEC.md` is the format.

Both are read in full, every session. See *Read this file whole* at the top.
