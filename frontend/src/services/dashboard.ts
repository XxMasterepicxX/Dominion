import type { DashboardState, ProjectSetup, ProjectSummary } from '../types/dashboard';
import { mockDashboardState } from '../stubs/mockDashboardState';
import { mockProjects } from '../stubs/mockProjects';
import { parseAgentMarkdown } from '../utils/markdownParser';
import { upsertStoredProjectSummary } from '../utils/projectStorage';
// ProjectSummary already imported in types above when needed

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
    // No fallback - throw the real error so we know what's actually happening
    console.error('[dashboard] Failed to fetch dashboard state:', error);
    throw error;
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

// Local cache keys for imported reports
const REPORT_CACHE_PREFIX = 'dominion/dashboard/';
const REPORT_CACHE_VERSION = 1;

type CachedReportEnvelope = {
  version: number;
  savedAt: number;
  state: any; // DashboardState shape - keep generic for imported reports
};

/**
 * Import a dashboard JSON (from file or parsed object) and register it locally as a completed report.
 * This saves the dashboard state to localStorage so the Dashboard page can load it by projectId.
 */
export async function importReportFromJson(report: any, filename?: string): Promise<ProjectSummary> {
  // Determine project id
  const projectId = report?.project?.id || (filename ? filename.replace(/\.json$/i, '') : `proj-${Date.now()}`);

  const now = new Date().toISOString();

  // Build a minimal ProjectSummary to show in Projects list
  const summary: ProjectSummary = {
    id: projectId,
    name: report?.project?.name || `Imported report ${projectId}`,
    type: (report?.project?.type as any) || 'market_research',
    market: report?.project?.market || (report?.reportContent?.marketContext || 'Imported market'),
    marketCode: report?.project?.marketCode || undefined,
    status: 'complete',
    progress: 100,
    createdAt: now,
    lastUpdated: now,
    description: report?.reportContent?.summary || report?.project?.name || 'Imported Dominion report',
    confidence: report?.reportContent?.confidence ?? report?.project?.confidence ?? undefined,
    opportunities: report?.opportunityQueue?.length ?? 0,
  };

  try {
    const envelope: CachedReportEnvelope = {
      version: REPORT_CACHE_VERSION,
      savedAt: Date.now(),
      state: report,
    };
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(`${REPORT_CACHE_PREFIX}${projectId}`, JSON.stringify(envelope));
    }
  } catch (e) {
    console.warn('[dashboard] failed to persist imported report to localStorage', e);
  }

  // Also store a local ProjectSummary so Projects page can merge/display it regardless of API
  try {
    upsertStoredProjectSummary(summary);
  } catch {
    // ignore
  }

  // Register in mockProjects so fetchProjects fallback will show it
  try {
    // ensure no duplicate id
    const existsIndex = mockProjects.findIndex((p) => p.id === summary.id);
    if (existsIndex !== -1) {
      mockProjects.splice(existsIndex, 1);
    }
    mockProjects.unshift(summary);
  } catch (e) {
    // ignore
  }

  return summary;
}

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
      market_value?: number;
      lot_size?: number;
      zoning?: string;
      type?: string;
    }>;
    developers?: Array<{
      name: string;
      property_count?: number;
      significance?: string;
    }>;
    recommendation?: string;
    confidence?: number;
    expected_return?: string;
    specialist_breakdown?: Array<{
      specialist: string;
      confidence: number;
      key_factors: string;
      tool_calls?: number;
      duration_seconds?: number;
    }>;
    risks?: Array<{
      risk: string;
      severity: number;
      probability: number;
      score: number;
      mitigation: string;
    }>;
    actions?: string[];
    assemblage?: {
      parcel_count: number;
      total_acres: number;
      total_value: number;
      description: string;
    };
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
 * Build report content from agent response using markdown parser
 */
