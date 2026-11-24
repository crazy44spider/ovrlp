import { useEffect, useState } from 'react'
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
    const error = new Error(
      typeof data?.detail === 'string'
        ? data.detail
        : 'Could not get a response from OvrLP. Check that the backend is running.',
    )
    error.status = response.status
    error.retryAfter = response.status === 503 ? response.headers.get('Retry-After') : null
    throw error
  }

  return data
}

function retryDelay(header) {
  if (!header) return 0
  const value = header.trim()
  const delay = /^\d+$/.test(value) ? Number(value) * 1000 : Date.parse(value) - Date.now()
  return Number.isFinite(delay) ? Math.max(0, delay) : 0
}

function discoveryParams(song, mode) {
  const params = { bpm: song.bpm, key: song.key, mode }
  if (song.id != null) params.reference_id = song.id
  return params
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
  const [mode, setMode] = useState('2')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [reference, setReference] = useState(null)
  const [manualTrack, setManualTrack] = useState(null)
  const [results, setResults] = useState(null)
  const [retryParams, setRetryParams] = useState(null)
  const [retryAt, setRetryAt] = useState(null)

  useEffect(() => {
    if (retryAt === null) return

    function finishCooldown() {
      if (Date.now() >= retryAt) setRetryAt(null)
    }

    const timer = window.setInterval(finishCooldown, 1000)
    return () => window.clearInterval(timer)
  }, [retryAt])

  function showFailure(stage, failure) {
    setError(`${stage}: ${failure.message}`)
    const delay = retryDelay(failure.retryAfter)
    if (delay > 0) setRetryAt(Date.now() + delay)
  }

  async function runDiscovery(params) {
    setError('')
    setStatus('Finding compatible songs…')
    setRetryParams(null)
    setResults(null)
    try {
      setResults(await getApi('discover', params))
    } catch (failure) {
      showFailure('Discovery failed', failure)
      if (failure.status !== 422) setRetryParams(params)
    } finally {
      setStatus('')
    }
  }

  async function handleSearch(event) {
    event.preventDefault()
    if (status || retryAt !== null) return
    const fields = new FormData(event.currentTarget)
    const title = fields.get('title').trim()
    const artist = fields.get('artist').trim()
    setError('')
    setRetryParams(null)
    setReference(null)
    setManualTrack(null)
    setResults(null)

    if (!title || !artist) {
      setError('Enter both a song title and an artist.')
      return
    }

    let song
    setStatus('Looking up your song…')
    try {
      song = await getApi('lookup', { title, artist })
    } catch (failure) {
      if (failure.status === 404) setManualTrack({ title, artist })
      showFailure('Song lookup failed', failure)
      setStatus('')
      return
    }

    setReference(song)
    if (song.bpm == null || song.key == null) {
      setManualTrack(song)
      setError('This song is missing BPM or key information.')
      setStatus('')
      return
    }

    await runDiscovery(discoveryParams(song, mode))
  }

  async function handleManualSearch(event) {
    event.preventDefault()
    if (status || retryAt !== null) return
    const fields = new FormData(event.currentTarget)
    const bpm = Number(fields.get('bpm'))
    const key = fields.get('key').trim()
    if (!Number.isFinite(bpm) || bpm < 1 || bpm > 300 || !key) {
      setError('Enter a BPM between 1 and 300 and a musical key.')
      return
    }

    const song = { ...manualTrack, bpm, key }
    setReference(song)
    await runDiscovery(discoveryParams(song, mode))
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
            <button type="submit" className="discover-button" disabled={retryAt !== null}>Discover</button>
          </fieldset>
          <fieldset className="mode-picker" disabled={Boolean(status)}>
            <legend>Matching mode</legend>
            <div className="mode-options">
              {modes.map(([value, label, description]) => (
                <label className="mode-option" key={value} title={description}>
                  <input type="radio" name="mode" value={value} checked={mode === value} onChange={() => setMode(value)} />
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
        {retryAt !== null && (
          <p className="status" role="status">
            Try again after {new Date(retryAt).toLocaleTimeString()}.
          </p>
        )}
        {retryParams && (
          <button
            type="button"
            className="discover-button retry-button"
            disabled={retryAt !== null}
            onClick={() => runDiscovery(retryParams)}
          >
            Retry discovery
          </button>
        )}

        {manualTrack && (
          <form className="manual-search" onSubmit={handleManualSearch}>
            <fieldset className="search-inputs" disabled={Boolean(status)}>
              <legend>Enter BPM and key manually</legend>
              <label>
                BPM
                <input name="bpm" type="number" min="1" max="300" step="any" defaultValue={manualTrack.bpm ?? ''} required />
              </label>
              <label>
                Musical key
                <input name="key" placeholder="e.g. Am or Bb" defaultValue={manualTrack.key ?? ''} required />
              </label>
              <button type="submit" className="discover-button" disabled={retryAt !== null}>Find matches</button>
            </fieldset>
          </form>
        )}

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
