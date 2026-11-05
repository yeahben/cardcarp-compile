# Commands

Each command runs from the root of a dataset repo and reads and writes paths relative to it.

## In order

`cardcarp-compile` comes first, because it builds the `dist/` files every other step reads. The three after it don't depend on each other.

```sh
cardcarp-compile      # data/ + schema/         ->  dist/*.json, dist/database.json
cardcarp-sets         # dist/ + dataset.yml      ->  dist/sets.json
cardcarp-manifest     # dist/                    ->  dist/manifest.json
cardcarp-properties   # dist/ + dataset.yml      ->  dist/properties.json
cardcarp-image FOLDER # PNG/JPEG scans           ->  {stem}.avif, {stem}-thumb.avif
```

`cardcarp-image` stands apart: it reads the folder you name rather than `dist/`, and needs nothing built first.

## cardcarp-compile

The build, and the step CI runs. It checks every file under `data/` against `schema/` and stops at the first that fails, naming the file and the field. A key repeated inside one file is an error too, because YAML would otherwise keep one value and silently lose the other.

It then derives every record's id and refuses two records that claim the same one. Next it checks that every reference resolves: a card's set and blueprint, a set's collection, a deck's set and every card in its list, a pack's sets and highlight, and a format's sets, bans and exceptions. Once the cards are joined it also checks that every pack slot's match finds at least one card in the pack's sets. It reports all the failures together rather than one at a time. Finally it joins each card with its blueprint, set and collection, works out its legality in every format, and writes `dist/database.json` alongside a file for each kind of record.

## cardcarp-sets

Writes `dist/sets.json`: the set tree, from collection type to collection to set, with a card total at each level. Collections are ordered by their first release date. Sets are ordered by index, the number first so set 9 comes before set 10, then any suffix so `01a` sits straight after `01`. Sets with no index follow, by date.

## cardcarp-manifest

Writes `dist/manifest.json`, the archive an app loads. It keys every card, deck and pack by id, carries the id inside each record as well, and gives every card and pack a `dir`: the path its art is published at. The file is written compact, because it's downloaded whole. See [The manifest contract](manifest.md).

## cardcarp-properties

Writes `dist/properties.json`: every distinct value of the card and deck fields `dataset.yml` lists. It's a reference to fill an app's filter options in from by hand, not a finished ordering.

## cardcarp-image

Converts a folder of card scans to the two AVIF files the apps fetch: the scan at `{stem}.avif`, and a 480px cut at `{stem}-thumb.avif`. The deckbox grid and table rows show the cut, which an app names in its config as `card.thumbnail` and `@cardcarp/core` appends to the card's `dir`; the scan is for the card dialog and the table. The folder is searched recursively and its layout is kept, so point it at the folder whose layout mirrors `dir`, such as `image/wow/card`.

```sh
cardcarp-image image/wow/card --limit 50    # calibrate on a few first
cardcarp-image image/wow/card               # the lot, sources kept
cardcarp-image image/wow/card --sweep       # then delete each PNG once both AVIFs exist
```

Bytes, not quality, are the constraint when hundreds of cards are on screen, so each file is encoded at the highest quality that fits a byte cap: `--max-bytes` for the scan (100KB) and `--thumb-max-bytes` for the cut (50KB). Quality is bisected over a ladder from 40 to 70, so a clean card lands at q70 and a grainy foil at q45, and a file that overshoots even at q40 is kept and listed at the end. `--thumb-width` sets the cut's width, `--thumb-suffix` its variant name, `--no-thumb` turns it off, and `--out` writes the tree somewhere other than beside the sources.

It is resumable: a stem whose outputs exist is skipped, so a run can be stopped and started again, and a tree converted before thumbnails existed only has the thumbnails added. An AVIF with no PNG or JPEG beside it is read as the scan itself, so an AVIF-only archive gets thumbnails too. `--force` re-encodes everything.

It needs `avifenc` on your path (`brew install libavif`) and, for thumbnails, Pillow: `pip install ".[image]"` in a dataset repo, or `pip install pillow`. Each card costs about three seconds of CPU across the ladder, so eight workers manage two or three a second and ten thousand cards take about an hour.

## cardcarp-split

The inverse of `cardcarp-compile`. It rewrites `data/card`, `data/blueprint`, `data/set` and `data/collection` from `dist/`, in schema field order and in the folder layout the records imply. It's for a structural change across thousands of files, and for tidying formatting after one.

It rewrites every file it owns, so run it on a clean working tree and read the diff before committing. It never touches `data/format`, `data/deck` or `data/pack`. Those are written by hand, with comments and long text that a round trip through JSON would flatten.

## Python helpers

A game's own scripts, usually the ones that turn an upstream bulk file into `data/`, can import the helpers the pipeline itself uses:

- `to_kebab_case`, the rule every id is built with
- `card_dir`, a card's path stem
- `save_yml`, which writes YAML in the house format
- `load_schema_order` and `order_by_schema`, for writing fields in schema order

```python
from cardcarp_compile import card_dir, to_kebab_case

to_kebab_case("Cynthia's Roserade")   # 'cynthias-roserade'
card_dir(record)                      # 'standard/01-base/01-base/058-pikachu'
```

---

← [Configuration](configuration.md) · [Compile](README.md) · [Design principles](principles.md) →
