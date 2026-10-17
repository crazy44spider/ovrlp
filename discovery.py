import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
BASE_URL = "https://api.getsong.co"
CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "getsongbpm"
# Keeping API results for a week to avoid unnecessary repeated requests.
CACHE_TTL = 7 * 24 * 60 * 60

# GetSongBPM uses pitch class (C=0) and mode (minor=0, major=1).
ROOTS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PITCH = {name: i for i, name in enumerate(ROOTS)}
# Canonical Camelot wheel, minor=A, major=B.
WHEEL = {
    1: ("G#m", "B"), 2: ("D#m", "F#"), 3: ("A#m", "C#"),
    4: ("Fm", "G#"), 5: ("Cm", "D#"), 6: ("Gm", "A#"),
    7: ("Dm", "F"), 8: ("Am", "C"), 9: ("Em", "G"),
    10: ("Bm", "D"), 11: ("F#m", "A"), 12: ("C#m", "E"),
}
CAMELOT = {key: (number, mode) for number, pair in WHEEL.items()
           for mode, key in zip(("A", "B"), pair)}
ENHARMONIC = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#",
              "E#": "F", "B#": "C", "Cb": "B", "Fb": "E"}


def normalize_key(key):
    if not key:
        raise ValueError("Missing musical key")
    key = key.strip().replace("♯", "#").replace("♭", "b")
    minor = key.lower().endswith("m")
    root = key[:-1] if minor else key
    root = root[0].upper() + root[1:]
    root = ENHARMONIC.get(root, root)
    normalized = root + ("m" if minor else "")
    if normalized not in CAMELOT:
        raise ValueError(f"Unsupported key: {key}")
    return normalized


def compatible_keys(key):
    number, mode = CAMELOT[normalize_key(key)]
    previous = 12 if number == 1 else number - 1
    following = 1 if number == 12 else number + 1
    opposite = "B" if mode == "A" else "A"
    return [key_from_camelot(n, m) for n, m in (
        (number, mode), (number, opposite), (previous, mode), (following, mode)
    )]


def key_from_camelot(number, mode):
    return WHEEL[number][0 if mode == "A" else 1]


def relationship(reference, candidate):
    a, amode = CAMELOT[normalize_key(reference)]
    b, bmode = CAMELOT[normalize_key(candidate)]
    if a == b and amode == bmode:
        return "same key"
    if a == b:
        return "relative major/minor"
    if amode == bmode and ((a - b) % 12 in (1, 11)):
        return "adjacent Camelot"
    return None


def transpose(key, semitones):
    key = normalize_key(key)
    minor = key.endswith("m")
    root = key[:-1] if minor else key
    return ROOTS[(PITCH[root] + semitones) % 12] + ("m" if minor else "")


def pitch_option(reference, candidate, max_shift=4):
    direct = relationship(reference, candidate)
    if direct:
        return (0, candidate, direct)
    for distance in range(1, max_shift + 1):
        for shift in (-distance, distance):
            shifted = transpose(candidate, shift)
            rel = relationship(reference, shifted)
            if rel:
                return (shift, shifted, rel)
    return None


def tempo_option(reference_bpm, candidate_bpm):
    options = []
    for factor, name in ((0.5, "half-time"), (1, "normal"), (2, "double-time")):
        interpreted = candidate_bpm * factor
        adjustment = 100 * (reference_bpm - interpreted) / interpreted
        options.append((abs(adjustment), adjustment, name, interpreted))
    _, adjustment, name, interpreted = min(options)
    return adjustment, name, interpreted


