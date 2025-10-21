import { Link } from 'react-router-dom';
import { StaticCanvasGlobe } from '../components/StaticCanvasGlobe';
import './Landing.css';
import { useEffect, useRef } from 'react';

const metrics = [
  { label: 'Entity resolution accuracy', value: '95%' },
  { label: 'Opportunity detection lead time', value: '3-6 weeks' },
  { label: 'Properties monitored', value: '108K' },
];

const capabilityCards = [
  {
    title: 'Create a Project',
    description:
      'Launch in under a minute. Choose your objective, load market context, and the agent immediately begins the workflow.',
    hint: 'Six project presets. Instant activation.',
  },
  {
    title: 'Agent Works 24/7',
    description:
      'Monitors permits, sales, and LLC filings continuously while reconciling fragmented ownership across every data source.',
    hint: 'Fully autonomous. Zero manual work.',
  },
  {
    title: 'Intelligence Stays Fresh',
    description:
      'Dashboards refresh the moment markets shift so developer moves, absorption swings, and new comps appear instantly.',
    hint: 'Live updates. No refresh needed.',
  },
];

const signalHighlights = [
  {
    title: 'Assemblage Detection',
    stat: '5 parcels found',
    description:
      'Detected Infinity Development LLC assembling five adjacent Gainesville parcels at 92% confidence and surfaced the remaining targets automatically.',
  },
  {
    title: 'Investment Scoring',
    stat: 'Auto-ranked 0-100',
    description:
      'Scores undervalued homes, entitled land, and long-hold owners as soon as they surface with clear reasoning for action.',
  },
  {
    title: 'Market Intelligence',
    stat: 'Live absorption',
    description:
      'Tracks inventory and absorption in real time so you know when to move fast versus negotiate carefully with daily updates.',
  },
  {
    title: 'Ordinance Search',
    stat: '2,588 sections indexed',
    description:
      'Answers zoning questions in plain English and returns cited sections instantly with no PDF digging required.',
  },
];

const useCases = [
  {
    title: 'Track Competitors',
    description:
      'Follow competitor acquisitions as soon as they close, correlate every permit and LLC, and understand the strategy before anyone else.',
  },
  {
    title: 'Find Off-Market Deals',
    description:
      'Surface motivated sellers before listings publish by combining hold periods, equity signals, and public record anomalies.',
  },
  {
    title: 'Validate Before Offering',
    description:
      'Generate comps, absorption metrics, and peer benchmarks in seconds so each offer is grounded in current market evidence.',
  },
];

const techFoundation = [
  {
    title: 'Entity Resolution',
    description:
      'Automatically unifies owners across permits, deeds, and LLC filings so fragmented records collapse into accurate relationship graphs.',
  },
  {
    title: 'Geospatial Intelligence',
    description:
      'Uses PostGIS to detect adjacent parcels, measure proximity, and flag when developers quietly assemble properties in a submarket.',
  },
  {
    title: 'Vector Search',
    description:
      'Indexes every ordinance section into a vector store so plain-language questions return cited answers without sifting lengthy PDFs.',
  },
];

