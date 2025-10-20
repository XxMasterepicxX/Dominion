/**
 * Markdown Parser for Agent Responses
 * 
 * Parses the agent's markdown output into structured sections for the dashboard.
 * Handles the specific format returned by Dominion AgentCore:
 * - Executive Summary
 * - Key Findings (Property, Market, Developer, Regulatory)
 * - Cross-Verification Analysis
 * - Validation Results
 * - Investment Thesis
 * - Risks & Mitigation (table)
 * - Recommended Actions (list)
 * - Confidence Breakdown (table)
 * - Data Quality Notes
 * - Alternative Scenarios
 */

export interface ParsedSection {
  title: string;
  content: string;
  subsections?: ParsedSection[];
  metrics?: Array<{ label: string; value: string; highlight?: boolean }>;
  table?: Array<Record<string, string>>;
  list?: string[];
}

export interface ParsedAgentResponse {
  title: string; // "DOMINION ANALYSIS"
  executiveSummary: {
    recommendation: string; // "CONDITIONAL BUY", "BUY", "PASS"
    confidence: number; // 0.6
    expectedReturn?: string; // "15-25% over 2-3 years"
    summary: string;
  };
  keyFindings: {
    property?: { content: string; confidence: number };
    market?: { content: string; confidence: number };
    developer?: { content: string; confidence: number };
    regulatory?: { content: string; confidence: number };
  };
  crossVerification?: {
    agreements: string[];
    conflicts: string[];
    resolution: string[];
  };
  validationResults?: {
    chainOfVerification?: string[];
    redTeam?: string[];
    preMortem?: string[];
    sensitivityAnalysis?: {
      bestCase?: string;
      baseCase?: string;
      worstCase?: string;
    };
  };
  investmentThesis?: string;
  risksAndMitigation?: Array<{
    risk: string;
    severity: number;
    probability: number;
    score: number;
    mitigation: string;
  }>;
  recommendedActions?: string[];
  confidenceBreakdown?: Array<{
    specialist: string;
    confidence: number;
    keyFactors: string;
  }>;
  dataQuality?: {
    strengths: string[];
    gaps: string[];
    assumptions: string[];
  };
  alternativeScenarios?: string[];
  rawMarkdown: string;
}

/**
 * Parse agent markdown response into structured data
 */