def cache_path(endpoint, params):
    import hashlib
    signature = json.dumps([endpoint, params], sort_keys=True)
    digest = hashlib.sha256(signature.encode()).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def api_get(session, endpoint, params):
    path = cache_path(endpoint, params)
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    response = session.get(f"{BASE_URL}/{endpoint}/", params=params, timeout=15)
    if response.status_code == 429:
        raise RuntimeError("GetSongBPM returned 429. Stop requests and respect Retry-After: "
                           + str(response.headers.get("Retry-After", "not specified")))
    response.raise_for_status()
    data = response.json()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def song_lookup(session, title, artist):
    data = api_get(session, "search", {
        "type": "both", "lookup": f"song:{title} artist:{artist}"
    })
    if not isinstance(data, dict):
        return None
    items = data.get("search", [])
    if not isinstance(items, list):
        return None
    items = [item for item in items if isinstance(item, dict)]
    if not items:
        return None

    def clean(value):
        return " ".join(value.casefold().strip().split()) if isinstance(value, str) else ""

    exact = [item for item in items
             if clean(item.get("title")) == clean(title)
             and isinstance(item.get("artist"), dict)
             and clean(item["artist"].get("name")) == clean(artist)]
    return (exact or items)[0]


MODES = {
    "1": "Exact Match",
    "2": "Tempo Match (Spotify transitions)",
    "3": "Key + Tempo Match (DJ/mashup)",
}


def discovery_plan(reference_bpm, reference_key, mode):
    """Choose searches based on what the selected mode actually permits."""
    if mode == "1":
        bpms = {round(reference_bpm)}
        keys = [normalize_key(reference_key)]
    elif mode == "2":
        # Spotify mode: no pitch shifts; literal BPM window +/-10.
        bpms = set(range(round(reference_bpm) - 10, round(reference_bpm) + 11))
        keys = compatible_keys(reference_key)
    else:
        # DJ mode: normal/half/double tempo, possible pitch shifting.
        bpms = set()
        for center in (reference_bpm / 2, reference_bpm, reference_bpm * 2):
            bpms.update(range(round(center) - 3, round(center) + 4))
        keys = list(CAMELOT)
    return sorted(b for b in bpms if 1 <= b <= 300), keys


def discover(session, reference_bpm, reference_key, mode="2", limit=50):
    """Find songs by intersecting bounded tempo and key result lists by ID."""
    bpms, candidate_keys = discovery_plan(reference_bpm, reference_key, mode)
    bpm_results = {}
    key_results = {}
    print(f"Searching {len(bpms)} tempos and {len(candidate_keys)} keys "
          f"(up to {len(bpms) + len(candidate_keys)} API queries; cached results reused)...")

    for bpm in bpms:
        for song in api_get(session, "tempo", {"bpm": bpm, "limit": limit}).get("tempo", []):
            bpm_results[song["song_id"]] = song

    for key in candidate_keys:
        minor = key.endswith("m")
        root = key[:-1] if minor else key
        params = {"key_of": PITCH[root], "mode": 0 if minor else 1, "limit": limit}
        for song in api_get(session, "key", params).get("key_of", []):
            key_results[song["song_id"]] = key

    matches = []
    for song_id in bpm_results.keys() & key_results.keys():
        song = bpm_results[song_id]
        try:
            bpm = float(song["tempo"])
            key = key_results[song_id]
            if mode == "1":
                if abs(bpm - reference_bpm) > 0.01 or key != reference_key:
                    continue
                adjustment, tempo_mode, interpreted = 0.0, "normal", bpm
                pitch = (0, key, "same key")
            elif mode == "2":
                # No key changes or half/double-time interpretations in Spotify mode.
                if abs(bpm - reference_bpm) > 10:
                    continue
                adjustment = 100 * (reference_bpm - bpm) / bpm
                tempo_mode, interpreted = "normal", bpm
                relation = relationship(reference_key, key)
                if not relation:
                    continue
                pitch = (0, key, relation)
            else:
                adjustment, tempo_mode, interpreted = tempo_option(reference_bpm, bpm)
                pitch = pitch_option(reference_key, key, max_shift=2)
                if not pitch or abs(adjustment) > 6:
                    continue
            semitones, shifted_key, harmonic_relation = pitch
            matches.append({
                "id": song_id, "title": song["song_title"],
                "artist": song.get("artist", {}).get("name", "Unknown"),
                "bpm": bpm, "key": key, "adjustment": adjustment,
                "tempo_mode": tempo_mode, "interpreted_bpm": interpreted,
                "semitones": semitones, "shifted_key": shifted_key,
                "relationship": harmonic_relation,
                "url": song.get("song_uri", ""),
            })
        except (ValueError, KeyError, TypeError, ZeroDivisionError):
            continue

    relation_rank = {"same key": 0, "relative major/minor": 1, "adjacent Camelot": 2}
    matches.sort(key=lambda s: (
        abs(s["semitones"]), abs(s["adjustment"]),
        relation_rank.get(s["relationship"], 3), s["title"].casefold()
    ))
    return matches, len(bpm_results), len(key_results)


