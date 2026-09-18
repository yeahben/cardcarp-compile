import json
import os

from cardcarp_compile.util import card_dir

def with_id(data):
    # The dict key becomes a property on the record, so a record still identifies itself once it is flattened out of the dict downstream.
    return {record_id: {"id": record_id, **record}
            for record_id, record in data.items()}


def combine_data():
    
    mappings = {
        'card_dict': 'dist/database.json',
        'deck_dict': 'dist/deck.json',
    }
    
    combined = {}
    
    for key, path in mappings.items():
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if key == 'card_dict':
                print(f"Processing paths for {len(data)} cards...")
                for record_id, record in data.items():
                    record['dir'] = card_dir(record)

            data = with_id(data)

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
