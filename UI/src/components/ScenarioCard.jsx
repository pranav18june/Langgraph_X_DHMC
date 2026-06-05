import './ScenarioCard.css';

function ScenarioCard({ scenario, selected = false, onClick }) {
  const { id, title, subtitle, icon, color, description } = scenario;

  return (
    <div
      className={`scenario-card ${selected ? 'scenario-card--selected' : ''}`}
      style={{ '--scenario-color': color }}
      onClick={() => onClick && onClick(id)}
    >
      <div className="scenario-card__indicator" />
      <div className="scenario-card__icon">{icon}</div>
      <div className="scenario-card__title">{title}</div>
      <div className="scenario-card__subtitle">{subtitle}</div>
      <div className="scenario-card__description">{description}</div>
    </div>
  );
}

export default ScenarioCard;
