#!/usr/bin/env python3
"""The viewer's local helper: Ask Claude, and the list of reports.

`00_Cerebrum_viewer.html` is one static file opened from disk, so it can read
nothing that was not baked into it and can reach nothing on its own. This
serves the two things it cannot do for itself: it answers a question by running
the librarian over the vault, and it lists what is in `Outputs/`.

**Run it yourself, from Terminal, when you want to ask something.** The viewer
opens and searches normally without it; only the Ask button greys out. Started
by hand is also the only way it works: the librarian authenticates through the
login keychain, which a session started by an agent cannot reach.

    python3 _scripts/viewer-server.py            # 127.0.0.1:8760
    python3 _scripts/viewer-server.py --port N

**Nothing leaves the Mac that the librarian does not send.** The question goes
to `claude -p` running in this vault, which is the same librarian a Terminal
session gets, under the same `CLAUDE.md` rules — so the answer arrives as a
question report in `Outputs/`, with its row in `Outputs/_REPORTS.md`, written
in the house style. The alternative, a cloud function holding an API key, would
put salary rounds and personnel assessments through someone else's service.

**It binds to 127.0.0.1 and answers only a page opened from disk.** A browser
sends `Origin: null` from a `file://` page and its real origin from anywhere
else, so any other origin is refused. Without that, a web page you happened to
be visiting could read your reports or spend money asking for one, because this
process can write to the vault and call the model.
"""
import argparse
import ctypes
import ctypes.util
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS = os.path.join(VAULT, 'Outputs')
REGISTER = os.path.join(OUTPUTS, '_REPORTS.md')
AUDIT_DIR = 'HealthChecks'
# A report's German version, same file name one folder deeper. A translation is
# the same report in another language and not a second report, so it takes no
# row in the register and `verify.py` does not ask for one. Owner's instruction
# of 16.09.2026.
DE_DIR = 'de'

# The default brain. "Opus Extra" was the owner's instruction of 16.09.2026:
# `xhigh` is the effort level of that name, one below `max`. Since the Brain
# section was added it is the default rather than the only choice, and the page
# may ask for another — but only one this file names.
MODEL = 'claude-opus-5'
EFFORT = 'xhigh'
TIMEOUT_S = 25 * 60
# A local model writes a whole report's worth of German or nothing useful.
# The longest report so far is about 7'000 tokens in, so the ceiling is set
# well above it rather than at it.
MAX_LOCAL_TOKENS = 16000

# **Where this vault keeps its own MLX weights, and it shares them with nothing.**
# An earlier draft read GLaDOS's folder instead, because 16 GB of Qwen already
# sits there and this disk is 96 per cent full. The owner refused it on
# 16.09.2026, and was right: the coupling is the path, and a path into another
# application's Application Support breaks silently the day that application
# tidies up. The vault already carries that lesson about its own knowledge
# bases; it applies the same way to a folder nothing here controls.
#
# Not inside the vault, either. The vault is an the cloud drive folder and a git
# repository, and seventeen gigabytes of weights belong in neither.
LOCAL_MODELS = os.path.expanduser(
    '~/Library/Application Support/00_Cerebrum/models')

EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']

# **The allowlist of brains, and the only place a model id is spelled.**
# Adapted from `ModelRegistry.swift` in the owner's GLaDOS, which learned the
# shape the expensive way: everything downstream asks the registry and branches
# on a capability field, never on the id string.
#
# `effort` says whether the model takes `--effort` at all — Haiku rejects it, and
# a local model has no such notion. `agentic` says whether it can run Ask Claude:
# that job is an agent which reads the vault, greps it, writes the report and
# adds the register row, and `claude -p` is that agent. A local model here is a
# text completion, prompt in and text out, with no loop and no tools. GLaDOS
# records the same trap in `LocalModelSpec.swift`: a second local model was added
# and removed the same day after 0 tool calls in 12 questions. Translating is a
# single completion, so `translates` is true for all of them.
#
# `bytes` and `revision` are pinned rather than discovered, for the same reason
# GLaDOS pins them: the download row needs a total before the first byte lands,
# and a moved `main` is a different model wearing the same name.
# The order the picker shows: Fable first, which is the one the owner reaches
# for — the same order and the same reason as GLaDOS's registry. `MODEL`
# above stays Opus: this is a display order, not a ranking, and the default
# is the model that should answer when nobody has chosen.
MODELS = [
    {'id': 'claude-fable-5-1', 'label': 'Fable 5.1', 'provider': 'anthropic',
     'effort': True, 'agentic': True, 'translates': True,
     'note': 'Warmer prose.'},
    {'id': 'claude-opus-5', 'label': 'Opus 5', 'provider': 'anthropic',
     'effort': True, 'agentic': True, 'translates': True,
     'note': 'The strongest reader.'},
    {'id': 'claude-sonnet-5', 'label': 'Sonnet 5', 'provider': 'anthropic',
     'effort': True, 'agentic': True, 'translates': True,
     'note': 'Faster and cheaper than Opus.'},
    {'id': 'claude-haiku-4-5', 'label': 'Haiku 4.5', 'provider': 'anthropic',
     'effort': False, 'agentic': True, 'translates': True,
     'note': 'The cheap one. No effort level.'},
    {'id': 'local:mlx-community/Qwen3-30B-A3B-Instruct-2507-4bit',
     'label': 'Qwen3 30B (local)', 'provider': 'local',
     'effort': False, 'agentic': False, 'translates': True,
     'repo': 'mlx-community/Qwen3-30B-A3B-Instruct-2507-4bit',
     'revision': 'e9675aa3ca5f900ccef55267914466d55ab325fa',
     'bytes': 17_197_087_380,
     'note': '30B resident, 3B read per token. The quick one.'},
    {'id': 'local:mlx-community/gemma-3-27b-it-4bit',
     'label': 'Gemma 3 27B (local)', 'provider': 'local',
     'effort': False, 'agentic': False, 'translates': True,
     'repo': 'mlx-community/gemma-3-27b-it-4bit',
     'revision': None, 'bytes': 15_600_000_000,
     'note': 'Sliding-window attention. Check its German on a long report.'},
    {'id': 'local:mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit',
     'label': 'Mistral Small 24B (local)', 'provider': 'local',
     'effort': False, 'agentic': False, 'translates': True,
     'repo': 'mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit',
     'revision': None, 'bytes': 13_400_000_000,
     'note': 'The European house. Strong multilingual.'},
]


