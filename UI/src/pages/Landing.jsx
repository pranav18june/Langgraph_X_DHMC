import { useNavigate } from 'react-router-dom'
import {
  Shield, ShieldAlert, ShieldOff, Zap, Lock, Eye, ArrowRight,
  ChevronRight, Fingerprint, GitBranch, FileCheck, AlertTriangle
} from 'lucide-react'
import './Landing.css'

const problems = [
  {
    icon: ShieldOff,
    title: 'Log Tampering',
    description: 'Attackers with database access can alter agent execution logs after the fact, hiding malicious actions.',
    color: 'var(--red-500)',
    glow: 'var(--red-glow)',
  },
  {
    icon: GitBranch,
    title: 'Policy Drift',
    description: 'Agents can deviate from standard routing, executing unauthorized operations or skipping critical verification steps.',
    color: 'var(--amber-500)',
    glow: 'var(--amber-glow)',
  },
  {
    icon: AlertTriangle,
    title: 'Context Hijacking',
    description: 'Inputs or intermediate state can be altered mid-flight to manipulate downstream AI decisions without breaking anything.',
    color: 'var(--purple-500)',
    glow: 'var(--purple-glow)',
  },
]

const features = [
  {
    icon: Fingerprint,
    title: 'Cryptographic Binding',
    description: 'Every step gets a unique fingerprint chained to all previous steps. Like a blockchain for AI decisions.',
  },
  {
    icon: Eye,
    title: '7-Check Forensic Audit',
    description: 'Seven independent security checks verify the entire execution chain — from nonce uniqueness to payload integrity.',
  },
  {
    icon: Lock,
    title: 'Policy Envelopes',
    description: 'Pre-committed rules define what each module can do. Any deviation is instantly flagged and recorded.',
  },
  {
    icon: Zap,
    title: 'Zero Overhead',
    description: 'Adds only ~74 microseconds per step. Less than 0.1% of total execution time. Invisible to performance.',
  },
]

