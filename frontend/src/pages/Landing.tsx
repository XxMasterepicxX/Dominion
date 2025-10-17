import { Link } from 'react-router-dom';
import { StaticCanvasGlobe } from '../components/StaticCanvasGlobe';
import './Landing.css';

const metrics = [
  { label: 'Active data sources', value: '10+' },
  { label: 'Entity resolution accuracy', value: '95%' },
  { label: 'Opportunity detection lead time', value: '3-6 weeks' },
];

const capabilityCards = [
  {
    title: 'Autonomous Data Collection',
    description:
      'Self-directed crawling across permits, LLC filings, property records, news, and civic documents with adaptive scheduling.',
    hint: 'Real-time monitoring woven across 10+ municipal and state systems.',
  },
  {
    title: 'Multi-Signal Intelligence',
    description:
      'LLM-assisted entity resolution correlates officers, parcels, permits, and filings into single source-of-truth dossiers.',
    hint: 'Confidence-scored matches drive prioritised alerting to your pipeline.',
  },
  {
    title: 'Opportunity Detection',
    description:
      'Detect property assemblage, LLC formations, and development sequences before they surface in traditional channels.',
    hint: 'Accelerate deal teams with weeks of lead time on emerging plays.',
  },
];

const signalHighlights = [
  {
    title: 'Assembler Radar',
    stat: '18 parcels',
    description: 'Detected early-stage assemblage by Infinity Development LLC in Gainesville FL, mapped to zoning overlays.',
  },
  {
    title: 'Permit Velocity',
    stat: '37% spike',
    description:
      'Week-over-week growth in commercial permits featuring high-value contractors, auto-ranked by likelihood to be pre-development.',
  },
  {
    title: 'Sentiment Pulse',
    stat: '124 stories',
    description:
      'Cross-referenced news and council transcripts tied to targeted entities, auto-summarised for investor briefings.',
  },
  {
    title: 'Risk Monitor',
    stat: '9 triggers',
    description: 'Automated legal, zoning, and capital stack alerts surfaced for analyst review within minutes of filing.',
  },
];

export const Landing = () => {
  return (
    <div className="landing">
      <section className="landing__hero">
        <div className="landing__hero-glow" />
        <div className="landing__hero-inner">
          <div className="landing__hero-copy">
            <p className="landing__eyebrow">AI agent for market foresight</p>
            <h1>Anticipate real estate moves before they materialise.</h1>
            <p className="landing__subtext">
              Dominion continuously discovers, tracks, and analyses development signals across fragmented public data so
              your team can seize opportunities weeks ahead of the market.
            </p>
            <div className="landing__cta">
              <Link className="landing__cta-primary" to="/projects">
                View projects
              </Link>
              <a className="landing__cta-secondary" href="#capabilities">
                Explore capabilities
              </a>
            </div>
            <dl className="landing__metrics">
              {metrics.map((metric) => (
                <div key={metric.label} className="landing__metric">
                  <dt>{metric.value}</dt>
                  <dd>{metric.label}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="landing__hero-visual" aria-hidden="true">
            <div className="landing__hero-globe-wrapper">
              <StaticCanvasGlobe className="landing__hero-globe" />
            </div>
          </div>
        </div>
      </section>

      <section className="landing__section" id="capabilities">
        <div className="landing__section-heading">
          <p className="landing__eyebrow">Operating picture</p>
          <h2>Command the full development lifecycle from one autonomous agent.</h2>
          <p>
            Dominion synthesises permits, property records, civic transcripts, and news into a clean, explainable feed of
            market intelligence built for institutional deal teams.
          </p>
        </div>
        <div className="landing__grid">
          {capabilityCards.map((card) => (
            <article key={card.title} className="landing__card">
              <h3>{card.title}</h3>
              <p>{card.description}</p>
              <span className="landing__card-hint">{card.hint}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="landing__section landing__section--split" id="signals">
        <div className="landing__split-copy">
          <p className="landing__eyebrow">Signal intelligence</p>
          <h2>From raw filings to actionable strategies.</h2>
          <p>
            Every signal is traceable back to its source with timestamps, confidence bands, and narrative context so the
            path from detection to decision stays transparent.
          </p>
          <div className="landing__signal-grid">
            {signalHighlights.map((signal) => (
              <div key={signal.title} className="landing__signal-card">
                <span className="landing__signal-stat">{signal.stat}</span>
                <h3>{signal.title}</h3>
                <p>{signal.description}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="landing__split-visual">
          <div className="landing__visual-cluster">
            <div className="landing__visual-globe">
              <div className="landing__visual-globe-ring landing__visual-globe-ring--outer" />
              <div className="landing__visual-globe-ring landing__visual-globe-ring--middle" />
              <div className="landing__visual-globe-ring landing__visual-globe-ring--inner" />
              <div className="landing__visual-globe-core">
                <span>Global feed</span>
                <strong>27 missions</strong>
              </div>
              <div className="landing__visual-globe-node landing__visual-globe-node--north" />
              <div className="landing__visual-globe-node landing__visual-globe-node--west" />
              <div className="landing__visual-globe-node landing__visual-globe-node--south" />
            </div>
            <div className="landing__visual-readout">
              <div className="landing__visual-readout-item">
                <span className="landing__visual-readout-label">Confidence</span>
                <div className="landing__visual-readout-bar">
                  <span style={{ width: '92%' }} />
                </div>
                <span className="landing__visual-readout-meta">Avg 0.92</span>
              </div>
              <div className="landing__visual-readout-item">
                <span className="landing__visual-readout-label">Processing time</span>
                <span className="landing__visual-readout-value">03m 22s</span>
              </div>
              <div className="landing__visual-readout-item">
                <span className="landing__visual-readout-label">Analyst queue</span>
                <span className="landing__visual-readout-value landing__visual-readout-value--accent">3 missions</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="landing__section landing__cta-panel">
        <div className="landing__cta-panel-inner">
          <div>
            <p className="landing__eyebrow">Deployment ready</p>
            <h2>Stand up an investment-grade intelligence desk in days, not quarters.</h2>
            <p>
              Use the dashboard to triage missions, review entity dossiers, and trigger research workflows with one
              cohesive control surface.
            </p>
          </div>
          <Link className="landing__cta-primary landing__cta-primary--large" to="/projects">
            Select a project
          </Link>
        </div>
      </section>
    </div>
  );
};
