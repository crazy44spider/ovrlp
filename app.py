import os

import requests
from fastapi import FastAPI, HTTPException

from discovery import RateLimitError, normalize_key, song_lookup

app = FastAPI(title="OvrLP API")


@app.get("/hello")
def hello():
    return {"message": "Hello from OvrLP!"}


@app.get("/api/lookup")
def lookup(title: str, artist: str):
    title, artist = title.strip(), artist.strip()
    if not title or not artist:
        raise HTTPException(status_code=422, detail="Enter both a song title and an artist.")

    api_key = os.getenv("GETSONGBPM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Song lookup is not configured.")

    try:
        with requests.Session() as session:
            session.headers["X-API-KEY"] = api_key
            song = song_lookup(session, title, artist)
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

    if song is None:
        raise HTTPException(status_code=404, detail="Song not found.")

    song_artist = song.get("artist")
    return {
        "title": song.get("title"),
        "artist": song_artist.get("name") if isinstance(song_artist, dict) else None,
        "bpm": song_bpm(song.get("tempo")),
        "key": song_key(song.get("key_of")),
    }


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
