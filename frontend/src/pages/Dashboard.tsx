import { Fragment, type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import logo from '../assets/logo.png';
import { Globe } from '../components/Globe';
import { LoadingScreen } from '../components/LoadingScreen';
import { MarketMap } from '../components/MarketMap';
import { connectDashboardUpdates, fetchDashboardState } from '../services/dashboard';
import type { DashboardState, MarketMarker } from '../types/dashboard';
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

type InlineSegment = {
  content: string;
  bold: boolean;
};

type MarkdownBlock =
  | { type: 'paragraph'; lines: InlineSegment[][] }
  | { type: 'list'; items: InlineSegment[][] };

const MISENCODED_BULLET = '\u00E2\u20AC\u00A2';

// Remove zero-width and non-breaking whitespace that can cause subtle misalignment in labels
const sanitizeInlineLabel = (text: string): string =>
  (text ?? '')
    .replace(/[\u200B\u200C\u200D\uFEFF\u00A0]/g, ' ') // zero-width + NBSP to regular space
    .replace(/\s+/g, ' ') // collapse runs of whitespace
    .trim();

const tokenizeInlineSegments = (line: string): InlineSegment[] => {
  const segments: InlineSegment[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(line)) !== null) {
    if (match.index > lastIndex) {
      const preceding = line.slice(lastIndex, match.index);
      if (preceding) {
        segments.push({ content: preceding, bold: false });
      }
    }
    segments.push({ content: match[1], bold: true });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < line.length) {
    const remaining = line.slice(lastIndex);
    if (remaining) {
      segments.push({ content: remaining, bold: false });
    }
  }

  if (segments.length === 0) {
    segments.push({ content: line, bold: false });
  }

  return segments;
};

const hasBulletPrefix = (line: string) => {
  const trimmed = line.trimStart();
  return (
    trimmed.startsWith('- ') ||
    trimmed.startsWith('* ') ||
    trimmed.startsWith('•') ||
    trimmed.startsWith('\u2022') ||
    trimmed.startsWith('\u25CF') ||
    trimmed.startsWith('\u25AA') ||
    trimmed.startsWith(MISENCODED_BULLET)
  );
};

const stripBulletPrefix = (line: string) => {
  let trimmed = line.trimStart();
  if (trimmed.startsWith(MISENCODED_BULLET)) {
    trimmed = trimmed.slice(MISENCODED_BULLET.length).trimStart();
  }
  if (/^[-*]\s+/.test(trimmed)) {
    return trimmed.replace(/^[-*]\s+/, '');
  }
  if (/^[\u2022\u25CF\u25AA]\s*/.test(trimmed)) {
    return trimmed.replace(/^[\u2022\u25CF\u25AA]\s*/, '');
  }
  return trimmed;
};

