import type { DashboardState, ProjectSetup, ProjectSummary } from '../types/dashboard';
import { mockDashboardState } from '../stubs/mockDashboardState';
import { mockProjects } from '../stubs/mockProjects';

const DEFAULT_PROJECT_ID = 'proj-123';
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL?.replace(/\/$/, '') ?? '';

type FetchDashboardStateOptions = {
  projectId?: string;
  signal?: AbortSignal;
};

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value));

export async function fetchDashboardState(
  options: FetchDashboardStateOptions = {},
): Promise<DashboardState> {
  const { projectId = DEFAULT_PROJECT_ID, signal } = options;
  const endpoint = `${API_BASE_URL}/api/projects/${projectId}/report`.replace('//api', '/api');

  try {
    const response = await fetch(endpoint, { signal, headers: { Accept: 'application/json' } });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    const payload = (await response.json()) as DashboardState;
    return payload;
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('[dashboard] Falling back to mock data:', error);
    return clone(mockDashboardState);
  }
}

export type DashboardUpdateMessage =
  | {
      type: 'update_detected';
      payload: {
        update: DashboardState['latestUpdates'][number];
      };
    }
  | {
      type: 'state_refresh';
      payload: {
        state: DashboardState;
      };
    };

type ConnectLiveUpdatesOptions = {
  projectId?: string;
  onUpdate: (message: DashboardUpdateMessage) => void;
};

const WS_BASE_URL = process.env.REACT_APP_WS_BASE_URL?.replace(/\/$/, '') ?? '';

export function connectDashboardUpdates({ projectId = DEFAULT_PROJECT_ID, onUpdate }: ConnectLiveUpdatesOptions) {
  if (!WS_BASE_URL) {
    return () => {};
  }

  const url = `${WS_BASE_URL}/ws/projects/${projectId}/updates`;
  const socket = new WebSocket(url);

  socket.addEventListener('message', (event) => {
    try {
      const data = JSON.parse(event.data) as DashboardUpdateMessage;
      onUpdate(data);
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('[dashboard] Failed to parse WebSocket message', error);
    }
  });

  return () => socket.close();
}

type FetchProjectsOptions = {
  signal?: AbortSignal;
};

export async function fetchProjects(options: FetchProjectsOptions = {}): Promise<ProjectSummary[]> {
  const { signal } = options;
  const endpoint = `${API_BASE_URL}/api/projects`.replace('//api', '/api');

  try {
    const response = await fetch(endpoint, { signal, headers: { Accept: 'application/json' } });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    const payload = (await response.json()) as ProjectSummary[];
    return payload;
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('[dashboard] Falling back to mock projects:', error);
    return clone(mockProjects);
  }
}

export interface CreateProjectResponse {
  project: ProjectSummary;
}

export async function createProject(setup: ProjectSetup): Promise<CreateProjectResponse> {
  const endpoint = `${API_BASE_URL}/api/projects`.replace('//api', '/api');
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(setup),
    });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    const payload = (await response.json()) as CreateProjectResponse;
    return payload;
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('[dashboard] Falling back to mock project create:', error);
    const id = `proj-${Math.floor(Math.random() * 10000)}`;
    const now = new Date().toISOString();
    const summary: ProjectSummary = {
      id,
      name: setup.name,
      type: setup.type,
      market: setup.market,
      marketCode: setup.marketCode ?? setup.market.toLowerCase().replace(/\s+/g, '_'),
      status: 'generating',
      progress: 12,
      createdAt: now,
      lastUpdated: now,
      description:
        setup.strategy ??
        setup.entityName ??
        setup.propertyId ??
        'Dominion report is being generated with your selected scope.',
      confidence: undefined,
      opportunities: 0,
    };
    mockProjects.unshift(summary);
    return { project: summary };
  }
}
