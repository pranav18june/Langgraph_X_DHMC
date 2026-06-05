import './GlassCard.css';

function GlassCard({ children, className = '', hover = false, glow, onClick }) {
  const classes = [
    'glass-card',
    hover ? 'glass-card--hoverable' : '',
    glow ? 'glass-card--glow' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const style = glow ? { '--glow-color': glow } : undefined;

  return (
    <div className={classes} style={style} onClick={onClick}>
      {children}
    </div>
  );
}

export default GlassCard;
