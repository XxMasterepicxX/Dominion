import { FormEvent, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { createProject } from '../services/dashboard';
import type { ProjectSetup, ProjectType } from '../types/dashboard';
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

export const ProjectCreate = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProjectSetup>(initialSetup);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requiredFields = useMemo(() => REQUIRED_BY_TYPE[form.type] ?? [], [form.type]);

  const handleInput = (key: keyof ProjectSetup, value: unknown) => {
    setForm((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleScopeToggle = (key: keyof ProjectSetup['analysisScope']) => {
    setForm((prev) => ({
      ...prev,
      analysisScope: {
        ...prev.analysisScope,
        [key]: !prev.analysisScope[key],
      },
    }));
  };

  const handleCriteriaChange = (key: keyof NonNullable<ProjectSetup['criteria']>, value: unknown) => {
    setForm((prev) => ({
      ...prev,
      criteria: {
        ...(prev.criteria ?? {}),
        [key]: value,
      },
    }));
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
      const payload = await createProject({
        ...form,
        askingPrice: form.askingPrice ? Number(form.askingPrice) : undefined,
        budget: form.budget ? Number(form.budget) : undefined,
        criteria: {
          ...form.criteria,
          maxPrice: form.criteria?.maxPrice ? Number(form.criteria.maxPrice) : undefined,
          minPrice: form.criteria?.minPrice ? Number(form.criteria.minPrice) : undefined,
          minLotSize: form.criteria?.minLotSize ? Number(form.criteria.minLotSize) : undefined,
          maxLotSize: form.criteria?.maxLotSize ? Number(form.criteria.maxLotSize) : undefined,
        },
      });
      navigate(`/dashboard?projectId=${payload.project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create project.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="project-create">
      <header className="project-create__header">
        <div>
          <p className="project-create__eyebrow">New Dominion project</p>
          <h1>Describe the project Dominion should analyze.</h1>
          <p>
            Dominion will generate a full intelligence report and hook into live updates once the project is created.
            Fill in the scope so the agent knows exactly what to monitor.
          </p>
        </div>
        <Link className="project-create__back" to="/projects">
          ← Back to projects
        </Link>
      </header>

      <form className="project-create__form" onSubmit={handleSubmit}>
        <section className="project-create__section">
          <h2>Basics</h2>
          <div className="project-create__grid project-create__grid--two">
            <label>
              <span>Project name *</span>
              <input
                type="text"
                value={form.name}
                onChange={(event) => handleInput('name', event.target.value)}
                placeholder="D.R. Horton Gainesville strategy"
                required
              />
            </label>
            <label>
              <span>Market *</span>
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
              {!MARKET_OPTIONS.some((option) => option.code === form.marketCode) && (
                <input
                  type="text"
                  value={form.market}
                  onChange={(event) => handleInput('market', event.target.value)}
                  placeholder="City, State"
                  className="project-create__input-inline"
                />
              )}
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
        </section>

        <section className="project-create__section">
          <h2>Type-specific details</h2>
          <div className="project-create__grid project-create__grid--two">
            {(form.type === 'developer_following' || form.type === 'assemblage_investigation' || form.type === 'exit_strategy') && (
              <label>
                <span>Entity name {requiredFields.includes('entityName') ? '*' : ''}</span>
                <input
                
                  type="text"
                  value={form.entityName ?? ''}
                  onChange={(event) => handleInput('entityName', event.target.value)}
                  placeholder="D R HORTON INC"
                  required={requiredFields.includes('entityName')}
                />
              </label>
            )}

            {(form.type === 'property_acquisition' || form.type === 'price_validation') && (
              <>
                <label>
                  <span>Property ID {requiredFields.includes('propertyId') ? '*' : ''}</span>
                  <input
                    type="text"
                    value={form.propertyId ?? ''}
                    onChange={(event) => handleInput('propertyId', event.target.value)}
                    placeholder="UUID or assessor ID"
                    required={requiredFields.includes('propertyId')}
                  />
                </label>
                <label>
                  <span>Parcel ID {requiredFields.includes('parcelId') ? '*' : ''}</span>
                  <input
                    type="text"
                    value={form.parcelId ?? ''}
                    onChange={(event) => handleInput('parcelId', event.target.value)}
                    placeholder="13785-000-000"
                    required={requiredFields.includes('parcelId')}
                  />
                </label>
              </>
            )}

            {(form.type === 'price_validation' || form.type === 'property_acquisition') && (
              <label>
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
                <label>
                  <span>Max price</span>
                  <input
                    type="number"
                    min="0"
                    value={form.criteria?.maxPrice ?? ''}
                    onChange={(event) => handleCriteriaChange('maxPrice', event.target.value === '' ? undefined : Number(event.target.value))}
                    placeholder="500000"
                  />
                </label>
                <label>
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
                <label>
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
        </section>

        <section className="project-create__section">
          <h2>Analysis scope</h2>
          <p className="project-create__section-sub">
            Select the domains Dominion should prioritize. All projects include core intelligence, you can tailor the toggles to your
            strategy.
          </p>
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
        </section>

        <section className="project-create__section">
          <h2>Investment parameters</h2>
          <div className="project-create__grid project-create__grid--three">
            <label>
              <span>Budget ceiling</span>
              <input
                type="number"
                min="0"
                value={form.budget ?? ''}
                onChange={(event) => handleInput('budget', event.target.value === '' ? undefined : Number(event.target.value))}
                placeholder="5000000"
              />
            </label>
            <label>
              <span>Preferred property type</span>
              <input
                type="text"
                value={form.preferredPropertyType ?? ''}
                onChange={(event) => handleInput('preferredPropertyType', event.target.value)}
                placeholder="Multifamily, vacant land"
              />
            </label>
            <label>
              <span>Strategy</span>
              <input
                type="text"
                value={form.strategy ?? ''}
                onChange={(event) => handleInput('strategy', event.target.value)}
                placeholder="Wholesale to developer partners"
              />
            </label>
          </div>
        </section>

        {error && <p className="project-create__error">{error}</p>}

        <div className="project-create__actions">
          <button type="submit" className="project-create__submit" disabled={submitting}>
            {submitting ? 'Creating project...' : 'Create project'}
          </button>
          <span className="project-create__footnote">Reports typically generate in under a minute.</span>
        </div>
      </form>
    </div>
  );
};