function buildReportContent(
  agentResponse: AgentResponse,
  setup: ProjectSetup,
  projectId: string,
  message: string,
  confidence: number,
  isBuyRecommendation: boolean
): DashboardState['reportContent'] {
  // Parse the markdown into structured sections
  const parsed = parseAgentMarkdown(message);

  // Build sections from parsed markdown
  const sections: Array<{ title: string; content: string; metrics?: Array<{ label: string; value: string; highlight?: boolean }> }> = [];

  // Executive Summary
  if (parsed.executiveSummary.summary) {
    sections.push({
      title: 'Executive Summary',
      content: parsed.executiveSummary.summary,
      metrics: [
        {
          label: 'Recommendation',
          value: parsed.executiveSummary.recommendation,
          highlight: parsed.executiveSummary.recommendation === 'BUY' || parsed.executiveSummary.recommendation === 'CONDITIONAL BUY',
        },
        {
          label: 'Confidence',
          value: `${Math.round(parsed.executiveSummary.confidence * 100)}%`,
          highlight: parsed.executiveSummary.confidence > 0.7,
        },
        ...(parsed.executiveSummary.expectedReturn ? [{
          label: 'Expected Return',
          value: parsed.executiveSummary.expectedReturn,
          highlight: true,
        }] : []),
      ],
    });
  }

  // Key Findings - Property Analysis
  if (parsed.keyFindings.property) {
    sections.push({
      title: 'Property Analysis',
      content: parsed.keyFindings.property.content,
      metrics: [
        {
          label: 'Specialist Confidence',
          value: `${Math.round(parsed.keyFindings.property.confidence * 100)}%`,
          highlight: parsed.keyFindings.property.confidence > 0.7,
        },
      ],
    });
  }

  // Key Findings - Market Analysis
  if (parsed.keyFindings.market) {
    sections.push({
      title: 'Market Analysis',
      content: parsed.keyFindings.market.content,
      metrics: [
        {
          label: 'Specialist Confidence',
          value: `${Math.round(parsed.keyFindings.market.confidence * 100)}%`,
          highlight: parsed.keyFindings.market.confidence > 0.7,
        },
      ],
    });
  }

  // Key Findings - Developer Intelligence
  if (parsed.keyFindings.developer) {
    sections.push({
      title: 'Developer Intelligence',
      content: parsed.keyFindings.developer.content,
      metrics: [
        {
          label: 'Specialist Confidence',
          value: `${Math.round(parsed.keyFindings.developer.confidence * 100)}%`,
          highlight: parsed.keyFindings.developer.confidence > 0.7,
        },
      ],
    });
  }

  // Key Findings - Regulatory & Risk
  if (parsed.keyFindings.regulatory) {
    sections.push({
      title: 'Regulatory & Risk',
      content: parsed.keyFindings.regulatory.content,
      metrics: [
        {
          label: 'Specialist Confidence',
          value: `${Math.round(parsed.keyFindings.regulatory.confidence * 100)}%`,
          highlight: parsed.keyFindings.regulatory.confidence > 0.7,
        },
      ],
    });
  }

  // Investment Thesis
  if (parsed.investmentThesis) {
    sections.push({
      title: 'Investment Thesis',
      content: parsed.investmentThesis,
    });
  }

  // Risks & Mitigation - convert table to metrics for better display
  if (parsed.risksAndMitigation && parsed.risksAndMitigation.length > 0) {
    // Sort by risk score (severity * probability) descending
    const sortedRisks = [...parsed.risksAndMitigation].sort((a, b) => b.score - a.score);
    
    // Create content with mitigation strategies
    const risksContent = sortedRisks
      .map(risk => `• ${risk.risk}: ${risk.mitigation}`)
      .join('\n');
    
    // Create metrics showing risk severity
    const riskMetrics = sortedRisks.map(risk => ({
      label: `${risk.risk} (Score: ${risk.score})`,
      value: `Severity ${risk.severity}/5 × Probability ${risk.probability}/5`,
      highlight: risk.score >= 12, // Highlight high-risk items (score 12+)
    }));
    
    sections.push({
      title: 'Risks & Mitigation',
      content: risksContent,
      metrics: riskMetrics,
    });
  }

  // Confidence Breakdown - convert table to metrics
  if (parsed.confidenceBreakdown && parsed.confidenceBreakdown.length > 0) {
    // Create content with key factors
    const confidenceContent = parsed.confidenceBreakdown
      .map(item => `• ${item.specialist}: ${item.keyFactors}`)
      .join('\n');
    
    // Create metrics showing confidence scores
    const confidenceMetrics = parsed.confidenceBreakdown.map(item => ({
      label: item.specialist,
      value: `${Math.round(item.confidence * 100)}%`,
      highlight: item.confidence > 0.8, // Highlight high confidence
    }));
    
    sections.push({
      title: 'Confidence Breakdown',
      content: confidenceContent,
      metrics: confidenceMetrics,
    });
  }

  // Alternative Scenarios
  if (parsed.alternativeScenarios && parsed.alternativeScenarios.length > 0) {
    sections.push({
      title: 'Alternative Scenarios',
      content: parsed.alternativeScenarios.join('\n\n'),
    });
  }

  // Fallback if no sections were parsed
  if (sections.length === 0) {
    sections.push({
      title: 'AI Agent Analysis',
      content: message,
    });
  }

  return {
    projectId,
    projectName: setup.name,
    analysisType: 'Multi-Agent AI Analysis (AWS Bedrock AgentCore)',
    confidence,
    confidenceLabel: confidence > 0.66 ? 'High' : confidence > 0.33 ? 'Medium' : 'Low',
    dataCoverage: 'Alachua County, Florida',
    summary: parsed.executiveSummary.summary || message.split('\n\n')[0] || message.substring(0, 200),
    marketContext: setup.market ? `Analysis for ${setup.market}, ${setup.type}` : undefined,
    sections,
    nextActions: agentResponse.structured_data?.actions && agentResponse.structured_data.actions.length > 0
      ? agentResponse.structured_data.actions
      : parsed.recommendedActions && parsed.recommendedActions.length > 0
        ? parsed.recommendedActions
        : isBuyRecommendation
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
      tools: ['Multi-Agent System', 'Property Specialist', 'Market Specialist', 'Developer Intelligence', 'Regulatory & Risk Specialist'],
      databases: ['Aurora PostgreSQL (108K properties, 89K entities, 5K ordinances)'],
      coverage: 'Alachua County, Florida',
    },
    rawResponse: agentResponse,
  };
}

