"""What a bundle is, in one place: where the vault is, what frontmatter looks
like, which folders are knowledge bases, which files are concepts, what a
base's assertions hold, one parse of each frontmatter block, and how a script
with a hyphen in its name is loaded.

Written 04.10.2026, in the clean-up after the review of the scripts. Until
then each script answered these for itself: the frontmatter pattern stood in
twelve files, `discover()` in seven, the concept walk in seventeen places and
the by-path loader in nine. The copies agreed that day, and that was luck with a
history: a fix had always landed in one of them, which is how `_to_delete/`
came to be counted as concepts twice (see `linkcheck.py` and
`attachment-register.py`) and how a `.claude` folder became an archive
chapter. Every output of every script was the same before and after the
copies were joined.

Three walks were left as they are, each for a reason of its own:
`visualize.py` meets concepts directory by directory and the order decides
the layout, `meetings.py` reads the bin as well, and `attribution-scan.py`
leaves `questions.md` out and reports in its own order.

It imports nothing of the vault's and nothing outside the standard library
at load, so any script can import it. PyYAML is asked for only where a parse
is made, which keeps the scripts that run without it running.
"""
import glob
import importlib.util
import os
import re
import unicodedata

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FM = re.compile(r'^---\n(.*?)\n---\n', re.S)
FENCE = re.compile(r'```.*?```', re.S)


def discover():
    """Every knowledge base: a folder with a `Wiki/` and a `CLAUDE.md`."""
    return sorted(d for d in os.listdir(VAULT)
                  if os.path.isdir(os.path.join(VAULT, d, 'Wiki'))
                  and os.path.exists(os.path.join(VAULT, d, 'CLAUDE.md')))


def assertions(kb=''):
    """A knowledge base's `assertions.yaml`, or the vault's own when kb is ''.

    The vault's file had a reader of its own, `vault_assertions()`, with this
    body and the path one folder up. Joined on 04.10.2026 in a review: joining
    VAULT with '' is VAULT, so the same file is opened.
    """
    import yaml
    p = os.path.join(VAULT, kb, 'assertions.yaml')
    if not os.path.exists(p):
        return {}
    return yaml.safe_load(open(p, encoding='utf-8')) or {}


def concept_files(kb, indexes=False):
    """Every concept file of a bundle, sorted: no index, no log, no bin.

    One walk for the audit and for every script that reads or repairs a
    bundle. The audit, `readset.py` and `readblocks.py` were joined in the
    review of 04.10.2026 and the rest in the clean-up of the same day; they
    gave the same files on all six bases, so nothing a script reports moved.

    `indexes` adds each directory's `index.md` and the bundle's `log.md`.
    `fix-runons.py` asks for them, because it has always repaired those too.
    """
    return [f for f in sorted(glob.glob(os.path.join(VAULT, kb, 'Wiki', '**',
                                                     '*.md'), recursive=True))
            if '_to_delete' not in f
            and (indexes or os.path.basename(f) not in ('index.md', 'log.md'))]


# One parse of each frontmatter block per process. `verify.py` parses a
# concept's frontmatter, then asks `coverage.py`, `reindex.py` and
# `stale-claims.py` about the same bundle, and each of them parsed the same
# block again: one whole-vault run asked for 5'103 parses of 1'138 distinct
# blocks, and parsing was 38 of the run's 62 profiled seconds. A run took 47
# seconds before 04.10.2026 and 14 after, this and the anchored `NOCONCEPT`
# pattern together.
#
# So the parse is remembered by the block's own text. Same loader, same text,
# same value. A block that does not parse stores nothing and raises as it did,
# so every caller's own `except` still sees it.
#
# **It has to be one object.** `verify.py` loads `coverage.py` and
# `stale-claims.py` by path, as separate instances, and a dict held in any one
# of them would be a dict per instance. An imported module is shared by all of
# them. It was a module of its own, `frontmatter.py`, for some hours of
# 04.10.2026, and was folded in here the same day.
#
# **The value is shared too, so no caller may change it.** None did that day:
# each reads keys and iterates `sources`, and after a whole run every stored
# value still equalled a fresh parse. A caller that needs to edit a parsed
# block copies it first.
_parsed = {}


