import type { DashboardState, ProjectSetup, ProjectSummary } from '../types/dashboard';
import { mockDashboardState } from '../stubs/mockDashboardState';
import { mockProjects } from '../stubs/mockProjects';

const DEFAULT_PROJECT_ID = 'proj-123';
// Vite exposes env vars on import.meta.env in the browser; fall back to process.env for node environments
const getEnv = (key: string) => (typeof (import.meta as any) !== 'undefined' ? (import.meta as any).env?.[key] : (process as any)?.env?.[key]);
const API_BASE_URL = (getEnv('REACT_APP_API_BASE_URL') as string | undefined)?.replace(/\/$/, '') ?? '';

// AWS AgentCore endpoint (Lambda Function URL - now public for demo)
const AGENT_URL = (getEnv('VITE_AGENT_URL') as string | undefined) || '';

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

const WS_BASE_URL = (getEnv('REACT_APP_WS_BASE_URL') as string | undefined)?.replace(/\/$/, '') ?? '';

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

/**
 * Agent response from AWS Lambda
 */
export interface AgentResponse {
  success: boolean;
  message: string;  // Text response from Supervisor agent
  architecture: string;
  supervisor: string;
  specialists: number;
  session_id: string;
  error?: string;
  structured_data?: {
    properties?: Array<{
      parcel_id: string;
      address: string;
      latitude: number;
      longitude: number;
    }>;
    developers?: Array<{
      name: string;
    }>;
    recommendation?: string;
    confidence?: number;
  };
}

/**
 * Invoke AWS multi-agent system for real estate analysis
 *
 * @param prompt - Natural language query describing the project
 * @param projectId - Project/session identifier
 * @param signal - AbortSignal for cancellation
 * @returns Agent analysis as text message
 */
export async function analyzeWithAgent(
  prompt: string,
  projectId: string,
  signal?: AbortSignal,
  onProgress?: (status: string) => void
): Promise<AgentResponse> {
  try {
    console.log('[Agent] Invoking multi-agent system:', { prompt, projectId });

    if (onProgress) onProgress('Connecting to agent...');

    // Add timeout wrapper (30 minutes = double Lambda's 15-min limit for safety)
    const timeoutMs = 30 * 60 * 1000; // 30 minutes
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    // Combine user abort signal with timeout
    const combinedSignal = signal || controller.signal;

    try {
      if (onProgress) onProgress('Agent analyzing (10-20 minutes)...');

      const response = await fetch(AGENT_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          prompt: prompt,
          session_id: projectId,
        }),
        signal: combinedSignal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new Error(`Agent request failed: ${response.status} - ${errorText}`);
      }

      const agentResponse = (await response.json()) as AgentResponse;

      console.log('[Agent] Analysis complete:', {
        success: agentResponse.success,
        session_id: agentResponse.session_id,
        message_length: agentResponse.message?.length || 0,
        has_structured_data: !!agentResponse.structured_data,
        properties_count: agentResponse.structured_data?.properties?.length || 0,
      });

      if (onProgress) onProgress('Analysis complete!');

      return agentResponse;
    } catch (fetchError) {
      clearTimeout(timeoutId);

      // Provide better error messages
      if (fetchError instanceof Error && fetchError.name === 'AbortError') {
        throw new Error('Agent analysis timed out after 30 minutes. The request has been cancelled. Please check CloudWatch logs or try again with a simpler query.');
      }
      throw fetchError;
    }
  } catch (error) {
    console.error('[Agent] Request failed:', error);
    throw error;
  }
}

/**
 * Get coordinates for a market/city
 * TODO: Fetch actual properties from Intelligence Lambda when it has a public URL
 * For now, returns city center coordinates
 */
function getMarketCoordinates(market: string): [number, number] {
  const cityLower = market.toLowerCase();
  if (cityLower.includes('gainesville')) return [29.6516, -82.3248];
  if (cityLower.includes('tampa')) return [27.9506, -82.4572];
  if (cityLower.includes('jacksonville')) return [30.3322, -81.6557];
  if (cityLower.includes('miami')) return [25.7617, -80.1918];
  if (cityLower.includes('orlando')) return [28.5383, -81.3792];
  return [0, 0];  // Default fallback
}

/**
 * Transform agent text response into DashboardState
 *
 * The agent returns a text analysis. We parse it to extract:
 * - Recommendation (BUY/PASS)
 * - Confidence score
 * - Property list
 * - Developer list
 * - Market insights
 */