/**
 * Transform agent response into dashboard state
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
    reportContent: buildReportContent(agentResponse, setup, projectId, message, confidence, isBuyRecommendation),
    opportunityQueue: buildOpportunityQueue(agentResponse, setup, projectId, confidence),
    activityLog: buildActivityLog(agentResponse, setup, isBuyRecommendation, confidence),
    isLive: false,
    lastDataCheck: now,
  };
}

/**
 * Build opportunity queue from agent analysis
 * Converts properties and insights into actionable opportunities
 */
function buildOpportunityQueue(
  agentResponse: AgentResponse,
  setup: ProjectSetup,
  projectId: string,
  confidence: number
): Array<{
  id: string;
  type: 'property_deal' | 'assemblage' | 'market_arbitrage' | 'entity_following' | 'zoning_play';
  entity?: string;
  property?: string;
  market: string;
  marketCode: string;
  signal: string;
  signalType: string;
  confidence: number;
  confidenceLabel: string;
  leadTime: string;
  action: string;
  estimatedReturn?: string;
  risks?: string[];
  status: 'new' | 'queued' | 'in_analysis' | 'executed' | 'passed';
  supportingTools: string[];
  relatedProjectId?: string;
  discoveredAt: string;
  updatedAt?: string;
}> {
  const now = new Date().toISOString();
  const opportunities: any[] = [];
  const structuredProps = agentResponse.structured_data?.properties || [];
  const developers = agentResponse.structured_data?.developers || [];

  // Create property opportunities from structured data
  structuredProps.forEach((prop, index) => {
    opportunities.push({
      id: `opp-property-${Date.now()}-${index}`,
      type: 'property_deal' as const,
      property: `${prop.address} (Parcel: ${prop.parcel_id})`,
      market: setup.market,
      marketCode: setup.marketCode || setup.market.toLowerCase().replace(/\s+/g, '_'),
      signal: `Property identified in ${setup.market}`,
      signalType: 'ai_analysis',
      confidence,
      confidenceLabel: confidence > 0.66 ? 'High' : confidence > 0.33 ? 'Medium' : 'Low',
      leadTime: 'Immediate',
      action: 'Review property details and conduct site visit',
      supportingTools: ['Property Specialist', 'Market Analysis'],
      relatedProjectId: projectId,
      discoveredAt: now,
      status: 'new' as const,
    });
  });

  // Create developer following opportunities
  developers.slice(0, 3).forEach((dev, index) => {
    opportunities.push({
      id: `opp-developer-${Date.now()}-${index}`,
      type: 'entity_following' as const,
      entity: dev.name,
      market: setup.market,
      marketCode: setup.marketCode || setup.market.toLowerCase().replace(/\s+/g, '_'),
      signal: `Active developer in ${setup.market}`,
      signalType: 'pattern_analysis',
      confidence: confidence * 0.9, // Slightly lower confidence for developer patterns
      confidenceLabel: confidence > 0.66 ? 'High' : confidence > 0.33 ? 'Medium' : 'Low',
      leadTime: '1-3 months',
      action: 'Monitor developer acquisitions and pipeline',
      supportingTools: ['Developer Intelligence', 'Entity Analysis'],
      relatedProjectId: projectId,
      discoveredAt: now,
      status: 'new' as const,
    });
  });

  // Create assemblage opportunity if identified by agent
  if (agentResponse.structured_data?.assemblage) {
    const assemblage = agentResponse.structured_data.assemblage;
    opportunities.push({
      id: `opp-assemblage-${Date.now()}`,
      type: 'assemblage' as const,
      property: assemblage.description || `${assemblage.parcel_count} contiguous parcels`,
      market: setup.market,
      marketCode: setup.marketCode || setup.market.toLowerCase().replace(/\s+/g, '_'),
      signal: `${assemblage.parcel_count} parcels (${assemblage.total_acres} acres) - $${assemblage.total_value?.toLocaleString()}`,
      signalType: 'spatial_analysis',
      confidence: confidence * 0.95,
      confidenceLabel: confidence > 0.66 ? 'High' : confidence > 0.33 ? 'Medium' : 'Low',
      leadTime: 'Immediate',
      action: 'Assemble parcels for developer sale',
      estimatedReturn: agentResponse.structured_data.expected_return,
      supportingTools: ['Property Specialist', 'Market Analysis', 'Developer Intelligence'],
      relatedProjectId: projectId,
      discoveredAt: now,
      status: 'new' as const,
    });
  }

  return opportunities;
}

