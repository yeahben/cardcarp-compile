import json
import os
import sys
import re
from cerberus import Validator
from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError

# Extend Cerberus to understand YAML coercion in Python
COERCE_MAP = {
    'int': lambda v: None if v is None else int(v),
    'float': lambda v: None if v is None else float(v),
    'str': lambda v: None if v is None else str(v),
    'bool': lambda v: None if v is None else bool(v)
}

MAX_REPORTED_PROBLEMS = 25

from cardcarp_compile.util import to_kebab_case

def hydrate_schema(data):
    if isinstance(data, dict):
        for key, value in data.items():
            # If we find a 'coerce' key and its value is in our map, swap it
            if key == 'coerce' and value in COERCE_MAP:
                data[key] = COERCE_MAP[value]
            # Otherwise, keep digging down the tree
            else:
                hydrate_schema(value)

    elif isinstance(data, list):
        # This catches complex rules like 'anyof' or 'allof' which contain lists of dicts
        for item in data:
            hydrate_schema(item)

    return data


def load_yml(path):
    yaml = YAML()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.load(f)
    except DuplicateKeyError as err:
        # A repeated mapping key silently drops data, so treat it like a schema failure
        print(f"Error in {path}:")
        for line in str(err).splitlines():
            if line.strip().startswith(('found duplicate key', 'in "')):
                print(f"  - {line.strip()}")
        sys.exit(1)


def get_validator(schema_name):
    schema_path = f'schema/{schema_name}.yml'
    if os.path.exists(schema_path):
        raw_schema = load_yml(schema_path)
        live_schema = hydrate_schema(raw_schema)
        return Validator(live_schema)
    return None


def validate_data(data, validator, context_name):
    is_valid = validator.validate(data)

    if not is_valid:
        print(f"Error in {context_name}:")
        for field, errors in validator.errors.items():
            print(f"  - {field}: {errors}")
        sys.exit(1)

    return validator.document


def resolve_refs(record, refs):
    # YAML holds human-readable names; ids are always derived from them.
    # 'collection: Base' becomes 'collection_id: base'.
    if not refs:
        return record

    for field, target in refs.items():
        if field in record:
            record[target] = to_kebab_case(record.pop(field))

    return record


def load_entities(directory, schema_name, id_fn, refs=None):
    # Walks nested folders: the path is navigation for editors, never the id.
    validator = get_validator(schema_name)
    records = {}
    origins = {}

    if not os.path.exists(directory):
        return records

    for root, dirs, files in os.walk(directory):
        dirs.sort()
        for filename in sorted(files):
            if not filename.endswith('.yml'):
                continue

            path = os.path.join(root, filename)
            clean_data = validate_data(load_yml(path), validator, path)
            record_id = id_fn(clean_data)

            if not record_id:
                print(f"Error in {path}:")
                print(f"  - could not derive an id from this record's properties")
                sys.exit(1)

            if record_id in origins:
                print(f"Error in {path}:")
                print(f"  - id '{record_id}' already claimed by {origins[record_id]}")
                print(f"    Rename one, or scope the id.")
                sys.exit(1)

            records[record_id] = resolve_refs(clean_data, refs)
            origins[record_id] = path

    return records


def by_name(record):
    return to_kebab_case(record.get('name'))