def model_by_id(mid):
    """The descriptor for an id, or None. The allowlist is the whole guard:
    an id this file does not name never reaches a command line."""
    for m in MODELS:
        if m['id'] == mid:
            return m
    return None


def weights_dir(m):
    """Where this model's weights are, or None when they are not installed.

    One folder, this vault's own. `config.json` is the marker rather than the
    directory: a half-finished download leaves a directory behind, and a
    directory is not an installation.
    """
    if m['provider'] != 'local':
        return None
    d = os.path.join(LOCAL_MODELS, m['repo'].replace('/', '_'))
    if os.path.isdir(d) and os.path.isfile(os.path.join(d, 'config.json')):
        return d
    return None


def footprint(d):
    """What a model's folder actually occupies. Reported rather than assumed:
    the row offers to delete it and must name what that frees."""
    n = 0
    for root, _dirs, files in os.walk(d):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n


def remove_weights(mid):
    """Delete one local model's weights. Returns an error string, or None.

    **The registry and the folder are both checked.** An id this file does not
    name never gets here, and a resolved path that is not inside this vault's
    own model folder is refused whatever the registry says — a delete that
    takes a wrong turn is the one mistake in this file that cannot be undone
    by running it again.
    """
    m = model_by_id(mid)
    if not m or m['provider'] != 'local':
        return 'no such local model'
    d = weights_dir(m)
    if not d:
        return None                                   # already gone
    root = os.path.realpath(LOCAL_MODELS)
    real = os.path.realpath(d)
    if real != root and not real.startswith(root + os.sep):
        return 'that model is not in this vault\'s model folder'
    import shutil                                     # noqa: PLC0415
    try:
        shutil.rmtree(real)
    except OSError as e:
        return str(e)
    return None


def free_bytes():
    """What macOS will actually give a large download, in bytes.

    **`statvfs` is the wrong number on this Mac, and using it refused a
    download that would have worked.** The owner reported it on 16.09.2026:
    Finder said more than 150 GB free and this said 26. Both were true.
    APFS counts local Time Machine snapshots and other purgeable data as
    available and deletes them when a write needs the room — 24 snapshots
    stood on that disk, and `volumeAvailableCapacityForImportantUsage` read
    158 GB against `statvfs`'s 26.7.

    Reached through ctypes rather than pyobjc, so the helper keeps its promise
    of needing nothing installed, and falling back to `statvfs` on any Mac
    where the call does not answer — a conservative number is a refused
    download, which is the safe direction to be wrong in.
    """
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
        ctypes.cdll.LoadLibrary(ctypes.util.find_library('Foundation'))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        def send(recv, name, argtypes=(), args=(), restype=ctypes.c_void_p):
            fn = objc.objc_msgSend
            fn.restype = restype
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + list(argtypes)
            return fn(recv, objc.sel_registerName(name.encode()), *args)

        def nsstr(text):
            return send(objc.objc_getClass(b'NSString'),
                        'stringWithUTF8String:', [ctypes.c_char_p],
                        [text.encode()])

        url = send(objc.objc_getClass(b'NSURL'), 'fileURLWithPath:',
                   [ctypes.c_void_p], [nsstr(VAULT)])
        out = ctypes.c_void_p()
        ok = send(url, 'getResourceValue:forKey:error:',
                  [ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
                   ctypes.c_void_p],
                  [ctypes.byref(out),
                   nsstr('NSURLVolumeAvailableCapacityForImportantUsageKey'),
                   None], ctypes.c_bool)
        if ok and out.value:
            n = int(send(out, 'longLongValue', restype=ctypes.c_longlong))
            if n > 0:
                return n
    except Exception:                                 # noqa: BLE001
        pass
    try:
        st = os.statvfs(VAULT)
        return st.f_bavail * st.f_frsize
    except OSError:
        return 0

PROMPT = """A question was asked from the vault viewer. Answer it against the corpus.

Follow *Question report protocol* in CLAUDE.md exactly: answer from the Wiki \
first, then Raw and the archive layers; write the report to `Outputs/`, which \
is where a question report goes and not `Outputs/HealthChecks/`; add its row to \
`Outputs/_REPORTS.md`; follow `About me/writing-rules.md`. Do not run a compile, \
a health check or a git command, and change no concept.

End your reply with the report's path relative to the vault root, on a line of \
its own, and nothing else on that line.

The question:

%s
"""

# One at a time. Two librarians in one vault would write the register's last
# line twice and one of the two rows would be lost.
BUSY = threading.Lock()

TRANSLATE = """Translate one question report of this vault into German.

Read `Outputs/%(rel)s` whole, then write `Outputs/de/%(rel)s`. Write nothing \
else, change no other file, and **add no row to `Outputs/_REPORTS.md`**: a \
translation is the same report in another language, not a second report.

The same document in German. Same headings in the same order, same tables with \
the same columns and rows, same lists, same footnote labels and definitions.

What does not change:
- **German quotations stay as they are**, and the English gloss in brackets \
after one is dropped, because in a German text it explains nothing. Keep \
anything in that gloss which the quote itself does not carry.
- **Proper nouns are never translated**: org units, meeting series, roles, \
document types, systems, people, file names, paths. Central IT, \
Steering Group, standing bilateral, offsite, written warning, Bila, ToT, MAG, the programme.
- Figures, dates and ids. Currency keeps the apostrophe: `CHF 4'500`.
- Anything inside backticks or a fenced block is code.
- An English quotation stays English, with a German gloss in square brackets.

The one thing that changes besides the language: **the file sits one folder \
deeper**, so every relative link that climbs out of `Outputs/` needs one more \
`../` — `../Alpha_kb/Wiki/x.md` becomes `../../Alpha_kb/Wiki/x.md`. Check each one.

German as a Swiss reader of these notes writes it: **ss, never ß**, plain words, \
short sentences.

When you are done, print `Outputs/de/%(rel)s` on the last line and nothing else \
on that line.
"""


