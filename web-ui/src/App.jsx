import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || '/api'

const STEP1_STAGES = [
  { id: 1, label: 'Uploading image', icon: '📤', duration: 2000 },
  { id: 2, label: 'Generating video with Kling AI', icon: '🎬', duration: 180000 },
]

const STEP2_STAGES = [
  { id: 1, label: 'Converting script to speech', icon: '🎙️', duration: 30000 },
  { id: 2, label: 'Merging video & audio', icon: '🔀', duration: 15000 },
  { id: 3, label: 'Generating metadata', icon: '📝', duration: 5000 },
  { id: 4, label: 'Finalizing', icon: '✨', duration: 3000 },
]

const VOICES = [
  // Documentary / Narrator voices (recommended for Attenborough-style)
  { id: 'george', name: 'George', description: 'British, warm - Nature documentaries', recommended: true },
  { id: 'daniel', name: 'Daniel', description: 'British, authoritative - Factual content', recommended: true },
  { id: 'bill', name: 'Bill', description: 'Older male, trustworthy - Classic narrator', recommended: true },
  { id: 'clyde', name: 'Clyde', description: 'War veteran - Deep, gravelly' },
  // Additional voices
  { id: 'adam', name: 'Adam', description: 'Deep narrative - American male' },
  { id: 'antoni', name: 'Antoni', description: 'Well-rounded - Young male' },
  { id: 'drew', name: 'Drew', description: 'News reader - Middle-aged male' },
  { id: 'rachel', name: 'Rachel', description: 'Calm - Young female' },
]

