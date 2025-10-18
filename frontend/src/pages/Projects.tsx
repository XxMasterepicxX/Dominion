import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchProjects } from '../services/dashboard';
import type { ProjectSummary, ProjectType, ProjectStatus } from '../types/dashboard';
import './Projects.css';

const TYPE_LABELS: Record<ProjectType, string> = {
  developer_following: 'Developer following',
  property_acquisition: 'Property acquisition',
  market_research: 'Market research',
  price_validation: 'Price validation',
  assemblage_investigation: 'Assemblage investigation',
  exit_strategy: 'Exit strategy',
};

const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: 'Draft',
  generating: 'Generating',
  complete: 'Complete',
  live: 'Live updates',
};

const formatDate = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};

const formatConfidence = (value?: number) => {
  if (typeof value !== 'number') return '--';
  return `${Math.round(value * 100)}%`;
};

const formatProgress = (progress: number) => Math.min(100, Math.max(0, Math.round(progress)));

export const Projects = () => {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchProjects({ signal: controller.signal })
      .then((data) => {
        setProjects(data);
        setError(null);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError('Unable to load projects.');
        }
      })
      .finally(() => {
        setLoading(false);
      });

    return () => controller.abort();
  }, []);

  const groupedProjects = useMemo(() => {
    const live = projects.filter((project) => project.status === 'live');
    const complete = projects.filter((project) => project.status === 'complete');
    const generating = projects.filter((project) => project.status === 'generating');
    const drafts = projects.filter((project) => project.status === 'draft');
    return { live, complete, generating, drafts };
  }, [projects]);

  return (
    <div className="projects">
      <header className="projects__header">
        {/* changed the classname for the div right below */}
        <div className="projects__header-text">
          <p className="projects__eyebrow">Dominion projects</p>
          <h1>Choose a project to open its intelligence report.</h1>
          <p className="projects__lead">
            Each project bundles the full Dominion analysis, live update stream, and action queue for the market focus
            you define.
          </p>
        </div>
        <div className="projects__header-actions">
          <Link className="projects__new" to="/projects/new">
            + New project
          </Link>
          <span className="projects__hint">Create a project to generate a Dominion report.</span>
        </div>
      </header>

      {loading && (
        <section className="projects__state">
          <span className="projects__spinner" aria-hidden="true" />
          <p>Loading projects...</p>
        </section>
      )}

      {error && !loading && (
        <section className="projects__state projects__state--error">
          <p>{error}</p>
        </section>
      )}

      {!loading && !error && projects.length === 0 && (
        <section className="projects__state">
          <p>No projects yet. Create one to generate your first Dominion report.</p>
        </section>
      )}

      {!loading && !error && projects.length > 0 && (
        <div className="projects__sections">
          {Object.entries(groupedProjects).map(([groupName, entries]) => {
            if (entries.length === 0) return null;
            const labelMap: Record<string, string> = {
              live: 'Live updates',
              complete: 'Completed reports',
              generating: 'In progress',
              drafts: 'Drafts',
            };
            return (
              <section key={groupName} className="projects__section">
                <header className="projects__section-header">
                  <h2>{labelMap[groupName] ?? groupName}</h2>
                  <span>{entries.length} project{entries.length === 1 ? '' : 's'}</span>
                </header>
                <div className="projects__grid">
                  {entries.map((project) => {
                    const progress = formatProgress(project.progress);
                    return (
                      <article key={project.id} className="projects__card">
                        <header className="projects__card-header">
                          <div className="projects__tags">
                            <span>{TYPE_LABELS[project.type]}</span>
                            <span>{project.market}</span>
                          </div>
                          <span className={`projects__status projects__status--${project.status}`}>
                            {STATUS_LABELS[project.status]}
                          </span>
                        </header>
                        <div className="projects__card-body">
                          <h3>{project.name}</h3>
                          <p>{project.description}</p>
                        </div>
                        <dl className="projects__meta">
                          <div>
                            <dt>Last updated</dt>
                            <dd>{formatDate(project.lastUpdated)}</dd>
                          </div>
                          <div>
                            <dt>Confidence</dt>
                            <dd>{formatConfidence(project.confidence)}</dd>
                          </div>
                          <div>
                            <dt>Opportunities</dt>
                            <dd>{typeof project.opportunities === 'number' ? project.opportunities : '--'}</dd>
                          </div>
                        </dl>
                        <div className="projects__progress">
                          <label htmlFor={`progress-${project.id}`}>Progress</label>
                          <div className="projects__progress-bar" id={`progress-${project.id}`}>
                            <span style={{ width: `${progress}%` }} aria-hidden="true" />
                          </div>
                          <span className="projects__progress-value">{progress}%</span>
                        </div>
                        <footer className="projects__card-footer">
                          <Link className="projects__open" to={`/dashboard?projectId=${project.id}`}>
                            Open project -&gt;
                          </Link>
                        </footer>
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
};
