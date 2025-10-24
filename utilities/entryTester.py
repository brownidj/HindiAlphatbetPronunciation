import sys
from pathlib import Path
import yaml
import logging
import subprocess
import shutil
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
LOGGER = logging.getLogger("entry_tester")

def load_yaml_letters(project_root: Path):
    """Load the main letters.yaml file from the project root."""
    yaml_path = project_root / 'data' / 'letters.yaml'
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")
    with yaml_path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        # Also support schema: {letters: [...]}
        if isinstance(data, dict) and isinstance(data.get('letters'), list):
            return data['letters']
        raise ValueError("letters.yaml must contain a list of entries or a {letters: [...]} block")
    return data

def pick_entry(letters, symbol=None, index=None, translit=None, noun=None):
    """Select a single entry by symbol, index, transliteration, or noun."""
    if symbol:
        for entry in letters:
            if entry.get('symbol') == symbol:
                return entry
    if index is not None and 0 <= index < len(letters):
        return letters[index]
    if translit:
        q = translit.lower()
        for entry in letters:
            if q in (entry.get('example', '').lower()):
                return entry
    if noun:
        q = noun.lower()
        for entry in letters:
            if q in (entry.get('example', '').lower()):
                return entry
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test a single entry from letters.yaml")
    parser.add_argument('--symbol', type=str, help='Devanagari symbol to load')
    parser.add_argument('--index', type=int, help='Zero-based index of entry to load')
    parser.add_argument('--translit', type=str, help='Match transliteration text')
    parser.add_argument('--noun', type=str, help='Match English noun text')
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    letters = load_yaml_letters(project_root)

    entry = pick_entry(letters, args.symbol, args.index, args.translit, args.noun)
    if not entry:
        LOGGER.warning("No matching entry found.")
        sys.exit(1)

    example = entry.get('example') or ''
    LOGGER.info("Testing entry: %s – %s", entry.get('symbol'), example)

    data_dir = project_root / 'data'
    app_yaml = data_dir / 'letters.yaml'
    backup_yaml = data_dir / 'letters.yaml.bak'

    single_list = [entry]

    # Backup existing file, write test entry, launch app, then restore
    try:
        if app_yaml.exists():
            shutil.copy2(app_yaml, backup_yaml)
            LOGGER.info(f"Backed up {app_yaml.name} -> {backup_yaml.name}")
        with app_yaml.open('w', encoding='utf-8') as f:
            yaml.safe_dump(single_list, f, allow_unicode=True, sort_keys=False)
        LOGGER.info("Wrote single-entry letters.yaml for testing")

        LOGGER.info("Launching app with test entry...")
        subprocess.run([sys.executable, str(project_root / 'main.py')], cwd=str(project_root))
    finally:
        if backup_yaml.exists():
            shutil.move(str(backup_yaml), str(app_yaml))
            LOGGER.info("Restored original letters.yaml from backup")

if __name__ == '__main__':
    main()