def compile_base_jsons():
    print("Step 1: Validating and building base JSON files...")
    os.makedirs('dist', exist_ok=True)

    # Each id is composed from the record's own properties, so the filename stays free to be what is easiest for an editor to find.
    # Oracle names repeat in the hundreds, so the id pairs name with the earliest-printing (held in 'origin')
    def oracle_id(record):
        return to_kebab_case(f"{record.get('name')}-{record.get('origin')}")

    mappings = [
        ('data/oracle', 'dist/oracle.json', 'oracle', oracle_id, None),
        ('data/set', 'dist/set.json', 'set', by_name, {'collection': 'collection_id'}),
        ('data/collection', 'dist/collection.json', 'collection', by_name, None),
    ]

    for yml_dir, json_out, schema_name, id_fn, refs in mappings:
        data_map = load_entities(yml_dir, schema_name, id_fn, refs)

        with open(json_out, 'w', encoding='utf-8') as f:
            json.dump(data_map, f, indent=2, ensure_ascii=False)
        print(f"  Built {json_out} ({len(data_map)} records)")

    # Formats have no name field, so they stay keyed by filename
    format_validator = get_validator('format')
    formats = {}
    if os.path.exists('data/format'):
        for filename in sorted(os.listdir('data/format')):
            if filename.endswith('.yml'):
                path = os.path.join('data/format', filename)
                formats[filename[:-4]] = validate_data(load_yml(path), format_validator, path)

    with open('dist/format.json', 'w', encoding='utf-8') as f:
        json.dump(formats, f, indent=2, ensure_ascii=False)
    print(f"  Built dist/format.json ({len(formats)} formats)")

    # Cards: id is the set plus the normalized printed index, which keeps
    # "030" and "030a" apart within a set.
    def card_id(record):
        return to_kebab_case(f"{record.get('set')}-{record.get('index')}")

    cards = load_entities(
        'data/card', 'card', card_id,
        {'set': 'set_id', 'oracle': 'oracle_id'}
    )

    for record in cards.values():
        record['card_index'] = record.pop('index', None)

    with open('dist/card.json', 'w', encoding='utf-8') as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)
    print(f"  Built dist/card.json ({len(cards)} cards)")

    # For decks 'group' is a free label: often the game's set, but it may be any grouping ('2013', 'raid'), so it is never checked against sets
    def deck_id(record):
        return to_kebab_case(f"{record.get('group')}-{record.get('name')}")

    decks = load_entities('data/deck', 'deck', deck_id, {'group': 'group_id'})

    with open('dist/deck.json', 'w', encoding='utf-8') as f:
        json.dump(decks, f, indent=2, ensure_ascii=False)
    print(f"  Built dist/deck.json ({len(decks)} decks)")


def check_references(cards, oracles, sets, collections, formats, decks):
    # Schema validation only ever sees one file at a time, so a reference to a record that does not exist will pass as a false-positive, this is what catches that.
    problems = []

    def check(source, field, value, target, label):
        if value and value not in target:
            problems.append(f"{source}: {field} '{value}' is not a known {label}")

    for card_id, record in cards.items():
        check(f"card {card_id}", 'oracle', record.get('oracle_id'), oracles, 'oracle')
        check(f"card {card_id}", 'set', record.get('set_id'), sets, 'set')

    # An oracle's origin is the card id of its earliest printing, and split places the oracle's file by that card.
    for oracle_id, record in oracles.items():
        check(f"oracle {oracle_id}", 'origin', record.get('origin'), cards, 'card')

    for set_id, record in sets.items():
        check(f"set {set_id}", 'collection', record.get('collection_id'), collections, 'collection')

    for deck_id, record in decks.items():
        check(f"deck {deck_id}", 'highlight', record.get('highlight'), cards, 'card')

        for section, entries in (record.get('list') or {}).items():
            if isinstance(entries, dict):
                for card_ref in entries:
                    check(f"deck {deck_id} list.{section}", 'card', card_ref, cards, 'card')

    vocabulary = set()
    for record in oracles.values():
        vocabulary.update(record.get('category') or [])
        vocabulary.update(record.get('trait') or [])

    for format_id, record in formats.items():
        # '*' is the wildcard meaning "every set"
        for value in (record.get('set_allow') or []):
            if value != '*':
                check(f"format {format_id}", 'set_allow', value, sets, 'set')

        for field in ('oracle_ban', 'oracle_restrict'):
            entries = record.get(field) or []
            # oracle_restrict maps an id to its limit; oracle_ban is a plain list
            for value in (entries.keys() if isinstance(entries, dict) else entries):
                check(f"format {format_id}", field, value, oracles, 'oracle')

        # oracle_exception is keyed by a category or trait value rather than an id.
        # A key that matches nothing would silently never apply, so it is checked here against the vocabulary the oracles actually use.
        for value in (record.get('oracle_exception') or {}):
            check(f"format {format_id}", 'oracle_exception', value, vocabulary, 'category or trait')

    if problems:
        print(f"Error: {len(problems)} reference(s) do not resolve:")
        for problem in problems[:MAX_REPORTED_PROBLEMS]:
            print(f"  - {problem}")
        if len(problems) > MAX_REPORTED_PROBLEMS:
            print(f"  ... and {len(problems) - MAX_REPORTED_PROBLEMS} more")
        sys.exit(1)

    print("  All references resolve.")


def exception_limit(table, categories, traits):
    # oracle_exception is flat: a key is matched against an oracle's categories and its traits alike. 
    # Nothing here keeps the two vocabularies apart, so a trait must never reuse a category's name.
    # Example: in Pokémon a basic Energy is traited 'Basic Energy' rather than 'Basic'.
    if not table:
        return None

    for value in (*categories, *traits):
        if value in table:
            return table[value]

    return None


