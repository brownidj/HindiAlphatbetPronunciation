# findImages.py
# [Prompt: generate small transparent PNG images for examples using ChatGPT image API]
from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    # OpenAI Python SDK (>=1.0)
    from openai import OpenAI  # type: ignore
except Exception as exc:  # noqa: BLE001
    print("ERROR: OpenAI SDK not installed. Please add `openai>=1.0.0` to requirements.txt", file=sys.stderr)
    raise

try:
    import yaml  # PyYAML
except Exception:
    print("ERROR: PyYAML not installed. Please add `PyYAML` to requirements.txt", file=sys.stderr)
    raise

PROJECT_ROOT = Path(__file__).resolve().parent
# Use letters.yaml exclusively
DATA_FILE = PROJECT_ROOT.parent / "data" / "letters.yaml"
print(f"DEBUG DATA_FILE: {DATA_FILE}", file=sys.stderr)
OUT_DIR = PROJECT_ROOT.parent / "assets" / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Smallest supported size for OpenAI images (as of SDK >=1.0)
IMAGE_SIZE = "1024x1024"
MODEL = "gpt-image-1"


def _load_yaml(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _extract_examples(data: Dict) -> List[Tuple[str, str, str, str]]:
    """Return list of (symbol, english_noun, transliteration, example_full).

    Supports both schemas:
    1) New explicit schema:
       letters:
         - symbol: "आ"
           example: "आम (aam) – Mango"
           ...
    2) Legacy schema:
       HINDI_VOWELS: { "अ": [dep, approx, hint, "कमल (kamal) – Lotus"], ... }
       HINDI_CONSONANTS: { ... }
    """
    results: List[Tuple[str, str, str, str]] = []

    # --- Preferred: new explicit schema under `letters`
    try:
        letters_block = data.get("letters")
        if isinstance(letters_block, list):
            for item in letters_block:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or "").strip()
                example = str(item.get("example") or "").strip()
                if not symbol or not example:
                    continue
                # Parse transliteration and English noun: "WORD (translit) – Noun"
                parts = re.split(r"\s+[\-–—]\s+", example)
                english = parts[-1].strip() if parts else example
                english_clean = re.sub(r"\(.*?\)", "", english).strip()
                translit_match = re.search(r"\(([^)]+)\)", example)
                transliteration = translit_match.group(1).strip() if translit_match else ""
                noun = english_clean.split(",")[0].strip()
                noun = noun.split(" – ")[0].strip()
                results.append((symbol, noun, transliteration, example))
    except Exception:
        # fall back silently to legacy parsing
        pass

    if results:
        return results

    # --- Legacy fallback: HINDI_VOWELS / HINDI_CONSONANTS blocks
    sections = ["HINDI_VOWELS", "HINDI_CONSONANTS"]
    for section in sections:
        block = data.get(section) or {}
        if not isinstance(block, dict):
            continue
        for symbol, arr in block.items():
            if not isinstance(arr, (list, tuple)) or len(arr) < 4:
                continue
            example = str(arr[3])
            parts = re.split(r"\s+[\-–—]\s+", example)
            english = parts[-1].strip() if parts else example
            english_clean = re.sub(r"\(.*?\)", "", english).strip()
            translit_match = re.search(r"\(([^)]+)\)", example)
            transliteration = translit_match.group(1).strip() if translit_match else ""
            noun = english_clean.split(",")[0].strip()
            noun = noun.split(" – ")[0].strip()
            results.append((str(symbol), noun, transliteration, example))

    return results


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "image"


def _prompt_for(hindi_word: str, symbol: str, example_full: str) -> str:
    """Build a concise, icon-style prompt for smallest transparent PNG."""
    return (
        "Create a photo-realistic illustration of a {noun} using the Hindi word "
        "for the noun being created."
        "Transparent background. Centered. No text. No border. Minimal detail. "
        "High contrast, clear silhouette, suitable at 1024x1024."
    ).format(noun=hindi_word)


def _generate_png(client: OpenAI, prompt: str) -> bytes:
    """Call OpenAI Images API and return raw PNG bytes with transparency."""
    resp = client.images.generate(
        model=MODEL,
        prompt=prompt,
        size=IMAGE_SIZE,
        background="transparent",
        n=1,
    )
    # SDK returns base64 data in resp.data[0].b64_json
    b64 = resp.data[0].b64_json
    return base64.b64decode(b64)


def _save_png(png_bytes: bytes, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        f.write(png_bytes)


def main() -> int:
    # ---- Hardcoded limiter: set to an integer to restrict number of images generated
    # e.g., set to 5 to generate only five images. Leave as None for all.
    max_generate: Optional[int] = None

    # Environment diagnostics to help debug PyCharm vs shell envs
    try:
        dbg_keys = {k: v for k, v in os.environ.items() if "OPENAI" in k or "HINDI" in k}
        dbg_list = ", ".join(f"{k}={'set' if (v or '').strip() else 'empty'}" for k, v in sorted(dbg_keys.items()))
        print(f"DEBUG env: {dbg_list}", file=sys.stderr)
        print(f"DEBUG python: {sys.executable}", file=sys.stderr)
        print(f"DEBUG cwd: {os.getcwd()}", file=sys.stderr)
    except Exception:
        pass

    # Prefer project-specific key; fall back to OPENAI_API_KEY if present
    api_key = os.getenv("HINDI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        print("ERROR: Please set HINDI_OPENAI_API_KEY in your environment (or OPENAI_API_KEY).", file=sys.stderr)
        return 2

    api_key = api_key.strip()

    # Make sure the OpenAI SDK sees the key. Two belts: set env var and pass explicitly.
    os.environ["OPENAI_API_KEY"] = api_key

    data = _load_yaml(DATA_FILE)
    items = _extract_examples(data)
    if items:
        print(f"Found {len(items)} example(s) from letters.yaml", file=sys.stderr)
    else:
        print("No examples parsed from letters.yaml — check schema and example formatting.", file=sys.stderr)
        return 1

    # Apply hardcoded limit if set
    if isinstance(max_generate, int) and max_generate > 0:
        items = items[:max_generate]

    client = OpenAI(api_key=api_key)

    # Generate images for each example noun; skip if file already exists and is non-zero size
    for symbol, noun, transliteration, example_full in items:
        if not noun and not transliteration:
            continue
        base = _slugify(noun)
        trn = _slugify(transliteration) if transliteration else ""
        fname = f"{base}_{trn}.png" if trn else f"{base}.png"
        out_path = OUT_DIR / fname
        # Skip if an image file already exists and is valid (non-zero size)
        if out_path.exists() and out_path.stat().st_size > 0:
            print(f"SKIP existing image for {noun!r}: {out_path}")
            continue

        prompt = _prompt_for(noun, symbol, example_full)
        print(f"Generating {noun}_{transliteration} for symbol {symbol} -> {out_path}")
        print(f"[API] Requesting image generation from ChatGPT for noun: {noun}_{transliteration}")
        try:
            png = _generate_png(client, prompt)
            _save_png(png, out_path)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {noun!r} ({symbol}): {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())