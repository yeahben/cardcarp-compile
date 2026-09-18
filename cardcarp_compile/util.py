import re
import os
import sys
import unicodedata

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


def to_kebab_case(text):
    if text is None:
        return ""

    text = str(text)

    # Remove apostrophes entirely (Lodash behavior), curly included so that "Cynthia's" and "Cynthia’s" cannot kebab to different ids
    text = re.sub(r"['‘’]", "", text)

    # Transliterate accents to their base letter, so "Pokémon" becomes "pokemon" rather than being split on the accented character
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    # No camelCase splitting: these are proper product names, not code identifiers. "McDonald's" is one word, as are HeartGold and BREAKpoint.

    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text)

    # Normalize case and trim
    return text.lower().strip("-")

def index_prefix(value):
    # A folder's ordering prefix.
    # Plain numbers are zero-padded to two digits so 2 sorts before 10. 
    # Anything else is passed through untouched.
    # Not every game numbers its sets with integers.
    # Example: 'reborn-01' or '01a' are ordering schemes, rather than malformed numbers.
    if value is None or value == "":
        return None

    text = str(value).strip()
    try:
        return f"{int(text):02d}"
    except (TypeError, ValueError):
        return text


def index_parts(value):
    # Adds an index for easy scanning folders for editors familiar with said game.
    # Index is unique, not tied specifically to a game's own published index.
    # More like a "what is intuitive" rather than any official numbering.
    if value is None or value == "":
        return (True, 0, "")

    text = str(value)
    match = re.search(r"\d+", text)
    if not match:
        return (False, 0, text)
    return (False, int(match.group()), text[:match.start()] + text[match.end():])


def folder_segment(index, name):
    # One folder: '01-base', or just 'base' where there is no index.
    prefix = index_prefix(index)
    slug = to_kebab_case(name)
    return f"{prefix}-{slug}" if prefix else slug


def card_dir(record):
    # Path stem for card.
    # Relative to data/card (and any tree mirroring it).
    # The card's own index is NOT an ordering prefix.
    card_index = record.get('card_index')
    filename = f"{card_index}-{to_kebab_case(record.get('name'))}" if card_index else to_kebab_case(record.get('name'))

    segments = [
        to_kebab_case(record.get('collection_type')),
        folder_segment(record.get('collection_index'), record.get('collection_name')),
        folder_segment(record.get('set_index'), record.get('set_name')),
        filename,
    ]
    return "/".join(s for s in segments if s)

def save_yml(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    yaml = YAML()
    yaml.width = sys.maxsize
    yaml.explicit_start = False

    # mapping (spaces for dicts), sequence (spaces for list items), offset (spaces before the dash)
    yaml.indent(mapping=2, sequence=4, offset=2)

    cmap = data if isinstance(data, CommentedMap) else CommentedMap(data)

    # Blank line before every top-level key except the first
    for i, key in enumerate(cmap.keys()):
        if i > 0:
            cmap.yaml_set_comment_before_after_key(key, before='\n')

    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(cmap, f)

def load_schema_order(schema_name):
    # Field order is taken from the schema file so the two never drift apart
    schema_path = f'schema/{schema_name}.yml'
    if not os.path.exists(schema_path):
        print(f"Warning: schema/{schema_name}.yml not found, leaving field order as-is.")
        return None

    yaml = YAML()
    with open(schema_path, 'r', encoding='utf-8') as f:
        return list(yaml.load(f).keys())

def order_by_schema(entry, order):
    # Keys the schema knows about come first, in schema order.
    # Anything unrecognized is kept at the end rather than dropped.
    if not order:
        return entry

    ordered = {key: entry[key] for key in order if key in entry}
    ordered.update({k: v for k, v in entry.items() if k not in order})
    return ordered


DATASET_FILE = 'schema/dataset.yml'
DATASET_KEYS = ('card_properties', 'deck_properties', 'collection_types')


def load_dataset(path=DATASET_FILE):
    # This game's own vocabulary.
    if not os.path.exists(path):
        print(f"Error: {path} not found at the root of this repo.")
        print(f"  It declares {', '.join(DATASET_KEYS)} for this game.")
        sys.exit(1)

    yaml = YAML(typ='safe')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.load(f) or {}

    missing = [key for key in DATASET_KEYS if key not in data]
    if missing:
        print(f"Error: {path} is missing {', '.join(missing)}.")
        sys.exit(1)

    # The first collection type is the game's primary one, so there must be one.
    if not data['collection_types']:
        print(f"Error: {path} must list at least one collection type.")
        sys.exit(1)

    return {key: list(data[key] or []) for key in DATASET_KEYS}
