---
type: Writing Rules
title: Writing rules
description: House style for everything the librarian writes in this vault. Derived from Wikipedia's "Signs of AI writing".
tags: [meta, style]
status: stable
generated: { by: librarian/claude-opus-5, at: 2026-08-08T21:05:00Z }
sources:
  - id: wp-signs
    resource: https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
    title: Wikipedia:Signs of AI writing
    author: team:wikiproject-ai-cleanup
    last_modified: unknown
---

# What this governs

Every concept body in a `Wiki/` folder, every prose-heavy file in `Outputs/`, and any draft written for the person who owns this vault.

Not governed: frontmatter, navigation files (`index.md`, `log.md`, `CHANGELOG.md`, `_INGESTED.md`, `CLAUDE.md`), and quotations from source material, which stay verbatim in their original language even where they break every rule below.

The source is Wikipedia's essay *Signs of AI writing*, maintained by WikiProject AI Cleanup. That essay is a detection guide. This file inverts it into a set of instructions.

# The test

Before writing a sentence, ask whether it carries a fact a reader could act on or check. If it only carries an impression, cut it. Most of what follows is that test applied to specific habits.

# Vocabulary

## Never use these words

delve, tapestry, pivotal, underscore, foster, testament, enhance, crucial, intricate, landscape (figurative), realm, navigate (figurative), seamless, robust, leverage (as a verb), harness, embark, journey (figurative), unlock, unleash, elevate, empower, showcase, spearhead, garner, myriad, plethora, vibrant, dynamic, cutting-edge, state-of-the-art, game-changing, transformative, groundbreaking, innovative, holistic, nuanced, multifaceted, comprehensive (as praise rather than measurement), ever-evolving, fast-paced, rich (figurative), profound, invaluable, indelible, enduring, meticulous.

Most have a plain replacement. `enhance` is almost always `improve`. `leverage` is `use`. `crucial` is either `required` or nothing.

## Never use these phrases

- stands as a testament to · serves as a testament to · is a testament to
- plays a vital role · plays a significant role · plays a key role
- watershed moment · turning point (unless the source says so and the pivot is named)
- rich cultural heritage · rich tapestry · enduring legacy · deeply rooted
- it is important to note · it is worth noting · it should be noted
- no discussion of X would be complete without
- in today's fast-paced world · in an increasingly digital landscape
- embark on a journey · navigate the complexities of
- at the end of the day · when all is said and done
- I hope this helps · let me know if · feel free to · as an AI language model · as of my last knowledge update

The last group is chatbot residue. If any of it reaches a file, the file was not read before it was saved.

# Constructions

## Negative parallelism

Do not write "it is not just X, it is Y" or "not only X but also Y". The pattern manufactures drama by inventing a position nobody held.

> **No.** The programme was not just a technology project; it was a cultural transformation.
> **Yes.** The programme replaced per-region workplace IT with one national service. It also forced every unit onto a shared release cycle, which is where most of the resistance came from.

## The rule of three

Do not reach for three parallel adjectives or three parallel clauses. Wikipedia flags the triplet because writers use it for rhythm when they have one thing to say.

> **No.** The rollout was efficient, effective, and well received.
> **Yes.** The rollout finished four weeks early. Two departments filed complaints about the migration window.

Three items are fine when there are exactly three things and each is doing separate work.

## Superficial trailing analysis

Do not end a sentence with a present participle that restates it as significance.

> **No.** The new client manager replaced the old one across the section, highlighting the shift toward cloud-managed clients.
> **Yes.** The new client manager replaced the old one across the section. The Linux estate stayed on its own tooling.

Watch for: highlighting, emphasising, reflecting, underscoring, demonstrating, showcasing, ensuring, illustrating, marking, signalling.

## False ranges

Do not use "from X to Y" unless X and Y are the actual endpoints of a real scale.

> **No.** The section's remit ranges from strategic planning to hands-on support.
> **Yes.** The section runs the service desk and client engineering for Windows, macOS and Linux.

## Vague attribution

Every opinion gets a name or a footnote. "Some critics argue", "observers have noted", "industry reports suggest", "it has been described as", "studies show" are all banned. In this vault the rule is stronger than Wikipedia's, because the sourcing model already requires a `sources[].id` behind each claim. An unattributed opinion is a sourcing failure, not a style one.

## Hedging

Do not soften a claim to cover uncertainty. The frontmatter has fields for that.

- Uncertain because the evidence is thin → `status: draft`, and say what is missing.
- Uncertain because two sources disagree → both go in `questions.md` under Contradictions.
- Uncertain because a date is unreliable → write `ca. 2024-03` and log the reason.

Banned as cover: might, could, perhaps, arguably, generally, somewhat, in many cases, it seems, one could argue. These words are permitted only when the uncertainty is the point and is itself sourced.

## Summaries and conclusions

Do not open a paragraph with "In summary", "In conclusion", "Overall", or "Ultimately". Concepts are reference documents; nobody arrives at the end needing a recap of the middle. If a concept needs a summary, that is the `description` field.

## Transitions

Cut "moreover", "furthermore", "in addition", "additionally". "However" and "but" are fine, sparingly. Sequential facts do not need connective tissue announcing that they are sequential.

## Openings

No rhetorical questions, no scene-setting, no "Have you ever wondered". A concept opens with its subject.

> **No.** What makes a service-level agreement work in a federated university?
> **Yes.** SLAs here are negotiated per department, not centrally.

# Punctuation