/**
 * Build activity log from agent execution
 * Shows specialist invocations and analysis steps
 */
function buildActivityLog(
  agentResponse: AgentResponse,
  setup: ProjectSetup,
  isBuyRecommendation: boolean,
  confidence: number
): Array<{
  id: string;
  timestamp: string;
  toolName: string;
  description: string;
  result: string;
  status: 'running' | 'complete' | 'failed';
  duration?: string;
}> {
  const baseTime = Date.now();
  const log: any[] = [];

  // === USE STRUCTURED DATA IF AVAILABLE (PREFERRED) ===
  if (agentResponse.structured_data?.specialist_breakdown && agentResponse.structured_data.specialist_breakdown.length > 0) {
    let timeOffset = 600000; // Start 10 min ago
    
    // Add supervisor entry first
    log.push({
      id: `activity-supervisor-${baseTime}`,
      timestamp: new Date(baseTime - timeOffset).toISOString(),
      toolName: 'supervisor',
      description: `Orchestrating analysis: "${setup.strategy || setup.name}"`,
      result: `Delegated to ${agentResponse.structured_data.specialist_breakdown.length} specialist agents`,
      status: 'complete' as const,
      duration: '~5s',
    });
    
    // Add each specialist from breakdown
    agentResponse.structured_data.specialist_breakdown.forEach((specialist) => {
      const duration = specialist.duration_seconds || 180;
      timeOffset -= 60000; // Offset by 1 min between specialists
      
      log.push({
        id: `activity-${specialist.specialist.toLowerCase().replace(/\s+/g, '-')}-${baseTime}`,
        timestamp: new Date(baseTime - timeOffset).toISOString(),
        toolName: specialist.specialist.toLowerCase().replace(/\s+/g, '_'),
        description: `${specialist.specialist}: ${specialist.key_factors}`,
        result: `Confidence: ${Math.round(specialist.confidence * 100)}%${specialist.tool_calls ? ` | Tool calls: ${specialist.tool_calls}` : ''}`,
        status: 'complete' as const,
        duration: `~${Math.floor(duration / 60)}min`,
      });
      
      timeOffset -= duration * 1000;
    });
    
    return log;
  }

  // === FALLBACK TO GENERIC LOG (no specialist_breakdown provided) ===
  
  // Add supervisor entry
  log.push({
    id: `activity-supervisor-${baseTime}`,
    timestamp: new Date(baseTime - 600000).toISOString(), // 10 min ago
    toolName: 'supervisor',
    description: `Analyzing: "${setup.strategy || setup.name}"`,
    result: 'Delegated to specialist agents for analysis',
    status: 'complete' as const,
    duration: '~5s',
  });

  // Add Property Specialist entry (if properties found)
  if (agentResponse.structured_data?.properties && agentResponse.structured_data.properties.length > 0) {
    log.push({
      id: `activity-property-${baseTime}`,
      timestamp: new Date(baseTime - 540000).toISOString(), // 9 min ago
      toolName: 'property_specialist',
      description: `Searching for properties in ${setup.market}`,
      result: `Found ${agentResponse.structured_data.properties.length} properties matching criteria`,
      status: 'complete' as const,
      duration: '~4min',
    });
  }

  // Add Market Specialist entry
  log.push({
    id: `activity-market-${baseTime}`,
    timestamp: new Date(baseTime - 300000).toISOString(), // 5 min ago
    toolName: 'market_specialist',
    description: `Analyzing market trends in ${setup.market}`,
    result: 'Market analysis complete with comparable properties and trends',
    status: 'complete' as const,
    duration: '~3min',
  });

  // Add Developer Intelligence entry (if developers found)
  if (agentResponse.structured_data?.developers && agentResponse.structured_data.developers.length > 0) {
    log.push({
      id: `activity-developer-${baseTime}`,
      timestamp: new Date(baseTime - 240000).toISOString(), // 4 min ago
      toolName: 'developer_intelligence',
      description: `Identifying active developers in ${setup.market}`,
      result: `Identified ${agentResponse.structured_data.developers.length} active developers`,
      status: 'complete' as const,
      duration: '~2min',
    });
  }

  // Add Regulatory Risk entry
  log.push({
    id: `activity-regulatory-${baseTime}`,
    timestamp: new Date(baseTime - 120000).toISOString(), // 2 min ago
    toolName: 'regulatory_risk',
    description: `Analyzing zoning and regulatory risks in ${setup.market}`,
    result: 'Regulatory analysis complete with zoning insights',
    status: 'complete' as const,
    duration: '~2min',
  });

  // Add final synthesis entry
  log.push({
    id: `activity-final-${baseTime}`,
    timestamp: new Date(baseTime).toISOString(),
    toolName: 'supervisor',
    description: 'Synthesizing specialist analyses into recommendation',
    result: `${isBuyRecommendation ? 'BUY' : 'PASS'} recommendation with ${Math.round(confidence * 100)}% confidence`,
    status: 'complete' as const,
    duration: '~1min',
  });

  return log;
}
