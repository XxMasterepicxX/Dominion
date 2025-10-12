import { useState } from 'react';
import { Link } from 'react-router-dom';
import logo from '../assets/logo.png';
import { Globe } from '../components/Globe';
import './Dashboard.css';

const signalTimeline = [
  {
    title: 'Assemblage sweep complete',
    detail: 'Innovation Square perimeter parcels verified across Gainesville property appraiser and Sunbiz filings.',
    timestamp: 'Oct 10 - 02:26',
    status: 'Completed',
  },
  {
    title: 'Permit velocity spike detected',
    detail: 'Tampa River District commercial permits up 37% week-over-week. Flagged for investor review.',
    timestamp: 'Oct 09 - 19:04',
    status: 'Queued',
  },
  {
    title: 'LLC cluster enrichment',
    detail: 'Jacksonville logistics corridor LLC formations mapped to parcel acquisitions.',
    timestamp: 'Oct 09 - 11:42',
    status: 'Research',
  },
];

const opportunityQueue = [
  {
    entity: 'Infinity Development LLC',
    market: 'Gainesville, FL',
    signal: 'Assemblage pattern',
    confidence: '0.92',
    lead: '14d lead',
  },
  {
    entity: 'Urban Nexus Capital',
    market: 'Tampa, FL',
    signal: 'Permit velocity spike',
    confidence: '0.88',
    lead: '21d lead',
  },
  {
    entity: 'Beacon Ridge Partners',
    market: 'Jacksonville, FL',
    signal: 'LLC formation cluster',
    confidence: '0.85',
    lead: '9d lead',
  },
];

const missionBrief = {
  confidence: '0.92',
  leadTime: '3-6 weeks',
  summary:
    'Dominion agent is tracking Gainesville Innovation Square assemblage activity. Parcel consolidation, overlapping LLC registrations, and council agenda references indicate pre-development motion with high investor interest.',
  nextSteps: [
    'Validate parcel acquisition chain completion',
    'Model entitlement outcomes using council transcripts',
    'Stage Gainesville investor briefing by Monday 09:00 ET',
  ],
};

type PanelKey = 'mission' | 'queue' | 'timeline';