export function transformAgentResponseToDashboard(
  agentResponse: AgentResponse,
  setup: ProjectSetup,
  projectId: string
): DashboardState {
  const now = new Date().toISOString();
  const message = agentResponse.message || '';

  // Parse recommendation from message
  const isBuyRecommendation = message.toUpperCase().includes('BUY') &&
                              !message.toUpperCase().includes('DO NOT BUY') &&
                              !message.toUpperCase().includes('PASS');

  // Extract confidence (look for patterns like "confidence: 75%" or "75% confidence")
  const confidenceMatch = message.match(/(?:confidence|conf)[:\s]+(\d+)%/i) ||
                         message.match(/(\d+)%\s+confidence/i);
  const confidence = confidenceMatch ? parseFloat(confidenceMatch[1]) / 100 : 0.5;

  // Extract key numbers from message
  const propertiesMatch = message.match(/(\d+)\s+(?:properties|property)/i);
  const developersMatch = message.match(/(\d+)\s+(?:developers|developer|entities|entity)/i);

  const propertiesFound = propertiesMatch ? parseInt(propertiesMatch[1]) : 0;
  const developersFound = developersMatch ? parseInt(developersMatch[1]) : 0;

  // Create summary from first paragraph or first 200 chars
  const firstParagraph = message.split('\n\n')[0] || message.substring(0, 200);

  // Build markets array from structured data (if available) or fallback to city center
  const structuredProps = agentResponse.structured_data?.properties || [];
  const markets = structuredProps.length > 0
    ? structuredProps.map(prop => ({
        location: [prop.longitude, prop.latitude] as [number, number],
        size: 0.08,
        label: prop.address,
        marketCode: setup.marketCode || setup.market.toLowerCase().replace(/\s+/g, '_'),
        properties: 1,
        entities: developersFound,
        activeEntities: 0,
        confidence,
        confidenceLabel: confidence > 0.66 ? 'High' : confidence > 0.33 ? 'Medium' : 'Low',
      }))
    : [
        {
          location: getMarketCoordinates(setup.market),
          size: 0.15,
          label: setup.market,
          marketCode: setup.marketCode || setup.market.toLowerCase().replace(/\s+/g, '_'),
          properties: propertiesFound,
          entities: developersFound,
          activeEntities: Math.floor(developersFound * 0.6),
          confidence,
          confidenceLabel: confidence > 0.66 ? 'High' : confidence > 0.33 ? 'Medium' : 'Low',
        },
      ];

  return {
    project: {
      id: projectId,
      name: setup.name,
      type: setup.type,
      market: setup.market,
      marketCode: setup.marketCode || setup.market.toLowerCase().replace(/\s+/g, '_'),
      generatedAt: now,
      lastUpdated: now,
      isLive: false,
      updateCount: 1,
      confidence,
      opportunities: isBuyRecommendation ? Math.max(propertiesFound, 1) : 0,
    },
    latestUpdates: [
      {
        id: `update-${Date.now()}`,
        title: 'AI Analysis Complete',
        detail: isBuyRecommendation
          ? `Found ${propertiesFound} properties matching criteria`
          : 'Analysis complete - see report for details',
        timestamp: now,
        updateType: 'new_opportunity',
        status: 'new',
        relatedProjectId: projectId,
        impact: isBuyRecommendation ? 'positive' : 'neutral',
      },
    ],
    trackingDensity: {
      label: 'Properties Analyzed',
      value: `${propertiesFound} properties`,
      metric: 'properties',
    },
    focusCard: {
      header: setup.market,
      tag: isBuyRecommendation ? 'BUY' : 'PASS',
      tagType: isBuyRecommendation ? 'success' : 'warning',
      summary: firstParagraph,
      stats: [
        {
          label: 'Confidence',
          value: `${Math.round(confidence * 100)}%`,
          highlight: confidence > 0.7,
        },
        {
          label: 'Properties Found',
          value: propertiesFound.toString(),
        },
        {
          label: 'Developers Identified',
          value: developersFound.toString(),
        },
      ],
    },
    markets,
    reportContent: {
      projectId,
      projectName: setup.name,
      analysisType: 'Multi-Agent AI Analysis (AWS Bedrock AgentCore)',
      confidence,
      confidenceLabel: confidence > 0.66 ? 'High' : confidence > 0.33 ? 'Medium' : 'Low',
      dataCoverage: 'Alachua County, Florida',
      summary: firstParagraph,
      sections: [
        {
          title: 'AI Agent Analysis',
          content: message,
        },
      ],
      nextActions: isBuyRecommendation
        ? [
            'Review detailed property list',
            'Contact identified developers',
            'Conduct on-site property inspections',
            'Verify zoning and permits',
          ]
        : [
            'Review analysis for data gaps',
            'Consider adjusting search criteria',
            'Explore alternative markets',
          ],
      sources: {
        tools: ['Multi-Agent System', 'Property Search', 'Entity Analysis', 'Market Trends', 'Ordinance Search'],
        databases: ['Aurora PostgreSQL (108K properties, 89K entities, 5K ordinances)'],
        coverage: 'Alachua County, Florida',
      },
      rawResponse: agentResponse,
    },
    opportunityQueue: [],
    activityLog: [
      {
        id: `activity-${Date.now()}`,
        timestamp: now,
        toolName: 'multi_agent_analysis',
        description: `Analyzing: "${setup.strategy || prompt}"`,
        result: `Analysis complete: ${isBuyRecommendation ? 'BUY' : 'PASS'} recommendation with ${Math.round(confidence * 100)}% confidence`,
        status: 'complete',
        duration: '~60s',
      },
    ],
    isLive: false,
    lastDataCheck: now,
  };
}
