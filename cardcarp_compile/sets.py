import json
import re
import os
from collections import Counter
from cardcarp_compile.util import index_parts, load_dataset

SET_PATH = 'dist/set.json'
COLLECTION_PATH = 'dist/collection.json'
CARD_PATH = 'dist/card.json'
OUTPUT_PATH = 'dist/sets.json'

# Sorts last, so an undated record trails the dated ones instead of leading them.
UNDATED = '9999-99'

def as_number(value):
    # The number an index carries, as written to sets.json.
    # Example: '02', and '02a' are both valid unique sets.
    match = re.search(r'\d+', str(value or ''))
    return int(match.group()) if match else None


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def ordered_types(present, order):
    # order first by the game's schema.dataset.yml. 
    # A type not listed will still appear, sorted after the ones it does, rather than being dropped.
    known = [t for t in order if t in present]
    return known + sorted(set(present) - set(order))


def count_cards_per_set(card_path):
    # Actual printed count per set, tallied from the card records themselves
    if not os.path.exists(card_path):
        print(f"Warning: {card_path} not found, card totals will be 0.")
        return Counter()

    totals = Counter()
    for card in load_json(card_path).values():
        set_id = card.get('set_id')
        if set_id:
            totals[set_id] += 1

    return totals


def create_sets():
    # Mirrors how the dataset nests, and how data/ is foldered: 
    # Collection-type -> Collection -> Set
    missing = [p for p in (SET_PATH, COLLECTION_PATH) if not os.path.exists(p)]
    if missing:
        print(f"Error: {', '.join(missing)} not found. Run compile.py first.")
        return

    order = load_dataset()['collection_types']
    sets = load_json(SET_PATH)
    collections = load_json(COLLECTION_PATH)
    card_totals = count_cards_per_set(CARD_PATH)

    grouped = {}
    orphans = []

    for set_id, record in sets.items():
        collection_id = record.get('collection_id')
        if collection_id not in collections:
            orphans.append((set_id, collection_id))
            continue

        grouped.setdefault(collections[collection_id].get('type'), {}) \
               .setdefault(collection_id, []).append({
                   'id': set_id,
                   'name': record.get('name'),
                   'index': as_number(record.get('index')),
                   'type': record.get('type'),
                   'publisher': record.get('publisher'),
                   'date': record.get('date'),
                   'card_total': card_totals.get(set_id, 0),
               })

    if orphans:
        # compile.py rejects these, so reaching here means dist/ is stale
        print(f"Warning: {len(orphans)} set(s) reference an unknown collection:")
        for set_id, collection_id in orphans[:5]:
            print(f"  - {set_id} -> {collection_id}")

    hierarchy = []

    for collection_type in ordered_types(grouped, order):
        by_collection = grouped[collection_type]

        def set_key(entry):
            # The number first and any suffix after it, so 9 < 10 and a companion like '01a' sits straight after its parent. 
            # A set with no index trails, by date.
            raw = sets[entry['id']].get('index')
            return (*index_parts(raw), entry['date'] or UNDATED, entry['name'] or '')

        def collection_key(collection_id):
            # First release date leads. 
            # If a game numbers its collections that is the order the numbers already encode
            members = by_collection[collection_id]
            first = min((s['date'] for s in members if s['date']), default=UNDATED)
            index = collections[collection_id].get('index')
            return (first, *index_parts(index), collection_id)

        entries = []
        for collection_id in sorted(by_collection, key=collection_key):
            members = sorted(by_collection[collection_id], key=set_key)
            collection = collections[collection_id]

            entries.append({
                'id': collection_id,
                'name': collection.get('name'),
                'index': as_number(collection.get('index')),
                'date': min((s['date'] for s in members if s['date']), default=None),
                'card_total': sum(s['card_total'] for s in members),
                'list': members,
            })

        hierarchy.append({
            'type': collection_type,
            'card_total': sum(c['card_total'] for c in entries),
            'list': entries,
        })

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(hierarchy, f, indent=2, ensure_ascii=False)

    total = sum(len(c['list']) for t in hierarchy for c in t['list'])
    # The first listed collection type is the game's primary one.
    primary_type = order[0]
    primary = sum(len(c['list']) for t in hierarchy for c in t['list']
                  if t['type'] == primary_type)
    print(f"Built {OUTPUT_PATH} ({len(hierarchy)} collection types, {total} sets, "
          f"{primary} of them {primary_type})")


def main():
    create_sets()


if __name__ == "__main__":
    main()
