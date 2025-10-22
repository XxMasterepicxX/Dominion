export type EntityInsight = {
  badge: string;
  description: string;
};

const normalize = (value?: string | null) => (value ?? '').trim().toUpperCase();

export const getEntityInsight = (rawName?: string | null): EntityInsight | null => {
  const name = normalize(rawName);
  if (!name) {
    return null;
  }

  const contains = (...tokens: string[]) => tokens.some((token) => name.includes(token));

  if (contains('CITY OF', 'COUNTY', 'STATE OF', 'REDEVELOPMENT AGENCY', 'COMMUNITY REDEVELOPMENT')) {
    return {
      badge: 'Public sector',
      description: 'Government or agency owner - expect procurement steps and public approvals.',
    };
  }

  if (contains('UNIVERSITY', 'COLLEGE', 'UF ', 'UNIV OF FLORIDA', 'HOSPITAL', 'HEALTH SYSTEM')) {
    return {
      badge: 'Institutional',
      description: 'Institutional partner - align strategy with long-term campus and research missions.',
    };
  }

  if (contains('TRUST')) {
    return {
      badge: 'Trust vehicle',
      description: 'Owned by a trust entity, often signaling estate planning or legacy holdings.',
    };
  }

  if (contains(' LLC', 'L.L.C', 'LLC.', ' LC', 'LC ', 'LIMITED LIABILITY COMPANY')) {
    return {
      badge: 'Single-asset LLC',
      description: 'Likely a special purpose vehicle holding the parcel for liability protection.',
    };
  }

  if (contains(' L.P', 'LIMITED PARTNERSHIP', ' LLP', 'L.L.P', 'PARTNERSHIP')) {
    return {
      badge: 'Partnership',
      description: 'Capital pooled across partners - JV dynamics and deal timing can hinge on consensus.',
    };
  }

  if (contains(' INC', 'CORP', 'CORPORATION', 'COMPANY', ' CO', 'CO.', 'HOLDINGS', 'HOLDING')) {
    return {
      badge: 'Corporate operator',
      description: 'Corporate developer/operator with formal review cycles and balance-sheet backing.',
    };
  }

  if (contains('DEVELOPMENT', 'PROPERTIES', 'REALTY', 'REAL ESTATE', 'BUILDERS', 'HOMES')) {
    return {
      badge: 'Regional developer',
      description: 'Active development group - monitor pipeline and competitive activity nearby.',
    };
  }

  if (contains('MINISTRIES', 'CHURCH', 'FOUNDATION', 'NON PROFIT', 'NONPROFIT')) {
    return {
      badge: 'Mission-driven',
      description: 'Non-profit or mission-driven owner; engagement hinges on community impact narratives.',
    };
  }

  return {
    badge: 'Private owner',
    description: 'Likely an individual or boutique investor - negotiations can move quickly with clear terms.',
  };
};