const pipelineSteps = [
  { label: 'M1', name: 'Intent Parsing', type: 'LLM', color: 'var(--blue-500)' },
  { label: 'M2', name: 'Multi-Source Eval', type: 'RAG + TOOL', color: 'var(--purple-500)' },
  { label: 'M3', name: 'Decision', type: 'LLM', color: 'var(--green-500)' },
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div className="landing page">
      <div className="container">
        {/* ── Hero Section ─────────────────────────────────── */}
        <section className="landing__hero">
          <div className="landing__hero-badge animate-fade-in-up">
            <Shield size={14} />
            <span>Forensic-Grade Cryptographic Provenance</span>
          </div>
          <h1 className="landing__hero-title animate-fade-in-up stagger-1">
            <span className="landing__hero-highlight">Tamper-Proof Security</span>
            <br />
            for AI Agent Pipelines
          </h1>
          <p className="landing__hero-subtitle animate-fade-in-up stagger-2">
            DHMC wraps your AI agent pipeline with an invisible cryptographic shield.
            Every decision, every step, every output is permanently recorded in a chain
            that no one can alter without being caught.
          </p>
          <div className="landing__hero-actions animate-fade-in-up stagger-3">
            <button
              className="btn btn--primary btn--lg"
              onClick={() => navigate('/simulator')}
            >
              <Play size={18} />
              Try the Simulator
            </button>
            <button
              className="btn btn--secondary btn--lg"
              onClick={() => navigate('/glossary')}
            >
              Learn More
              <ArrowRight size={16} />
            </button>
          </div>

          {/* Mini pipeline visualization */}
          <div className="landing__pipeline animate-fade-in-up stagger-4">
            <div className="landing__pipeline-label">Loan Approval Pipeline</div>
            <div className="landing__pipeline-flow">
              {pipelineSteps.map((step, i) => (
                <div key={step.label} className="landing__pipeline-group">
                  {i > 0 && (
                    <div className="landing__pipeline-arrow">
                      <ChevronRight size={20} />
                    </div>
                  )}
                  <div
                    className="landing__pipeline-step"
                    style={{ '--step-color': step.color }}
                  >
                    <div className="landing__pipeline-step-label">{step.label}</div>
                    <div className="landing__pipeline-step-name">{step.name}</div>
                    <div className="landing__pipeline-step-type">{step.type}</div>
                    <div className="landing__pipeline-step-hash">
                      <Lock size={10} />
                      <span className="mono">0x7f3a...</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="landing__pipeline-shield">
              <Shield size={16} />
              <span>DHMC Protected — Every step cryptographically bound</span>
            </div>
          </div>
        </section>

        {/* ── Problem Statement ────────────────────────────── */}
        <section className="landing__section">
          <h2 className="section-title">The Problem</h2>
          <p className="section-subtitle">
            AI agents make critical decisions, but their execution logs can be altered. DHMC fixes that.
          </p>
          <div className="grid grid-3">
            {problems.map((problem, i) => (
              <div
                key={problem.title}
                className="landing__problem-card animate-fade-in-up"
                style={{
                  animationDelay: `${i * 100}ms`,
                  '--card-color': problem.color,
                  '--card-glow': problem.glow,
                }}
              >
                <div className="landing__problem-icon">
                  <problem.icon size={24} />
                </div>
                <h3>{problem.title}</h3>
                <p>{problem.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── How It Works (Simple) ───────────────────────── */}
        <section className="landing__section">
          <h2 className="section-title">How DHMC Protects Your Pipeline</h2>
          <p className="section-subtitle">
            Think of it as a tamper-proof receipt for every AI decision your system makes.
          </p>
          <div className="landing__how-it-works">
            <div className="landing__hiw-step animate-fade-in-up">
              <div className="landing__hiw-number">1</div>
              <div className="landing__hiw-content">
                <h4>Wrap Your Pipeline</h4>
                <p>DHMC sits invisibly around your existing AI pipeline. No code changes needed — zero modification.</p>
              </div>
            </div>
            <div className="landing__hiw-connector"></div>
            <div className="landing__hiw-step animate-fade-in-up stagger-2">
              <div className="landing__hiw-number">2</div>
              <div className="landing__hiw-content">
                <h4>Cryptographic Recording</h4>
                <p>Every step automatically gets a unique fingerprint that chains to all previous steps. Like a blockchain for AI decisions.</p>
              </div>
            </div>
            <div className="landing__hiw-connector"></div>
            <div className="landing__hiw-step animate-fade-in-up stagger-4">
              <div className="landing__hiw-number">3</div>
              <div className="landing__hiw-content">
                <h4>Forensic Verification</h4>
                <p>Run the 7-check audit suite anytime. It will tell you if anything was tampered with — and exactly where.</p>
              </div>
            </div>
          </div>
        </section>

        {/* ── Features ─────────────────────────────────────── */}
        <section className="landing__section">
          <h2 className="section-title">Key Features</h2>
          <p className="section-subtitle">
            Built for enterprise-grade security with near-zero performance impact.
          </p>
          <div className="grid grid-2">
            {features.map((feature, i) => (
              <div
                key={feature.title}
                className="landing__feature-card animate-fade-in-up"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <div className="landing__feature-icon">
                  <feature.icon size={20} />
                </div>
                <div>
                  <h4>{feature.title}</h4>
                  <p>{feature.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── CTA ──────────────────────────────────────────── */}
        <section className="landing__cta">
          <div className="landing__cta-inner">
            <FileCheck size={32} className="landing__cta-icon" />
            <h2>Ready to see it in action?</h2>
            <p>Run a simulated loan approval pipeline and watch DHMC catch attacks in real-time.</p>
            <button
              className="btn btn--primary btn--lg"
              onClick={() => navigate('/simulator')}
            >
              Launch Simulator
              <ArrowRight size={18} />
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}

function Play(props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={props.size || 24} height={props.size || 24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="6 3 20 12 6 21 6 3" />
    </svg>
  )
}