export const Dashboard = () => {
  const [activePanel, setActivePanel] = useState<PanelKey>('mission');

  return (
    <div className="dashboard dashboard--ready">
      <div className="dashboard__screen">
        <aside className="dashboard__sidebar">
          <div className="dashboard__sidebar-header">
            <Link to="/" className="dashboard__sidebar-brand-link">
              <img src={logo} alt="Dominion logo" className="dashboard__sidebar-logo" />
              <div className="dashboard__sidebar-brand-text">
                <span className="dashboard__sidebar-brand">Dominion</span>
                <span className="dashboard__sidebar-sub">Command Center</span>
              </div>
            </Link>
          </div>
          <div className="dashboard__sidebar-section">
            <div className="dashboard__sidebar-heading">
              <span>Current mission</span>
              <span className="dashboard__sidebar-tag">Gainesville, FL</span>
            </div>
            <button type="button" className="dashboard__sidebar-primary">
              Preview briefing
            </button>
          </div>
          <div className="dashboard__sidebar-list">
            <span className="dashboard__sidebar-label">Latest signals</span>
            <ul>
              {signalTimeline.map((item) => (
                <li key={item.title}>
                  <div>
                    <span className="dashboard__sidebar-item-title">{item.title}</span>
                    <span className="dashboard__sidebar-item-detail">{item.detail}</span>
                  </div>
                  <div className="dashboard__sidebar-item-meta">
                    <span>{item.timestamp}</span>
                    <span className="dashboard__sidebar-status">{item.status}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <section className="dashboard__globe-stage">
          <div className="dashboard__globe-wrapper">
            <Globe className="dashboard__globe" />
            <div className="dashboard__globe-overlay">
              <span>Mission density</span>
              <strong>30 active</strong>
            </div>
          </div>

          <div className="dashboard__focus-card">
            <header>
              <span>Gainesville assemblage overview</span>
              <span className="dashboard__focus-card-tag">High confidence</span>
            </header>
            <div className="dashboard__focus-card-body">
              <p>
                Infinity Development LLC is consolidating parcels across Innovation Square with supporting signals from
                permit filings, LLC registrations, and council agenda references.
              </p>
              <div className="dashboard__focus-grid">
                <div>
                  <span className="dashboard__focus-label">Parcels linked</span>
                  <strong>18</strong>
                </div>
                <div>
                  <span className="dashboard__focus-label">Timeline coverage</span>
                  <strong>6 weeks</strong>
                </div>
                <div>
                  <span className="dashboard__focus-label">Supporting signals</span>
                  <strong>Permits / LLC filings / News</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        <aside className="dashboard__widgets">
          <div className="dashboard__widgets-tabs">
            <button
              type="button"
              className={`dashboard__widgets-tab ${activePanel === 'mission' ? 'dashboard__widgets-tab--active' : ''}`}
              onClick={() => setActivePanel('mission')}
            >
              Mission brief
            </button>
            <button
              type="button"
              className={`dashboard__widgets-tab ${activePanel === 'queue' ? 'dashboard__widgets-tab--active' : ''}`}
              onClick={() => setActivePanel('queue')}
            >
              Opportunity queue
            </button>
            <button
              type="button"
              className={`dashboard__widgets-tab ${activePanel === 'timeline' ? 'dashboard__widgets-tab--active' : ''}`}
              onClick={() => setActivePanel('timeline')}
            >
              Signal timeline
            </button>
          </div>

          <article className="dashboard__widget dashboard__widget--deck">
            {activePanel === 'mission' && (
              <>
                <header className="dashboard__widget-header">
                  <span>Mission brief</span>
                  <span className="dashboard__widget-tag">Dominion agent</span>
                </header>
                <div className="dashboard__widget-stage">
                  <span>Confidence</span>
                  <strong>{missionBrief.confidence}</strong>
                </div>
                <div className="dashboard__widget-stage">
                  <span>Lead time</span>
                  <strong>{missionBrief.leadTime}</strong>
                </div>
                <p className="dashboard__widget-summary">{missionBrief.summary}</p>
                <div className="dashboard__widget-next">
                  <span>Next actions</span>
                  <ul>
                    {missionBrief.nextSteps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ul>
                </div>
              </>
            )}

            {activePanel === 'queue' && (
              <>
                <header className="dashboard__widget-header">
                  <span>Opportunity queue</span>
                  <span className="dashboard__widget-tag">Auto-ranked</span>
                </header>
                <ul className="dashboard__queue">
                  {opportunityQueue.map((row) => (
                    <li key={row.entity}>
                      <div className="dashboard__queue-entity">
                        <span className="dashboard__queue-name">{row.entity}</span>
                        <span className="dashboard__queue-market">{row.market}</span>
                      </div>
                      <div className="dashboard__queue-meta">
                        <span>{row.signal}</span>
                        <span className="dashboard__queue-confidence">
                          Confidence <strong>{row.confidence}</strong>
                        </span>
                        <span>{row.lead}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {activePanel === 'timeline' && (
              <>
                <header className="dashboard__widget-header">
                  <span>Signal timeline</span>
                  <span className="dashboard__widget-tag dashboard__widget-tag--accent">Live feed</span>
                </header>
                <ul className="dashboard__timeline">
                  {signalTimeline.map((item) => (
                    <li key={`${item.title}-timeline`}>
                      <div className="dashboard__timeline-header">
                        <span>{item.title}</span>
                        <span>{item.timestamp}</span>
                      </div>
                      <p>{item.detail}</p>
                      <span className="dashboard__timeline-status">{item.status}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </article>
        </aside>
      </div>
    </div>
  );
};