const roadmapPhases = [
  {
    phase: 'Phase 1',
    status: 'Live Now',
    timeline: 'Current',
    title: 'Monitoring & Entity Intelligence',
    description:
      'Delivers continuous monitoring, catches early assemblages, and resolves messy ownership networks into ranked opportunity queues.',
  },
  {
    phase: 'Phase 2',
    status: 'In Development',
    timeline: 'Q1 2026',
    title: 'Financial Modeling & Valuation',
    description:
      'Builds dynamic cash-flow models, evaluates IRR and NPV, and stress-tests exit strategies before capital is committed.',
  },
  {
    phase: 'Phase 3',
    status: 'Planned',
    timeline: 'Q2 2026',
    title: 'Predictive Analytics & Forecasting',
    description:
      'Learns developer behavior patterns, predicts absorption twelve to twenty four months ahead, and surfaces early indicators worth watching.',
  },
  {
    phase: 'Phase 4',
    status: 'Planned',
    timeline: 'Q3-Q4 2026',
    title: 'Autonomous Decision Intelligence',
    description:
      'Produces buy, hold, and sell guidance with traceable confidence and optimizes portfolios across markets in near real time.',
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
                VIEW PROJECTS
              </Link>
              <a className="landing__cta-secondary" href="#capabilities">
                EXPLORE CAPABILITIES
              </a>
            </div>
            <div className="landing__metrics">
              {metrics.map((metric) => (
                <div key={metric.label} className="landing__metric-card">
                  <span className="landing__metric-value">{metric.value}</span>
                  <span className="landing__metric-label">{metric.label}</span>
                </div>
              ))}
            </div>
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
            <div className="landing__workflow-icon landing__workflow-icon--create">
              <span className="landing__workflow-number">1</span>
              <svg
                className="landing__workflow-symbol"
                viewBox="0 0 24 24"
                aria-hidden="true"
                focusable="false"
              >
                <path
                  d="M9 3h6l1 2h3v15H5V5h3l1-2zm3 8v5m0-5-2 2m2-2 2 2"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <span className="landing__workflow-label">Create Project</span>
          </div>
          <div className="landing__workflow-arrow" aria-hidden="true">
            <span className="landing__workflow-arrow-line" />
            <span className="landing__workflow-arrow-head" />
          </div>
          <div className="landing__workflow-step">
            <div className="landing__workflow-icon landing__workflow-icon--analyze">
              <span className="landing__workflow-number">2</span>
              <svg
                className="landing__workflow-symbol"
                viewBox="0 0 24 24"
                aria-hidden="true"
                focusable="false"
              >
                <circle cx="11" cy="11" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                <line
                  x1="14.5"
                  y1="14.5"
                  x2="19"
                  y2="19"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </div>
            <span className="landing__workflow-label">Agent Analyzes</span>
          </div>
          <div className="landing__workflow-arrow" aria-hidden="true">
            <span className="landing__workflow-arrow-line" />
            <span className="landing__workflow-arrow-head" />
          </div>
          <div className="landing__workflow-step">
            <div className="landing__workflow-icon landing__workflow-icon--update">
              <span className="landing__workflow-number">3</span>
              <svg
                className="landing__workflow-symbol"
                viewBox="0 0 24 24"
                aria-hidden="true"
                focusable="false"
              >
                <path
                  d="M6 9a6 6 0 0 1 10.2-4.2L18 7"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M18 15a6 6 0 0 1-10.2 4.2L6 17"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <polyline
                  points="18 7 18 11 14 11"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <polyline
                  points="6 17 6 13 10 13"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
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
          <div className="landing__section-heading">
            <p className="landing__eyebrow">What you get</p>
            <h2>Real patterns. Real opportunities.</h2>
            <p>
              Actual intelligence from Gainesville. Every project delivers insights like these.
            </p>
          </div>
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
          <p>
            Pick a scenario to see how Dominion guides everyday workflows for acquisition teams.
          </p>
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
        <div className="landing__tech-intro">
          <div className="landing__section-heading">
            <p className="landing__eyebrow">Technical foundation</p>
            <h2>Purpose-built for real estate intelligence.</h2>
            <p>
              These building blocks keep the agent grounded in production data and ready for scale.
            </p>
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
              <div className="landing__data-node landing__data-node--7">News</div>
              <div className="landing__data-node landing__data-node--8">City Council</div>
            </div>
          </div>
        </div>

        <div className="landing__tech-grid">
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
            Dominion's agent evolves through four distinct intelligence phases over 12 months. Each phase builds on the previous, adding deeper reasoning, forward-looking prediction, and autonomous decision-making. The system learns continuously, from entity patterns and market cycles to developer behavior and portfolio optimization strategies.
          </p>
          <div className="landing__roadmap-progress">
            <div className="landing__roadmap-progress-bar">
              <div className="landing__roadmap-progress-fill" style={{ width: '25%' }} />
            </div>
            <span className="landing__roadmap-progress-label">Phase 1 of 4 Complete - 12-month development cycle</span>
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
