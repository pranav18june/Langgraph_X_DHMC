import { useEffect, useRef } from 'react';
import './LiveLogFeed.css';

function LiveLogFeed({ logs = [] }) {
  const entriesRef = useRef(null);

  useEffect(() => {
    if (entriesRef.current) {
      entriesRef.current.scrollTop = entriesRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="live-log-feed">
      <div className="live-log-feed__header">
        <div className="live-log-feed__dot" />
        Live Audit Log
      </div>
      <div className="live-log-feed__entries" ref={entriesRef}>
        {logs.length === 0 ? (
          <div className="live-log-feed__empty">Waiting for pipeline events…</div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className={`live-log-entry live-log-entry--${log.type || 'info'}`}>
              <span className="live-log-entry__time">{log.timestamp}</span>
              <span className="live-log-entry__message">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default LiveLogFeed;
