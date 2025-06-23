"use client"

import { useState, useEffect } from "react"
import "./App.css"
import SummaryReport from "./components/SummaryReport"
import FactCheckReport from "./components/FactCheckReport"

function App() {
  const [url, setUrl] = useState("")
  const [taskId, setTaskId] = useState(null)
  const [status, setStatus] = useState("IDLE") // IDLE, PENDING, SUCCESS, FAILURE
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const API_BASE_URL = "http://127.0.0.1:8000"

  // Polling effect for task status
  useEffect(() => {
    if (status !== "PENDING" || !taskId) {
      return
    }

    console.log("🔄 Polling for task:", taskId) // DEBUG LOG

    const intervalId = setInterval(async () => {
      try {
        console.log("📡 Checking status for task:", taskId) // DEBUG LOG
        const response = await fetch(`${API_BASE_URL}/status/${taskId}`)
        if (!response.ok) {
          throw new Error("Network response was not ok")
        }
        const data = await response.json()
        console.log("📊 Status response:", data) // DEBUG LOG

        if (data.status === "SUCCESS") {
          setStatus("SUCCESS")
          setResult(data.result)
          clearInterval(intervalId)
          console.log("✅ Analysis complete!", data.result) // DEBUG LOG
        } else if (data.status === "FAILURE") {
          setStatus("FAILURE")
          setError(data.result?.error || "An unknown error occurred.")
          clearInterval(intervalId)
          console.log("❌ Analysis failed:", data.result?.error) // DEBUG LOG
        }
      } catch (err) {
        console.error("🚨 Polling error:", err) // DEBUG LOG
        setStatus("FAILURE")
        setError("Failed to fetch task status.")
        clearInterval(intervalId)
      }
    }, 5000) // Poll every 5 seconds

    return () => clearInterval(intervalId)
  }, [status, taskId])

  const handleSubmit = async (e) => {
    e.preventDefault()
    console.log("🚀 Form submitted with URL:", url) // DEBUG LOG

    if (!url.trim()) {
      setError("Please enter a valid YouTube URL.")
      console.log("❌ Empty URL") // DEBUG LOG
      return
    }

    // Validate URL format
    if (!url.includes("youtube.com/watch?v=") && !url.includes("youtu.be/")) {
      setError("Please enter a valid YouTube URL")
      console.log("❌ Invalid URL format") // DEBUG LOG
      return
    }

    console.log("📤 Sending request to backend...") // DEBUG LOG
    setStatus("PENDING")
    setTaskId(null)
    setResult(null)
    setError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      })

      console.log("📡 Backend response status:", response.status) // DEBUG LOG

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      console.log("📊 Backend response data:", data) // DEBUG LOG
      setTaskId(data.task_id)
    } catch (err) {
      console.error("🚨 Submit error:", err) // DEBUG LOG
      setStatus("FAILURE")
      setError(err instanceof Error ? err.message : "An unexpected error occurred")
    }
  }

  const handleReset = () => {
    console.log("🔄 Resetting form") // DEBUG LOG
    setUrl("")
    setTaskId(null)
    setStatus("IDLE")
    setResult(null)
    setError(null)
  }

  return (
    <div className="App">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-background">
          <div className="floating-shapes">
            <div className="shape shape-1"></div>
            <div className="shape shape-2"></div>
            <div className="shape shape-3"></div>
            <div className="shape shape-4"></div>
          </div>
        </div>

        <div className="hero-content">
          <div className="hero-badge">
            <span className="badge-icon">🚀</span>
            <span>Powered by AI Agents</span>
          </div>

          <h1 className="hero-title">
            <span className="title-icon">🤖</span>
            YouTube Summarizer And Fact-checker
            <span className="title-accent">Pro</span>
          </h1>

          <p className="hero-subtitle">
            Transform any YouTube video into comprehensive insights with our cutting-edge AI analysis engine. Get
            detailed summaries, chapter breakdowns, and thorough fact-checking in seconds.
          </p>

          <div className="hero-features">
            <div className="feature-item">
              <span className="feature-icon">📝</span>
              <span>Smart Summaries</span>
            </div>
            <div className="feature-item">
              <span className="feature-icon">🔍</span>
              <span>Fact Verification</span>
            </div>
            <div className="feature-item">
              <span className="feature-icon">⏱️</span>
              <span>Chapter Analysis</span>
            </div>
            <div className="feature-item">
              <span className="feature-icon">📊</span>
              <span>Credibility Scoring</span>
            </div>
          </div>
        </div>
      </section>

      <main className="main-content">
        {(status === "IDLE" || status === "FAILURE") && (
          <>
            {/* Analysis Form Section */}
            <section className="analysis-section">
              <div className="section-header">
                <h2 className="section-title">
                  <span className="section-icon">🎯</span>
                  Start Your Analysis
                </h2>
                <p className="section-description">
                  Simply paste any YouTube URL below and let our AI do the heavy lifting. Our advanced algorithms will
                  extract key insights, verify claims, and provide you with a comprehensive analysis report.
                </p>
              </div>

              <div className="form-container enhanced-form">
                {error && (
                  <div className="error-alert">
                    <span className="error-icon">⚠️</span>
                    <div className="error-content">
                      <h4>Analysis Error</h4>
                      <p>{error}</p>
                    </div>
                  </div>
                )}

                <form onSubmit={handleSubmit} className="url-form">
                  <div className="input-group">
                    <label htmlFor="url" className="input-label">
                      <span className="label-icon">🔗</span>
                      YouTube Video URL
                    </label>
                    <div className="input-wrapper">
                      <input
                        id="url"
                        type="text"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                        disabled={status === "PENDING"}
                        required
                        className="url-input"
                      />
                      <div className="input-decoration"></div>
                    </div>
                  </div>

                  <button type="submit" className="submit-button enhanced-button" disabled={status === "PENDING"}>
                    <span className="button-icon">🔍</span>
                    <span className="button-text">Analyze Content</span>
                    <div className="button-shine"></div>
                  </button>
                </form>

                <div className="form-footer">
                  <div className="security-badge">
                    <span className="security-icon">🔒</span>
                    <span>Secure & Private Analysis</span>
                  </div>
                  <div className="processing-info">
                    <span className="info-icon">⚡</span>
                    <span>Average processing time: 2-5 minutes</span>
                  </div>
                </div>
              </div>
            </section>

            {/* Features Section */}
            <section className="features-section">
              <div className="section-header">
                <h2 className="section-title">
                  <span className="section-icon">✨</span>
                  Powerful Analysis Features
                </h2>
                <p className="section-description">
                  Our AI-powered platform provides comprehensive video analysis with multiple layers of insight
                </p>
              </div>

              <div className="features-grid">
                <div className="feature-card">
                  <div className="feature-header">
                    <div className="feature-icon-large">📝</div>
                    <h3>Intelligent Summaries</h3>
                  </div>
                  <p>
                    Get concise, well-structured summaries that capture the essence of any video content. Our AI
                    identifies key points, main arguments, and important details.
                  </p>
                  <ul className="feature-list">
                    <li>✓ Overall content summary</li>
                    <li>✓ Chapter-by-chapter breakdown</li>
                    <li>✓ Key insights extraction</li>
                    <li>✓ Timestamped highlights</li>
                  </ul>
                </div>

                <div className="feature-card">
                  <div className="feature-header">
                    <div className="feature-icon-large">🔍</div>
                    <h3>Advanced Fact-Checking</h3>
                  </div>
                  <p>
                    Verify claims and statements with our sophisticated fact-checking engine. Get detailed analysis of
                    content credibility and accuracy.
                  </p>
                  <ul className="feature-list">
                    <li>✓ Claim identification & verification</li>
                    <li>✓ Source cross-referencing</li>
                    <li>✓ Confidence scoring</li>
                    <li>✓ Detailed explanations</li>
                  </ul>
                </div>

                <div className="feature-card">
                  <div className="feature-header">
                    <div className="feature-icon-large">📊</div>
                    <h3>Comprehensive Reports</h3>
                  </div>
                  <p>
                    Receive detailed, interactive reports with visual elements, charts, and organized information that's
                    easy to understand and share.
                  </p>
                  <ul className="feature-list">
                    <li>✓ Interactive visualizations</li>
                    <li>✓ Credibility ratings</li>
                    <li>✓ Exportable reports</li>
                    <li>✓ Mobile-friendly design</li>
                  </ul>
                </div>
              </div>
            </section>

            {/* How It Works Section */}
            <section className="how-it-works-section">
              <div className="section-header">
                <h2 className="section-title">
                  <span className="section-icon">⚙️</span>
                  How It Works
                </h2>
                <p className="section-description">
                  Our advanced AI pipeline processes your video through multiple analysis stages
                </p>
              </div>

              <div className="process-steps">
                <div className="step-item">
                  <div className="step-number">1</div>
                  <div className="step-content">
                    <h3>Video Processing</h3>
                    <p>
                      We extract audio, transcribe content, and identify key segments using advanced speech recognition
                      and NLP technologies.
                    </p>
                  </div>
                </div>

                <div className="step-connector"></div>

                <div className="step-item">
                  <div className="step-number">2</div>
                  <div className="step-content">
                    <h3>Content Analysis</h3>
                    <p>
                      Our AI analyzes the content structure, identifies main topics, extracts claims, and creates
                      comprehensive summaries.
                    </p>
                  </div>
                </div>

                <div className="step-connector"></div>

                <div className="step-item">
                  <div className="step-number">3</div>
                  <div className="step-content">
                    <h3>Fact Verification</h3>
                    <p>
                      Claims are cross-referenced with reliable sources, verified for accuracy, and assigned confidence
                      scores.
                    </p>
                  </div>
                </div>

                <div className="step-connector"></div>

                <div className="step-item">
                  <div className="step-number">4</div>
                  <div className="step-content">
                    <h3>Report Generation</h3>
                    <p>
                      All insights are compiled into an interactive, comprehensive report with summaries, fact-checks,
                      and credibility assessments.
                    </p>
                  </div>
                </div>
              </div>
            </section>
          </>
        )}

        {status === "PENDING" && (
          <section className="loading-section">
            <div className="loading-container enhanced-loading">
              <div className="loading-animation">
                <div className="spinner-ring">
                  <div className="spinner-inner"></div>
                </div>
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>

              <div className="loading-content">
                <h3 className="loading-title">🧠 AI Analysis in Progress</h3>
                <p className="loading-subtitle">Our advanced algorithms are processing your video...</p>

                <div className="progress-steps">
                  <div className="progress-step active">
                    <span className="step-icon">🎵</span>
                    <span>Extracting Audio</span>
                  </div>
                  <div className="progress-step active">
                    <span className="step-icon">📝</span>
                    <span>Transcribing Content</span>
                  </div>
                  <div className="progress-step active">
                    <span className="step-icon">🤖</span>
                    <span>AI Analysis</span>
                  </div>
                  <div className="progress-step">
                    <span className="step-icon">✅</span>
                    <span>Generating Report</span>
                  </div>
                </div>

                <div className="task-info">
                  <p>
                    Task ID: <span className="task-id-badge">{taskId}</span>
                  </p>
                  <p className="estimated-time">Estimated completion: 2-5 minutes</p>
                </div>
              </div>
            </div>
          </section>
        )}

        {status === "SUCCESS" && result && (
          <section className="results-section">
            <div className="results-header">
              <h2 className="results-title">
                <span className="results-icon">📋</span>
                Analysis Complete
              </h2>
              <p className="results-subtitle">Your comprehensive video analysis is ready</p>
            </div>

            <div className="results-container">
              <SummaryReport summary={result} />
              <FactCheckReport result={result} />

              <div className="results-actions">
                <button onClick={handleReset} className="reset-button enhanced-reset">
                  <span className="button-icon">🔄</span>
                  <span>Analyze Another Video</span>
                </button>
              </div>
            </div>
          </section>
        )}

        {/* Technology Section */}
        <section className="technology-section">
          <div className="section-header">
            <h2 className="section-title">
              <span className="section-icon">🧬</span>
              Powered by Advanced AI
            </h2>
            <p className="section-description">
              Built with cutting-edge machine learning and natural language processing technologies
            </p>
          </div>

          <div className="tech-grid">
            <div className="tech-item">
              <div className="tech-icon">🧠</div>
              <h4>Neural Networks</h4>
              <p>Deep learning models trained on millions of hours of content</p>
            </div>
            <div className="tech-item">
              <div className="tech-icon">🔤</div>
              <h4>NLP Processing</h4>
              <p>Advanced natural language understanding and generation</p>
            </div>
            <div className="tech-item">
              <div className="tech-icon">📊</div>
              <h4>Data Analytics</h4>
              <p>Sophisticated statistical analysis and pattern recognition</p>
            </div>
            <div className="tech-item">
              <div className="tech-icon">🔍</div>
              <h4>Fact Verification</h4>
              <p>Real-time cross-referencing with trusted knowledge bases</p>
            </div>
          </div>
        </section>

        {/* Demo Information */}
        <section className="demo-section">
          <div className="demo-container">
            <div className="demo-header">
              <h3 className="demo-title">
                <span className="demo-icon">🚧</span>
                Demo Environment
              </h3>
            </div>
            <div className="demo-content">
              <p className="demo-description">
                This is a demonstration of the AI Content Analyzer frontend interface. To experience the full
                functionality:
              </p>
              <ul className="demo-requirements">
                <li>
                  ✓ Backend API server running on <code>localhost:8000</code>
                </li>
                <li>✓ All required AI models and dependencies installed</li>
                <li>✓ Valid YouTube API credentials configured</li>
                <li>✓ Fact-checking database connections established</li>
              </ul>
              <div className="demo-note">
                <span className="note-icon">💡</span>
                <span>
                  The interface includes real-time polling, interactive visualizations, and comprehensive reporting
                  features.
                </span>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Enhanced Footer */}
      <footer className="app-footer">
        <div className="footer-content">
          <div className="footer-section">
            <h4>YouTube Summarizer n Factchecker</h4>
            <p>Transforming video content into actionable insights with advanced AI technology.</p>
          </div>
          <div className="footer-section">
            <h4>Features</h4>
            <ul>
              <li>Smart Summaries</li>
              <li>Fact Verification</li>
              <li>Chapter Analysis</li>
              <li>Credibility Scoring</li>
            </ul>
          </div>
          <div className="footer-section">
            <h4>Technology</h4>
            <ul>
              <li>Machine Learning</li>
              <li>Natural Language Processing</li>
              <li>Real-time Analysis</li>
              <li>Interactive Reports</li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <p>© {new Date().getFullYear()} AI Content Analyzer Pro. Powered by advanced artificial intelligence.</p>
        </div>
      </footer>
    </div>
  )
}

export default App
