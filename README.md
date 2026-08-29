# releases

Update manifests and downloads for kedavra-code's Mac apps.

| App | What it is | Latest |
|---|---|---|
| [unus](unus/appcast.json) | An offline natural-language calculator | see [Releases](../../releases?q=unus) |
| [murmur](murmur/appcast.json) | On-device dictation | see [Releases](../../releases?q=murmur) |

## Layout

```
unus/appcast.json      ← manifests live here, in the repo tree
murmur/appcast.json
```

The DMGs are **release assets**, tagged `unus-49`, `murmur-31` and so on.

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
