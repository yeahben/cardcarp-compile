# Design principles

These hold for every dataset Compile builds. Each game's own curation rules, such as what counts as a set or which printing wins when two disagree, live in that game's repository. [ptcg's CONTRIBUTING](https://github.com/yeahben/cardcarp-ptcg/blob/main/CONTRIBUTING.md) has the fullest set.

## YAML is the source

A dataset is its `data/` folder, one YAML file to a record. `dist/` is output: it's rebuilt from `data/` on every run and never committed. Anything worth keeping is written in YAML, where a contributor can find it, read it and change it in a pull request.

<sub>data/card/standard/01-base/01-base/040-raticate.yml</sub>

```yaml
oracle: raticate-base-040

index: '040'

rarity: Uncommon

artist: Ken Sugimori

set: Base
```

## Ids come from the record

No file contains its own id. A collection's and a set's come from its name. A card's comes from its set and its printed index, an oracle's from its name and the printing it first appeared in, and a deck's from its set and its name, all kebab-cased at build time. Base and 040 make `base-040`.

Because the id is derived, a filename is free to be whatever helps an editor find the file, and renaming one changes nothing. Two records that derive the same id fail the build, and the error names both files.

## References are names

A card says `set: Base`, not an id, and the build turns the name into one. An oracle is the one exception, written as its id, because thousands of cards share a name and the name alone can't pick out one oracle.

Checking against the schema only ever sees one file, so on its own it can't tell whether that set exists. The reference check that follows looks across the whole dataset, and reports every reference that doesn't resolve.

## The round trip

`cardcarp-split` is the exact inverse of `cardcarp-compile` for the records it owns. That makes a structural change to thousands of files a matter of changing `dist/` and splitting it back out.

Hand-written files stay outside that loop on purpose. Formats and decks carry comments and long text that a trip through JSON would flatten, and neither is large enough for a bulk edit to be worth the risk.

## A printing is not its mechanics

An oracle holds what a card does, meaning its rules and its type, and every printing of that card shares it. A card holds one printing: its set, its index, its artist, its rarity. That split decides where a field belongs.

A regulation mark is printed on a card, so it's written on the card. The pool of every mark an oracle has been printed under is gathered at build time rather than stored, and legality checks the pool, because a player may use any printing whose mark is legal. Stored on the oracle instead, a modern mark would spread back onto a card printed years before the mark existed.

## No game in the code

Nothing in Compile names a game. What a valid record is lives in the schema. The fields worth filtering on, and the order collection types appear in, live in `dataset.yml`. A difference between two games is data, never a branch in the pipeline. See [Configuration](configuration.md).

## Any numbering

Games number things differently. Pokémon uses plain integers. Warcraft uses zero-padded strings, with companion sets like `01a` and named reprint lines like `reborn-01`, and many of its sets have no number at all.

The pipeline reads all of them the same way: it takes the number where there is one and keeps the rest. A card's art path therefore comes out the same whichever scheme produced it, and no game ever has to renumber its data to fit another's. A card's own index goes into its path exactly as printed, so `040` stays `040`.

---

← [Commands](commands.md) · [Compile](README.md) · [Bring your own game](your-game.md) →