**Em dash.** At most one per paragraph, and only for a genuine aside. Where a comma works, use a comma. Where the aside is long, use a full stop. This is the most-cited tell and the easiest to overrun.

**En dash** for numeric and date ranges: 2019–2022, pages 4–7. Not a hyphen.

**Straight quotes and apostrophes**, not curly. Curly quotes are a copy-paste signature.

**Oxford comma:** no, unless the sentence is ambiguous without it. Wikipedia lists its consistent presence as a tell; the deeper point is consistency, and the house default here is off.

**Exclamation marks:** none.

**Emoji:** none, anywhere, including headings.

# Formatting

This vault instructs the librarian to favour structural markdown, and Wikipedia's essay flags heavy structure as a tell. Both are right, and the reconciliation matters:

**Structure is earned by the content, never applied as decoration.** A table is correct when the content is genuinely tabular — a chronology, an attendee roster, an org structure. A list is correct when the items are genuinely parallel. Neither is correct as a way of making three sentences look organised.

Concrete rules:

- **No bold-colon-restatement bullets.** The `**Term:** The term is a thing that does term-like work.` pattern is the single most recognisable ChatGPT artefact. If a term needs defining, it is a table with a definition column, or it is prose.
- **Bold sparingly**, for a genuine warning or a term at its point of definition. Never on every list item. Never on product names.
- **Sentence case in headings**, always. Title Case On Every Heading is a tell.
- **Prose is allowed to be prose.** A `Decision` concept is an argument, and arguments do not tabulate. Do not bullet a narrative to look structured.
- No horizontal rules as decoration.
- No markdown artefacts left in text: stray `**`, `##`, or numbered lists that restart at 1.

# Voice

Plain, specific, direct. Short sentences carrying facts. Vary sentence length so the rhythm is not machine-even — Wikipedia lists uniform sentence length and repeated structure as a tell in its own right.

Concepts are written in the third person, about their subject and about their own making alike. A coverage note, a caveat or an open question is still the concept speaking, not the librarian: "No page in this scope states the naming rule" rather than "I did not find a page that states the naming rule".

This said the opposite until 22.08.2026, on the reasoning that first person beats passive evasion. The reasoning was right and the inference was wrong. The cure for "the 2023 pages were not read" is not the pronoun — it is "this scope does not cover the 2023 pages", which names an agent and evades nothing. What the old rule could not anticipate is that a corpus built from one person's own notes makes the pronoun ambiguous in a way it would not be elsewhere: a reader meeting "I use this table to place people in streams" cannot tell whether the "I" is the note's author or the compile agent that wrote the sentence.

`verify.py` enforces this. Quotes and their bracketed glosses are exempt, because there the "I" belongs to the person quoted and stays verbatim, as do roman numerals and bare letters used as labels.

Never write a compliment about the subject matter. Never editorialise on whether a decision was good. If the outcome is known, state the outcome and cite it; the reader draws the conclusion.

# Regional conventions

**British English**, not American: organisation, prioritise, analyse, behaviour, licence (noun) / license (verb), programme (a body of work) / program (software). LLMs default to American spelling, which makes consistent British spelling a small anti-tell as well as the correct register here.

**Local conventions** where they apply. This vault's are Swiss: thousands separator `1'500`, currency as `CHF 4,500` or `kCHF 45`, dates in prose as `12.03.2024`, dates in frontmatter and tables as ISO `2024-03-12`. Replace them with your own and keep them consistent — consistency is the point, not the particular choice.

**Source-language terms** keep their real names and are never translated — meeting series, org units, roles and document types alike. Gloss on first use in a concept, then use plainly. These are the strings the archive is searched with; translating them severs the concept from its source. List the ones your corpus actually uses here, so a run can recognise them.

# Self-check

Before saving anything:

1. Search the text for every word in the banned vocabulary list.
2. Count em dashes. More than one per paragraph means rewrite.
3. Find every `-ing` word that ends a sentence and ask whether it adds a fact.
4. Find every bolded item and justify it.
5. Find every opinion and confirm it has a footnote resolving to a `sources[].id`.
6. Read the first sentence of each paragraph in sequence. If they could open any document on any subject, the paragraphs are padding.

# Provenance

The rules above are derived from *Wikipedia:Signs of AI writing*. That page could not be retrieved directly in this session — Wikipedia is served from cache to this environment and the fetch was refused — so the essay's content was reconstructed from five secondary sources that quote it, cross-checked against each other. The categories, example phrases and constructions are consistent across all five and match the essay as published.

Two consequences worth knowing:

- The essay is roughly 15,000 words. This file covers its language, style, punctuation and formatting sections, which is what applies to a private knowledge base. It omits the sections specific to Wikipedia itself: broken wikitext, citation-template misuse, fabricated references, and the encyclopaedia's own notability and neutrality policies.
- If the page is fetched directly later, this file should be checked against it and the provenance note updated.

Sources cross-checked: [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) (target, not fetched) · [ETBI Digital Library summary](https://library.etbi.ie/sources2/aisigns) · [Beutler Ink](https://www.beutlerink.com/blog/how-to-spot-ai-writing) · [MakeUseOf](https://www.makeuseof.com/wikipedia-best-ai-writing-detection-guide/) · [HumanizeAI](https://humanizeai.com/blog/wikipedias-signs-of-ai-writing-list-plus-a-prompt-you-can-turn-into-a-skill/) · [Blake Stockton](https://www.blakestockton.com/takeaways-from-wikipedias-signs-of-ai-writing-2/)