const parseSimpleMarkdownBlocks = (text: string): MarkdownBlock[] => {
  if (!text) {
    return [];
  }

  const cleaned = text
    .replace(/\r/g, '')
    .replace(new RegExp(MISENCODED_BULLET, 'g'), '- ')
    .replace(/^\s*#+\s*/gm, '')
    .replace(/^\s*---\s*$/gm, '')
    .trim();

  if (!cleaned) {
    return [];
  }

  const rawBlocks = cleaned.split(/\n{2,}/);
  const blocks: MarkdownBlock[] = [];

  rawBlocks.forEach((block) => {
    const lines = block
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    if (lines.length === 0) {
      return;
    }

    const isList = lines.every((line) => hasBulletPrefix(line));

    if (isList) {
      blocks.push({
        type: 'list',
        items: lines.map((line) => tokenizeInlineSegments(stripBulletPrefix(line))),
      });
      return;
    }

    blocks.push({
      type: 'paragraph',
      lines: lines.map((line) => tokenizeInlineSegments(line)),
    });
  });

  return blocks;
};

const renderInlineSegments = (segments: InlineSegment[], keyPrefix: string): ReactNode[] =>
  segments.map((segment, index) =>
    segment.bold ? (
      <strong key={`${keyPrefix}-strong-${index}`}>{segment.content}</strong>
    ) : (
      <Fragment key={`${keyPrefix}-text-${index}`}>{segment.content}</Fragment>
    ),
  );

const renderSimpleMarkdown = (
  text: string,
  keyPrefix: string,
  options: { paragraphClass?: string; listClass?: string } = {},
): ReactNode[] => {
  const blocks = parseSimpleMarkdownBlocks(text);
  if (blocks.length === 0) {
    return [];
  }

  return blocks.map((block, blockIndex) => {
    if (block.type === 'list') {
      return (
        <ul
          key={`${keyPrefix}-list-${blockIndex}`}
          className={options.listClass}
        >
          {block.items.map((item, itemIndex) => (
            <li key={`${keyPrefix}-list-${blockIndex}-item-${itemIndex}`}>
              {renderInlineSegments(item, `${keyPrefix}-list-${blockIndex}-item-${itemIndex}`)}
            </li>
          ))}
        </ul>
      );
    }

    const nodes: ReactNode[] = [];
    block.lines.forEach((line, lineIndex) => {
      nodes.push(
        ...renderInlineSegments(line, `${keyPrefix}-paragraph-${blockIndex}-line-${lineIndex}`),
      );
      if (lineIndex < block.lines.length - 1) {
        nodes.push(<br key={`${keyPrefix}-paragraph-${blockIndex}-br-${lineIndex}`} />);
      }
    });

    return (
      <p
        key={`${keyPrefix}-paragraph-${blockIndex}`}
        className={options.paragraphClass}
      >
        {nodes}
      </p>
    );
  });
};
const DASHBOARD_CACHE_PREFIX = 'dominion/dashboard/';
const DASHBOARD_CACHE_VERSION = 1;
const DASHBOARD_CACHE_TTL_MS = 1000 * 60 * 20; // 20 minutes

type CachedDashboardEnvelope = {
  version: number;
  savedAt: number;
  state: DashboardState;
};

const dashboardCacheKey = (projectId: string) => `${DASHBOARD_CACHE_PREFIX}${projectId}`;

const loadCachedDashboardState = (projectId: string): DashboardState | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    // First try sessionStorage (for fresh agent results)
    const sessionKey = `dominion/dashboard/${projectId}`;
    const sessionRaw = window.sessionStorage.getItem(sessionKey);
    if (sessionRaw) {
      const parsed = JSON.parse(sessionRaw) as CachedDashboardEnvelope;
      if (parsed && parsed.version === DASHBOARD_CACHE_VERSION && parsed.state) {
        console.log('[Dashboard] Loaded from sessionStorage:', projectId);
        return parsed.state;
      }
    }

    // Fallback to localStorage
    const raw = window.localStorage.getItem(dashboardCacheKey(projectId));
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as CachedDashboardEnvelope;
    if (!parsed || parsed.version !== DASHBOARD_CACHE_VERSION || !parsed.state) {
      return null;
    }
    if (Date.now() - parsed.savedAt > DASHBOARD_CACHE_TTL_MS) {
      window.localStorage.removeItem(dashboardCacheKey(projectId));
      return null;
    }
    if (parsed.state.project?.id !== projectId) {
      return null;
    }
    return parsed.state;
  } catch {
    return null;
  }
};

const persistDashboardState = (projectId: string, state: DashboardState) => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    const payload: CachedDashboardEnvelope = {
      version: DASHBOARD_CACHE_VERSION,
      savedAt: Date.now(),
      state,
    };
    window.localStorage.setItem(dashboardCacheKey(projectId), JSON.stringify(payload));
  } catch {
    // Ignore storage errors (quota, private mode, etc.)
  }
};

