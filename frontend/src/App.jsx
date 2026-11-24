import { useState } from 'react'
import './App.css'

const modes = [
  ['1', 'Exact Match', 'Same BPM and key'],
  ['2', 'Tempo Match', 'Within 10 BPM, compatible key'],
  ['3', 'DJ / Mashup', 'Tempo and pitch adjustments'],
]

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

function Artwork({ variant = 0 }) {
  return <div className={`artwork artwork-${variant % 5}`} aria-hidden="true" />
}

function TrackMetadata({ bpm, musicalKey }) {
  return (
    <div className="metadata">
      <span>{bpm == null ? 'BPM unavailable' : `${bpm} BPM`}</span>
      <span className="key-badge">{musicalKey ?? 'Key unavailable'}</span>
    </div>
  )
}

function MatchCard({ song, index }) {
  const tempoAdjustment = Math.abs(song.adjustment).toFixed(1)
  const pitchSign = song.semitones > 0 ? '+' : ''

  return (
    <li className="match-card">
      <Artwork variant={index} />
      <h3>{song.title}</h3>
      <p className="artist">{song.artist}</p>
      <TrackMetadata bpm={song.bpm} musicalKey={song.key} />
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
    <div className="layout">
      <aside className="sidebar">
        <a className="wordmark" href="./" aria-label="OvrLP home">ovrlp<span>.</span></a>
        <nav aria-label="Main navigation">
          <a className="active-link" href="#discover" aria-current="page">Discover</a>
          <a href="https://github.com/crazy44spider/ovrlp">GitHub</a>
        </nav>
      </aside>
      <main className="page" id="discover">
        <header className="intro">
          <h1>Find what <span>fits.</span></h1>
          <p>Start with a song. Find tracks that flow with it.</p>
        </header>

        <form onSubmit={handleSearch} className="search">
          <fieldset className="search-inputs" disabled={Boolean(status)}>
            <label>
              Song title
              <input name="title" placeholder="e.g. One More Time" required />
            </label>
            <label>
              Artist
              <input name="artist" placeholder="e.g. Daft Punk" required />
            </label>
            <button type="submit" className="discover-button">Discover</button>
          </fieldset>
          <fieldset className="mode-picker" disabled={Boolean(status)}>
            <legend>Matching mode</legend>
            <div className="mode-options">
              {modes.map(([value, label, description]) => (
                <label className="mode-option" key={value} title={description}>
                  <input type="radio" name="mode" value={value} defaultChecked={value === '2'} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </form>

        <div className="status" role="status">
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
            <Artwork />
            <div className="reference-title">
              <p className="reference-label">Reference track</p>
              <h2>{reference.title}</h2>
              <p>{reference.artist}</p>
            </div>
            <TrackMetadata bpm={reference.bpm} musicalKey={reference.key} />
          </section>
        )}

        {results?.matches.length > 0 && (
          <section className="recommendations" aria-labelledby="recommendations-heading">
            <h2 id="recommendations-heading">Recommended Tracks</h2>
            <ul className="matches">
              {results.matches.map((song, index) => (
                <MatchCard key={song.id} song={song} index={index} />
              ))}
            </ul>
          </section>
        )}

        <footer>Music metadata from <a href="https://getsongbpm.com">GetSongBPM</a>.</footer>
      </main>
    </div>
  )
}

export default App
