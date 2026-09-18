import json
import os
from cardcarp_compile.util import load_dataset

DATABASE = 'dist/database.json'
DECKS = 'dist/deck.json'
SETS = 'dist/set.json'
OUTPUT = 'dist/properties.json'

def load(path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def collect(records, properties):
    found = {prop: set() for prop in properties}

    for record in records.values():
        for prop in properties:
            value = record.get(prop)
            if value is None:
                continue
            if isinstance(value, list):
                found[prop].update(item for item in value if item)
            elif value:
                found[prop].add(value)

    return {prop: sorted(found[prop]) for prop in properties}


def readable_groups(decks, sets):

    named = {}

    for deck_id, record in decks.items():
        entry = dict(record)
        # A group naming a set reads as that set's name; any other label is kept as its id rather than dropped.
        group_id = entry.get('group_id')
        group = sets.get(group_id)
        if group:
            entry['group'] = group.get('name')
        elif group_id:
            entry['group'] = group_id
        named[deck_id] = entry

    return named


def create_properties():
    database = load(DATABASE)
    if database is None:
        print(f"Error: {DATABASE} not found. Run compile.py first.")
        return

    vocabulary = load_dataset()
    properties = {'cards': collect(database, vocabulary['card_properties'])}

    decks = load(DECKS)
    if decks is None:
        print(f"Warning: {DECKS} not found, deck properties omitted.")
    else:
        decks = readable_groups(decks, load(SETS) or {})
        properties['decks'] = collect(decks, vocabulary['deck_properties'])

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(properties, f, indent=2, ensure_ascii=False)

    summary = '; '.join(
        f"{group} ({', '.join(f'{k} {len(v)}' for k, v in values.items())})"
        for group, values in properties.items())
    print(f"Built {OUTPUT}: {summary}")


def main():
    create_properties()


if __name__ == "__main__":
    main()
