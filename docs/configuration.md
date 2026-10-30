# Configuration

Compile runs the same code for every game. A game decides two things for itself: what its records look like, in `schema/`, and a little vocabulary, in `dataset.yml`.

## dataset.yml

It sits at the root of the dataset repo and holds three lists. All three are required.

- `card_properties` are the card fields worth filtering on. `cardcarp-properties` collects every distinct value of each into `dist/properties.json`.
- `deck_properties` are the same, for decks.
- `collection_types` is the order a game's collection types appear in `dist/sets.json`. The first is the game's primary type. A type the data uses but the list leaves out still appears, after the listed ones, so forgetting one never drops a set.

<sub>dataset.yml — ptcg</sub>

```yaml
# Card fields worth filtering on. Written to dist/properties.json.
card_properties:
  - layout
  - category
  - trait
  - type
  - rarity
  - regulation

# Deck fields worth filtering on.
deck_properties:
  - format
  - group
  - theme
  - complexity
  - division

# Collection types, in display order. The first is this game's primary type.
collection_types:
  - Standard
  - Starter
  - Extra
```

If the file is missing, or a list is absent, the step that needs it stops and names what's missing. `cardcarp-compile` doesn't read it, so a pull request that only changes cards is checked without it.

## Why it is per game

Warcraft's lists show why this isn't built into the pipeline. Faction, class and combat are Warcraft mechanics, and a Raid or a Dungeon has no Pokémon equivalent. When the pipeline carried Pokémon's lists, a second game quietly lost its own filters and saw its collection types in the wrong order. Nothing failed; the output was just wrong.

<sub>dataset.yml — wow</sub>

```yaml
card_properties:
  - layout
  - category
  - trait
  - faction
  - class
  - type
  - combat
  - rarity
  - regulation

deck_properties:
  - format
  - group
  - theme
  - complexity
  - division

collection_types:
  - Set
  - Raid
  - Dungeon
  - Starter
  - Promo
  - Craft
  - Badge
  - Token
  - Extra
```

## The schema

Everything else a game decides lives in `schema/`: one cerberus schema for each kind of record, namely card, oracle, set, collection, format and deck. It says which fields exist, which are required and what each one holds, and `cardcarp-compile` checks every file against it.

The schema's key order is also the order `cardcarp-split` writes fields in, so the schema and the files it checks always read the same way.

---

← [Install](install.md) · [Compile](README.md) · [Commands](commands.md) →