def get_reference_song(session):
    """Look up a reference song, or let the user supply its BPM and key."""
    while True:
        title = input("Song title: ").strip()
        artist = input("Artist: ").strip()
        if not title or not artist:
            print("Please enter both a song title and an artist.\n")
            continue

        song = song_lookup(session, title, artist)
        if song and song.get("tempo") and song.get("key_of"):
            try:
                bpm = float(song["tempo"])
                key = normalize_key(song["key_of"])
                if not 1 <= bpm <= 300:
                    raise ValueError("BPM must be between 1 and 300.")
                return {
                    "title": song.get("title", title),
                    "artist": (song.get("artist") or {}).get("name", artist) if isinstance(song.get("artist"), dict) else artist,
                    "bpm": bpm,
                    "key": key,
                    "id": song.get("id"),
                }
            except (ValueError, TypeError):
                pass

        if song:
            print("\nSong found, but its BPM or key is missing/invalid.")
        else:
            print("\nSong not found.")

        while True:
            choice = input(
                "1. Try searching again\n"
                "2. Enter BPM and key manually\n"
                "3. Cancel\n"
                "Choose [1/2/3]: "
            ).strip()
            if choice in ("1", "2", "3"):
                break
            print("Please choose 1, 2, or 3.")

        if choice == "1":
            print()
            continue
        if choice == "3":
            return None

        while True:
            entered_bpm = input("BPM (e.g. 93): ").strip()
            try:
                bpm = float(entered_bpm)
                if not 1 <= bpm <= 300:
                    raise ValueError()
                break
            except ValueError:
                print("Enter a BPM between 1 and 300.")

        while True:
            entered_key = input("Key (e.g. Am, C#, Bbm): ").strip()
            try:
                key = normalize_key(entered_key)
                break
            except (ValueError, IndexError):
                print("Invalid key. Examples: Am, C, F#m, Bb.")

        return {
            "title": title,
            "artist": artist,
            "bpm": bpm,
            "key": key,
            "id": None,
        }


def main():
    api_key = os.getenv("GETSONGBPM_KEY")
    if not api_key:
        print("Missing GETSONGBPM_KEY in .env")
        return
    print("OvrLP discovery modes:")
    for code, name in MODES.items():
        print(f"  {code}. {name}")
    mode = input("Choose mode [2]: ").strip() or "2"
    if mode not in MODES:
        print("Invalid mode; choose 1, 2, or 3.")
        return

    session = requests.Session()
    session.headers.update({"X-API-KEY": api_key})
    try:
        reference = get_reference_song(session)
        if reference is None:
            print("Search cancelled.")
            return

        bpm = reference["bpm"]
        key = reference["key"]
        print(f"\nReference: {reference['title']} — {reference['artist']} | {bpm:g} BPM | {key}")
        print(f"Mode: {MODES[mode]}")
        matches, tempo_count, key_count = discover(session, bpm, key, mode=mode)
        matches = [s for s in matches if s["id"] != reference["id"]]
        print(f"\nFound {len(matches)} matches in overlapping results "
              f"({tempo_count} tempo candidates, {key_count} key candidates).\n")
        for s in matches[:30]:
            direction = "speed up" if s["adjustment"] > 0 else "slow down"
            tempo_note = (f"{direction} {abs(s['adjustment']):.1f}%"
                          if abs(s["adjustment"]) > 0.05 else "no tempo change")
            pitch_note = ("no pitch shift" if s["semitones"] == 0 else
                          f"pitch shift {s['semitones']:+d} → {s['shifted_key']}")
            print(f"{s['title']} — {s['artist']} | {s['bpm']:g} BPM | {s['key']}")
            print(f"  {s['tempo_mode']}; {tempo_note}; {s['relationship']}; {pitch_note}")
    except (requests.RequestException, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Could not complete discovery: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
