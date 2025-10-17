export type ProjectType =
  | 'developer_following'
  | 'property_acquisition'
  | 'market_research'
  | 'price_validation'
  | 'assemblage_investigation'
  | 'exit_strategy';

export interface ProjectReportHeader {
  id: string;
  name: string;
  type: ProjectType;
  market: string;
  marketCode: string;
  generatedAt: string;
  lastUpdated: string;
  isLive: boolean;
  updateCount: number;
  confidence?: number;
  opportunities: number;
}

export type UpdateType = 'data_change' | 'new_opportunity' | 'alert' | 'context';

export interface LatestUpdate {
  id: string;
  title: string;
  detail: string;
  timestamp: string;
  updateType: UpdateType;
  status: 'new' | 'acknowledged';
  relatedProjectId: string;
  changeType?: 'acquisition' | 'price_change' | 'market_shift' | 'new_opportunity';
  before?: unknown;
  after?: unknown;
  impact?: 'positive' | 'negative' | 'neutral';
}

export interface MarketMarker {
  location: [number, number];
  size: number;
  label: string;
  marketCode: string;
  properties: number;
  entities: number;
  activeEntities: number;
  recentActivity?: string;
  confidence?: number;
  confidenceLabel?: string;
}

export interface MissionDensity {
  label: string;
  value: string;
  metric: 'properties' | 'projects' | 'entities';
}

export interface FocusCardStat {
  label: string;
  value: string;
  highlight?: boolean;
}

export interface FocusCard {
  header: string;
  tag: string;
  tagType: 'success' | 'warning' | 'info';
  summary: string;
  stats: FocusCardStat[];
}

export interface ReportSectionMetric {
  label: string;
  value: string;
  highlight?: boolean;
}

export interface ReportSection {
  title: string;
  content: string;
  metrics?: ReportSectionMetric[];
  data?: unknown;
}

export interface ReportContent {
  projectId: string;
  projectName: string;
  analysisType: string;
  confidence: number;
  confidenceLabel: string;
  dataCoverage: string;
  summary: string;
  sections: ReportSection[];
  marketContext?: string;
  nextActions: string[];
  sources?: {
    tools: string[];
    databases: string[];
    coverage: string;
  };
  rawResponse?: unknown;
}

export type OpportunityType =
  | 'entity_following'
  | 'property_deal'
  | 'market_arbitrage'
  | 'zoning_play'
  | 'assemblage';

export interface Opportunity {
  id: string;
  type: OpportunityType;
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
}

export interface AnalysisStep {
  id: string;
  timestamp: string;
  toolName: string;
  description: string;
  result: string;
  status: 'running' | 'complete' | 'failed';
  duration?: string;
}

export interface DashboardState {
  project: ProjectReportHeader;
  latestUpdates: LatestUpdate[];
  trackingDensity: MissionDensity;
  focusCard: FocusCard;
  markets: MarketMarker[];
  reportContent: ReportContent;
  opportunityQueue: Opportunity[];
  activityLog: AnalysisStep[];
  isLive: boolean;
  lastDataCheck: string;
}

export type ProjectStatus = 'draft' | 'generating' | 'complete' | 'live';

export interface ProjectSummary {
  id: string;
  name: string;
  type: ProjectType;
  market: string;
  marketCode: string;
  status: ProjectStatus;
  progress: number;
  createdAt: string;
  lastUpdated: string;
  description: string;
  confidence?: number;
  opportunities?: number;
}

export interface ProjectAnalysisScope {
  portfolio: boolean;
  patterns: boolean;
  geography: boolean;
  opportunities: boolean;
  market: boolean;
  zoning?: boolean;
  comparables?: boolean;
}

export interface ProjectSetupCriteria {
  propertyType?: string;
  maxPrice?: number;
  minPrice?: number;
  minLotSize?: number;
  maxLotSize?: number;
  area?: string;
  ownerType?: string;
}

export interface ProjectSetup {
  name: string;
  type: ProjectType;
  market: string;
  marketCode?: string;
  entityName?: string;
  propertyId?: string;
  parcelId?: string;
  askingPrice?: number;
  criteria?: ProjectSetupCriteria;
  analysisScope: ProjectAnalysisScope;
  budget?: number;
  preferredPropertyType?: string;
  strategy?: string;
}
