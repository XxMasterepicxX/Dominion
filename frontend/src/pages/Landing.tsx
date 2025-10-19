import { Link } from 'react-router-dom';
import { StaticCanvasGlobe } from '../components/StaticCanvasGlobe';
import './Landing.css';
import { useEffect, useRef } from 'react';

const metrics = [
  { label: 'AI agent uptime', value: '24/7' },
  { label: 'Entity resolution accuracy', value: '95%' },
  { label: 'Opportunity detection lead time', value: '3-6 weeks' },
  { label: 'Properties monitored', value: '108K'}
];

const capabilityCards = [
  {
    title: 'Create a Project',
    description:
      '30 seconds to start. Track D.R. Horton acquisitions. Find assemblages forming. Research markets. Validate pricing. Pick your objective, execution happens automatically.',
    hint: 'Six project types. Instant activation.',
  },
  {
    title: 'Agent Works 24/7',
    description:
      'Monitors permits, sales, LLCs, and filings continuously. Links fragmented ownership records across databases. Reveals hidden patterns as they emerge.',
    hint: 'Fully autonomous. Zero manual work.',
  },
  {
    title: 'Intelligence Stays Fresh',
    description:
      'Dashboard updates when conditions change. Developer assembles parcels? Reflected immediately. Absorption accelerates? You see it. Always current, never outdated.',
    hint: 'Live updates. No refresh needed.',
  },
];

const signalHighlights = [
  {
    title: 'Assemblage Detection',
    stat: '5 parcels found',
    description: 'Caught Infinity Development LLC buying five neighboring lots in SW Gainesville before anyone noticed. Connected permits, deeds, and LLC filings at 92% confidence. Flagged remaining acquisition opportunities.',
  },
  {
    title: 'Investment Scoring',
    stat: 'Auto-ranked 0-100',
    description:
      'Properties scored the moment they surface. Homes 20% undervalued. Vacant lots zoned for development. Owners who held 20+ years. Automatically found, ranked, and explained.',
  },
  {
    title: 'Market Intelligence',
    stat: 'Live absorption',
    description:
      'Know when to lowball and when to move fast. Tracks inventory, calculates absorption, classifies buyer vs seller markets. Professional metrics updated daily.',
  },
  {
    title: 'Ordinance Search',
    stat: '2,588 sections indexed',
    description: 'Ask about setbacks in plain English. Get answers with citations in seconds. Every zoning code across Gainesville searchable instantly. No PDF hunting required.',
  },
];

const useCases = [
  {
    title: 'Track Competitors',
    description: 'Monitor every property D.R. Horton acquires the moment it closes. Every permit filed. Every LLC formed. Understand their strategy before your competition does.'
  },
  {
    title: 'Find Off-Market Deals',
    description: 'Surface motivated sellers before they list. Long-hold owners. High equity plays. Undervalued properties identified automatically from public records and ownership patterns.'
  },
  {
    title: 'Validate Before Offering',
    description: 'Stop overpaying. Pulls comps, calculates absorption, benchmarks against similar properties. Know true market value before making an offer.'
  },
];

const techFoundation = [
  {
    title: 'Entity Resolution',
    description: 'Matching owners across permits, sales, and LLCs is complex. Same company appearing as different names gets linked automatically with 95% accuracy. Fragments become ownership networks.'
  },
  {
    title: 'Geospatial Intelligence',
    description: 'Finding adjacent parcels requires spatial reasoning. PostGIS identifies assemblages, calculates distances, and flags when entities control neighboring properties. Geography becomes actionable data.'
  },
  {
    title: 'Vector Search',
    description: 'Zoning codes live in hundred-page PDFs. Every section indexed with embeddings for semantic search. Ask "what are the setback requirements" in plain English, get cited answers instantly.'
  },
];

const roadmapPhases = [
  {
    phase: 'Phase 1',
    status: 'Live Now',
    timeline: 'Current',
    title: 'Monitoring & Entity Intelligence',
    description: `Continuous property monitoring. Identifies assemblages, resolves fragmented ownership, ranks investment opportunities.`,
  },
  {
    phase: 'Phase 2',
    status: 'In Development',
    timeline: 'Q1 2025',
    title: 'Financial Modeling & Valuation',
    description: `Builds DCF models, calculates IRR/NPV, runs sensitivity analysis. Evaluates exit strategies and return projections.`,
  },
  {
    phase: 'Phase 3',
    status: 'Planned',
    timeline: 'Q2 2025',
    title: 'Predictive Analytics & Forecasting',
    description: `Forecasts market movements 12-24 months ahead. Learns developer behavior patterns, predicts absorption rates, identifies leading indicators.`,
  },
  {
    phase: 'Phase 4',
    status: 'Planned',
    timeline: 'Q3-Q4 2025',
    title: 'Autonomous Decision Intelligence',
    description: `Delivers buy/hold/sell recommendations with confidence scores. Optimizes portfolios across submarkets and times market cycles.`,
  },
];

