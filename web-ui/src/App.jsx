import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || '/api'

const STEPS = [
  { id: 1, label: 'Uploading image', icon: '📤', duration: 2000 },
  { id: 2, label: 'Generating video with Runway AI', icon: '🎬', duration: 120000 },
  { id: 3, label: 'Converting script to speech', icon: '🎙️', duration: 30000 },
  { id: 4, label: 'Merging video & audio', icon: '🔀', duration: 15000 },
  { id: 5, label: 'Generating metadata', icon: '📝', duration: 5000 },
  { id: 6, label: 'Finalizing', icon: '✨', duration: 3000 },
]

const VOICES = [
  { id: 'onyx', name: 'Onyx', description: 'Deep, authoritative' },
  { id: 'nova', name: 'Nova', description: 'Friendly, upbeat' },
  { id: 'alloy', name: 'Alloy', description: 'Neutral, balanced' },
  { id: 'echo', name: 'Echo', description: 'Warm, conversational' },
  { id: 'fable', name: 'Fable', description: 'Expressive, dramatic' },
  { id: 'shimmer', name: 'Shimmer', description: 'Clear, professional' },
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
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [script, setScript] = useState('')
  const [motionPrompt, setMotionPrompt] = useState('')
  const [voice, setVoice] = useState('onyx')
  const [duration, setDuration] = useState(10)
  const [loading, setLoading] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  
  const fileInputRef = useRef(null)

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
    
    advanceStep()
    
    const timers = STEPS.slice(0, -1).map((step, i) => {
      const delay = STEPS.slice(0, i + 1).reduce((sum, s) => sum + s.duration, 0)
      return setTimeout(advanceStep, delay)
    })
    
    return () => timers.forEach(t => clearTimeout(t))
  }, [loading])

  const handleImageChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      setImage(file)
      const reader = new FileReader()
      reader.onloadend = () => {
        setImagePreview(reader.result)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('image/')) {
      setImage(file)
      const reader = new FileReader()
      reader.onloadend = () => {
        setImagePreview(reader.result)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!image) {
      setError('Please select an image')
      return
    }
    if (!script.trim()) {
      setError('Please enter a script')
      return
    }
    
    setLoading(true)
    setError('')
    setCurrentStep(1)
    setElapsedTime(0)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('image', image)
      formData.append('script', script)
      formData.append('voice', voice)
      formData.append('duration', duration)
      if (motionPrompt) {
        formData.append('motion_prompt', motionPrompt)
      }

      const response = await axios.post(`${API_URL}/generate`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 600000, // 10 minute timeout
      })
      
      setCurrentStep(STEPS.length + 1)
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'An error occurred')
      setCurrentStep(0)
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setImage(null)
    setImagePreview(null)
    setScript('')
    setMotionPrompt('')
    setResult(null)
    setError('')
  }

  return (
    <div className="app">
      <header className="header">
        <div className="logo-section">
          <h1>🎬 AI Video Generator</h1>
          <p className="subtitle">Image + Script → YouTube Video</p>
        </div>
        <div className="powered-by">
          Powered by <span>Runway Gen-4</span> & <span>OpenAI</span>
        </div>
      </header>

      <main className="main">
        <div className="card">
          <h2>Generate Video</h2>
          
          <form onSubmit={handleSubmit}>
            {/* Image Upload */}
            <div className="form-group">
              <label>Source Image</label>
              <div 
                className={`dropzone ${imagePreview ? 'has-image' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
              >
                {imagePreview ? (
                  <img src={imagePreview} alt="Preview" className="image-preview" />
                ) : (
                  <div className="dropzone-content">
                    <span className="dropzone-icon">📷</span>
                    <p>Click or drag image here</p>
                    <small>PNG, JPG, WEBP supported</small>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                  disabled={loading}
                  style={{ display: 'none' }}
                />
              </div>
              {imagePreview && (
                <button type="button" className="clear-btn" onClick={() => { setImage(null); setImagePreview(null) }}>
                  ✕ Clear image
                </button>
              )}
            </div>

            {/* Script Input */}
            <div className="form-group">
              <label>Commentary Script</label>
              <textarea
                value={script}
                onChange={(e) => setScript(e.target.value)}
                placeholder="Enter your video commentary script here...

This will be converted to speech and overlaid on the generated video."
                rows={6}
                disabled={loading}
                required
              />
              <small>{script.length} characters • ~{Math.ceil(script.split(' ').filter(w => w).length / 150)} min audio</small>
            </div>

            {/* Motion Prompt (Optional) */}
            <div className="form-group">
              <label>Motion Prompt <span className="optional">(optional)</span></label>
              <input
                type="text"
                value={motionPrompt}
                onChange={(e) => setMotionPrompt(e.target.value)}
                placeholder="e.g., Slow zoom in with gentle camera movement"
                disabled={loading}
              />
              <small>Describe how the image should animate. Leave blank to auto-generate.</small>
            </div>

            {/* Voice & Duration */}
            <div className="form-row">
              <div className="form-group half">
                <label>Voice</label>
                <select value={voice} onChange={(e) => setVoice(e.target.value)} disabled={loading}>
                  {VOICES.map(v => (
                    <option key={v.id} value={v.id}>{v.name} - {v.description}</option>
                  ))}
                </select>
              </div>
              
              <div className="form-group half">
                <label>Video Duration</label>
                <select value={duration} onChange={(e) => setDuration(Number(e.target.value))} disabled={loading}>
                  <option value={5}>5 seconds</option>
                  <option value={10}>10 seconds</option>
                </select>
                <small>Runway video length (audio extends)</small>
              </div>
            </div>

            <button type="submit" disabled={loading || !image || !script.trim()} className="submit-btn">
              {loading ? '⏳ Generating...' : '🚀 Generate Video'}
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

          {result && (
            <div className="result-box">
              <h3>✅ Video Generated Successfully!</h3>
              <p className="completion-time">Completed in {Math.floor(elapsedTime / 60)}:{(elapsedTime % 60).toString().padStart(2, '0')}</p>
              
              <div className="result-section">
                <h4>📹 Job ID</h4>
                <p><code>{result.job_id}</code></p>
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
                      rows={4}
                    />
                    <button onClick={() => navigator.clipboard.writeText(result.metadata.description)}>
                      Copy
                    </button>
                  </div>

                  <div className="result-section">
                    <h4>🏷️ Tags</h4>
                    <div className="tags">
                      {result.metadata.tags?.map((tag, i) => (
                        <span key={i} className="tag">{tag}</span>
                      ))}
                    </div>
                    <button onClick={() => navigator.clipboard.writeText(result.metadata.tags?.join(', ') || '')}>
                      Copy All
                    </button>
                  </div>
                </>
              )}

              <div className="download-section">
                <a 
                  href={`${API_URL.replace('/api', '')}${result.download_url}`}
                  className="download-btn"
                  target="_blank"
                >
                  ⬇️ Download Video
                </a>
                <a 
                  href={`${API_URL.replace('/api', '')}${result.download_url}/audio`}
                  className="download-btn secondary"
                  target="_blank"
                >
                  🎙️ Download Audio
                </a>
              </div>

              <button className="reset-btn" onClick={resetForm}>
                🔄 Create Another Video
              </button>
            </div>
          )}
        </div>

        <div className="info-card">
          <h3>ℹ️ How It Works</h3>
          <ol>
            <li>Upload a source image (photo, illustration, etc.)</li>
            <li>Write your commentary script</li>
            <li>AI generates video from image using Runway</li>
            <li>Script is converted to natural speech</li>
            <li>Video and audio are merged together</li>
            <li>YouTube metadata is auto-generated</li>
            <li>Download and upload to YouTube!</li>
          </ol>

          <div className="features">
            <h4>✨ Features</h4>
            <ul>
              <li>Runway Gen-4 Turbo video generation</li>
              <li>6 professional voice options</li>
              <li>Auto-generated motion prompts</li>
              <li>SEO-optimized YouTube metadata</li>
              <li>Video loops to match audio length</li>
              <li>1080p output quality</li>
            </ul>
          </div>

          <div className="tips">
            <h4>💡 Tips</h4>
            <ul>
              <li>Use high-quality images for best results</li>
              <li>Keep scripts concise for short videos</li>
              <li>Motion prompts work best with action words</li>
              <li>Onyx voice is great for serious topics</li>
            </ul>
          </div>
        </div>
      </main>

      <footer className="footer">
        <p>AI Video Generator • Powered by Runway & OpenAI</p>
      </footer>
    </div>
  )
}

export default App
