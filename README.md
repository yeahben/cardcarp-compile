# CardCarp Compile 🧵

The shared build pipeline behind the CardCarp card datasets.

It turns thousands of small hand-edited YAML files into flat, fully-joined JSON: one
record per card printing, with its rules text, set, era and format legality already
resolved. Any trading card game can use it.

<br>

> [!NOTE]
> This repo is the tooling only. It contains no card data.<br>
> Each game's data lives in its own repo, which installs this pipeline as a dependency and runs it against its own `data/` and `schema/`.

<br>

## 🧭 Why a Shared Pipeline

Most trading card games have the same structure, even if the words are different: a card is
printed in a set, sets belong to an era, the same card gets reprinted, and formats decide
what's legal. The pipeline handles that structure once. Each game only has to supply
its own vocabulary and validation rules.

That means:

- **One data model.** A card from any CardCarp dataset has the same shape, so one app can read all of them.<br>
- **One set of guarantees.** Every dataset gets the same validation, id rules and reference checks.<br>
- **Fixes land everywhere.** An improvement to the build reaches every game on its next install.

<br>

## 🗂️ The Data Model

The pipeline expects six kinds of records. Each one is a separate YAML file.

| Record | Holds | Example |
| --- | --- | --- |
| **card** | One physical printing: artist, rarity, collector number | *Pikachu, Base Set #58* |
| **oracle** | Rules that stay the same across every reprint | *Pikachu's HP, attacks, weakness* |
| **set** | A group of cards sharing a set mark and number sequence | *Base Set* |
| **collection** | A larger group of sets, such as an era or block | *Base era* |
| **format** | Legality rules: allowed sets, bans, restrictions, copy limits | *Standard* |
| **deck** | A pre-built product decklist, pointing to specific printings | *Theme Deck: Overgrowth* |

The build joins them together. Each card takes on the fields of its oracle, then its set,
then its collection, and gets a `legality` entry for every format.

<br>

## 🚀 Quick Start

You need Python 3.10 or newer. Each game repo lists this pipeline as a dependency, so installing the game repo installs the pipeline too:

```bash
git clone https://github.com/cardcarp/ptcg.git
cd ptcg
pip install .
cardcarp-compile
```

To work on the pipeline itself, clone this repo and install it in editable mode. Then run commands from the root of a game repo:

```bash
pip install -e path/to/compile
```

Every command reads and writes relative to **the directory you run it from**. Always run it from a game repo's root.

<br>

## 🐍 Commands

### Primary

This is the main editing loop: edit YAML, compile, and optionally convert the build back to YAML.

- `cardcarp-compile` checks every YAML file against `schema/` and fails on duplicate keys or ids. It then confirms that every cross-reference points to a real record and writes the joined JSON to `dist/`. **This is the build.** It is also what CI runs on every pull request.<br>

- `cardcarp-split` regenerates `data/card`, `data/oracle`, `data/set` and `data/collection` from `dist/`. It is the exact reverse of compile: on an unchanged build, the output matches the source byte for byte. Use it for bulk restructuring or to normalize formatting. `data/format` and `data/deck` are written by hand and are never touched.

> [!WARNING]
> `cardcarp-split` deletes the four folders it manages before rewriting them. Commit your changes or stash them first.

<br>

### Secondary

These commands are optional and outside the main loop. Each one reads `dist/` and adds one more file to it. None of them touch `data/`. Run `cardcarp-compile` first.

- `cardcarp-sets` writes `dist/sets.json`: a tree of collection type → collection → set, with card totals at every level.<br>

- `cardcarp-manifest` writes `dist/manifest.json`: every card and deck, keyed by id, with `id` and a `dir` path included in each record. It's written without whitespace because apps download it.<br>

- `cardcarp-properties` writes `dist/properties.json`: every distinct value of the fields a game marks as filterable. Use it to build dropdown options.

<br>

### Output

| File | Contents |
| --- | --- |
| `card.json` `oracle.json` `set.json` `collection.json` `format.json` `deck.json` | Each record type validated on its own, keyed by id, with references resolved |
| `database.json` | **The full dataset.** Every card, joined with its oracle, set and collection, plus legality |
| `sets.json` | The set tree, in order, with totals *(from `cardcarp-sets`)* |
| `manifest.json` | Cards and decks in one compact file *(from `cardcarp-manifest`)* |
| `properties.json` | Values for filters *(from `cardcarp-properties`)* |

<br>

## 🧩 Making a Game Dataset

A game repo contains data and schemas, with no Python of its own:

```
your-game/
├── pyproject.toml        depends on cardcarp-compile-core
├── schema/
│   ├── dataset.yml       the game's vocabulary
│   ├── card.yml          one validation schema per record type
│   ├── oracle.yml
│   ├── set.yml
│   ├── collection.yml
│   ├── format.yml
│   └── deck.yml
└── data/
    ├── card/  oracle/  set/  collection/  format/  deck/
```

Copy `pyproject.toml` and `.github/workflows/validate.yml` from an existing game to get the dependency and the CI check.

<br>

### `schema/dataset.yml`

This file is the only place a game declares what makes it different from other games:

```yaml
card_properties:     # card fields to collect for filters
  - category
  - rarity

deck_properties:     # deck fields to collect for filters
  - format

collection_types:    # display order; the first entry is the game's main type
  - Standard
  - Extra
```

<br>

### Schemas

Schemas use [Cerberus](https://docs.python-cerberus.org/) rules written in YAML. YAML can't store Python functions, so `coerce` accepts the names `int`, `float`, `str` or `bool`.

The key order in a schema also sets the field order when `cardcarp-split` writes YAML. Put fields in the order an editor would expect to read them.

Beyond the fields a game adds itself, the build reads these:

| Record | Fields the pipeline uses |
| --- | --- |
| card | `set`, `index`, `oracle`, `regulation` *(optional)* |
| oracle | `name`, `origin`, `category`, `trait` |
| set | `name`, `collection`, `index`, `type`, `date`, `publisher` |
| collection | `name`, `index`, `type` |
| format | `set_allow`, `regulation_allow`, `oracle_ban`, `oracle_restrict`, `oracle_exception`, `oracle_limit` |
| deck | `name`, `group`, `highlight`, `list` |

<br>

## 🔑 How IDs Work

IDs are never written by hand. Records refer to each other by readable names
(`set: Base`, `collection: Neo`), and the build turns every name into a kebab-case id:

| Record | Id built from | Example |
| --- | --- | --- |
| card | set + printed index | `base-058` |
| oracle | name + `origin` (the card id of its first printing) | `pikachu-base-058` |
| set, collection | name | `base` |
| deck | group + name | `base-overgrowth` |
| format | file name | `standard` |

When turning a name into an id, the build removes apostrophes (straight and curly), strips accents (`Pokémon` → `pokemon`)
and never splits camelCase (`BREAKpoint` stays one word). Two records that end up with the
same id stop the build, and the error names both files.

Folder paths exist to make files easy to find, and **are never part of an id**. Prefixes
such as `01-base/` keep folders in release order and can be renamed freely. A prefix comes
from the record's `index`: whole numbers are padded to two digits, other values such as `01a` are
used as written, and a record with no `index` gets a folder with no prefix.

<br>

## ⚖️ How Legality Works

Each card gets a result for every format in `data/format`:

- **Admission.** A format can admit a card by set (`set_allow`), by regulation mark (`regulation_allow`), or both. The two checks are independent, so a card passes if either one lets it in. `'*'` means every set.<br>
- **Pooled marks.** A regulation mark is recorded on the card where it's printed. For legality, the build combines all the marks from an oracle's printings, so any printing counts if the card has ever carried an allowed mark.<br>
- **Limits.** A ban removes the card from the format. Otherwise the copy limit comes from the first rule that applies: `oracle_restrict` for that card, then `oracle_exception` for its category or trait, then `oracle_limit`, which defaults to 4.

Each card ends up with `legality` (a limit for each format) plus quick lists: `legal`, `ban` and `restrict`.

<br>

## 🎴 Datasets

| Game | Repo |
| --- | --- |
| Pokémon TCG | [cardcarp/ptcg](https://github.com/cardcarp/ptcg) |
| World of Warcraft TCG | [cardcarp/wow](https://github.com/cardcarp/wow) |

Building a dataset for another game? Come say hello on Discord.

<br>

## 🐝 Community

- **[Join Discord](https://chat.cardcarp.com):** discuss the pipeline, the data model, and new games.<br>
- **[CardCarp](https://cardcarp.com):** the web app built on these datasets.<br>
- **[Support the project](https://patronage.cardcarp.com):** help keep the datasets maintained.

<br>

## 📜 License

The pipeline code is released under [MIT No Attribution](LICENSE.md). Each game dataset has its own license and disclaimer. Check the dataset's repo before using its data.

<sub>CardCarp is an independent, community-driven project. It is not affiliated with, endorsed by, or sponsored by any card game publisher or intellectual property owner.</sub>