function ProgressSteps({ stages, currentStep, elapsedTime }) {
  return (
    <div className="progress-steps">
      {stages.map((step) => {
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
  // Workflow state: 'input' | 'generating_video' | 'preview' | 'adding_commentary' | 'complete'
  const [workflowStep, setWorkflowStep] = useState('input')
  
  // Form inputs
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [script, setScript] = useState('')
  const [motionPrompt, setMotionPrompt] = useState('')
  const [voice, setVoice] = useState('george')
  const [duration, setDuration] = useState(10)
  
  // Job state
  const [jobId, setJobId] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  
  // UI state
  const [loading, setLoading] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  
  const fileInputRef = useRef(null)
  const videoRef = useRef(null)

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

  // Step progression effect for video generation
  useEffect(() => {
    if (workflowStep !== 'generating_video' || !loading) return
    
    let stepIndex = 0
    const stages = STEP1_STAGES
    const advanceStep = () => {
      if (stepIndex < stages.length) {
        setCurrentStep(stages[stepIndex].id)
        stepIndex++
      }
    }
    
    advanceStep()
    
    const timers = stages.slice(0, -1).map((step, i) => {
      const delay = stages.slice(0, i + 1).reduce((sum, s) => sum + s.duration, 0)
      return setTimeout(advanceStep, delay)
    })
    
    return () => timers.forEach(t => clearTimeout(t))
  }, [workflowStep, loading])

  // Step progression effect for commentary
  useEffect(() => {
    if (workflowStep !== 'adding_commentary' || !loading) return
    
    let stepIndex = 0
    const stages = STEP2_STAGES
    const advanceStep = () => {
      if (stepIndex < stages.length) {
        setCurrentStep(stages[stepIndex].id)
        stepIndex++
      }
    }
    
    advanceStep()
    
    const timers = stages.slice(0, -1).map((step, i) => {
      const delay = stages.slice(0, i + 1).reduce((sum, s) => sum + s.duration, 0)
      return setTimeout(advanceStep, delay)
    })
    
    return () => timers.forEach(t => clearTimeout(t))
  }, [workflowStep, loading])

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

  // STEP 1: Generate video preview
  const handleGenerateVideo = async (e) => {
    e.preventDefault()
    
    if (!image) {
      setError('Please select an image')
      return
    }
    if (!motionPrompt.trim()) {
      setError('Please enter a motion prompt describing what happens in the video')
      return
    }
    
    setWorkflowStep('generating_video')
    setLoading(true)
    setError('')
    setCurrentStep(1)
    setElapsedTime(0)
    setResult(null)
    setJobId(null)
    setPreviewUrl(null)

    try {
      const formData = new FormData()
      formData.append('image', image)
      formData.append('motion_prompt', motionPrompt)
      formData.append('duration', duration)

      const response = await axios.post(`${API_URL}/generate-video`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 600000, // 10 minute timeout
      })
      
      setJobId(response.data.job_id)
      setPreviewUrl(`${API_URL.replace('/api', '')}${response.data.preview_url}`)
      setWorkflowStep('preview')
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'An error occurred')
      setWorkflowStep('input')
    } finally {
      setLoading(false)
    }
  }

  // STEP 2: Add commentary
  const handleAddCommentary = async () => {
    if (!script.trim()) {
      setError('Please enter a commentary script')
      return
    }
    
    setWorkflowStep('adding_commentary')
    setLoading(true)
    setError('')
    setCurrentStep(1)
    setElapsedTime(0)

    try {
      const response = await axios.post(`${API_URL}/add-commentary`, {
        job_id: jobId,
        script: script,
        voice: voice
      }, {
        timeout: 300000, // 5 minute timeout
      })
      
      setResult(response.data)
      setWorkflowStep('complete')
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'An error occurred')
      setWorkflowStep('preview') // Go back to preview on error
    } finally {
      setLoading(false)
    }
  }

  // Regenerate video with different motion prompt
  const handleRegenerateVideo = () => {
    setWorkflowStep('input')
    setPreviewUrl(null)
    setJobId(null)
  }

  const resetForm = () => {
    setWorkflowStep('input')
    setImage(null)
    setImagePreview(null)
    setScript('')
    setMotionPrompt('')
    setResult(null)
    setError('')
    setJobId(null)
    setPreviewUrl(null)
  }

  return (
    <div className="app">
      <header className="header">
        <div className="logo-section">
          <h1>🎬 AI Video Generator</h1>
          <p className="subtitle">Image + Script → YouTube Video</p>
        </div>
        <div className="powered-by">
          Powered by <span>Kling AI</span> & <span>OpenAI</span>
        </div>
      </header>

      <main className="main">
        <div className="card">
          {/* Workflow Progress Indicator */}
          <div className="workflow-indicator">
            <div className={`workflow-step ${workflowStep === 'input' || workflowStep === 'generating_video' ? 'active' : ''} ${workflowStep === 'preview' || workflowStep === 'adding_commentary' || workflowStep === 'complete' ? 'complete' : ''}`}>
              <span className="workflow-number">1</span>
              <span className="workflow-label">Generate Video</span>
            </div>
            <div className="workflow-connector"></div>
            <div className={`workflow-step ${workflowStep === 'preview' ? 'active' : ''} ${workflowStep === 'adding_commentary' || workflowStep === 'complete' ? 'complete' : ''}`}>
              <span className="workflow-number">2</span>
              <span className="workflow-label">Preview & Approve</span>
            </div>
            <div className="workflow-connector"></div>
            <div className={`workflow-step ${workflowStep === 'adding_commentary' ? 'active' : ''} ${workflowStep === 'complete' ? 'complete' : ''}`}>
              <span className="workflow-number">3</span>
              <span className="workflow-label">Add Commentary</span>
            </div>
          </div>

          {/* STEP 1: Input Form */}
          {(workflowStep === 'input' || workflowStep === 'generating_video') && (
            <>
              <h2>Step 1: Generate Video</h2>
              
              <form onSubmit={handleGenerateVideo}>
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

                {/* Motion Prompt (Required) */}
                <div className="form-group">
                  <label>Motion Prompt <span className="required">*</span></label>
                  <textarea
                    value={motionPrompt}
                    onChange={(e) => setMotionPrompt(e.target.value)}
                    placeholder="Describe what happens in the video...

Example: 'Dinosaur running into a dark cave, looking scared, dust particles in the air'"
                    rows={3}
                    disabled={loading}
                    required
                  />
                  <small>Describe the action/motion you want to see in the video</small>
                </div>

                {/* Duration */}
                <div className="form-group">
                  <label>Video Duration</label>
                  <select value={duration} onChange={(e) => setDuration(Number(e.target.value))} disabled={loading}>
                    <option value={5}>5 seconds</option>
                    <option value={10}>10 seconds</option>
                  </select>
                  <small>Kling AI video length</small>
                </div>

                <button type="submit" disabled={loading || !image || !motionPrompt.trim()} className="submit-btn">
                  {loading ? '⏳ Generating Video...' : '🎬 Generate Video Preview'}
                </button>
              </form>

              {loading && workflowStep === 'generating_video' && (
                <ProgressSteps stages={STEP1_STAGES} currentStep={currentStep} elapsedTime={elapsedTime} />
              )}
            </>
          )}

          {/* STEP 2: Preview & Approve */}
          {workflowStep === 'preview' && (
            <>
              <h2>Step 2: Preview Video</h2>
              <p className="step-description">Review the generated video. If it looks good, add your commentary script.</p>
              
              <div className="preview-section">
                <div className="video-preview-container">
                  <video 
                    ref={videoRef}
                    src={previewUrl} 
                    controls 
                    autoPlay 
                    loop
                    className="video-preview"
                  >
                    Your browser does not support the video tag.
                  </video>
                </div>
                
                <div className="preview-info">
                  <p><strong>Job ID:</strong> <code>{jobId}</code></p>
                  <p><strong>Motion:</strong> {motionPrompt}</p>
                </div>

                <div className="preview-actions">
                  <button className="btn-secondary" onClick={handleRegenerateVideo}>
                    🔄 Regenerate Video
                  </button>
                </div>
              </div>

              <hr className="divider" />

              <h3>Add Commentary</h3>
              
              {/* Script Input */}
              <div className="form-group">
                <label>Commentary Script <span className="required">*</span></label>
                <textarea
                  value={script}
                  onChange={(e) => setScript(e.target.value)}
                  placeholder="Enter your video commentary script here...

Example: 'The dinosaur, sensing danger, makes a desperate dash for the cave. Its powerful legs kick up clouds of dust as it seeks shelter from the circling predator above.'"
                  rows={6}
                  disabled={loading}
                  required
                />
                <small>{script.length} characters • ~{Math.ceil(script.split(' ').filter(w => w).length / 150)} min audio</small>
              </div>

              {/* Voice Selection */}
              <div className="form-group">
                <label>Voice <span className="elevenlabs-badge">ElevenLabs</span></label>
                <select value={voice} onChange={(e) => setVoice(e.target.value)} disabled={loading}>
                  <optgroup label="🎬 Documentary Voices (Recommended)">
                    {VOICES.filter(v => v.recommended).map(v => (
                      <option key={v.id} value={v.id}>⭐ {v.name} - {v.description}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Additional Voices">
                    {VOICES.filter(v => !v.recommended).map(v => (
                      <option key={v.id} value={v.id}>{v.name} - {v.description}</option>
                    ))}
                  </optgroup>
                </select>
                <small>George is closest to Attenborough-style narration</small>
              </div>

              <button 
                onClick={handleAddCommentary} 
                disabled={loading || !script.trim()} 
                className="submit-btn"
              >
                🎙️ Add Commentary & Finalize
              </button>
            </>
          )}

          {/* Adding Commentary Progress */}
          {workflowStep === 'adding_commentary' && (
            <>
              <h2>Step 3: Adding Commentary</h2>
              <ProgressSteps stages={STEP2_STAGES} currentStep={currentStep} elapsedTime={elapsedTime} />
            </>
          )}

          {/* Error Display */}
          {error && (
            <div className="error-box">
              <p>❌ {error}</p>
            </div>
          )}

          {/* COMPLETE: Results */}
          {workflowStep === 'complete' && result && (
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
            <li><strong>Step 1:</strong> Upload image & describe the motion</li>
            <li>AI generates video preview using Kling AI</li>
            <li><strong>Step 2:</strong> Preview the video</li>
            <li>If not satisfied, regenerate with different prompt</li>
            <li><strong>Step 3:</strong> Add your commentary script</li>
            <li>Script is converted to natural speech</li>
            <li>Video and audio are merged together</li>
            <li>Download and upload to YouTube!</li>
          </ol>

          <div className="features">
            <h4>✨ Features</h4>
            <ul>
              <li>Preview video before adding audio</li>
              <li>Kling AI video generation</li>
              <li>6 professional voice options</li>
              <li>SEO-optimized YouTube metadata</li>
              <li>Video loops to match audio length</li>
              <li>1080p output quality</li>
            </ul>
          </div>

          <div className="tips">
            <h4>💡 Tips</h4>
            <ul>
              <li>Be specific with motion prompts</li>
              <li>Describe actions: "running", "flying", "turning"</li>
              <li>Include atmosphere: "dust", "fog", "sunlight"</li>
              <li>Preview before adding commentary</li>
            </ul>
          </div>
        </div>
      </main>

      <footer className="footer">
        <p>AI Video Generator • Powered by Kling AI & OpenAI</p>
      </footer>
    </div>
  )
}

export default App