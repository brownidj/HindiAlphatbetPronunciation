import os
import yaml
from pathlib import Path
from openai import OpenAI

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "letters.yaml"
API_KEY = os.getenv("HINDI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise EnvironmentError("Please set HINDI_OPENAI_API_KEY or OPENAI_API_KEY in your environment.")

client = OpenAI(api_key=API_KEY)

def _normalize_letters(data):
    """Return a list of entry dicts regardless of YAML shape.
    Accepts either a top-level list of entries, or a dict with key 'letters'.
    Filters out any non-dict items defensively.
    """
    if isinstance(data, dict) and isinstance(data.get("letters"), list):
        items = data["letters"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("letters.yaml must be a list or contain a 'letters' list")

    # Keep only dict entries; skip stray strings or other types
    out = []
    for i, item in enumerate(items):
        if isinstance(item, dict):
            out.append(item)
        else:
            print(f"[WARN] Skipping non-dict item at index {i}: {type(item).__name__}")
    return out

def get_dependent_example(symbol: str, dependent_form: str, pronunciation: str) -> str:
    """Ask ChatGPT for a short word using the dependent form, in the format 'का (kā) – Crow'."""
    prompt = f"""
You are helping build a Hindi learning app. 
Suggest a *very simple and common Hindi word* that clearly uses the dependent form '{dependent_form}' 
of the vowel/consonant '{symbol}'. 
Format it as: <Hindi word> (<transliteration>) – <English meaning>.
Example: का (kā) – Crow
If the dependent form is empty or not applicable, return an empty string.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a Hindi language assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.6,
        )
        text = response.choices[0].message.content.strip()
        return text
    except Exception as e:
        print(f"[ERROR] API call failed for {symbol}: {e}")
        return ""

def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Cannot find {DATA_FILE}")

    with DATA_FILE.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    letters = _normalize_letters(raw)
    print(f"Loaded {len(letters)} entries from {DATA_FILE}")

    updated = 0
    for i, entry in enumerate(letters):
        if not isinstance(entry, dict):
            print(f"[{i+1}] Skipping non-dict entry: {type(entry).__name__}")
            continue
        symbol = entry.get("symbol", "")
        dependent_form = (entry.get("dependent_form") or "").strip()
        pronunciation = entry.get("pronunciation", "")
        existing = entry.get("dependent_form_example")

        if existing or not dependent_form:
            print(f"[{i+1}] Skipping {symbol} (already has example or no dependent form)")
            continue

        print(f"[{i+1}] Generating dependent form example for {symbol} ({dependent_form})...")

        example = get_dependent_example(symbol, dependent_form, pronunciation)
        if example:
            entry["dependent_form_example"] = example
            print(f"   → Added: {example}")
            updated += 1
        else:
            print(f"   → No example generated for {symbol}")

    if updated:
        backup = DATA_FILE.with_suffix(".bak.yaml")
        DATA_FILE.replace(backup)
        print(f"\nBackup created at: {backup}")

        # Write back preserving top-level shape
        if isinstance(raw, dict) and isinstance(raw.get("letters"), list):
            raw["letters"] = letters
            to_dump = raw
        else:
            to_dump = letters

        with DATA_FILE.open("w", encoding="utf-8") as f:
            yaml.safe_dump(to_dump, f, allow_unicode=True, sort_keys=False)

        print(f"\n✅ Updated {updated} entries with new dependent_form_example.")
    else:
        print("\nNo updates were needed.")

if __name__ == "__main__":
    main()