def frontmatter(block):
    """`yaml.safe_load(block)`, parsed once per process."""
    if block not in _parsed:
        import yaml
        _parsed[block] = yaml.safe_load(block)
    return _parsed[block]


def mapping(block):
    """`frontmatter(block)` where that holds keys, {} where it does not.

    An empty block parses to None and a block of `- ` lines to a list. Four
    scripts the audit calls took the parse and asked it for a key, so the
    empty block passed as no keys and the list stopped the run: found
    05.10.2026 by the kept cases of the list.
    `verify.py` reports such a block as a defect of its concept; a reader
    that only wants the keys takes this and reads none.
    """
    fm = frontmatter(block)
    return fm if isinstance(fm, dict) else {}


def canon(path):
    """One canonical spelling for a path, so that sets of pages can be compared.

    macOS stores filenames decomposed (NFD): `regulär` is `r-e-g-u-l-a-` plus a
    combining diaeresis. A citation typed or rewritten in a markdown file is
    composed (NFC), one code point for the whole letter. The two strings are
    not equal, so a set of pages read off the filesystem and a set of pages
    read out of `sources[].resource` never intersect on those names, and the
    page reads as uncited.

    Found 08.09.2026 in `coverage.py`, where this function was born as `_p`:
    a sweep rewrote citations to NFC on the way and coverage fell from 100.0
    to 92.6 per cent in `Alpha_kb` and to 96.0 in `Beta_kb`, by exactly the
    number of NFD-only filenames in each archive. It moved here on 04.10.2026
    so that every script keys a page the same way: `verify.py` keyed by the
    path as written until that day and held eleven Alpha pages as twenty-two.
    """
    return unicodedata.normalize('NFC', os.path.abspath(path))


def entries(block):
    """The `sources` entries of one frontmatter block, as the YAML gives
    them: a list of mappings, empty where the block holds none or does not
    parse, and where `sources` is no list. `sources: 5` stopped every reader
    here until 05.10.2026; `verify.py` reports it as a defect of its concept."""
    try:
        fm = frontmatter(block)
    except Exception:
        return []
    srcs = fm.get('sources') if isinstance(fm, dict) else None
    return [s for s in (srcs if isinstance(srcs, list) else []) if isinstance(s, dict)]


def sources(concept):
    """A concept's citations: a list of (entry, page), `page` being the
    canonical path its `resource` resolves to, or None where it names none.

    One reader since 04.10.2026. Until then `verify.py` and `coverage.py`
    parsed the YAML and five scripts each matched `resource:` lines with a
    pattern of their own. The patterns misread 26 of 8'072 citations in
    `Alpha_kb` and 11 of 122 in `Zeta_kb` that day: a path in double quotes,
    an entry that opens with `resource:` and not with `id:`, a path holding an
    apostrophe. Fenced blocks are taken out before the frontmatter is matched,
    as `verify.py` does, so an illustrative entry in a fence is not a citation.
    """
    m = FM.match(FENCE.sub('', open(concept, encoding='utf-8').read()))
    if not m:
        return []
    d = os.path.dirname(concept)
    return [(s, canon(os.path.join(d, str(s['resource']))) if s.get('resource') else None)
            for s in entries(m.group(1))]


def script(filename):
    """A sibling script as a module, loaded by path.

    Most scripts here carry a hyphen in their name and cannot be imported by
    it. Each call loads a fresh instance, as the loaders this replaces did:
    eight scripts each wrote out the same four lines until 04.10.2026.
    """
    name = 'cerebrum_' + os.path.splitext(filename)[0].replace('-', '_')
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(VAULT, '_scripts', filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