def compile_joined_database():
    print("Step 2: Joining data and outputing database...")

    with open('dist/card.json', 'r') as f: cards = json.load(f)
    with open('dist/oracle.json', 'r') as f: oracles = json.load(f)
    with open('dist/set.json', 'r') as f: sets = json.load(f)
    with open('dist/collection.json', 'r') as f: collections = json.load(f)
    with open('dist/format.json', 'r') as f: formats = json.load(f)
    with open('dist/deck.json', 'r') as f: decks = json.load(f)

    check_references(cards, oracles, sets, collections, formats, decks)

    # A regulation mark is printed on a card, so it is authored there. 
    # The pool of every mark an oracle has appeared under is gathered from its printings here rather than stored.
    # This is what keeps a 2007 printing from inheriting a mark that did not exist until 2020.
    regulation_pool = {}
    for record in cards.values():
        mark = record.get("regulation")
        if not mark:
            continue
        marks = regulation_pool.setdefault(record.get("oracle_id"), [])
        if mark not in marks:
            marks.append(mark)

    card_complete_dict = {}

    for card_id, record in cards.items():
        oracle_id = record.get("oracle_id")
        if oracle_id in oracles:
            for k, v in oracles[oracle_id].items():
                if k not in record: record[k] = v

        sid = record.get("set_id")
        coll_id_from_set = None
        if sid in sets:
            set_info = sets[sid]
            coll_id_from_set = set_info.get("collection_id")
            for k, v in set_info.items():
                match k:
                    case 'name':
                        key = "set_name"
                    case 'type':
                        key = "set_type"
                    case 'index':
                        key = "set_index"
                    case _:
                        key = k
                if key not in record: record[key] = v

        cid = record.get("collection_id") or coll_id_from_set
        if cid in collections:
            for k, v in collections[cid].items():
                match k:
                    case 'name':
                        key = "collection_name"
                    case 'type':
                        key = "collection_type"
                    case 'index':
                        key = "collection_index"
                    case _:
                        key = k
                if key not in record: record[key] = v

        # Calculate Legality. 'legality' is keyed by format name; 
        # Also note that 'format' is reserved for naming a format, the way a deck's own 'format' does
        # Not to be confused with a guaranteed legality. 
        record["legality"] = {}
        record["legal"] = []
        record["ban"] = []
        record["restrict"] = []
        c_set_id = record.get("set_id")
        c_oid = record.get("oracle_id")
        c_cat = record.get("category") or []
        c_trait = record.get("trait") or []

        # A player may use any printing whose mark is legal
        # Legality tests the oracle's whole pool, not just the mark on the card in hand.
        # The card keeps its own printed mark in 'regulation'.
        record["oracle_regulation"] = sorted(regulation_pool.get(c_oid, []))
        c_reg = record["oracle_regulation"]

        for f_name, f_rules in formats.items():
            legal, limit = False, 0
            s_allow = f_rules.get("set_allow") or []
            r_allow = f_rules.get("regulation_allow") or []
            bans = f_rules.get("oracle_ban") or []

            if c_oid in bans:
                record["ban"].append(f_name)

            # Set and regulation are independent routes to legality, not a combined pair of gates. 
            # Perhaps specific only for Pokémon: Regulation marks are a newer mechanic: older cards can only qualify by set, newer ones only by mark. 
            # An empty list means the format does not admit cards by that route at all.
            by_set = "*" in s_allow or c_set_id in s_allow
            by_regulation = "*" in r_allow or any(mark in r_allow for mark in c_reg)

            if (by_set or by_regulation) and c_oid not in bans:
                restricts = f_rules.get("oracle_restrict")
                exception = exception_limit(f_rules.get("oracle_exception"), c_cat, c_trait)
                if restricts and c_oid in restricts:
                    legal, limit = True, restricts[c_oid]
                    record["restrict"].append(f_name)
                elif exception is not None:
                    legal, limit = True, exception
                else:
                    legal, limit = True, f_rules.get("oracle_limit", 4)
                record["legal"].append(f_name)

            record["legality"][f_name] = {"legal": legal, "limit": limit}

        card_complete_dict[card_id] = record

    with open('dist/database.json', 'w', encoding='utf-8') as f:
        json.dump(card_complete_dict, f, indent=2, ensure_ascii=False)
    print(f"  Built dist/database.json ({len(card_complete_dict)} cards)")


def main():
    compile_base_jsons()
    print("-" * 30)
    compile_joined_database()


if __name__ == "__main__":
    main()
