import json
import os

from cardcarp_compile.util import card_dir, pack_dir


def load_if_present(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def pack_collection(record, sets, collections):
    # A pack's art lives under the collection of the first set it draws from.
    for set_id in (record.get('set_id') or []):
        collection = collections.get((sets.get(set_id) or {}).get('collection_id'))
        if collection:
            return collection
    return {}

def with_id(data):
    # The dict key becomes a property on the record, so a record still identifies itself once it is flattened out of the dict downstream.
    return {record_id: {"id": record_id, **record}
            for record_id, record in data.items()}


def combine_data():
    
    mappings = {
        'card_dict': 'dist/database.json',
        'deck_dict': 'dist/deck.json',
        'pack_dict': 'dist/pack.json',
    }
    
    combined = {}

    sets = load_if_present('dist/set.json')
    collections = load_if_present('dist/collection.json')
    
    for key, path in mappings.items():
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if key == 'card_dict':
                print(f"Processing paths for {len(data)} cards...")
                for record_id, record in data.items():
                    record['dir'] = card_dir(record)

            data = with_id(data)

            if key == 'pack_dict':
                for record in data.values():
                    record['dir'] = pack_dir(record, pack_collection(record, sets, collections))

            combined[key] = data
            print(f"Loaded {path} into key '{key}'")

        else:
            print(f"Warning: {path} not found, skipping key '{key}'")
            combined[key] = {}

    output_path = 'dist/manifest.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        # Written compact rather than pretty-printed.
        json.dump(combined, f, separators=(',', ':'))
    
    print(f"Successfully created {output_path}")


def main():
    combine_data()


if __name__ == "__main__":
    main()