# **The same job told two ways, because the two kinds of model are told things
# differently.** `TRANSLATE` above is an instruction to an agent: read this
# file, write that one. A local model has no file tools — it is a completion,
# prompt in and text out — so it was handed an instruction it could not carry
# out and returned nothing, in eight seconds, on 16.09.2026. Found by running
# it rather than by reading it.
#
# This one carries the document in the prompt and asks for the German back.
# The helper writes the file, which is the part the model cannot do.
TRANSLATE_TEXT = """Translate this document into German. Reply with the German \
document and nothing else — no preamble, no explanation, no code fence.

Rules:
- Same headings in the same order, same tables with the same columns and rows, \
same lists, same footnote labels and definitions, same emphasis.
- German quotations stay exactly as they are, and the English gloss in brackets \
after one is dropped.
- Proper nouns are never translated: org units, meeting series, roles, document \
types, systems, people, file names, paths. Central IT, Steering Group, \
standing bilateral, offsite, written warning, Bila, ToT, MAG, the programme.
- Figures, dates and ids stay. Currency keeps the apostrophe: `CHF 4'500`.
- Anything inside backticks or a fenced block is code and is not translated.
- Every relative link gains one `../`, because the German file sits one folder \
deeper: `../Alpha_kb/Wiki/x.md` becomes `../../Alpha_kb/Wiki/x.md`.
- Swiss German spelling: ss, never the sharp s.

The document:

%s
"""


def run_model(prompt, emit, started_note, mid=None, effort=None):
    """Run whichever brain was asked for. Returns (text, seconds).

    The one place the two providers meet. Everything above this calls it and
    never asks which kind of model it got; everything below branches once.
    An id the registry does not name never reaches here — `_pick()` in the
    handler refuses it first.
    """
    m = model_by_id(mid) or model_by_id(MODEL)
    if m['provider'] == 'local':
        return run_local(prompt, emit, started_note, m)
    return run_claude(prompt, emit, started_note, m['id'],
                      effort if m['effort'] else None)


def run_local(prompt, emit, started_note, m):
    """Generate with MLX, in this process's own Python, on this Mac.

    MLX rather than Ollama, which is the owner's instruction of 16.09.2026 and
    the right call on this machine: Ollama would be a second stack, a daemon,
    and a second copy of weights on a disk that is 96 per cent full.

    **There are no tools and no loop.** This is a completion — prompt in, text
    out — which is why the registry marks every local model `agentic: False`.
    It is enough for a translation, which is one document in and one document
    out, and it is not enough to answer a question, which means reading the
    vault and writing files.
    """
    d = weights_dir(m)
    if not d:
        emit({'type': 'error',
              'error': '%s is not installed. Settings, Brain, Download.'
                       % m['label']})
        return None, None
    try:
        from mlx_lm import load, generate            # noqa: PLC0415
    except ImportError:
        emit({'type': 'error',
              'error': 'mlx-lm is not installed. Run: '
                       'python3 -m pip install --user mlx-lm'})
        return None, None
    emit({'type': 'step', 'phase': 'start', 'text': started_note})
    started = time.time()
    try:
        model, tok = load(d)
        emit({'type': 'step', 'phase': 'work',
              'text': 'weights loaded, writing'})
        msgs = [{'role': 'user', 'content': prompt}]
        text = tok.apply_chat_template(msgs, add_generation_prompt=True,
                                       tokenize=False)
        out = generate(model, tok, prompt=text, max_tokens=MAX_LOCAL_TOKENS,
                       verbose=False)
    except Exception as e:                            # noqa: BLE001
        emit({'type': 'error', 'error': '%s: %s' % (type(e).__name__, e)})
        return None, None
    return out, round(time.time() - started)


