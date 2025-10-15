import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import logo from '../assets/logo.png';
import { Globe } from '../components/Globe';
import { connectDashboardUpdates, fetchDashboardState } from '../services/dashboard';
import type { DashboardState } from '../types/dashboard';
import './Dashboard.css';

type PanelKey = 'report' | 'opportunities' | 'activity';

const formatRelativeTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 0) {
    return 'just now';
  }
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
};

const formatConfidence = (value?: number) => {
  if (typeof value !== 'number') {
    return '--';
  }
  return `${Math.round(value * 100)}%`;
};

const formatToolName = (toolName: string) =>
  toolName.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());

export const Dashboard = () => {
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<DashboardState | null>(null);
  const [activePanel, setActivePanel] = useState<PanelKey>('report');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const requestedProjectId = searchParams.get('projectId') ?? undefined;
  const projectId = state?.project.id ?? requestedProjectId ?? undefined;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchDashboardState({ projectId: requestedProjectId, signal: controller.signal })
      .then((data) => {
        setState(data);
        setError(null);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError('Unable to load project report.');
        }
      })
      .finally(() => {
        setLoading(false);
      });

    return () => controller.abort();
  }, [requestedProjectId]);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    const disconnect = connectDashboardUpdates({
      projectId,
      onUpdate: (message) => {
        if (message.type === 'update_detected') {
          setState((prev) => {
            if (!prev) return prev;
            const updates = [
              message.payload.update,
              ...prev.latestUpdates.filter((item) => item.id !== message.payload.update.id),
            ];
            return {
              ...prev,
              latestUpdates: updates.slice(0, 10),
            };
          });
        }

        if (message.type === 'state_refresh') {
          setState(message.payload.state);
        }
      },
    });

    return () => {
      disconnect?.();
    };
  }, [projectId]);

  const markers = useMemo(
    () =>
      state?.markets.map((marker) => ({
        location: marker.location,
        size: marker.size,
      })) ?? [],
    [state],
  );
  const globeConfig = useMemo(() => ({ markers }), [markers]);

  if (!state) {
    return (
      <div className="dashboard dashboard--ready">
        <div className="dashboard__loading">
          <span>{loading ? 'Loading project report...' : error ?? 'No project data available.'}</span>
        </div>
      </div>
    );
  }

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
              <span>Project Report</span>
              <span className="dashboard__sidebar-tag">{state.project.market}</span>
            </div>
            <div className="dashboard__sidebar-meta">
              <span>{state.project.name}</span>
              <span>Generated {formatRelativeTime(state.project.generatedAt)}</span>
              <span>Last updated {formatRelativeTime(state.lastDataCheck)}</span>
              <span>Confidence {formatConfidence(state.project.confidence)}</span>
              <span>Opportunities {state.project.opportunities}</span>
            </div>
            <div className={`dashboard__live ${state.isLive ? 'dashboard__live--active' : ''}`}>
              <span className="dashboard__live-dot" />
              <span>{state.isLive ? 'Live updates enabled' : 'Live updates paused'}</span>
            </div>
            <button type="button" className="dashboard__sidebar-primary">
              Export PDF
            </button>
          </div>
          <div className="dashboard__sidebar-list">
            <span className="dashboard__sidebar-label">Latest Updates</span>
            <ul>
              {state.latestUpdates.map((item) => (
                <li
                  key={item.id}
                  className={`dashboard__sidebar-item ${item.status === 'new' ? 'dashboard__sidebar-item--new' : ''}`}
                >
                  <div>
                    <span className="dashboard__sidebar-item-title">{item.title}</span>
                    <span className="dashboard__sidebar-item-detail">{item.detail}</span>
                  </div>
                  <div className="dashboard__sidebar-item-meta">
                    <span>{formatRelativeTime(item.timestamp)}</span>
                    <span className="dashboard__sidebar-status">{item.updateType.replace('_', ' ')}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <section className="dashboard__globe-stage">
          <div className="dashboard__globe-wrapper">
            <Globe className="dashboard__globe" config={globeConfig} />
            <div className="dashboard__globe-overlay">
              <span>{state.trackingDensity.label}</span>
              <strong>{state.trackingDensity.value}</strong>
            </div>
          </div>

          <div className="dashboard__focus-card">
            <header>
              <span>{state.focusCard.header}</span>
              <span
                className={`dashboard__focus-card-tag dashboard__focus-card-tag--${state.focusCard.tagType}`}
              >
                {state.focusCard.tag}
              </span>
            </header>
            <div className="dashboard__focus-card-body">
              <p>{state.focusCard.summary}</p>
              <div className="dashboard__focus-grid">
                {state.focusCard.stats.map((stat) => (
                  <div key={stat.label}>
                    <span className="dashboard__focus-label">{stat.label}</span>
                    <strong>{stat.value}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <aside className="dashboard__widgets">
          <div className="dashboard__widgets-tabs">
            <button
              type="button"
              className={`dashboard__widgets-tab ${activePanel === 'report' ? 'dashboard__widgets-tab--active' : ''}`}
              onClick={() => setActivePanel('report')}
            >
              Report
            </button>
            <button
              type="button"
              className={`dashboard__widgets-tab ${
                activePanel === 'opportunities' ? 'dashboard__widgets-tab--active' : ''
              }`}
              onClick={() => setActivePanel('opportunities')}
            >
              Opportunities
            </button>
            <button
              type="button"
              className={`dashboard__widgets-tab ${activePanel === 'activity' ? 'dashboard__widgets-tab--active' : ''}`}
              onClick={() => setActivePanel('activity')}
            >
              Activity
            </button>
          </div>

          <article className="dashboard__widget dashboard__widget--deck">
            {activePanel === 'report' && (
              <>
                <header className="dashboard__widget-header">
                  <span>Report</span>
                  <span className="dashboard__widget-tag">Dominion Intelligence</span>
                </header>
                <div className="dashboard__report-meta">
                  <div>
                    <span>Confidence</span>
                    <strong>{`${state.reportContent.confidenceLabel} (${formatConfidence(
                      state.reportContent.confidence,
                    )})`}</strong>
                  </div>
                  <div>
                    <span>Coverage</span>
                    <strong>{state.reportContent.dataCoverage}</strong>
                  </div>
                  <div>
                    <span>Analysis</span>
                    <strong>{state.reportContent.analysisType}</strong>
                  </div>
                </div>
                <p className="dashboard__report-summary">{state.reportContent.summary}</p>
                {state.reportContent.marketContext && (
                  <p className="dashboard__report-market">{state.reportContent.marketContext}</p>
                )}

                <div className="dashboard__report-sections">
                  {state.reportContent.sections.map((section) => (
                    <section key={section.title} className="dashboard__report-section">
                      <header>
                        <h3>{section.title}</h3>
                      </header>
                      <p>{section.content}</p>
                      {section.metrics && (
                        <ul className="dashboard__report-metrics">
                          {section.metrics.map((metric) => (
                            <li
                              key={`${section.title}-${metric.label}`}
                              className={metric.highlight ? 'dashboard__report-metric--highlight' : ''}
                            >
                              <span>{metric.label}</span>
                              <strong>{metric.value}</strong>
                            </li>
                          ))}
                        </ul>
                      )}
                    </section>
                  ))}
                </div>

                <div className="dashboard__report-next">
                  <span>Next actions</span>
                  <ul>
                    {state.reportContent.nextActions.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ul>
                </div>

                {state.reportContent.sources && (
                  <div className="dashboard__report-sources">
                    <div>
                      <span>Tools</span>
                      <strong>{state.reportContent.sources.tools.join(' | ')}</strong>
                    </div>
                    <div>
                      <span>Data</span>
                      <strong>{state.reportContent.sources.databases.join(' | ')}</strong>
                    </div>
                    <div>
                      <span>Coverage</span>
                      <strong>{state.reportContent.sources.coverage}</strong>
                    </div>
                  </div>
                )}
              </>
            )}

            {activePanel === 'opportunities' && (
              <>
                <header className="dashboard__widget-header">
                  <span>Opportunity queue</span>
                  <span className="dashboard__widget-tag">Auto-ranked</span>
                </header>
                <ul className="dashboard__queue">
                  {state.opportunityQueue.map((row) => (
                    <li key={row.id}>
                      <div className="dashboard__queue-entity">
                        <span className="dashboard__queue-name">{row.entity ?? row.property ?? row.market}</span>
                        <span className="dashboard__queue-market">{row.market}</span>
                      </div>
                      <div className="dashboard__queue-meta">
                        <span>{row.signal}</span>
                        <span>Lead {row.leadTime}</span>
                        <span className="dashboard__queue-confidence">
                          Confidence{' '}
                          <strong>{`${row.confidenceLabel} (${formatConfidence(row.confidence)})`}</strong>
                        </span>
                      </div>
                      <div className="dashboard__queue-meta">
                        <span>Action: {row.action}</span>
                        {row.estimatedReturn && <span>Return {row.estimatedReturn}</span>}
                      </div>
                      {row.risks && row.risks.length > 0 && (
                        <div className="dashboard__queue-risks">Risks: {row.risks.join(' | ')}</div>
                      )}
                      <div className="dashboard__queue-status">
                        <span className={`dashboard__queue-status-dot dashboard__queue-status-dot--${row.status}`} />
                        <span>{row.status.replace('_', ' ')}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {activePanel === 'activity' && (
              <>
                <header className="dashboard__widget-header">
                  <span>Activity log</span>
                  <span className="dashboard__widget-tag dashboard__widget-tag--accent">Tool executions</span>
                </header>
                <ul className="dashboard__timeline">
                  {state.activityLog.map((item) => (
                    <li key={item.id}>
                      <div className="dashboard__timeline-header">
                        <span>{formatToolName(item.toolName)}</span>
                        <span>{formatRelativeTime(item.timestamp)}</span>
                      </div>
                      <p>{item.description}</p>
                      <span className="dashboard__timeline-status">
                        {item.status === 'complete' ? 'Complete' : item.status}
                        {item.duration ? ` | ${item.duration}` : ''}
                      </span>
                      <p className="dashboard__timeline-result">{item.result}</p>
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

