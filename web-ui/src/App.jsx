import { useState, useEffect } from 'react'
import axios from 'axios'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || '/api'

const STEPS = [
  { id: 1, label: 'Downloading transcript', icon: '📝', duration: 3000 },
  { id: 2, label: 'Generating AI commentary', icon: '🤖', duration: 15000 },
  { id: 3, label: 'Converting to speech', icon: '🎙️', duration: 20000 },
  { id: 4, label: 'Downloading video', icon: '📥', duration: 15000 },
  { id: 5, label: 'Merging video & audio', icon: '🎬', duration: 30000 },
  { id: 6, label: 'Finalizing', icon: '✨', duration: 5000 },
]

function ProgressSteps({ currentStep, elapsedTime }) {
  return (
    <div className="progress-steps">
      {STEPS.map((step) => {
        const isComplete = step.id < currentStep
        const isCurrent = step.id === currentStep
        const isPending = step.id > currentStep
        
        return (
          <div 
            key={step.id} 
            className={`progress-step ${isComplete ? 'complete' : ''} ${isCurrent ? 'current' : ''} ${isPending ? 'pending' : ''}`}
          >
            <div className="step-icon">
              {isComplete ? '✅' : step.icon}
            </div>
            <div className="step-content">
              <span className="step-label">{step.label}</span>
              {isCurrent && (
                <div className="step-progress">
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ animation: `fillProgress ${step.duration}ms linear forwards` }}></div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )
      })}
      <div className="elapsed-time">
        ⏱️ Elapsed: {Math.floor(elapsedTime / 60)}:{(elapsedTime % 60).toString().padStart(2, '0')}
      </div>
    </div>
  )
}

