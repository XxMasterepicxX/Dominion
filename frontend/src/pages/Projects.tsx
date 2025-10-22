import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchProjects } from '../services/dashboard';
import type { ProjectSummary, ProjectType, ProjectStatus } from '../types/dashboard';
import { getStoredProjectSummaries, removeStoredProjectSummary, deleteDraftSetup } from '../utils/projectStorage';
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

const cleanMarkdown = (text: string) => {
  if (!text) return '';
  
  return text
    // Remove bold markdown (**text** or __text__)
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    // Remove italic markdown (*text* or _text_)
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/_(.*?)_/g, '$1')
    // Remove headers (# ## ### etc.)
    .replace(/^#{1,6}\s+/gm, '')
    // Remove inline code (`code`)
    .replace(/`(.*?)`/g, '$1')
    // Remove strikethrough (~~text~~)
    .replace(/~~(.*?)~~/g, '$1')
    // Clean up any remaining markdown artifacts
    .replace(/[*#`~_]/g, '')
    // Clean up extra whitespace
    .replace(/\s+/g, ' ')
    .trim();
};

// Test the function with your example
// Input: "The Gainesville market presents a **buyer's opportunity** with stable trends and 8.1% absorption. However, a critical price discrepancy exists between Property Specialist ($199K) and Market Special..."
// Output: "The Gainesville market presents a buyer's opportunity with stable trends and 8.1% absorption. However, a critical price discrepancy exists between Property Specialist ($199K) and Market Special..."

export const Projects = () => {
  
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingProject, setDeletingProject] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchProjects({ signal: controller.signal })
      .then((data) => {
        // Merge with locally stored summaries (drafts, imported completes, local generating)
        const local = getStoredProjectSummaries();
        const combinedMap = new Map<string, ProjectSummary>();
        [...data, ...local].forEach((item) => {
          const existing = combinedMap.get(item.id);
          if (!existing) {
            combinedMap.set(item.id, item);
          } else {
            // Prefer the one with the most recent lastUpdated
            const existingDate = new Date(existing.lastUpdated).getTime();
            const incomingDate = new Date(item.lastUpdated).getTime();
            if (incomingDate >= existingDate) {
              combinedMap.set(item.id, { ...existing, ...item });
            }
          }
        });
        // Sort projects by lastUpdated (most recent first)
        const sortedProjects = Array.from(combinedMap.values()).sort((a, b) => {
          const dateA = new Date(a.lastUpdated).getTime();
          const dateB = new Date(b.lastUpdated).getTime();
          return dateB - dateA; // Descending order (newest first)
        });
        setProjects(sortedProjects);
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

  const handleDeleteProject = async (projectId: string, projectName: string) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${projectName}"? This action cannot be undone.`
    );
    
    if (!confirmed) return;

    setDeletingProject(projectId);
    
    try {
      // Remove from local storage
      removeStoredProjectSummary(projectId);
      deleteDraftSetup(projectId);
      
      // Remove from session storage (dashboard data)
      sessionStorage.removeItem(`dominion/dashboard/${projectId}`);
      
      // Update local state
      setProjects(prev => prev.filter(p => p.id !== projectId));
      
    } catch (err) {
      console.error('Failed to delete project:', err);
      setError('Failed to delete project. Please try again.');
    } finally {
      setDeletingProject(null);
    }
  };

  const groupedProjects = useMemo(() => {
    // Projects are already sorted by lastUpdated, so we maintain that order within each group
    const live = projects.filter((project) => project.status === 'live');
    const complete = projects.filter((project) => project.status === 'complete');
    const generating = projects.filter((project) => project.status === 'generating');
    const drafts = projects.filter((project) => project.status === 'draft');
    return { live, complete, generating, drafts };
  }, [projects]);

  return (
    <div className="projects">
      <header className="projects__header">
        <p className="projects__eyebrow">Dominion projects</p>
        <div className="projects__title-row">
          <h1>Choose a project to open its intelligence report.</h1>
          <Link className="projects__new" to="/projects/new">
            + NEW PROJECT
          </Link>
        </div>
        <p className="projects__lead">
          Each project bundles the full Dominion analysis, live update stream, and action queue for the market focus you
          define. Projects are sorted by most recently updated.
        </p>
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
                          <p>{cleanMarkdown(project.description)}</p>
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
                          {project.status === 'draft' ? (
                            <Link className="projects__open projects__open--draft" to={`/projects/new?draft=${project.id}`}>
                              Continue planning -&gt;
                            </Link>
                          ) : project.status === 'generating' ? (
                            <Link className="projects__open" to={`/dashboard?projectId=${project.id}`}>
                              View progress -&gt;
                            </Link>
                          ) : (
                            <Link className="projects__open" to={`/dashboard?projectId=${project.id}`}>
                              Open project -&gt;
                            </Link>
                          )}
                          <button
                            type="button"
                            className="projects__delete"
                            onClick={() => handleDeleteProject(project.id, project.name)}
                            disabled={deletingProject === project.id}
                            title="Delete project"
                          >
                            {deletingProject === project.id ? '...' : '×'}
                          </button>
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
