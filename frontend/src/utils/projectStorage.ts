import type { ProjectSetup, ProjectSummary } from '../types/dashboard';

const SUMMARIES_KEY = 'dominion/projects/summaries';
const DRAFT_PREFIX = 'dominion/projects/draft/';

const parseSummaries = (): ProjectSummary[] => {
  try {
    const raw = localStorage.getItem(SUMMARIES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter((entry): entry is ProjectSummary => typeof entry === 'object' && entry !== null && typeof entry.id === 'string');
    }
    return [];
  } catch {
    return [];
  }
};

const storeSummaries = (summaries: ProjectSummary[]) => {
  try {
    localStorage.setItem(SUMMARIES_KEY, JSON.stringify(summaries));
  } catch {
    // ignore write errors
  }
};

export const getStoredProjectSummaries = (): ProjectSummary[] => parseSummaries();

export const upsertStoredProjectSummary = (summary: ProjectSummary) => {
  const summaries = parseSummaries();
  const index = summaries.findIndex((item) => item.id === summary.id);
  if (index >= 0) {
    summaries[index] = { ...summaries[index], ...summary };
  } else {
    summaries.push(summary);
  }
  storeSummaries(summaries);
};

export const removeStoredProjectSummary = (id: string) => {
  const summaries = parseSummaries().filter((entry) => entry.id !== id);
  storeSummaries(summaries);
};

export const saveDraftSetup = (id: string, setup: ProjectSetup) => {
  try {
    localStorage.setItem(
      `${DRAFT_PREFIX}${id}`,
      JSON.stringify({
        version: 1,
        savedAt: Date.now(),
        setup,
      }),
    );
  } catch {
    // ignore
  }
};

export const loadDraftSetup = (id: string): ProjectSetup | undefined => {
  try {
    const raw = localStorage.getItem(`${DRAFT_PREFIX}${id}`);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.setup) {
      return parsed.setup as ProjectSetup;
    }
    return undefined;
  } catch {
    return undefined;
  }
};

export const deleteDraftSetup = (id: string) => {
  try {
    localStorage.removeItem(`${DRAFT_PREFIX}${id}`);
  } catch {
    // ignore
  }
};