function App() {
  const [inputType, setInputType] = useState('url')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [incidentId, setIncidentId] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  // Timer effect
  useEffect(() => {
    let interval
    if (loading) {
      interval = setInterval(() => {
        setElapsedTime(prev => prev + 1)
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [loading])

  // Step progression effect
  useEffect(() => {
    if (!loading) return
    
    let stepIndex = 0
    const advanceStep = () => {
      if (stepIndex < STEPS.length) {
        setCurrentStep(STEPS[stepIndex].id)
        stepIndex++
      }
    }
    
    // Advance through steps based on estimated timing
    advanceStep() // Start immediately
    
    const timers = STEPS.slice(0, -1).map((step, i) => {
      const delay = STEPS.slice(0, i + 1).reduce((sum, s) => sum + s.duration, 0)
      return setTimeout(advanceStep, delay)
    })
    
    return () => timers.forEach(t => clearTimeout(t))
  }, [loading])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setCurrentStep(1)
    setElapsedTime(0)
    setResult(null)

    try {
      const payload = inputType === 'url' 
        ? { youtube_url: youtubeUrl }
        : { incident_id: incidentId }

      const response = await axios.post(`${API_URL}/process`, payload)
      
      setCurrentStep(STEPS.length + 1) // Complete
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'An error occurred')
      setCurrentStep(0)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="logo-section">
          <h1>🎬 Islamophobia UK</h1>
          <p className="subtitle">Video Commentary Pipeline</p>
        </div>
        <div className="social">
          <a href="https://islamophobiauk.co.uk" target="_blank">Website</a>
          <a href="https://youtube.com/@IslamophobiaUK" target="_blank">@IslamophobiaUK</a>
        </div>
      </header>

      <main className="main">
        <div className="card">
          <h2>Process Video</h2>
          
          <div className="input-type-selector">
            <button 
              className={inputType === 'url' ? 'active' : ''}
              onClick={() => setInputType('url')}
              disabled={loading}
            >
              YouTube URL
            </button>
            <button 
              className={inputType === 'id' ? 'active' : ''}
              onClick={() => setInputType('id')}
              disabled={loading}
            >
              Incident ID
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            {inputType === 'url' ? (
              <div className="form-group">
                <label>YouTube URL</label>
                <input
                  type="text"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="https://youtube.com/watch?v=..."
                  required
                  disabled={loading}
                />
                <small>Supports: youtube.com/watch, youtu.be, youtube.com/shorts</small>
              </div>
            ) : (
              <div className="form-group">
                <label>Incident ID</label>
                <input
                  type="text"
                  value={incidentId}
                  onChange={(e) => setIncidentId(e.target.value)}
                  placeholder="cd0cdc60-9db6-4f1b-89f5-570605a86f4a"
                  required
                  disabled={loading}
                />
                <small>UUID from your database</small>
              </div>
            )}

            <button type="submit" disabled={loading} className="submit-btn">
              {loading ? '⏳ Processing...' : '🚀 Process Video'}
            </button>
          </form>

          {loading && (
            <ProgressSteps currentStep={currentStep} elapsedTime={elapsedTime} />
          )}

          {error && (
            <div className="error-box">
              <p>❌ {error}</p>
            </div>
          )}

          {result && !result.jobs && (
            <div className="result-box">
              <h3>✅ Video Processed Successfully!</h3>
              <p className="completion-time">Completed in {Math.floor(elapsedTime / 60)}:{(elapsedTime % 60).toString().padStart(2, '0')}</p>
              
              <div className="result-section">
                <h4>📹 Video ID</h4>
                <p><code>{result.video_id}</code></p>
              </div>

              {result.metadata && (
                <>
                  <div className="result-section">
                    <h4>📝 YouTube Title</h4>
                    <p>{result.metadata.title}</p>
                    <button onClick={() => navigator.clipboard.writeText(result.metadata.title)}>
                      Copy
                    </button>
                  </div>

                  <div className="result-section">
                    <h4>📄 YouTube Description</h4>
                    <textarea 
                      readOnly 
                      value={result.metadata.description}
                      rows={8}
                    />
                    <button onClick={() => navigator.clipboard.writeText(result.metadata.description)}>
                      Copy
                    </button>
                  </div>

                  <div className="result-section">
                    <h4>🏷️ Tags</h4>
                    <div className="tags">
                      {result.metadata.tags.map((tag, i) => (
                        <span key={i} className="tag">{tag}</span>
                      ))}
                    </div>
                    <button onClick={() => navigator.clipboard.writeText(result.metadata.tags.join(', '))}>
                      Copy All
                    </button>
                  </div>
                </>
              )}

              {result.files && (
                <div className="result-section">
                  <h4>📁 Generated Files</h4>
                  <ul>
                    {result.files.transcript && <li>✅ Transcript</li>}
                    {result.files.script && <li>✅ Commentary Script</li>}
                    {result.files.audio && <li>✅ Audio Commentary</li>}
                    {result.files.video && <li>✅ Original Video</li>}
                    {result.files.final_video && <li>✅ Final Commentary Video</li>}
                  </ul>
                </div>
              )}

              {result.download_url && (
                <a 
                  href={`${API_URL}${result.download_url}`} 
                  className="download-btn"
                  target="_blank"
                >
                  ⬇️ Download Final Video
                </a>
              )}
            </div>
          )}
        </div>

        <div className="info-card">
          <h3>ℹ️ How It Works</h3>
          <ol>
            <li>Enter a YouTube URL or incident ID</li>
            <li>AI downloads transcript and generates commentary</li>
            <li>Text-to-speech creates voice narration</li>
            <li>Video is downloaded and processed</li>
            <li>Split-screen layout with branding added</li>
            <li>YouTube metadata (title, description, tags) generated</li>
            <li>Final video ready to upload!</li>
          </ol>

          <div className="features">
            <h4>✨ Features</h4>
            <ul>
              <li>Automated AI commentary generation</li>
              <li>Professional voice narration</li>
              <li>Split-screen layout with branding</li>
              <li>SEO-optimized YouTube metadata</li>
              <li>Supports YouTube Shorts</li>
              <li>Batch processing available</li>
            </ul>
          </div>
        </div>
      </main>

      <footer className="footer">
        <p>© 2024 Islamophobia UK | Educational Commentary Platform</p>
        <p>
          <a href="https://islamophobiauk.co.uk">islamophobiauk.co.uk</a> | 
          <a href="https://youtube.com/@IslamophobiaUK">@IslamophobiaUK</a>
        </p>
      </footer>
    </div>
  )
}

export default App