import { useEffect, useCallback } from 'react';
import { X, Hash, Clock, Shield, FileText } from 'lucide-react';
import './StepDetailModal.css';

function StepDetailModal({ step, isOpen, onClose }) {
  const handleOverlayClick = useCallback(
    (e) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose]
  );

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEsc);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen || !step) return null;

  // Extract step record data — handle both direct record and nested
  const rec = step.record || step;

  return (
    <div className="step-modal-overlay" onClick={handleOverlayClick}>
      <div className="step-modal">
        <div className="step-modal__header">
          <div className="step-modal__title">
            <FileText size={20} />
            Step Forensic Detail
          </div>
          <button className="step-modal__close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="step-modal__body">
          {/* Identity */}
          <div className="step-modal__section">
            <div className="step-modal__section-title">
              <Shield size={14} />
              Identity
            </div>
            <div className="step-modal__grid">
              <div className="step-modal__field">
                <div className="step-modal__field-label">Step ID</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.stepId || step.nodeId || '—'}
                </div>
              </div>
              <div className="step-modal__field">
                <div className="step-modal__field-label">Module</div>
                <div className="step-modal__field-value">{rec.moduleId || step.moduleId || '—'}</div>
              </div>
              <div className="step-modal__field">
                <div className="step-modal__field-label">Type</div>
                <div className="step-modal__field-value">{rec.stepType || step.stepType || '—'}</div>
              </div>
              <div className="step-modal__field">
                <div className="step-modal__field-label">Counter</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.monotonicCounter ?? '—'}
                </div>
              </div>
            </div>
          </div>

          {/* Timing */}
          <div className="step-modal__section">
            <div className="step-modal__section-title">
              <Clock size={14} />
              Timing & Nonce
            </div>
            <div className="step-modal__grid">
              <div className="step-modal__field">
                <div className="step-modal__field-label">Timestamp</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.timestamp || '—'}
                </div>
              </div>
              <div className="step-modal__field">
                <div className="step-modal__field-label">Nonce</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.nonce || '—'}
                </div>
              </div>
            </div>
          </div>

          {/* Hash Chain */}
          <div className="step-modal__section">
            <div className="step-modal__section-title">
              <Hash size={14} />
              Hash Chain
            </div>
            <div className="step-modal__grid">
              <div className="step-modal__field step-modal__field--full">
                <div className="step-modal__field-label">PreHash</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.preHash || '—'}
                </div>
              </div>
              <div className="step-modal__field step-modal__field--full">
                <div className="step-modal__field-label">PostHash</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.postHash || '—'}
                </div>
              </div>
              <div className="step-modal__field step-modal__field--full">
                <div className="step-modal__field-label">Binding (Leaf Hash)</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.binding || '—'}
                </div>
              </div>
            </div>
          </div>

          {/* CAS References */}
          <div className="step-modal__section">
            <div className="step-modal__section-title">
              <FileText size={14} />
              CAS References
            </div>
            <div className="step-modal__grid">
              <div className="step-modal__field step-modal__field--full">
                <div className="step-modal__field-label">Input CAS URI</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.inputCasUri || '—'}
                </div>
              </div>
              <div className="step-modal__field step-modal__field--full">
                <div className="step-modal__field-label">Output CAS URI</div>
                <div className="step-modal__field-value step-modal__field-value--mono">
                  {rec.outputCasUri || '—'}
                </div>
              </div>
            </div>
          </div>

          {/* Deviation */}
          {rec.deviation && (
            <div className="step-modal__section">
              <div className="step-modal__deviation">
                <div className="step-modal__deviation-label">⚠ Deviation Record</div>
                <div className="step-modal__deviation-text">{rec.deviation}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default StepDetailModal;