export const Landing = () => {
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('landing__animate-in');
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -100px 0px' }
    );

    const elements = document.querySelectorAll('.landing__observe');
    elements.forEach((el) => observerRef.current?.observe(el));

    return () => observerRef.current?.disconnect();
  }, []);

  return (
    <div className="landing">
      <section className="landing__hero">
        <div className="landing__hero-glow" />
        <div className="landing__hero-inner">
          <div className="landing__hero-copy">
            <p className="landing__eyebrow">AI agent for real estate intelligence</p>
            <h1>Anticipate real estate moves before they materialise.</h1>
            <p className="landing__subtext">
              Autonomous intelligence monitoring 108,000 properties across Gainesville. Identifies assemblages forming. Spots market shifts. Updates continuously. Zero manual work.
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

      <section className="landing__section landing__observe" id="capabilities">
        <div className="landing__section-heading">
          <p className="landing__eyebrow">How it works</p>
          <h2>Launch once. Intelligence runs continuously.</h2>
          <p>
            Create your project. The agent takes over. You focus on deals. It monitors markets.
          </p>
        </div>

        <div className="landing__workflow-visual landing__observe">
          <div className="landing__workflow-step">
            <div className="landing__workflow-icon landing__workflow-icon--create">1</div>
            <span className="landing__workflow-label">Create Project</span>
          </div>
          <div className="landing__workflow-arrow">→</div>
          <div className="landing__workflow-step">
            <div className="landing__workflow-icon landing__workflow-icon--analyze">2</div>
            <span className="landing__workflow-label">Agent Analyzes</span>
          </div>
          <div className="landing__workflow-arrow">→</div>
          <div className="landing__workflow-step">
            <div className="landing__workflow-icon landing__workflow-icon--update">3</div>
            <span className="landing__workflow-label">Continuous Updates</span>
          </div>
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

      <section className="landing__section landing__section--split landing__observe" id="signals">
        <div className="landing__split-copy">
          <p className="landing__eyebrow">What you get</p>
          <h2>Real patterns. Real opportunities.</h2>
          <p>
            Actual intelligence from Gainesville. Every project delivers insights like these.
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
                <span>Gainesville, FL</span>
                <strong>108K properties</strong>
              </div>
              <div className="landing__visual-globe-node landing__visual-globe-node--north" />
              <div className="landing__visual-globe-node landing__visual-globe-node--west" />
              <div className="landing__visual-globe-node landing__visual-globe-node--south" />
            </div>
            <div className="landing__visual-readout">
              <div className="landing__visual-readout-item">
                <span className="landing__visual-readout-label">Entity resolution</span>
                <div className="landing__visual-readout-bar">
                  <span style={{ width: '95%' }} />
                </div>
                <span className="landing__visual-readout-meta">95% accuracy</span>
              </div>
              <div className="landing__visual-readout-item">
                <span className="landing__visual-readout-label">Entities tracked</span>
                <span className="landing__visual-readout-value">89,189</span>
              </div>
              <div className="landing__visual-readout-item">
                <span className="landing__visual-readout-label">Ordinance sections</span>
                <span className="landing__visual-readout-value landing__visual-readout-value--accent">2,588</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="landing__section landing__section--compact landing__observe">
        <div className="landing__section-heading">
          <p className="landing__eyebrow">Use cases</p>
          <h2>What you can do with it.</h2>
        </div>
        <div className="landing__grid">
          {useCases.map((useCase) => (
            <article key={useCase.title} className="landing__card">
              <h3>{useCase.title}</h3>
              <p>{useCase.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing__section landing__section--dark landing__observe">
        <div className="landing__section-heading">
          <p className="landing__eyebrow">Technical foundation</p>
          <h2>Purpose-built for real estate intelligence.</h2>
        </div>

        <div className="landing__data-visual landing__observe">
          <div className="landing__data-center">
            <div className="landing__data-core">Agent</div>
            <div className="landing__data-ring"></div>
          </div>
          <div className="landing__data-sources">
            <div className="landing__data-node landing__data-node--1">Permits</div>
            <div className="landing__data-node landing__data-node--2">Property Sales</div>
            <div className="landing__data-node landing__data-node--3">LLC Filings</div>
            <div className="landing__data-node landing__data-node--4">Ordinances</div>
            <div className="landing__data-node landing__data-node--5">GIS Data</div>
            <div className="landing__data-node landing__data-node--6">Ownership</div>
          </div>
        </div>

        <div className="landing__grid">
          {techFoundation.map((tech) => (
            <article key={tech.title} className="landing__card landing__card--transparent">
              <h3>{tech.title}</h3>
              <p>{tech.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing__section landing__section--roadmap landing__observe">
        <div className="landing__section-heading">
          <p className="landing__eyebrow">Intelligence Roadmap</p>
          <h2>From reactive monitoring to autonomous decision intelligence.</h2>
          <p>
            Dominion's agent evolves through four distinct intelligence phases over 12 months. Each phase builds on the previous, adding deeper reasoning, forward-looking prediction, and autonomous decision-making. The system learns continuously—from entity patterns and market cycles to developer behavior and portfolio optimization strategies.
          </p>
          <div className="landing__roadmap-progress">
            <div className="landing__roadmap-progress-bar">
              <div className="landing__roadmap-progress-fill" style={{ width: '25%' }} />
            </div>
            <span className="landing__roadmap-progress-label">Phase 1 of 4 Complete • 12-month development cycle</span>
          </div>
        </div>
        <div className="landing__roadmap">
          {roadmapPhases.map((phase, index) => (
            <div
              key={phase.phase}
              className={`landing__roadmap-phase ${index === 0 ? 'landing__roadmap-phase--active' : ''}`}
              data-phase={index + 1}
            >
              <div className="landing__roadmap-header">
                <span className="landing__roadmap-status">{phase.status}</span>
                <span className="landing__roadmap-timeline">{phase.timeline}</span>
              </div>
              <h3>{phase.title}</h3>
              <p className="landing__roadmap-description">{phase.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing__section landing__cta-panel">
        <div className="landing__cta-panel-inner">
          <div>
            <p className="landing__eyebrow">Ready to start</p>
            <h2>Stop researching manually. Start knowing automatically.</h2>
            <p>
              Create a project in 30 seconds. First report generates instantly. Agent monitors continuously. Intelligence updates automatically.
            </p>
          </div>
          <Link className="landing__cta-primary landing__cta-primary--large" to="/projects">
            Create your first project
          </Link>
        </div>
      </section>
    </div>
  );
};
