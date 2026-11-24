import { useState } from 'react'
import './App.css'

async function getApi(path, params) {
  const query = new URLSearchParams(params)
  const response = await fetch(`/api/${path}?${query}`)
  const data = await response.json().catch(() => null)

  if (!response.ok || !data) {
    throw new Error(
      typeof data?.detail === 'string'
        ? data.detail
        : 'Could not get a response from OvrLP. Check that the backend is running.',
    )
  }

  return data
}

function MatchCard({ song }) {
  const tempoAdjustment = Math.abs(song.adjustment).toFixed(1)
  const pitchSign = song.semitones > 0 ? '+' : ''

  return (
    <li className="match-card">
      <div>
        <h3>{song.title}</h3>
        <p>{song.artist}</p>
      </div>
      <div className="metadata">{song.bpm} BPM · {song.key}</div>
      <div className="compatibility">
        <span>{song.relationship}</span>
        {song.tempo_mode !== 'normal' && <span>{song.tempo_mode}</span>}
        {tempoAdjustment !== '0.0' && (
          <span>{song.adjustment > 0 ? 'Speed up' : 'Slow down'} {tempoAdjustment}%</span>
        )}
        {song.semitones !== 0 && (
          <span>Shift {pitchSign}{song.semitones} semitones to {song.shifted_key}</span>
        )}
      </div>
    </li>
  )
}

function App() {
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [reference, setReference] = useState(null)
  const [results, setResults] = useState(null)

  async function handleSearch(event) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const title = fields.get('title').trim()
    const artist = fields.get('artist').trim()
    const mode = fields.get('mode')

    setError('')
    setReference(null)
    setResults(null)

    if (!title || !artist) {
      setError('Enter both a song title and an artist.')
      return
    }

    try {
      setStatus('Looking up your song…')
      const song = await getApi('lookup', { title, artist })
      setReference(song)

      if (song.bpm == null || song.key == null) {
        throw new Error('This song is missing a BPM or musical key. Try another song.')
      }

      setStatus('Finding compatible songs…')
      const params = { bpm: song.bpm, key: song.key, mode }
      if (song.id != null) {
        params.reference_id = song.id
      }
      setResults(await getApi('discover', params))
    } catch (failure) {
      setError(failure.message)
    } finally {
      setStatus('')
    }
  }

  return (
    <main className="page">
      <header>
        <h1>Ovr<span>LP</span></h1>
        <p>Find songs that mix with a track you love.</p>
      </header>

      <form onSubmit={handleSearch} className="search">
        <fieldset disabled={Boolean(status)}>
          <label>
            Song title
            <input name="title" placeholder="e.g. One More Time" required />
          </label>
          <label>
            Artist
            <input name="artist" placeholder="e.g. Daft Punk" required />
          </label>
          <label>
            Match mode
            <select name="mode" defaultValue="2">
              <option value="1">Exact match</option>
              <option value="2">Spotify transitions</option>
              <option value="3">DJ / mashup</option>
            </select>
          </label>
          <button type="submit">Find matches</button>
        </fieldset>
      </form>

      <div role="status">
        {status && <p>{status}</p>}
        {results && (
          <p>
            {results.total_matches === 0
              ? 'No compatible songs found. Try another song or match mode.'
              : `Showing ${results.matches.length} of ${results.total_matches} compatible songs`}
          </p>
        )}
      </div>
      {error && <p className="error" role="alert">{error}</p>}

      {reference && (
        <section className="reference" aria-label="Reference song">
          <div>
            <h2>{reference.title}</h2>
            <p>{reference.artist}</p>
          </div>
          <div className="metadata">
            {reference.bpm == null ? 'BPM unavailable' : `${reference.bpm} BPM`}
            {' · '}
            {reference.key ?? 'Key unavailable'}
          </div>
        </section>
      )}

      {results?.matches.length > 0 && (
        <ul className="matches" aria-label="Compatible songs">
          {results.matches.map((song) => <MatchCard key={song.id} song={song} />)}
        </ul>
      )}

      <footer>Music metadata from <a href="https://getsongbpm.com">GetSongBPM</a>.</footer>
    </main>
  )
}

export default App
