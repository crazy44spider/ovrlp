
# OvrLP matching engine
CAMELOT = {
    "Abm": "1A", "G#m": "1A", "B": "1B",
    "Ebm": "2A", "D#m": "2A", "F#": "2B",
    "Bbm": "3A", "A#m": "3A", "Db": "3B", "C#": "3B",
    "Fm": "4A", "Ab": "4B", "G#": "4B",
    "Cm": "5A", "Eb": "5B", "D#": "5B",
    "Gm": "6A", "Bb": "6B", "A#": "6B",
    "Dm": "7A", "F": "7B",
    "Am": "8A", "C": "8B",
    "Em": "9A", "G": "9B",
    "Bm": "10A", "D": "10B",
    "F#m": "11A", "Gbm": "11A", "A": "11B",
    "C#m": "12A", "Dbm": "12A", "E": "12B"
}

NOTES = {
    "C": 0,
    "C#": 1, "Db": 1,
    "D": 2,
    "D#": 3, "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6, "Gb": 6,
    "G": 7,
    "G#": 8, "Ab": 8,
    "A": 9,
    "A#": 10, "Bb": 10,
    "B": 11
}

# Names used when shifting notes
NOTE_NAMES = [
    "C", "Db", "D", "Eb", "E", "F",
    "Gb", "G", "Ab", "A", "Bb", "B"
]


def compare_tempo(bpm1, bpm2):
    bpm1 = float(bpm1)
    bpm2 = float(bpm2)

    if bpm1 <= 0 or bpm2 <= 0:
        return None

    possibilities = [
        ("Normal", bpm2),
        ("Half-time", bpm2 / 2),
        ("Double-time", bpm2 * 2)
    ]

    best = None

    for interpretation, effective_bpm in possibilities:
        change = (bpm1 - effective_bpm) / effective_bpm * 100

        if best is None or abs(change) < abs(best["change"]):
            best = {
                "interpretation": interpretation,
                "effective_bpm": effective_bpm,
                "change": change
            }

    return best


def compare_keys(key1, key2):
    camelot1 = CAMELOT.get(key1)
    camelot2 = CAMELOT.get(key2)

    if camelot1 is None or camelot2 is None:
        return "Unknown key"

    number1 = int(camelot1[:-1])
    number2 = int(camelot2[:-1])

    mode1 = camelot1[-1]
    mode2 = camelot2[-1]

    distance = min(
        (number1 - number2) % 12,
        (number2 - number1) % 12
    )

    if camelot1 == camelot2:
        return "Same key"

    if number1 == number2:
        return "Relative major/minor"

    if distance == 1 and mode1 == mode2:
        return "Adjacent harmonic keys"

    if distance == 1 and mode1 != mode2:
        return "Experimental cross-mode match"

    return "Not compatible under current rules"


def shift_key(key, semitones):
    # Determine whether the original key is minor
    is_minor = key.endswith("m")

    # Remove the minor suffix to get the root note
    root = key[:-1] if is_minor else key

    if root not in NOTES:
        return None

    # Move the root by the requested number of semitones
    new_position = (NOTES[root] + semitones) % 12
    new_root = NOTE_NAMES[new_position]

    # Preserve major/minor mode
    if is_minor:
        return new_root + "m"

    return new_root


def find_pitch_shift(key1, key2):
    # If already conventionally compatible, don't shift
    current_match = compare_keys(key1, key2)

    standard_matches = [
        "Same key",
        "Relative major/minor",
        "Adjacent harmonic keys"
    ]

    if current_match in standard_matches:
        return {
            "shift": 0,
            "new_key": key2,
            "relationship": current_match
        }

    if current_match == "Unknown key":
        return None

    # Try shifting song 2 by up to 6 semitones
    # Check smaller shifts first
    for amount in range(1, 7):
        for shift in [-amount, amount]:
            shifted_key = shift_key(key2, shift)
            relationship = compare_keys(key1, shifted_key)

            if relationship in standard_matches:
                return {
                    "shift": shift,
                    "new_key": shifted_key,
                    "relationship": relationship
                }

    return None


def compare_songs(bpm1, key1, bpm2, key2):
    tempo = compare_tempo(bpm1, bpm2)
    current_match = compare_keys(key1, key2)
    pitch = find_pitch_shift(key1, key2)

    print("\n========== OvrLP ==========")
    print(f"Song 1: {bpm1} BPM | {key1}")
    print(f"Song 2: {bpm2} BPM | {key2}")

    print("\n--- TEMPO ---")

    if tempo is None:
        print("Tempo data unavailable.")
    else:
        print("Best interpretation:", tempo["interpretation"])
        print(f"Effective BPM: {tempo['effective_bpm']:g}")
        print(f"Tempo adjustment: {tempo['change']:+.2f}%")

    print("\n--- ORIGINAL KEY RELATIONSHIP ---")
    print(current_match)

    print("\n--- PITCH SHIFT ---")

    if pitch is None:
        print("Unable to calculate a pitch adjustment.")

    elif pitch["shift"] == 0:
        print("No pitch shift needed.")
        print("Relationship:", pitch["relationship"])

    else:
        if current_match == "Experimental cross-mode match":
            print("These keys may already work without shifting.")
            print("Optional standard-harmony adjustment:")

        print(f"Relative pitch shift: {pitch['shift']:+d} semitones")
        print(f"Song 2 would become: {pitch['new_key']}")
        print(f"New relationship: {pitch['relationship']}")
        print("You can distribute the relative shift between tracks.")


# Temporary tests
compare_songs(160, "Bm", 75, "D")
compare_songs(125, "F", 128, "Am")
compare_songs(125, "C", 128, "E")