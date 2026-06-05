import { useState } from 'react';
import { CheckCircle2, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import './AuditCheckCard.css';

function AuditCheckCard({ check, passed, detail, evidence, index = 0 }) {
  const [showEvidence, setShowEvidence] = useState(false);

  return (
    <div
      className={`audit-check-card ${passed ? 'audit-check-card--passed' : 'audit-check-card--failed'}`}
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <div className="audit-check-card__header">
        <div className="audit-check-card__number">{index + 1}</div>
        <div className="audit-check-card__name">{check}</div>
        <div className={`audit-check-card__badge ${passed ? 'audit-check-card__badge--pass' : 'audit-check-card__badge--fail'}`}>
          {passed ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
          {passed ? 'PASS' : 'FAIL'}
        </div>
      </div>

      {detail && <div className="audit-check-card__detail">{detail}</div>}

      {evidence && (
        <>
          <button
            className="audit-check-card__evidence-toggle"
            onClick={() => setShowEvidence(!showEvidence)}
          >
            {showEvidence ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {showEvidence ? 'Hide Evidence' : 'Show Evidence'}
          </button>
          {showEvidence && (
            <div className="audit-check-card__evidence">
              {typeof evidence === 'string' ? evidence : JSON.stringify(evidence, null, 2)}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default AuditCheckCard;
