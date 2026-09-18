import json
import os
import shutil
import sys

from cardcarp_compile.util import folder_segment, to_kebab_case, save_yml, load_schema_order, order_by_schema

# The only trees this script owns. data/format and data/deck are deliberately excluded.
# Both are hand-authored, both carry comments and block scalars that a JSON round-trip would flatten.
# They are never read, rewritten, or deleted here.
OWNED_DIRS = ('data/oracle', 'data/collection', 'data/set', 'data/card')

REQUIRED_INPUTS = ('dist/collection.json', 'dist/set.json', 'dist/oracle.json', 'dist/card.json')


MAX_REPORTED_PROBLEMS = 25


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def unresolved(collections, sets, oracles, cards):
    # The references split follows to name folders and files, each of which would raise mid-write if missing.
    problems = []

    for set_id, record in sets.items():
        if record.get('collection_id') not in collections:
            problems.append(f"set {set_id}: collection '{record.get('collection_id')}' is not a known collection")

    for oracle_id, record in oracles.items():
        if record.get('origin') not in cards:
            problems.append(f"oracle {oracle_id}: origin '{record.get('origin')}' is not a known card")

    for card_id, record in cards.items():
        if record.get('oracle_id') not in oracles:
            problems.append(f"card {card_id}: oracle '{record.get('oracle_id')}' is not a known oracle")
        if record.get('set_id') not in sets:
            problems.append(f"card {card_id}: set '{record.get('set_id')}' is not a known set")

    return problems


def split_json_to_yml():

    missing = [path for path in REQUIRED_INPUTS if not os.path.exists(path)]
    if missing:
        print("Error: cannot split without a complete build. Missing:")
        for path in missing:
            print(f"  - {path}")
        return

    collections = load_json('dist/collection.json')
    sets = load_json('dist/set.json')
    oracles = load_json('dist/oracle.json')
    cards = load_json('dist/card.json')

    # Every lookup the decomposition makes is checked before anything is deleted.
    # A reference that fails halfway through would otherwise leave data/ partly removed.
    problems = unresolved(collections, sets, oracles, cards)
    if problems:
        print(f"Error: {len(problems)} reference(s) in dist/ do not resolve, so data/ was left untouched:")
        for problem in problems[:MAX_REPORTED_PROBLEMS]:
            print(f"  - {problem}")
        if len(problems) > MAX_REPORTED_PROBLEMS:
            print(f"  ... and {len(problems) - MAX_REPORTED_PROBLEMS} more")
        print("Run cardcarp-compile and fix its errors first.")
        sys.exit(1)

    print("Cleaning up old data...")
    for folder in OWNED_DIRS:
        # Clear previous YAMLs and folders to avoid orphaned content
        shutil.rmtree(folder, ignore_errors=True)
    os.makedirs('data', exist_ok=True)

    print("Starting decomposition...")

    # Same folder naming as card_dir: '01-base', '01a-base' or plain 'base', so an index need not be an integer, or present at all.
    def collection_folder(collection_id):
        record = collections[collection_id]
        return folder_segment(record.get('index'), record['name'])

    def set_folder(set_id):
        record = sets[set_id]
        return folder_segment(record.get('index'), record['name'])

    def set_path(set_id):
        collection_id = sets[set_id]['collection_id']
        return (f"{to_kebab_case(collections[collection_id]['type'])}"
                f"/{collection_folder(collection_id)}"
                f"/{set_folder(set_id)}")

    collection_order = load_schema_order('collection')
    set_order = load_schema_order('set')
    oracle_order = load_schema_order('oracle')
    card_order = load_schema_order('card')

    for collection_id, record in collections.items():
        save_yml(f"data/collection/{collection_folder(collection_id)}.yml",
                 order_by_schema(dict(record), collection_order))
    print(f"Finished collections. Total: {len(collections)}")

    for set_id, record in sets.items():
        entry = dict(record)
        entry['collection'] = collections[entry.pop('collection_id')]['name']
        save_yml(f"data/set/{set_path(set_id)}.yml", order_by_schema(entry, set_order))
    print(f"Finished sets. Total: {len(sets)}")

    # An oracle's `origin` is the card id of its earliest printing, so that card gives both the set it belongs in and the index its filename starts with.
    for oracle_id, record in oracles.items():
        origin = cards[record['origin']]
        filename = f"{origin['card_index']}-{to_kebab_case(record['name'])}.yml"
        save_yml(f"data/oracle/{set_path(origin['set_id'])}/{filename}",
                 order_by_schema(dict(record), oracle_order))
    print(f"Finished oracles. Total: {len(oracles)}")

    # Cards carry no name of their own; it lives on the oracle they point at.
    for card_id, record in cards.items():
        entry = dict(record)
        oracle_id = entry.pop('oracle_id')
        oracle = oracles[oracle_id]
        set_id = entry.pop('set_id')

        # Oracle ids are already kebab-case, so the reference is the id itself
        entry['oracle'] = oracle_id
        entry['set'] = sets[set_id]['name']
        entry['index'] = entry.pop('card_index')

        filename = f"{entry['index']}-{to_kebab_case(oracle['name'])}.yml"
        save_yml(f"data/card/{set_path(set_id)}/{filename}",
                 order_by_schema(entry, card_order))
    print(f"Finished cards. Total: {len(cards)}")


def main():
    split_json_to_yml()

if __name__ == "__main__":
    main()
