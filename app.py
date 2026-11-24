import os
from contextlib import contextmanager
from typing import Annotated, Literal

import requests
from fastapi import FastAPI, HTTPException, Query

from discovery import RateLimitError, discover, normalize_key, song_lookup

app = FastAPI(title="OvrLP API")


@app.get("/hello")
def hello():
    return {"message": "Hello from OvrLP!"}


@app.get("/api/lookup")
def lookup(title: str, artist: str):
    title, artist = title.strip(), artist.strip()
    if not title or not artist:
        raise HTTPException(status_code=422, detail="Enter both a song title and an artist.")

    with provider_session() as session:
        song = song_lookup(session, title, artist)

    if song is None:
        raise HTTPException(status_code=404, detail="Song not found.")

    song_artist = song.get("artist")
    return {
        "id": song.get("id"),
        "title": song.get("title"),
        "artist": song_artist.get("name") if isinstance(song_artist, dict) else None,
        "bpm": song_bpm(song.get("tempo")),
        "key": song_key(song.get("key_of")),
    }


@app.get("/api/discover")
def discover_songs(
    bpm: Annotated[float, Query(ge=1, le=300)],
    key: str,
    mode: Literal["1", "2", "3"] = "2",
    reference_id: str | None = None,
):
    normalized_key = song_key(key)
    if normalized_key is None:
        raise HTTPException(status_code=422, detail="Enter a musical key such as Am, C, or Bb.")

    with provider_session() as session:
        matches, tempo_count, key_count = discover(session, bpm, normalized_key, mode=mode)

    if reference_id is not None:
        matches = [song for song in matches if str(song["id"]) != reference_id]

    return {
        "matches": matches[:100],
        "total_matches": len(matches),
        "tempo_candidates": tempo_count,
        "key_candidates": key_count,
    }


@contextmanager
def provider_session():
    api_key = os.getenv("GETSONGBPM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="The song data provider is not configured.")

    try:
        with requests.Session() as session:
            session.headers["X-API-KEY"] = api_key
            yield session
    except RateLimitError as error:
        headers = {"Retry-After": error.retry_after} if error.retry_after else None
        raise HTTPException(
            status_code=503, detail="The song data provider is rate-limiting requests.",
            headers=headers,
        ) from error
    except requests.Timeout as error:
        raise HTTPException(status_code=504, detail="The song data provider timed out.") from error
    except (requests.RequestException, OSError) as error:
        raise HTTPException(status_code=502, detail="Could not retrieve song data.") from error


def song_bpm(value):
    try:
        bpm = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return bpm if 1 <= bpm <= 300 else None


def song_key(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return normalize_key(value)
    except (ValueError, IndexError):
        return None
