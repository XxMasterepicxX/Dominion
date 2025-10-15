import type { DashboardState } from '../types/dashboard';
import { mockDashboardState } from '../stubs/mockDashboardState';

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