export function parseAgentMarkdown(markdown: string): ParsedAgentResponse {
  const parsed: ParsedAgentResponse = {
    title: '',
    executiveSummary: {
      recommendation: 'UNKNOWN',
      confidence: 0.5,
      summary: '',
    },
    keyFindings: {},
    rawMarkdown: markdown,
  };

  // Extract title (first # header)
  const titleMatch = markdown.match(/^#\s+(.+)$/m);
  parsed.title = titleMatch ? titleMatch[1].trim() : 'DOMINION ANALYSIS';

  // Extract Executive Summary
  const execSummarySection = extractSection(markdown, '## EXECUTIVE SUMMARY');
  if (execSummarySection) {
    // Extract recommendation (look for **Recommendation: XXX**)
    const recMatch = execSummarySection.match(/\*\*Recommendation:\s*([A-Z\s]+)\*\*/);
    if (recMatch) {
      parsed.executiveSummary.recommendation = recMatch[1].trim();
    }

    // Extract confidence
    const confMatch = execSummarySection.match(/\*\*Confidence:\s*(\d+)%\*\*/);
    if (confMatch) {
      parsed.executiveSummary.confidence = parseInt(confMatch[1]) / 100;
    }

    // Extract expected return
    const returnMatch = execSummarySection.match(/\*\*Expected Return:\s*(.+?)\*\*/);
    if (returnMatch) {
      parsed.executiveSummary.expectedReturn = returnMatch[1].trim();
    }

    // Extract summary (first paragraph after headers)
    const summaryParagraphs = execSummarySection.split('\n\n').filter(p =>
      !p.startsWith('#') && !p.startsWith('**') && !p.startsWith('---') && p.trim().length > 20
    );
    parsed.executiveSummary.summary = summaryParagraphs[0] || '';
  }

  // Extract Key Findings
  const keyFindingsSection = extractSection(markdown, '## KEY FINDINGS');
  if (keyFindingsSection) {
    // Property Analysis
    const propSection = extractSubsection(keyFindingsSection, '### Property Analysis');
    if (propSection) {
      const confMatch = propSection.match(/\*\*Confidence:\s*(\d+)%\*\*/);
      parsed.keyFindings.property = {
        content: propSection.replace(/\*\*Confidence:\s*\d+%\*\*/, '').trim(),
        confidence: confMatch ? parseInt(confMatch[1]) / 100 : 0.5,
      };
    }

    // Market Analysis
    const marketSection = extractSubsection(keyFindingsSection, '### Market Analysis');
    if (marketSection) {
      const confMatch = marketSection.match(/\*\*Confidence:\s*(\d+)%\*\*/);
      parsed.keyFindings.market = {
        content: marketSection.replace(/\*\*Confidence:\s*\d+%\*\*/, '').trim(),
        confidence: confMatch ? parseInt(confMatch[1]) / 100 : 0.5,
      };
    }

    // Developer Intelligence
    const devSection = extractSubsection(keyFindingsSection, '### Developer Intelligence');
    if (devSection) {
      const confMatch = devSection.match(/\*\*Confidence:\s*(\d+)%\*\*/);
      parsed.keyFindings.developer = {
        content: devSection.replace(/\*\*Confidence:\s*\d+%\*\*/, '').trim(),
        confidence: confMatch ? parseInt(confMatch[1]) / 100 : 0.5,
      };
    }

    // Regulatory & Risk
    const regSection = extractSubsection(keyFindingsSection, '### Regulatory & Risk');
    if (regSection) {
      const confMatch = regSection.match(/\*\*Confidence:\s*(\d+)%\*\*/);
      parsed.keyFindings.regulatory = {
        content: regSection.replace(/\*\*Confidence:\s*\d+%\*\*/, '').trim(),
        confidence: confMatch ? parseInt(confMatch[1]) / 100 : 0.5,
      };
    }
  }

  // Extract Recommended Actions
  const actionsSection = extractSection(markdown, '## RECOMMENDED ACTIONS');
  if (actionsSection) {
    parsed.recommendedActions = extractNumberedList(actionsSection);
  }

  // Extract Risks & Mitigation (table)
  const risksSection = extractSection(markdown, '## RISKS & MITIGATION');
  if (risksSection) {
    parsed.risksAndMitigation = parseRisksTable(risksSection);
  }

  // Extract Confidence Breakdown (table)
  const confidenceSection = extractSection(markdown, '## CONFIDENCE BREAKDOWN');
  if (confidenceSection) {
    parsed.confidenceBreakdown = parseConfidenceTable(confidenceSection);
  }

  // Extract Investment Thesis
  const thesisSection = extractSection(markdown, '## INVESTMENT THESIS');
  if (thesisSection) {
    parsed.investmentThesis = thesisSection.split('\n\n')[0].trim();
  }

  // Extract Alternative Scenarios
  const altSection = extractSection(markdown, '## ALTERNATIVE SCENARIOS');
  if (altSection) {
    const scenarios = altSection.split('\n\n').filter(p =>
      p.startsWith('**If') || p.startsWith('**Alternative') || p.startsWith('**Final')
    );
    parsed.alternativeScenarios = scenarios;
  }

  return parsed;
}

/**
 * Extract a section by header
 */
function extractSection(markdown: string, header: string): string | null {
  const regex = new RegExp(`${escapeRegex(header)}\\n([\\s\\S]*?)(?=\\n## |$)`, 'i');
  const match = markdown.match(regex);
  return match ? match[1].trim() : null;
}

/**
 * Extract a subsection by header
 */
function extractSubsection(text: string, header: string): string | null {
  const regex = new RegExp(`${escapeRegex(header)}\\n([\\s\\S]*?)(?=\\n### |\\n## |$)`, 'i');
  const match = text.match(regex);
  return match ? match[1].trim() : null;
}

/**
 * Extract numbered list items
 */
function extractNumberedList(text: string): string[] {
  const matches = text.match(/^\d+\.\s+(.+)$/gm);
  return matches ? matches.map(m => m.replace(/^\d+\.\s+/, '').trim()) : [];
}

/**
 * Parse risks table
 */
function parseRisksTable(text: string): Array<{
  risk: string;
  severity: number;
  probability: number;
  score: number;
  mitigation: string;
}> {
  const risks: any[] = [];
  const lines = text.split('\n').filter(l => l.startsWith('|') && !l.includes('---'));

  // Skip header row
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split('|').map(c => c.trim()).filter(c => c);
    if (cols.length >= 5) {
      risks.push({
        risk: cols[0],
        severity: parseInt(cols[1]) || 0,
        probability: parseInt(cols[2]) || 0,
        score: parseInt(cols[3]) || 0,
        mitigation: cols[4],
      });
    }
  }

  return risks;
}

/**
 * Parse confidence breakdown table
 */
function parseConfidenceTable(text: string): Array<{
  specialist: string;
  confidence: number;
  keyFactors: string;
}> {
  const breakdown: any[] = [];
  const lines = text.split('\n').filter(l => l.startsWith('|') && !l.includes('---'));

  // Skip header row
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split('|').map(c => c.trim()).filter(c => c);
    if (cols.length >= 3) {
      const confMatch = cols[1].match(/(\d+)%/);
      breakdown.push({
        specialist: cols[0],
        confidence: confMatch ? parseInt(confMatch[1]) / 100 : 0.5,
        keyFactors: cols[2],
      });
    }
  }

  return breakdown;
}

/**
 * Escape special regex characters
 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