export const Dashboard = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState<DashboardState | null>(null);
  const [activePanel, setActivePanel] = useState<PanelKey>('report');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'globe' | 'map'>('globe');
  const [selectedMarket, setSelectedMarket] = useState<MarketMarker | null>(null);
  const [globeReady, setGlobeReady] = useState(false);
  const [introProgress, setIntroProgress] = useState(8);

  const requestedProjectId = searchParams.get('projectId') ?? undefined;
  const projectId = state?.project.id ?? requestedProjectId ?? undefined;

  useEffect(() => {
    if (!requestedProjectId) {
      setState(null);
      setError(null);
      setLoading(false);
      setGlobeReady(false);
      setIntroProgress(8);
      navigate('/projects', { replace: true });
      return;
    }

    const controller = new AbortController();
    let isActive = true;

    setGlobeReady(false);
    setError(null);

    const cachedState = loadCachedDashboardState(requestedProjectId);
    if (cachedState) {
      // Found cached data - use it directly without trying to refresh from API
      // Data comes from agent analysis stored in sessionStorage
      setState(cachedState);
      setLoading(false);
      setIntroProgress((prev) => (prev < 92 ? 92 : prev));
      console.log('[Dashboard] Using cached data, skipping API refresh');
      return; // Don't try to fetch from API
    }

    // No cached data - this shouldn't happen in normal flow
    // User should create project first which populates sessionStorage
    setState(null);
    setLoading(false);
    setError('No report found. Please create a new project first.');
    console.warn('[Dashboard] No cached data found for project:', requestedProjectId);

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [navigate, requestedProjectId]);

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

  useEffect(() => {
    if (!state?.project.id) {
      return;
    }
    setViewMode('globe');
    setSelectedMarket(null);
  }, [state?.project.id]);

  useEffect(() => {
    if (selectedMarket && viewMode !== 'map') {
      setViewMode('map');
    }
  }, [selectedMarket, viewMode]);

  useEffect(() => {
    if (!state?.project.id) {
      return;
    }
    persistDashboardState(state.project.id, state);
  }, [state]);

  const isWaitingForGlobe = Boolean(state && !globeReady);
  const targetProgress = !state ? (loading ? 72 : 12) : globeReady ? 100 : 92;

  useEffect(() => {
    if (introProgress >= targetProgress) {
      return;
    }
    const timer = window.setTimeout(() => {
      setIntroProgress((prev) => {
        if (prev >= targetProgress) {
          return prev;
        }
        const delta = targetProgress - prev;
        const increment = Math.max(1, Math.round(delta * 0.2));
        return Math.min(targetProgress, prev + increment);
      });
    }, 90);
    return () => window.clearTimeout(timer);
  }, [introProgress, targetProgress]);

  const introProjectLine = useMemo(() => {
    if (state) {
      return `${state.project.name} · ${state.project.market}`;
    }
    if (requestedProjectId) {
      return `Project ${requestedProjectId}`;
    }
    return undefined;
  }, [requestedProjectId, state]);

  const { status: introStatus, detail: introDetail, caption: introCaption } = useMemo(() => {
    const withProject = (base?: string) => {
      if (introProjectLine) {
        return base ? `${base} · ${introProjectLine}` : introProjectLine;
      }
      return base;
    };

    if (!state) {
      if (introProgress < 28) {
        return {
          status: 'Connecting to Dominion relays',
          detail: withProject('Negotiating credentials'),
          caption: 'Requesting project manifest',
        };
      }
      if (introProgress < 64) {
        return {
          status: 'Collecting market telemetry',
          detail: withProject('Streaming intelligence feeds'),
          caption: 'Awaiting data payload',
        };
      }
      return {
        status: 'Assembling command interface',
        detail: withProject('Staging dashboards'),
        caption: 'Preparing surface layout',
      };
    }

    if (!globeReady) {
      if (introProgress < 96) {
        return {
          status: 'Aligning orbital viewport',
          detail: withProject('Positioning geospatial focus'),
          caption: 'Calibrating spatial renderer',
        };
      }
      return {
        status: 'Sealing command surface',
        detail: withProject('Locking navigation controls'),
        caption: 'Finalizing interface',
      };
    }

    return {
      status: 'Dispatching command surface',
      detail: withProject('Dominion systems nominal'),
      caption: 'Ready to deploy',
    };
  }, [globeReady, introProgress, introProjectLine, state]);

  const showIntroOverlay = isWaitingForGlobe || introProgress < 100;

  const markers = useMemo(() => state?.markets ?? [], [state]);
  const primaryMarket = useMemo<MarketMarker | null>(() => {
    if (!state) {
      return null;
    }
    const byMarketCode = state.markets.find((market) => market.marketCode === state.project.marketCode);
    const byLabel = state.markets.find((market) => market.label === state.project.market);
    return byMarketCode ?? byLabel ?? state.markets[0] ?? null;
  }, [state]);
  const isMapView = viewMode === 'map' && !!selectedMarket;
  const handleGlobeReady = useCallback(() => {
    setGlobeReady(true);
  }, []);

  if (!state) {
    if (loading) {
      return (
        <div className="dashboard dashboard--ready">
          <LoadingScreen
            className="dashboard__loading-screen"
            subtitle="Command center handshake"
            status={introStatus}
            detail={introDetail}
            progress={introProgress}
            progressCaption={introCaption}
          />
        </div>
      );
    }

    return (
      <div className="dashboard dashboard--ready">
        <div className="dashboard__loading">
          <span>{error ?? 'No project data available.'}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard dashboard--ready">
      {showIntroOverlay && (
        <LoadingScreen
          className="dashboard__loading-screen"
          subtitle="Command center handshake"
          status={introStatus}
          detail={introDetail}
          progress={introProgress}
          progressCaption={introCaption}
        />
      )}
      <div className={`dashboard__backdrop${isMapView ? ' dashboard__backdrop--map' : ''}`}>
        <div className="dashboard__backdrop-layer dashboard__backdrop-layer--globe">
          <Globe
            className="dashboard__globe"
            markers={markers}
            focusMarket={selectedMarket ?? primaryMarket}
            autoRotate={false}
            onReady={handleGlobeReady}
            onMarkerSelect={(marker) => {
              const candidate =
                markers.find(
                  (item) =>
                    item.marketCode === marker.marketCode &&
                    item.location[0] === marker.location[0] &&
                    item.location[1] === marker.location[1],
                ) ?? (marker as MarketMarker);
              setSelectedMarket(candidate);
              setViewMode('map');
            }}
          />
        </div>
        {isMapView && selectedMarket && (
          <div className="dashboard__backdrop-layer dashboard__backdrop-layer--map">
            <MarketMap
              market={selectedMarket}
              className="dashboard__map"
              renderOverlay={false}
              onBack={() => {
                setViewMode('globe');
                setSelectedMarket(null);
              }}
            />
          </div>
        )}
      </div>

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
              Export JSON
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

        <section className={`dashboard__globe-stage${isMapView ? ' dashboard__globe-stage--map' : ''}`}>
          <div className="dashboard__globe-overlay">
            <span>{state.trackingDensity.label}</span>
            <strong>{state.trackingDensity.value}</strong>
          </div>
          {isMapView && (
            <div className="dashboard__focus-card">
              <div className="dashboard__focus-card-main">
                <div className="dashboard__focus-card-title">
                  <span>{state.focusCard.header}</span>
                  <span className={`dashboard__focus-card-tag dashboard__focus-card-tag--${state.focusCard.tagType}`}>
                    {state.focusCard.tag}
                  </span>
                </div>
                {renderSimpleMarkdown(state.focusCard.summary, 'focus-card-summary', {
                  paragraphClass: 'dashboard__focus-card-summary',
                  listClass: 'dashboard__focus-card-list',
                })}
              </div>
              <div className="dashboard__focus-card-stats">
                {state.focusCard.stats.map((stat) => (
                  <div key={stat.label}>
                    <span className="dashboard__focus-label">{stat.label}</span>
                    <strong>{stat.value}</strong>
                  </div>
                ))}
                <button
                  type="button"
                  className="dashboard__focus-card-back"
                  onClick={() => {
                    setViewMode('globe');
                    setSelectedMarket(null);
                  }}
                >
                  Back to globe
                </button>
              </div>
            </div>
          )}
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
                <div className="dashboard__widget-scroll">
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
                  {renderSimpleMarkdown(state.reportContent.summary, 'report-summary', {
                    paragraphClass: 'dashboard__report-summary',
                    listClass: 'dashboard__report-list',
                  })}
                  {state.reportContent.marketContext &&
                    renderSimpleMarkdown(state.reportContent.marketContext, 'report-market', {
                      paragraphClass: 'dashboard__report-market',
                      listClass: 'dashboard__report-list',
                    })}

                  <div className="dashboard__report-sections">
                    {state.reportContent.sections.map((section, sectionIndex) => (
                      <section key={section.title} className="dashboard__report-section">
                        <header>
                          <h3>{section.title}</h3>
                        </header>
                        {section.content &&
                          section.content.trim().length > 0 &&
                          renderSimpleMarkdown(section.content, `section-${sectionIndex}`, {
                            paragraphClass: 'dashboard__report-text',
                            listClass: 'dashboard__report-list',
                          })}
                        {section.list && section.list.length > 0 && (
                          <ul className="dashboard__report-list">
                            {section.list.map((item, index) => (
                              <li key={`${section.title}-item-${index}`}>
                                {renderInlineSegments(
                                  tokenizeInlineSegments(item),
                                  `${section.title}-item-${index}`,
                                )}
                              </li>
                            ))}
                          </ul>
                        )}
                        {section.metrics && section.metrics.length > 0 && (
                          <ul className="dashboard__report-metrics">
                            {section.metrics.map((metric) => (
                              <li
                                key={`${section.title}-${metric.label}`}
                                className={metric.highlight ? 'dashboard__report-metric--highlight' : ''}
                              >
                                <span>{sanitizeInlineLabel((metric.label ?? '').toString())}</span>
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
                </div>
              </>
            )}

            {activePanel === 'opportunities' && (
              <>
                <header className="dashboard__widget-header">
                  <span>Opportunity queue</span>
                  <span className="dashboard__widget-tag">Auto-ranked</span>
                </header>
                <div className="dashboard__widget-scroll">
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
                </div>
              </>
            )}

            {activePanel === 'activity' && (
              <>
                <header className="dashboard__widget-header">
                  <span>Activity log</span>
                  <span className="dashboard__widget-tag dashboard__widget-tag--accent">Tool executions</span>
                </header>
                <div className="dashboard__widget-scroll">
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
                </div>
              </>
            )}
          </article>
        </aside>
      </div>
    </div>
  );
};