def run_claude(prompt, emit, started_note, mid=None, effort=None):
    """Run the librarian and report the tools it picks up. Returns its text."""
    cmd = ['claude', '-p', prompt, '--model', mid or MODEL,
           '--output-format', 'stream-json', '--verbose']
    # Haiku rejects `--effort` outright, so the flag is added rather than always
    # present. The registry says which models take it; this only obeys.
    if effort:
        cmd[3:3] = ['--effort', effort]
    emit({'type': 'step', 'phase': 'start', 'text': started_note})
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('CLAUDE') and k != 'CLAUDECODE'}
    try:
        p = subprocess.Popen(cmd, cwd=VAULT, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, bufsize=1,
                             env=env)
    except FileNotFoundError:
        emit({'type': 'error', 'error': 'claude is not on PATH'})
        return None, None
    started, result, tools = time.time(), None, 0
    try:
        for line in p.stdout:
            if time.time() - started > TIMEOUT_S:
                p.kill()
                emit({'type': 'error', 'error': 'timed out after %d minutes'
                      % (TIMEOUT_S // 60)})
                return None, None
            line = line.strip()
            if not line.startswith('{'):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get('type') == 'assistant':
                for bl in d.get('message', {}).get('content', []) or []:
                    if bl.get('type') == 'tool_use':
                        tools += 1
                        emit({'type': 'step', 'phase': 'work', 'tools': tools,
                              'text': 'reading the corpus (%s)'
                                      % bl.get('name')})
                    elif bl.get('type') == 'text' and bl.get('text', '').strip():
                        emit({'type': 'note',
                              'text': bl['text'].strip().split(chr(10))[0][:160]})
            elif d.get('type') == 'result' or 'result' in d:
                result = d
    finally:
        try:
            p.stdout.close()
        except Exception:
            pass
        p.wait()
    text = str((result or {}).get('result') or '')
    if (result or {}).get('is_error') or p.returncode not in (0, None):
        if 'authenticate' in text.lower() or 'oauth' in text.lower():
            emit({'type': 'error', 'error': 'Claude Code is signed out. Run '
                                            '`claude auth login` in Terminal, '
                                            'then ask again.'})
        else:
            emit({'type': 'error', 'error': text[:400]
                  or 'the librarian exited with code %s' % p.returncode})
        return None, None
    return text, round(time.time() - started)


def login_state():
    """How long the command-line login has left, for the viewer to show.

    The command line signs in separately from the desktop app and its login
    dies after about a month with nothing to say so: on 16.09.2026 the first
    sign was a run failing three weeks after it had expired. macOS
    notifications do not reach the owner's Mac, so the two places that do are
    the launcher and this — the page the question is asked from.
    """
    try:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location(
            'checklogin', os.path.join(VAULT, '_scripts', 'check-login.py'))
        m = ilu.module_from_spec(spec)
        spec.loader.exec_module(m)
        _, refresh, err = m.read_expiry()
        if err or refresh is None:
            return {'state': 'unknown', 'note': err or 'no expiry recorded'}
        import datetime as _dt
        days = (refresh - _dt.datetime.now()).days
        return {'state': 'expired' if days < 0
                else ('soon' if days <= m.WARN_DAYS else 'ok'),
                'days': days, 'when': refresh.strftime('%d.%m.%Y')}
    except Exception as e:                                    # noqa: BLE001
        return {'state': 'unknown', 'note': '%s' % e}


def reports():
    """Every report, read from the register — the vault's own source of truth.

    The register carries what a directory scan cannot: the scope, the question
    as asked, and whether the report is an audit. Its Promotion cell says which
    kind a report is, and `verify.py` fails a row whose folder disagrees.
    """
    if not os.path.exists(REGISTER):
        return []
    out = []
    for line in open(REGISTER, encoding='utf-8').read().split('\n'):
        if not line.startswith('| 20'):
            continue
        c = [x.strip() for x in line.strip('|').split('|')]
        if len(c) < 4:
            continue
        m = re.search(r'\[([^\]]*)\]\(([^)]+\.md)\)', c[3])
        if not m:
            continue
        rel = m.group(2)
        out.append({
            'date': c[0],
            'scope': c[1],
            'question': re.sub(r'^audit\s*[—-]\s*', '', c[2]).strip(),
            'title': m.group(1),
            'path': rel,
            'audit': rel.startswith(AUDIT_DIR + '/'),
            'exists': os.path.isfile(os.path.join(OUTPUTS, rel)),
        })
    return out


def twin(rel):
    """(language of `rel`, path of its other language, whether that exists)."""
    if rel.startswith(DE_DIR + '/'):
        other = rel[len(DE_DIR) + 1:]
        return 'de', other, os.path.isfile(os.path.join(OUTPUTS, other))
    other = '%s/%s' % (DE_DIR, rel)
    return 'en', other, os.path.isfile(os.path.join(OUTPUTS, other))


def render(rel):
    """One report as a page, in the viewer's own colours.

    Deliberately small: headings, paragraphs, lists, tables, code, links,
    bold and inline code. A report is prose and tables; anything richer is a
    concept, and concepts are rendered by the viewer itself.
    """
    path = os.path.normpath(os.path.join(OUTPUTS, rel))
    if not path.startswith(OUTPUTS + os.sep) or not os.path.isfile(path):
        return None
    md = open(path, encoding='utf-8').read()
    body, lines, i, notes = [], md.split('\n'), 0, []

    def inline(s):
        s = html.escape(s)
        s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
        # A footnote reference is a link to its definition, not the literal
        # bracket text an unaware renderer leaves behind. These reports carry
        # dozens of them, and read as noise without it.
        s = re.sub(r'\[\^([^\]]+)\](?!:)',
                   lambda m: '<sup class="fr"><a href="#fn-%s">%s</a></sup>'
                   % (re.sub(r'[^\w.-]', '', m.group(1)), m.group(1)), s)
        s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', s)
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
        return s

    while i < len(lines):
        ln = lines[i]
        # A figure. `2026-09-02_two-loops-of-self-learning.md` carries three
        # hand-authored SVGs inline, and every line of this renderer is escaped,
        # so the reader got the markup instead of the picture — reported by the
        # owner on 16.09.2026. Obsidian renders them, so the report was right
        # and the renderer was missing a case.
        #
        # Only `<svg>`, and not raw HTML in general: passing everything through
        # would mean any line a report ever quoted from a source became live
        # markup on a page this helper serves. A script inside the figure is cut
        # even so, and so is an inline event handler — a figure is a drawing,
        # and neither belongs in one.
        if ln.lstrip().startswith('<svg'):
            j = i
            while j < len(lines) and '</svg>' not in lines[j]:
                j += 1
            raw = '\n'.join(lines[i:j + 1])
            raw = re.sub(r'(?is)<script.*?</script>', '', raw)
            raw = re.sub(r'(?is)<\s*/?\s*(?:script|iframe|object|embed)\b[^>]*>',
                         '', raw)
            raw = re.sub(r'(?i)\son\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)',
                         '', raw)
            body.append('<figure class="fig">%s</figure>' % raw)
            i = j + 1
            continue
        if ln.startswith('```'):
            j = i + 1
            while j < len(lines) and not lines[j].startswith('```'):
                j += 1
            body.append('<pre><code>%s</code></pre>'
                        % html.escape('\n'.join(lines[i + 1:j])))
            i = j + 1
            continue
        # A footnote definition. Collected and rendered at the end under its
        # own heading, as a reader expects and as Obsidian shows them.
        fm = re.match(r'^\[\^([^\]]+)\]:\s*(.*)$', ln)
        if fm:
            notes.append((fm.group(1), fm.group(2)))
            i += 1
            continue
        if ln.startswith('#'):
            n = len(ln) - len(ln.lstrip('#'))
            body.append('<h%d>%s</h%d>' % (min(n, 4), inline(ln[n:].strip()),
                                           min(n, 4)))
            i += 1
            continue
        if ln.startswith('|'):
            j = i
            rows = []
            while j < len(lines) and lines[j].startswith('|'):
                rows.append(lines[j])
                j += 1
            cells = [[c.strip() for c in r.strip().strip('|').split('|')]
                     for r in rows]
            cells = [c for c in cells
                     if not re.match(r'^[\s:|-]+$', '|'.join(c))]
            if cells:
                head = ''.join('<th>%s</th>' % inline(c) for c in cells[0])
                rest = ''.join(
                    '<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c)
                                            for c in r) for r in cells[1:])
                body.append('<table><thead><tr>%s</tr></thead><tbody>%s'
                            '</tbody></table>' % (head, rest))
            i = j
            continue
        if re.match(r'^\s*(?:[-*+]|\d+\.)\s+', ln):
            j, items = i, []
            while j < len(lines) and re.match(r'^\s*(?:[-*+]|\d+\.)\s+',
                                              lines[j]):
                items.append(re.sub(r'^\s*(?:[-*+]|\d+\.)\s+', '', lines[j]))
                j += 1
            tag = 'ol' if re.match(r'^\s*\d+\.', ln) else 'ul'
            body.append('<%s>%s</%s>' % (tag, ''.join(
                '<li>%s</li>' % inline(x) for x in items), tag))
            i = j
            continue
        if not ln.strip():
            i += 1
            continue
        j = i
        para = []
        while j < len(lines) and lines[j].strip() \
                and not lines[j].startswith(('#', '|', '```')) \
                and not re.match(r'^\s*(?:[-*+]|\d+\.)\s+', lines[j]):
            para.append(lines[j])
            j += 1
        body.append('<p>%s</p>' % inline(' '.join(para)))
        i = j

    if notes:
        body.append('<h2 class="fnh">Sources</h2><div class="fns">' + ''.join(
            '<div class="fn" id="fn-%s"><span class="fl">%s</span>%s</div>'
            % (re.sub(r'[^\w.-]', '', k), html.escape(k), inline(v))
            for k, v in notes) + '</div>')
    # The language switcher. Two buttons, the current one lit, in the page's own
    # grammar — the viewer's mode pair, one level quieter. The other language is
    # a link when it exists and a button that makes it when it does not: the
    # owner chose translation on demand over writing every report twice, so the
    # first press of DE on a new report is where the German comes from.
    lang, other, have = twin(rel)
    sw = ('<nav class="lang" aria-label="Language">'
          '<a class="lg%s" href="/report/%s" hreflang="en">EN</a>'
          '<a class="lg%s" href="/report/%s" hreflang="de">DE</a></nav>'
          % (' on' if lang == 'en' else '',
             html.escape(rel if lang == 'en' else other),
             ' on' if lang == 'de' else '',
             html.escape(other if lang == 'en' else rel))
          ) if have else (
          '<nav class="lang" aria-label="Language">'
          '<a class="lg%s" href="/report/%s">EN</a>'
          '<button class="lg make" data-rel="%s" title="No German version yet. '
          'This writes one, which takes about a minute.">DE</button></nav>'
          % (' on' if lang == 'en' else '',
             html.escape(rel if lang == 'en' else other),
             html.escape(rel if lang == 'en' else other)))

    title = os.path.basename(rel)[:-3]
    return PAGE % {'switch': sw, 'title': html.escape(title),
                   'body': '\n'.join(body),
                   'rel': html.escape(rel)}


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title><style>
/* The viewer's own palette, copied from `visualize.py`, so a report opened from
   the reports window looks like the vault it came from rather than like a
   browser default: the dark ground, the gold accent on every heading, the
   parchment body text. Kept literal rather than imported, because this page is
   served on its own and there is nothing here to inherit from. */
:root{color-scheme:dark;--bg:#242424;--fg:#f9f2d9;--mut:#a49a85;--line:#3a3733;
 --acc:#f0c755;--h3:#e5d5a1;--side:#191919;--card:#2b2b2b;--item:#bbaf96}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);overflow-x:hidden;
 font:15.2px/1.62 -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}
/* Centred, and using the width it is given. 76ch was a book column on a wide
   screen and left two thirds of the window empty; the owner asked for more of
   it on 16.09.2026. Capped at 1200px so a very wide window does not stretch a
   line past reading, and 90vw so a narrow one keeps its margins. */
main{max-width:min(1200px,90vw);margin:0 auto;padding:44px 32px 96px}
.crumb{color:var(--mut);font-size:.82em;letter-spacing:.06em;
 text-transform:uppercase;margin:0 0 14px}
h1,h2{color:var(--acc);font-weight:700}
h1{font-size:1.72em;line-height:1.24;margin:.1em 0 .7em}
h2{font-size:1.3em;margin:1.8em 0 .5em}
h3{color:var(--h3);font-size:1.08em;margin:1.5em 0 .4em}
h4{color:var(--item);font-size:.99em;margin:1.2em 0 .3em}
p{margin:.78em 0}
a{color:var(--acc)}
strong{color:var(--fg)}
code{background:var(--card);border-radius:4px;padding:1px 5px;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.86em;
 color:var(--item);overflow-wrap:anywhere}
/* Nothing scrolls sideways. A code block wraps at its own width and a table
   lays its columns out inside the page, because a horizontal scrollbar hides
   content behind a gesture nobody makes. Owner's instruction of 16.09.2026. */
pre{background:var(--side);border:1px solid var(--line);border-radius:8px;
 padding:12px 14px;white-space:pre-wrap;overflow-wrap:anywhere}
pre code{background:none;padding:0;color:var(--fg)}
table{border-collapse:collapse;margin:1.1em 0;font-size:.93em;width:100%%;
 table-layout:auto}
/* `break-word`, not `anywhere`: `anywhere` lets a column shrink to its
   narrowest possible break, which cut "Method" into "Metho / d" in a first
   column of one-word headings. `break-word` breaks only a word that cannot
   fit the line as it stands, so a column keeps its natural width. */
th,td{border:1px solid var(--line);padding:7px 11px;text-align:left;
 vertical-align:top;overflow-wrap:break-word}
th{background:var(--side);color:var(--acc);font-weight:600}
/* A figure takes the column's width and keeps its own proportions. The SVGs
   carry a viewBox and no width, so without this they render at whatever the
   browser guesses. Centred, because they are drawings and not text. */
figure.fig{margin:1.6em 0;text-align:center}
figure.fig svg{max-width:100%%;height:auto;display:block;margin:0 auto}
ul,ol{padding-left:1.4em}
li{margin:.3em 0}
hr{border:0;border-top:1px solid var(--line);margin:2em 0}
.fr{font-size:.7em;line-height:0}
.fr a{color:var(--mut);text-decoration:none;padding:0 1px}
.fr a:hover{color:var(--acc)}
.fnh{font-size:1.1em}
.fns{font-size:.88em;color:var(--mut)}
.fn{margin:.35em 0;padding-left:1.2em;text-indent:-1.2em}
.fn:target{color:var(--fg)}
.fl{color:var(--item);margin-right:.5em}
/* The language switcher, the viewer's mode pair one level quieter: two small
   buttons, the current language lit, no hover rule. It sits with the crumb so
   it is the first thing on the page and never moves the prose. */
.top{display:flex;align-items:baseline;justify-content:space-between;gap:16px;
 margin:0 0 14px}
.top .crumb{margin:0}
.lang{display:flex;gap:6px;flex:0 0 auto}
.lang .lg{display:inline-flex;align-items:center;justify-content:center;
 min-width:34px;padding:3px 8px;border:1px solid var(--line);border-radius:6px;
 background:transparent;color:var(--item);font:inherit;font-size:.78em;
 letter-spacing:.06em;text-decoration:none;cursor:pointer}
.lang .lg.on{border-color:var(--acc);color:var(--acc)}
.lang .lg.make{border-style:dashed;color:var(--mut)}
.lang .lg.make.busy{border-color:var(--acc);color:var(--acc)}
</style></head><body><main>
<div class="top"><p class="crumb">Outputs / %(rel)s</p>%(switch)s</div>
%(body)s
</main>
<script>
/* The DE button on a report that has no German version yet writes one. It is a
   plain POST and a wait, with the button saying so: a translation takes about a
   minute and a page that looks unchanged for a minute looks broken. */
const mk = document.querySelector('.lang .make');
if (mk) mk.addEventListener('click', async () => {
  if (mk.classList.contains('busy')) return;
  mk.classList.add('busy'); mk.textContent = 'DE …';
  try {
    const r = await fetch('/translate', {method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({path: mk.dataset.rel})});
    const d = await r.json();
    if (d.path) { location.href = '/report/' + d.path; return; }
    mk.textContent = 'DE'; mk.classList.remove('busy');
    mk.title = d.error || 'the translation did not finish';
  } catch (e) {
    mk.textContent = 'DE'; mk.classList.remove('busy'); mk.title = e.message;
  }
});
</script>
</body></html>
"""


def ask(question, emit, mid=None, effort=None):
    """Run the librarian over the vault and report what it is doing.

    Milestones come from `claude -p --output-format stream-json`: one per tool
    the librarian picks up. They are real steps, not a timer — a bar that moves
    on its own says a run is progressing when it may be stuck.
    """
    before = set(os.listdir(OUTPUTS))
    m = model_by_id(mid) or model_by_id(MODEL)
    note = 'asking the librarian, %s' % m['label']
    if m['effort'] and effort:
        note += ' at %s effort' % effort
    text, secs = run_model(PROMPT % question, emit, note, m['id'], effort)
    if text is None:
        return
    # The path the librarian printed, else whatever appeared in Outputs/.
    rel = None
    for cand in reversed([x.strip() for x in text.split('\n') if x.strip()]):
        m = re.search(r'((?:Outputs/)?[\w./-]+\.md)$', cand)
        if m:
            r = m.group(1).replace('Outputs/', '', 1)
            if os.path.isfile(os.path.join(OUTPUTS, r)):
                rel = r
                break
    if not rel:
        fresh = [f for f in set(os.listdir(OUTPUTS)) - before
                 if f.endswith('.md')]
        rel = sorted(fresh)[-1] if fresh else None
    # Every report exists in both languages. Owner's instruction of 16.09.2026:
    # the German version used to be written on demand, from the dashed DE button
    # on the report itself, and the owner wants both without asking for the
    # second. It runs here rather than being left to the next session, because
    # this is the one moment the report is certainly finished and nobody has to
    # remember. A translation that fails does not fail the question: the English
    # report is filed and correct, and the DE button is still there.
    de = None
    if rel:
        de, err, de_secs = write_german(rel, emit, mid, effort)
        secs += de_secs
    emit({'type': 'done', 'path': rel, 'de': de, 'seconds': secs,
          'text': text.strip()[-600:]})


def write_german(rel, emit, mid=None, effort=None):
    """Write `Outputs/de/<rel>`. Returns (path or None, reason, seconds).

    It emits the librarian's steps and nothing that ends a stream, so both the
    caller that answers a POST and the caller that is mid-question can use it.
    """
    if rel.startswith(DE_DIR + '/'):
        rel = rel[len(DE_DIR) + 1:]
    src = os.path.normpath(os.path.join(OUTPUTS, rel))
    if not src.startswith(OUTPUTS + os.sep) or not os.path.isfile(src):
        return None, 'no such report', 0
    out = '%s/%s' % (DE_DIR, rel)
    if os.path.isfile(os.path.join(OUTPUTS, out)):
        return out, '', 0
    m = model_by_id(mid) or model_by_id(MODEL)
    note = 'writing the German version with %s' % m['label']
    if m['agentic']:
        text, secs = run_model(TRANSLATE % {'rel': rel}, emit, note,
                               m['id'], effort)
        if text is None:
            return None, 'the librarian could not be run', secs
        if os.path.isfile(os.path.join(OUTPUTS, out)):
            return out, '', secs
        return None, 'the librarian finished without writing it', secs

    # A completion model is handed the document and gives the German back; the
    # file is written here, because writing files is the part it cannot do.
    english = open(src, encoding='utf-8').read()
    text, secs = run_model(TRANSLATE_TEXT % english, emit, note, m['id'], effort)
    if text is None:
        return None, 'the model could not be run', secs
    text = text.strip()
    # Some models wrap a whole document in a fence despite being told not to.
    if text.startswith('```'):
        text = re.sub(r'^```[a-z]*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
    text = swiss(text)
    if len(text) < len(english) // 4:
        return None, ('the model returned %d characters for a %d-character '
                      'report' % (len(text), len(english))), secs
    dest = os.path.join(OUTPUTS, out)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(text.rstrip() + chr(10))
    os.replace(tmp, dest)
    return out, '', secs


def translate(rel, emit, mid=None, effort=None):
    """Write the German version of one report, and say where it went."""
    out, err, secs = write_german(rel, emit, mid, effort)
    if out:
        emit({'type': 'done', 'path': out, 'seconds': secs})
    else:
        emit({'type': 'error', 'error': err})


def model_rows():
    """The registry as the page needs it: labels, capabilities, and whether the
    weights are actually here. Capability is read from the registry; presence is
    read from the disk, every time it is asked, because the answer changes when
    a download finishes or a folder is deleted."""
    free = free_bytes()
    out = []
    for m in MODELS:
        d = weights_dir(m)
        out.append({'id': m['id'], 'label': m['label'],
                    'provider': m['provider'], 'effort': m['effort'],
                    'agentic': m['agentic'], 'note': m['note'],
                    'installed': m['provider'] != 'local' or bool(d),
                    'bytes': m.get('bytes'), 'repo': m.get('repo'),
                    'onDisk': footprint(d) if d else 0,
                    'fits': (m.get('bytes') or 0) + (2 << 30) < free})
    return {'models': out, 'efforts': EFFORTS, 'default': MODEL,
            'defaultEffort': EFFORT, 'free': free,
            'mlx': mlx_installed(), 'dir': LOCAL_MODELS}


def mlx_installed():
    try:
        import mlx_lm                                 # noqa: F401, PLC0415
        return True
    except ImportError:
        return False


def pull(mid, emit):
    """Fetch one model's weights from Hugging Face, file by file, with progress.

    **It refuses a transfer it cannot finish.** The disk is the reason: with two
    gigabytes of headroom demanded on top of the model's own size, a download
    that would fill the volume never starts. A part file is written beside the
    target and renamed when its bytes are all there, so an interrupted download
    resumes at whole-file granularity rather than leaving a plausible-looking
    truncated shard. `config.json` is written last, because it is what
    `weights_dir` reads as proof of an installation.
    """
    m = model_by_id(mid)
    if not m or m['provider'] != 'local':
        emit({'type': 'error', 'error': 'no such local model'})
        return
    if weights_dir(m):
        emit({'type': 'done', 'path': m['id'], 'seconds': 0})
        return
    need = (m.get('bytes') or 0) + (2 << 30)
    free = free_bytes()
    if free < need:
        emit({'type': 'error',
              'error': '%s needs about %s of disk and there is %s free. '
                       'Weights stay on disk whether or not they are loaded, '
                       'so this is space rather than memory.'
                       % (m['label'], _gb(m.get('bytes') or 0), _gb(free))})
        return
    import urllib.request                             # noqa: PLC0415
    base = 'https://huggingface.co/%s/resolve/%s/' % (
        m['repo'], m.get('revision') or 'main')
    dest = os.path.join(LOCAL_MODELS, m['repo'].replace('/', '_'))
    os.makedirs(dest, exist_ok=True)
    emit({'type': 'step', 'phase': 'start',
          'text': 'listing %s' % m['repo']})
    try:
        api = 'https://huggingface.co/api/models/%s/tree/%s?recursive=true' % (
            m['repo'], m.get('revision') or 'main')
        with urllib.request.urlopen(api, timeout=60) as r:
            tree = json.load(r)
    except Exception as e:                            # noqa: BLE001
        emit({'type': 'error', 'error': 'could not list the model: %s' % e})
        return
    files = [t['path'] for t in tree if t.get('type') == 'file']
    if 'config.json' not in files:
        emit({'type': 'error', 'error': 'that repository carries no config.json'})
        return
    # config.json last: it is the marker an installation is complete.
    files = [f for f in files if f != 'config.json'] + ['config.json']
    total = sum(t.get('size') or 0 for t in tree if t.get('type') == 'file')
    got = 0
    for name in files:
        target = os.path.join(dest, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.isfile(target):
            got += os.path.getsize(target)
            emit({'type': 'step', 'phase': 'work', 'received': got,
                  'total': total, 'text': 'have %s' % name})
            continue
        part = target + '.part'
        try:
            with urllib.request.urlopen(base + name, timeout=300) as r, \
                    open(part, 'wb') as f:
                while True:
                    chunk = r.read(1 << 22)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    emit({'type': 'step', 'phase': 'work', 'received': got,
                          'total': total, 'text': name})
            os.replace(part, target)
        except Exception as e:                        # noqa: BLE001
            try:
                os.remove(part)
            except OSError:
                pass
            emit({'type': 'error', 'error': '%s failed: %s' % (name, e)})
            return
    emit({'type': 'done', 'path': m['id'], 'seconds': 0})


def swiss(text):
    """Swiss German has no sharp s. Qwen writes one anyway.

    Measured on 16.09.2026: the first local translation matched Opus's on
    headings, tables, footnote labels and links, and differed on exactly this.
    The prompt asks for `ss` and the model does not obey, so the rule is
    applied rather than requested — it is a spelling convention with one
    correct mapping, which is the kind of rule a script should hold.

    Code is left alone. A fenced block and a backticked span may carry an
    identifier, and an identifier is not German.
    """
    out, i = [], 0
    for m in re.finditer(r'```.*?(?:```|\Z)|`[^`\n]*`', text, re.S):
        out.append(text[i:m.start()].replace('\u00df', 'ss'))
        out.append(m.group(0))
        i = m.end()
    out.append(text[i:].replace('\u00df', 'ss'))
    return ''.join(out)


def _gb(n):
    return '%.1f GB' % (n / 1e9)


class Handler(BaseHTTPRequestHandler):
    server_version = 'CerebrumViewerHelper/1.0'

    def _allowed(self):
        """Only a page opened from disk, or a tool with no Origin at all."""
        o = self.headers.get('Origin')
        return o in (None, '', 'null')

    def _head(self, code=200, ctype='application/json', stream=False):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Access-Control-Allow-Origin', 'null')
        self.send_header('Access-Control-Allow-Headers', 'content-type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Vary', 'Origin')
        if stream:
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()

    def _json(self, obj, code=200):
        self._head(code)
        self.wfile.write(json.dumps(obj).encode())

    def do_OPTIONS(self):
        self._head(204, 'text/plain')

    def do_GET(self):
        if not self._allowed():
            return self._json({'error': 'this helper answers only the viewer'},
                              403)
        path = self.path.split('?')[0]
        if path in ('/health', '/'):
            return self._json({'ok': True, 'vault': VAULT, 'model': MODEL,
                               'effort': EFFORT,
                               'busy': BUSY.locked(),
                               'login': login_state(),
                               'reports': len(reports())})
        if path == '/models':
            return self._json(model_rows())
        if path == '/reports':
            return self._json({'reports': reports()})
        if path.startswith('/report/'):
            page = render(path[len('/report/'):])
            if page is None:
                return self._json({'error': 'no such report'}, 404)
            self._head(200, 'text/html; charset=utf-8')
            return self.wfile.write(page.encode('utf-8'))
        return self._json({'error': 'no such endpoint'}, 404)

    def _pick(self, body, job):
        """The model and effort a request asked for, or a reason to refuse.

        **The allowlist is the whole guard.** An id goes on a command line and
        names a folder on disk, so nothing that `MODELS` does not name gets
        past here. The job is checked too: a local model has no agent loop, so
        it cannot answer a question, and saying that plainly beats letting it
        run and produce nothing.
        """
        mid = (body.get('model') or MODEL).strip()
        m = model_by_id(mid)
        if not m:
            return None, None, 'this helper does not know the model %r' % mid[:60]
        if job == 'ask' and not m['agentic']:
            return None, None, ('%s runs on this Mac and cannot read the '
                                'vault. It translates. Ask needs a Claude '
                                'model.' % m['label'])
        if job == 'translate' and not m['translates']:
            return None, None, '%s cannot translate' % m['label']
        effort = (body.get('effort') or EFFORT).strip()
        if effort not in EFFORTS:
            return None, None, 'no such effort level %r' % effort[:30]
        return m['id'], (effort if m['effort'] else None), None

    def do_POST(self):
        if not self._allowed():
            return self._json({'error': 'this helper answers only the viewer'},
                              403)
        route = self.path.split('?')[0]
        if route not in ('/ask', '/translate', '/models/pull',
                         '/models/delete'):
            return self._json({'error': 'no such endpoint'}, 404)
        n = int(self.headers.get('content-length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            body = {}

        # Deleting is instant and answers plainly. **A failure must reach the
        # reader**: GLaDOS's own review found the message written only under the
        # not-installed branch, so a failed delete left the row installed and
        # said nothing, after the reader had confirmed a destructive action.
        if route == '/models/delete':
            mid = (body.get('model') or '').strip()
            if not BUSY.acquire(blocking=False):
                return self._json({'error': 'the librarian is busy'}, 409)
            try:
                print('[delete] %s' % mid[:120], flush=True)
                err = remove_weights(mid)
            finally:
                BUSY.release()
            if err:
                return self._json({'error': err}, 400)
            return self._json({'ok': True})

        # Downloading streams, because seventeen gigabytes is minutes of
        # silence otherwise. It takes the same lock as a question: one heavy
        # job at a time, and a download while a report is being written would
        # have them fighting for the same memory.
        if route == '/models/pull':
            mid = (body.get('model') or '').strip()
            if not BUSY.acquire(blocking=False):
                return self._json({'error': 'the librarian is busy'}, 409)
            self._head(200, 'text/event-stream', stream=True)

            def emit_pull(obj):
                try:
                    self.wfile.write(
                        ('data: %s\n\n' % json.dumps(obj)).encode())
                    self.wfile.flush()
                except (BrokenPipeError, ValueError):
                    pass
            try:
                print('[pull] %s' % mid[:120], flush=True)
                pull(mid, emit_pull)
            except Exception as e:                   # noqa: BLE001
                emit_pull({'type': 'error',
                           'error': '%s: %s' % (type(e).__name__, e)})
            finally:
                BUSY.release()
            return

        # Translating answers with the finished path rather than a stream: the
        # page that asks for it is the report itself, and all it does with the
        # answer is go there.
        if route == '/translate':
            rel = (body.get('path') or '').strip()
            if not rel:
                return self._json({'error': 'no report named'}, 400)
            mid, effort, why = self._pick(body, 'translate')
            if why:
                return self._json({'error': why}, 400)
            if not BUSY.acquire(blocking=False):
                return self._json({'error': 'the librarian is busy'}, 409)
            got = {}
            try:
                print('[translate] %s (%s)' % (rel[:120], mid), flush=True)
                translate(rel, lambda e: got.update(e)
                          if e.get('type') in ('done', 'error') else None,
                          mid, effort)
            finally:
                BUSY.release()
            if got.get('type') == 'done':
                return self._json({'path': got['path'],
                                   'seconds': got.get('seconds')})
            return self._json({'error': got.get('error')
                               or 'the translation did not finish'}, 500)

        q = (body.get('question') or '').strip()
        if not q:
            return self._json({'error': 'no question'}, 400)
        mid, effort, why = self._pick(body, 'ask')
        if why:
            return self._json({'error': why}, 400)
        if not BUSY.acquire(blocking=False):
            return self._json({'error': 'a report is already being written'},
                              409)
        self._head(200, 'text/event-stream', stream=True)

        def emit(obj):
            try:
                self.wfile.write(('data: %s\n\n' % json.dumps(obj)).encode())
                self.wfile.flush()
            except (BrokenPipeError, ValueError):
                pass
        try:
            print('[ask] %s (%s)' % (q[:120], mid), flush=True)
            ask(q, emit, mid, effort)
        except Exception as e:                       # noqa: BLE001
            emit({'type': 'error', 'error': '%s: %s' % (type(e).__name__, e)})
        finally:
            BUSY.release()

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--port', type=int, default=8760)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    print('viewer helper on http://127.0.0.1:%d  (%s at %s effort)'
          % (a.port, MODEL, EFFORT))
    print('%d report(s) in Outputs/. Ctrl-C to stop.' % len(reports()))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped')


if __name__ == '__main__':
    main()
