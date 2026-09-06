# releases

Update manifests and downloads for kedavra-code's Mac apps, and for anything
else that ships as a versioned download.

| App | What it is | Latest |
|---|---|---|
| [unus](unus/appcast.json) | An offline natural-language calculator | see [Releases](../../releases?q=unus) |
| [murmur](murmur/appcast.json) | On-device dictation | see [Releases](../../releases?q=murmur) |
| [00_Cerebrum](00_Cerebrum/manifest.json) | A self-improving knowledge-base system for Claude Code — the machinery, no corpus | see [Releases](../../releases?q=00_Cerebrum) |

## Layout

```
unus/appcast.json         ← manifests live here, in the repo tree
murmur/appcast.json
00_Cerebrum/manifest.json
```

The downloads are **release assets**, tagged `unus-49`, `murmur-31`,
`00_Cerebrum-114` and so on.

The two apps carry an `appcast.json`, which is what their updater polls.
00_Cerebrum carries a `manifest.json` instead: nothing polls it, because a
vault template is unpacked once rather than auto-updated. The layout is the
same and the file says what the current download is; the name is different
because calling it an appcast would promise an update feed that does not
exist.

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
