# releases

Update manifests and downloads for kedavra-code's Mac apps, and for anything
else that ships as a versioned download.

| App | What it is | Latest |
|---|---|---|
| [unus](unus/appcast.json) | An offline natural-language calculator | see [Releases](../../releases?q=unus) |
| [murmur](murmur/appcast.json) | On-device dictation | see [Releases](../../releases?q=murmur) |
| [00_Cerebrum](00_Cerebrum/) | A self-improving knowledge-base system for Claude Code — the machinery, no corpus | [browse](00_Cerebrum/) or see [Releases](../../releases?q=00_Cerebrum) |

## Layout

```
unus/appcast.json         ← manifests live here, in the repo tree
murmur/appcast.json
00_Cerebrum/manifest.json
00_Cerebrum/…            ← and, for this one only, the files themselves
```

The downloads are **release assets**, tagged `unus-49`, `murmur-31`,
`00_Cerebrum-114` and so on.

**00_Cerebrum is the exception to the binaries rule, because it is not one.**
The DMGs stay out of the tree because a git repository that stores binaries
grows forever. A vault template is fifty text files that a reader wants to
browse before downloading and to diff between builds, and keeping those out of
the tree costs the reader everything and saves nothing. So the files live at
`00_Cerebrum/` and the archives are that same tree packaged, byte for byte.

It also carries a `manifest.json` rather than an `appcast.json`: nothing polls
it, because a vault template is unpacked once and then diverges into the
reader's own corpus. The layout is otherwise the same, and the file says what
the current download is; the name differs because calling it an appcast would
promise an update feed that does not exist.

## Keeping the two copies honest

Shipping a component in the tree *and* as an archive means two copies of one
thing, and two copies drift. `release.py` is what stops them:

```
python3 release.py check   00_Cerebrum      before every push
python3 release.py build   00_Cerebrum
python3 release.py publish 00_Cerebrum
```

The build number needs no argument: it is this repository's commit count for
the component directory, plus one while the component has uncommitted changes,
because the commit carrying a build does not exist when the build is made. So
`00_Cerebrum-3` is the third commit to touch `00_Cerebrum/`, and the tag points
at exactly that. `--source-commit` optionally records the upstream a component
was cut from, which for `00_Cerebrum` is a private vault this repository cannot
reach.

`check` repacks the tree in memory and compares it against the sha256 the
manifest advertises. Edit a file in the tree and push without rebuilding, and
the manifest now describes an archive nobody can get; `check` exits 1 and says
so. It also compares the packed file list against `git ls-files` in both
directions, so a file that is in the tree and not the archive — or staged in
neither — is caught as well.

**The archive is the tree minus `manifest.json`.** The manifest is this
repository's record of the component rather than part of it: unpacking the
tarball should give you the thing, not a note saying where you got it.

The packing is deterministic — fixed timestamps, sorted entries, no uid or
gid, gzip's own mtime zeroed — so repacking an unchanged tree gives byte-
identical archives and a no-op rebuild shows up as no change at all. That is
what makes a checksum comparison meaningful rather than noise.

The split is deliberate. GitHub Releases have no folders and exactly one
"latest" per repository, so a `releases/latest/download/` URL for one app
resolves to whichever app shipped most recently — unus's URL would break the
moment murmur released after it. A path in the repo tree is per-app and
immune to release ordering, and is served straight from
`raw.githubusercontent.com`. The DMGs stay out of the tree because a git
repository that stores binaries grows forever.

## What an app reads

```
https://raw.githubusercontent.com/kedavra-code/releases/main/unus/appcast.json
```

```json
{
  "app": "unus",
  "build": 49,
  "commit": "8b2afd2",
  "url": "https://github.com/kedavra-code/releases/releases/download/unus-49/unus.dmg",
  "sha256": "…",
  "minimumSystemVersion": "26.0",
  "notes": "…"
}
```

`build` is the app's commit count — a monotonic integer, so there is no
version string to parse. An app installs only a build **strictly greater**
than its own.

Tree-shipped components number the same way but from *this* repository, since
that is where their source lives; `release.py` computes it.

## Downloads are verified, not trusted

Nothing here is a security boundary. An app checks the bundle it downloaded
against a code-signing requirement before replacing anything:

```
anchor apple generic and certificate leaf[subject.OU] = "<team id>" and notarized
```

The Team ID pin makes it ours — `anchor apple generic` alone would accept
every app Apple has ever signed — and `notarized` makes it a build Apple has
seen. A hijacked host, a poisoned DNS answer or a tampered download can only
produce something that fails that check. The `sha256` above catches a corrupt
download early; it is not the gate.
