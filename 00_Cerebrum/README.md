# 00_Cerebrum — template

A self-improving system for building and maintaining knowledge bases, run locally with Claude Code as the librarian. You drop sources into a folder; the librarian reads them, distils them into linked concept documents with a footnote behind every claim, audits itself on a schedule you set, and answers questions against the corpus with full provenance.

This repository is the **machinery and none of the corpus**. There are no knowledge bases in it, `Outputs/` is empty, and nothing has read a source yet.

The knowledge bases get better the longer they are used. The machinery gets better every time it fails, because the operating rule is that **a defect class is not fixed until a check exists that catches its recurrence**. `_scripts/` is the pile of those checks.

## What you get

| | |
|---|---|
| `CLAUDE.md` | The operating manual. Every session reads it end to end. This is the substance of the system |
| `SPEC.md` | Open Knowledge Format v0.2, the format the `Wiki/` bundles are written in |
| `_KB_CLAUDE_TEMPLATE.md` | The per-knowledge-base manual, filled in when you create one |
| `About me/writing-rules.md` | House style, derived from Wikipedia's *Signs of AI writing* and inverted into instructions |
| `_skills/` | Three Claude Code skills: compile an archive, health-check a bundle, action the open items |
| `_scripts/` | The executable checks and repairs, `verify.py` first among them |
| `assertions.yaml` | Vault-level assertions `verify.py` enforces over the manuals themselves |

## Starting

```bash
python3 -m pip install --user pyyaml numpy
python3 _scripts/verify.py
```

`verify.py` is the test suite. It should print `== 00_Cerebrum (vault): 0 defects` and exit 0 on a fresh clone.

Then open the folder in Claude Code and say **"create a knowledge base for \<topic\>"**. The librarian will scaffold it from `_KB_CLAUDE_TEMPLATE.md`, add its row to the *Current state* table in `CLAUDE.md`, and tell you where to put your sources.

From there the loop is three moves, and they are the only three that are yours:

1. **Add sources.** Drop files into `<Topic>_kb/Raw/`.
2. **Ask for a compile.** "Compile the \<topic\> archive."
3. **Ask questions.** Every question is answered and filed as a report in `Outputs/`, with a corpus-sufficiency section saying what the bundle could not answer — which is how the next compile knows what to read.

To put it under git:

```bash
CEREBRUM_REMOTE=git@github.com:you/your-vault.git sh _scripts/gitsetup.sh
```

That installs `verify.py` as a pre-commit hook, so a commit on a red audit is blocked rather than merely discouraged.

**Decide the repository's visibility from what your corpus will hold.** A vault compiled from workplace or personal notes carries material that must not be public. `gitsetup.sh` will not guess a remote for you, and the corpus is deliberately never sanitised — see *Scope: everything counts* in `CLAUDE.md`.

## The viewer: specula

specula is the vault's viewer, a Mac app of its own: the 2D map, the 3D view and its Timelapse, the concepts, the question reports, a dashboard of what waits for you, and Ask Claude, which answers a question over the vault and files the report. It is published beside this template:

- **Download:** the newest `specula` release at https://github.com/kedavra-code/releases/releases, the file `specula.dmg`. macOS on Apple silicon.
- **Install:** open the image and move specula into `/Applications`.
- **Point it at this folder:** specula › Settings › Armarium › Vault folder › Choose…, then this folder. `Open 00_Cerebrum.command` checks the Claude login and then opens it.

specula reads two scripts of this folder, `_scripts/visualize.py --json` and `_scripts/dashboard.py --json`, and writes only the reports Ask Claude files in `Outputs/`. It answers only the Mac it runs on.

## The three loops

**Read** turns new material into concepts that cite it. **Repair** checks those concepts against their sources and mends them, raising what needs your judgement as a written action item. **Remember** turns each fault into a check that catches it next time.

The third is the one that compounds. When something breaks, the fix is not just the instance: it is a check in `_scripts/`, proven by putting the defect back, watching `verify.py` go red, and restoring. From then on the pre-commit hook blocks that fault for good.

## Two things worth knowing before you start

**Everything is measured, nothing is asserted.** Coverage is the share of archive pages some concept actually cites — not whether a concept exists for a scope. Counts live in generated files and are banned from the manuals, because a number in prose goes stale and nothing keeps it true. `assertions.yaml` enforces that ban on `CLAUDE.md` itself.

**The corpus is bigger than the context window, and that is the design.** A session loads its instructions and then opens the few files a question needs; scripts read what a session cannot and hand back a summary; sub-agents read batches in windows that are not the session's. Nothing ever loads the vault.

## About the comments

The scripts and skills carry the incidents that produced their rules — a check exists because something broke, and the comment says what. Those incidents come from the vault this template was extracted from. Knowledge-base names have been replaced with neutral placeholders (`Alpha_kb`, `Beta_kb`, `Gamma_kb` and so on); no corpus content, no personal data, and no real organisation names remain. The reasoning is kept because it is the most useful part.

## Requirements

- Python 3 with `pyyaml` and `numpy`
- Claude Code
- Optional: specula, the viewer (see *The viewer: specula* above)
- Optional: Obsidian, for reading the vault by hand

## Credit

The pattern is Andrej Karpathy's LLM Knowledge Base, adapted to run locally. The house style is derived from Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup. The bundle format is Open Knowledge Format v0.2, specified in `SPEC.md`.

## Licence

MIT. See `LICENSE`.
