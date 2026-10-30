# Bring your own game

A dataset for a game cardcarp doesn't cover is a repository shaped like the existing ones. Nothing in Compile has to change for it.

## Start from a dataset

Copy the reference dataset's skeleton and leave its data behind: the `schema/` folder, `dataset.yml`, `pyproject.toml` and the validate workflow. [yeahben/cardcarp-ptcg](https://github.com/yeahben/cardcarp-ptcg) is the fullest reference. Its README describes the layout, and its CONTRIBUTING the reasoning behind each rule.

```text
your-game/
├── data/
│   ├── collection/
│   ├── set/
│   ├── oracle/
│   ├── card/
│   ├── format/
│   └── deck/
├── schema/            card, oracle, set, collection, format, deck
├── dataset.yml
├── pyproject.toml
└── .github/workflows/validate.yml
```

## Write the data

Write collections first, then sets, oracles and cards, and formats and decks last, since they refer to everything else. Each record is one file, and each reference is by name. Folders and filenames are for your own navigation; ids come from the records themselves.

<sub>data/set/standard/01-base/01-base.yml</sub>

```yaml
name: Base

type: Standard

index: 1

subtotal: 102

total: 102

date: '1999-01-09'

collection: Base

publisher: Wizards of the Coast
```

## State its vocabulary

Change `schema/` to the fields your game actually has. Then fill in `dataset.yml` with the card and deck fields worth filtering on, and your collection types in the order they should appear. See [Configuration](configuration.md).

## Build it

```sh
pip install .
cardcarp-compile       # repeat until it passes
cardcarp-sets
cardcarp-manifest
```

When something is wrong, `cardcarp-compile` names the file and the field, and lists every reference that doesn't resolve. Once it passes, the steps after it won't fail on your data.

## Publish it

Put `dist/manifest.json` and `dist/sets.json` where an app fetches them, and each card's art under its `dir`. See [The manifest contract](manifest.md).

## Show it

An app also needs the game's config: its card size, the filters its archive offers, its deck groups, and for a table, its layout. That lives in the app, not in the dataset. See the [core](https://github.com/yeahben/cardcarp-web/blob/main/packages/core/docs/configuration.md) and [simulator](https://github.com/yeahben/cardcarp-web/blob/main/packages/simulator/docs/configuration.md) Configuration pages. With that in place, an app built on both shows the new game, and neither package knows it exists.

---

← [Design principles](principles.md) · [Compile](README.md) · [The manifest contract](manifest.md) →
