import type { DashboardState } from '../types/dashboard';

const DASHBOARD_KEY_PREFIX = 'dominion/dashboard/';

export const storeDashboardState = (projectId: string, state: DashboardState) => {
  try {
    localStorage.setItem(
      `${DASHBOARD_KEY_PREFIX}${projectId}`,
      JSON.stringify({ version: 1, savedAt: Date.now(), state }),
    );
  } catch {
    // ignore
  }
};

export const loadDashboardState = (projectId: string): DashboardState | undefined => {
  try {
    const raw = localStorage.getItem(`${DASHBOARD_KEY_PREFIX}${projectId}`);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.state) {
      return parsed.state as DashboardState;
    }
    return undefined;
  } catch {
    return undefined;
  }
};

export const deleteDashboardState = (projectId: string) => {
  try {
    localStorage.removeItem(`${DASHBOARD_KEY_PREFIX}${projectId}`);
  } catch {
    // ignore
  }
};
