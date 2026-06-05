import { ShieldCheck, ShieldAlert, AlertTriangle } from 'lucide-react';
import './VerdictBanner.css';

const verdictConfig = {
  CLEAN: {
    icon: ShieldCheck,
    className: 'verdict-banner--clean',
    label: 'Audit Passed',
  },
  TAMPERED: {
    icon: ShieldAlert,
    className: 'verdict-banner--tampered',
    label: 'Tampering Detected',
  },
  POLICY_VIOLATION: {
    icon: AlertTriangle,
    className: 'verdict-banner--policy_violation',
    label: 'Policy Violation',
  },
};

function VerdictBanner({ verdict, sessionId, breachStep }) {
  const config = verdictConfig[verdict] || verdictConfig.CLEAN;
  const Icon = config.icon;

  return (
    <div className={`verdict-banner ${config.className}`}>
      <div className="verdict-banner__icon">
        <Icon size={28} />
      </div>
      <div className="verdict-banner__content">
        <div className="verdict-banner__label">{config.label}</div>
        <div className="verdict-banner__verdict">{verdict}</div>
        <div className="verdict-banner__meta">
          {sessionId && (
            <div className="verdict-banner__meta-item">
              Session: <span>{sessionId}</span>
            </div>
          )}
          {breachStep && (
            <div className="verdict-banner__meta-item">
              Breach at: <span>{breachStep}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default VerdictBanner;
