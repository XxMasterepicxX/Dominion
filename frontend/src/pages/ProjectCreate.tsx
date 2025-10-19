import { FormEvent, MouseEvent, ReactNode, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { analyzeWithAgent, transformAgentResponseToDashboard } from '../services/dashboard';
import type { ProjectSetup, ProjectType, DashboardState } from '../types/dashboard';
import { LoadingScreen } from '../components/LoadingScreen';
import './ProjectCreate.css';

const PROJECT_TYPES: Array<{ value: ProjectType; label: string; description: string }> = [
  { value: 'developer_following', label: 'Developer following', description: 'Track an entity and surface nearby moves.' },
  { value: 'property_acquisition', label: 'Property acquisition', description: 'Deep dive on a single parcel or asset.' },
  { value: 'market_research', label: 'Market research', description: 'Scan a market to surface opportunities.' },
  { value: 'price_validation', label: 'Price validation', description: 'Check if asking price aligns with comps.' },
  { value: 'assemblage_investigation', label: 'Assemblage investigation', description: 'Identify clustering and gap parcels.' },
  { value: 'exit_strategy', label: 'Exit strategy', description: 'Find buyers and disposition options.' },
];

const MARKET_OPTIONS = [
  { label: 'Gainesville, FL', code: 'gainesville_fl' },
  { label: 'Tampa, FL', code: 'tampa_fl' },
  { label: 'Jacksonville, FL', code: 'jacksonville_fl' },
  { label: 'Miami, FL', code: 'miami_fl' },
  { label: 'Orlando, FL', code: 'orlando_fl' },
];

const DEFAULT_SCOPE: ProjectSetup['analysisScope'] = {
  portfolio: true,
  patterns: true,
  geography: true,
  opportunities: true,
  market: true,
  zoning: false,
  comparables: false,
};

const initialSetup: ProjectSetup = {
  name: '',
  type: 'developer_following',
  market: MARKET_OPTIONS[0].label,
  marketCode: MARKET_OPTIONS[0].code,
  entityName: '',
  propertyId: '',
  parcelId: '',
  askingPrice: undefined,
  criteria: {},
  analysisScope: DEFAULT_SCOPE,
  budget: undefined,
  preferredPropertyType: '',
  strategy: '',
};

const REQUIRED_BY_TYPE: Partial<Record<ProjectType, Array<keyof ProjectSetup>>> = {
  developer_following: ['entityName'],
  property_acquisition: ['propertyId', 'parcelId'],
  price_validation: ['parcelId', 'askingPrice'],
};

const STAGES = [
  { id: 'overview', label: 'Overview', description: 'Name the initiative and select its profile.' },
  { id: 'focus', label: 'Focus', description: 'Dial in the specifics Dominion should pursue.' },
  { id: 'markets', label: 'Markets', description: 'Align territory, filters, and scope toggles.' },
  { id: 'notes', label: 'Ops Notes', description: 'Add any directives or nuance for the team.' },
  { id: 'launch', label: 'Launch', description: 'Review the charter before deploying.' },
] as const;

type StageId = (typeof STAGES)[number]['id'];

export const ProjectCreate = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProjectSetup>(initialSetup);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStageIndex, setCurrentStageIndex] = useState(0);
  const [hasChanges, setHasChanges] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisStatus, setAnalysisStatus] = useState<string>('Initializing...');

  const requiredFields = useMemo(() => REQUIRED_BY_TYPE[form.type] ?? [], [form.type]);
  const currentStage = STAGES[currentStageIndex];
  const isCustomMarket = useMemo(
    () => !MARKET_OPTIONS.some((option) => option.code === form.marketCode),
    [form.marketCode],
  );

  const markDirty = () => {
    setHasChanges(true);
  };

  const handleInput = (key: keyof ProjectSetup, value: unknown) => {
    markDirty();
    setForm((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleScopeToggle = (key: keyof ProjectSetup['analysisScope']) => {
    markDirty();
    setForm((prev) => ({
      ...prev,
      analysisScope: {
        ...prev.analysisScope,
        [key]: !prev.analysisScope[key],
      },
    }));
  };

  const handleCriteriaChange = (key: keyof NonNullable<ProjectSetup['criteria']>, value: unknown) => {
    markDirty();
    setForm((prev) => ({
      ...prev,
      criteria: {
        ...(prev.criteria ?? {}),
        [key]: value,
      },
    }));
  };

  const validateStage = (stageId: StageId) => {
    if (stageId === 'overview') {
      if (!form.name.trim()) {
        return 'Give this initiative a name.';
      }
      return null;
    }

    if (stageId === 'focus') {
      for (const field of requiredFields) {
        const val = form[field];
        if (val === undefined || (typeof val === 'string' && !val.trim())) {
          return 'Complete the focus details required for this profile.';
        }
      }
      if (form.askingPrice !== undefined && Number.isNaN(Number(form.askingPrice))) {
        return 'Enter a valid asking price.';
      }
      return null;
    }

    if (stageId === 'markets') {
      if (!form.market.trim()) {
        return 'Select or enter a market to align coverage.';
      }
      const numericCriteria = ['maxPrice', 'minPrice', 'minLotSize', 'maxLotSize'] as const;
      for (const key of numericCriteria) {
        const value = form.criteria?.[key];
        if (value !== undefined && Number.isNaN(Number(value))) {
          return 'Use valid numbers for the market filters.';
        }
      }
      if (form.budget !== undefined && Number.isNaN(Number(form.budget))) {
        return 'Enter a valid budget ceiling.';
      }
      return null;
    }

    return null;
  };

  const validate = () => {
    if (!form.name.trim()) {
      return 'Project name is required.';
    }
    if (!form.market.trim()) {
      return 'Market is required.';
    }
    for (const field of requiredFields) {
      const val = form[field];
      if (val === undefined || (typeof val === 'string' && !val.trim())) {
        return 'Please fill in the required fields for this project type.';
      }
    }
    if (form.askingPrice !== undefined && Number.isNaN(Number(form.askingPrice))) {
      return 'Enter a valid asking price.';
    }
    if (form.budget !== undefined && Number.isNaN(Number(form.budget))) {
      return 'Enter a valid budget.';
    }
    const numericCriteria = ['maxPrice', 'minPrice', 'minLotSize', 'maxLotSize'] as const;
    for (const key of numericCriteria) {
      const value = form.criteria?.[key];
      if (value !== undefined && Number.isNaN(Number(value))) {
        return 'Numeric filters must be valid numbers.';
      }
    }
    return null;
  };

  const goToStage = (index: number) => {
    setCurrentStageIndex(index);
    setError(null);
  };

  const handleAdvance = () => {
    const validation = validateStage(currentStage.id);
    if (validation) {
      setError(validation);
      return;
    }
    goToStage(Math.min(STAGES.length - 1, currentStageIndex + 1));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      // Generate project ID
      const projectId = `proj-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

      // Build comprehensive prompt with ALL form data
      let prompt = '';

      if (form.type === 'developer_following' && form.entityName) {
        prompt = `Analyze developer "${form.entityName}" in ${form.market}.`;
      } else if (form.type === 'property_acquisition' && form.parcelId) {
        prompt = `Analyze property ${form.parcelId} in ${form.market}.`;
        if (form.askingPrice) prompt += ` Asking price: $${form.askingPrice}.`;
      } else if (form.type === 'market_research') {
        prompt = `Find properties in ${form.market}.`;
      } else if (form.type === 'assemblage_investigation') {
        prompt = `Find assemblage opportunities in ${form.market}.`;
      } else if (form.type === 'exit_strategy' && form.entityName) {
        prompt = `Find buyers for properties owned by "${form.entityName}" in ${form.market}.`;
      } else if (form.type === 'price_validation' && form.parcelId) {
        prompt = `Validate asking price for property ${form.parcelId} in ${form.market}.`;
        if (form.askingPrice) prompt += ` Asking price: $${form.askingPrice}.`;
      } else {
        prompt = `Analyze real estate opportunities in ${form.market}.`;
      }

      // Add criteria filters
      const filters = [];
      if (form.budget) filters.push(`Budget: $${form.budget}`);
      if (form.criteria?.maxPrice) filters.push(`Max price: $${form.criteria.maxPrice}`);
      if (form.criteria?.minPrice) filters.push(`Min price: $${form.criteria.minPrice}`);
      if (form.criteria?.minLotSize) filters.push(`Min lot size: ${form.criteria.minLotSize} sqft`);
      if (form.criteria?.maxLotSize) filters.push(`Max lot size: ${ form.criteria.maxLotSize} sqft`);
      if (form.criteria?.propertyType) filters.push(`Property type: ${form.criteria.propertyType}`);
      if (form.preferredPropertyType) filters.push(`Preferred type: ${form.preferredPropertyType}`);

      if (filters.length > 0) {
        prompt += ` FILTERS: ${filters.join(', ')}.`;
      }

      // Add analysis scope preferences
      const scopeEnabled = Object.entries(form.analysisScope)
        .filter(([, enabled]) => enabled)
        .map(([key]) => key);
      if (scopeEnabled.length > 0) {
        prompt += ` FOCUS ON: ${scopeEnabled.join(', ')}.`;
      }

      // Add strategy notes last
      if (form.strategy) {
        prompt += ` NOTES: ${form.strategy}`;
      }

      console.log('[ProjectCreate] Invoking agent:', { projectId, prompt });

      // Simulate progress updates while agent processes (takes 10-20 min)
      const progressInterval = setInterval(() => {
        setAnalysisProgress(prev => Math.min(95, prev + 5)); // Max 95% until complete
      }, 30000); // Update every 30 seconds

      try {
        // Call AWS multi-agent system (this will take 10-20 minutes)
        const agentResponse = await analyzeWithAgent(prompt, projectId, undefined, (status) => {
          setAnalysisStatus(status);
        });

        clearInterval(progressInterval);
        setAnalysisProgress(100);
        setAnalysisStatus('Processing results...');

        if (!agentResponse.success) {
          throw new Error(agentResponse.error || 'Agent analysis failed');
        }

        // Transform agent response to dashboard state
        const dashboardState = transformAgentResponseToDashboard(agentResponse, form, projectId);

        // Store dashboard state in sessionStorage for immediate display
        sessionStorage.setItem(`dominion/dashboard/${projectId}`, JSON.stringify({
          version: 1,
          savedAt: Date.now(),
          state: dashboardState,
        }));

        setHasChanges(false);
        navigate(`/dashboard?projectId=${projectId}`);
      } catch (err) {
        clearInterval(progressInterval);
        throw err;
      }
    } catch (err) {
      console.error('[ProjectCreate] Error:', err);
      setError(err instanceof Error ? err.message : 'Unable to analyze project. Please try again.');
    } finally {
      setSubmitting(false);
      setAnalysisProgress(0);
      setAnalysisStatus('Initializing...');
    }
  };

  useEffect(() => {
    if (!hasChanges) {
      return;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = 'You have unsaved progress. Save before leaving?';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasChanges]);

  const handleBackToProjects = (event: MouseEvent<HTMLAnchorElement>) => {
    if (hasChanges) {
      const proceed = window.confirm('You have unsaved progress. Save before leaving?');
      if (!proceed) {
        event.preventDefault();
        return;
      }
    }
    setHasChanges(false);
  };

  const renderStage = (stageId: StageId): ReactNode => {
    if (stageId === 'overview') {
      return (
        <>
          <div className="project-create__fields project-create__fields--grid">
            <label className="project-create__field">
              <span>Initiative name *</span>
              <input
                type="text"
                value={form.name}
                onChange={(event) => handleInput('name', event.target.value)}
                placeholder="D.R. Horton Gainesville strategy"
              />
            </label>
          </div>
          <div className="project-create__type-selector">
            {PROJECT_TYPES.map((projectType) => (
              <button
                key={projectType.value}
                type="button"
                className={`project-create__type ${form.type === projectType.value ? 'project-create__type--active' : ''}`}
                onClick={() => handleInput('type', projectType.value)}
              >
                <strong>{projectType.label}</strong>
                <span>{projectType.description}</span>
              </button>
            ))}
          </div>
        </>
      );
    }

    if (stageId === 'focus') {
      return (
        <div className="project-create__fields project-create__fields--grid">
          {(form.type === 'developer_following' || form.type === 'assemblage_investigation' || form.type === 'exit_strategy') && (
            <label className="project-create__field">
              <span>Entity name {requiredFields.includes('entityName') ? '*' : ''}</span>
              <input
                type="text"
                value={form.entityName ?? ''}
                onChange={(event) => handleInput('entityName', event.target.value)}
                placeholder="D R HORTON INC"
              />
            </label>
          )}

          {(form.type === 'property_acquisition' || form.type === 'price_validation') && (
            <>
              <label className="project-create__field">
                <span>Property ID {requiredFields.includes('propertyId') ? '*' : ''}</span>
                <input
                  type="text"
                  value={form.propertyId ?? ''}
                  onChange={(event) => handleInput('propertyId', event.target.value)}
                  placeholder="UUID or assessor ID"
                />
              </label>
              <label className="project-create__field">
                <span>Parcel ID {requiredFields.includes('parcelId') ? '*' : ''}</span>
                <input
                  type="text"
                  value={form.parcelId ?? ''}
                  onChange={(event) => handleInput('parcelId', event.target.value)}
                  placeholder="13785-000-000"
                />
              </label>
            </>
          )}

          {(form.type === 'price_validation' || form.type === 'property_acquisition') && (
            <label className="project-create__field">
              <span>Asking price</span>
              <input
                type="number"
                min="0"
                value={form.askingPrice ?? ''}
                onChange={(event) => handleInput('askingPrice', event.target.value === '' ? undefined : Number(event.target.value))}
                placeholder="250000"
              />
            </label>
          )}

          {(form.type === 'market_research' || form.type === 'assemblage_investigation') && (
            <>
              <label className="project-create__field">
                <span>Max price</span>
                <input
                  type="number"
                  min="0"
                  value={form.criteria?.maxPrice ?? ''}
                  onChange={(event) => handleCriteriaChange('maxPrice', event.target.value === '' ? undefined : Number(event.target.value))}
                  placeholder="500000"
                />
              </label>
              <label className="project-create__field">
                <span>Min lot size (sqft)</span>
                <input
                  type="number"
                  min="0"
                  value={form.criteria?.minLotSize ?? ''}
                  onChange={(event) =>
                    handleCriteriaChange('minLotSize', event.target.value === '' ? undefined : Number(event.target.value))
                  }
                  placeholder="8000"
                />
              </label>
              <label className="project-create__field">
                <span>Property type</span>
                <input
                  type="text"
                  value={form.criteria?.propertyType ?? ''}
                  onChange={(event) => handleCriteriaChange('propertyType', event.target.value)}
                  placeholder="Vacant land"
                />
              </label>
            </>
          )}
        </div>
      );
    }

    if (stageId === 'markets') {
      return (
        <>
          <div className="project-create__fields project-create__fields--grid">
            <label className="project-create__field">
              <span>Primary market *</span>
              <select
                value={form.marketCode ?? ''}
                onChange={(event) => {
                  const selected = MARKET_OPTIONS.find((option) => option.code === event.target.value);
                  if (selected) {
                    handleInput('market', selected.label);
                    handleInput('marketCode', selected.code);
                  } else {
                    handleInput('marketCode', undefined);
                  }
                }}
              >
                {MARKET_OPTIONS.map((option) => (
                  <option key={option.code} value={option.code}>
                    {option.label}
                  </option>
                ))}
                <option value="">Custom...</option>
              </select>
              {isCustomMarket && (
                <input
                  type="text"
                  value={form.market}
                  onChange={(event) => handleInput('market', event.target.value)}
                  placeholder="City, State"
                  className="project-create__input-inline"
                />
              )}
            </label>
            <label className="project-create__field">
              <span>Budget ceiling</span>
              <input
                type="number"
                min="0"
                value={form.budget ?? ''}
                onChange={(event) => handleInput('budget', event.target.value === '' ? undefined : Number(event.target.value))}
                placeholder="5000000"
              />
            </label>
            <label className="project-create__field">
              <span>Preferred property type</span>
              <input
                type="text"
                value={form.preferredPropertyType ?? ''}
                onChange={(event) => handleInput('preferredPropertyType', event.target.value)}
                placeholder="Multifamily, vacant land"
              />
            </label>
          </div>
          <div className="project-create__scope">
            <p>Toggle the intelligence domains Dominion should emphasize.</p>
            <div className="project-create__scope-grid">
              {Object.entries(form.analysisScope).map(([key, value]) => (
                <label key={key} className={`project-create__toggle ${value ? 'project-create__toggle--active' : ''}`}>
                  <input
                    type="checkbox"
                    checked={Boolean(value)}
                    onChange={() => handleScopeToggle(key as keyof ProjectSetup['analysisScope'])}
                  />
                  <span>{key.replace(/([A-Z])/g, ' $1').toLowerCase()}</span>
                </label>
              ))}
            </div>
          </div>
        </>
      );
    }

    if (stageId === 'notes') {
      return (
        <div className="project-create__ops-notes">
          <label className="project-create__field">
            <span>Ops notes</span>
            <textarea
              value={form.strategy ?? ''}
              onChange={(event) => handleInput('strategy', event.target.value)}
              placeholder="Add nuance, partner expectations, constraints, or any intel Dominion should weigh while monitoring."
            />
          </label>
        </div>
      );
    }

    const summaryItems = [
      { label: 'Initiative', value: form.name || 'Not set' },
      { label: 'Profile', value: PROJECT_TYPES.find((item) => item.value === form.type)?.label ?? form.type },
      { label: 'Market', value: form.market || 'Not set' },
      {
        label: 'Focus',
        value:
          form.type === 'developer_following'
            ? form.entityName || 'Entity pending'
            : form.type === 'property_acquisition' || form.type === 'price_validation'
            ? form.parcelId || form.propertyId || 'Parcel pending'
            : form.type === 'market_research' || form.type === 'assemblage_investigation'
            ? form.criteria?.propertyType || 'Criteria pending'
            : form.preferredPropertyType || 'Detail pending',
      },
      {
        label: 'Scope',
        value: Object.entries(form.analysisScope)
          .filter(([, value]) => value)
          .map(([key]) => key.replace(/([A-Z])/g, ' $1').toLowerCase())
          .join(', ')
          .replace(/(^|, )\w/g, (match) => match.toUpperCase()) || 'Using default coverage',
      },
      {
        label: 'Budget',
        value: form.budget ? `$${Number(form.budget).toLocaleString()}` : 'Not provided',
      },
    ];

    return (
      <div className="project-create__summary">
        <div className="project-create__summary-grid">
          {summaryItems.map((item) => (
            <div key={item.label} className="project-create__summary-item">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
        <div className="project-create__summary-notes">
          <span>Ops notes</span>
          <p>{form.strategy ? form.strategy : 'No additional guidance provided.'}</p>
        </div>
      </div>
    );
  };

  const canMoveBackward = currentStageIndex > 0;
  const onBack = () => {
    if (canMoveBackward) {
      goToStage(currentStageIndex - 1);
    }
  };

  // Show loading screen while agent is processing
  if (submitting) {
    return (
      <LoadingScreen
        title="Multi-Agent Analysis"
        subtitle="AWS Bedrock AgentCore"
        status={analysisStatus}
        detail={`Analyzing ${form.market} real estate opportunities · ${form.type.replace(/_/g, ' ')}`}
        progress={analysisProgress}
        progressCaption={`Session: ${form.name.substring(0, 30)}...`}
        accentLabel="Dominion Intelligence"
      />
    );
  }

  return (
    <div className="project-create">
      <header className="project-create__masthead">
        <p className="project-create__eyebrow">New Dominion project</p>
        <div className="project-create__title-row">
          <h1>Charter a fresh intelligence initiative.</h1>
          <Link className="project-create__back" to="/projects" onClick={handleBackToProjects}>
            {'<< BACK TO PROJECTS'}
          </Link>
        </div>
        <p className="project-create__intro">
          Step through the briefing, tune the focus, and Dominion will assemble the data fabric that aligns with your objective.
        </p>
      </header>

      <div className="project-create__shell">
        <aside className="project-create__side">
          <div className="project-create__side-heading">
            <span>Charter stages</span>
          </div>
          <ol className="project-create__timeline">
            {STAGES.map((stage, index) => {
              const status =
                index < currentStageIndex ? 'complete' : index === currentStageIndex ? 'active' : ('upcoming' as const);
              return (
                <li key={stage.id} className={`project-create__timeline-item project-create__timeline-item--${status}`}>
                  <button
                    type="button"
                    onClick={() => {
                      if (index <= currentStageIndex) {
                        goToStage(index);
                      }
                    }}
                    className="project-create__timeline-button"
                  >
                    <span className="project-create__timeline-dot" aria-hidden="true" />
                    <div>
                      <strong>{stage.label}</strong>
                      <p>{stage.description}</p>
                    </div>
                  </button>
                </li>
              );
            })}
          </ol>
          <div className="project-create__side-summary">
            <span>Current snapshot</span>
            <p>{form.name ? form.name : 'Awaiting details'}</p>
            <p className="project-create__side-summary-sub">
              {form.market ? form.market : 'Market to be set'} |{' '}
              {PROJECT_TYPES.find((item) => item.value === form.type)?.label ?? 'Profile pending'}
            </p>
          </div>
        </aside>

        <form className="project-create__panel" onSubmit={handleSubmit}>
          <div className="project-create__panel-header">
            <span>
              Stage {currentStageIndex + 1} of {STAGES.length}
            </span>
            <h2>{currentStage.label}</h2>
            <p>{currentStage.description}</p>
          </div>

          <div className="project-create__panel-body">{renderStage(currentStage.id)}</div>

          {error && <p className="project-create__error">{error}</p>}

          <div className="project-create__panel-actions">
            <button type="button" className="project-create__ghost" onClick={onBack} disabled={!canMoveBackward}>
              Back
            </button>
            {currentStage.id !== 'launch' ? (
              <button type="button" className="project-create__primary" onClick={handleAdvance}>
                Continue
              </button>
            ) : (
              <button type="submit" className="project-create__primary" disabled={submitting}>
                {submitting ? 'Deploying...' : 'Launch project'}
              </button>
            )}
          </div>
          {currentStage.id !== 'launch' && (
            <p className="project-create__footnote">You'll get a reminder before leaving without launching.</p>
          )}
        </form>
      </div>
    </div>
  );
};

export default ProjectCreate;
