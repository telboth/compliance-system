export type CountryRiskTier = 1 | 2 | 3 | 4;

export const TIER_LABELS: Record<CountryRiskTier, string> = {
  1: "Low",
  2: "Normal",
  3: "Elevated",
  4: "High",
};

export const TIER_COLORS: Record<CountryRiskTier, string> = {
  1: "#15803d",
  2: "#ca8a04",
  3: "#ea580c",
  4: "#dc2626",
};

export const TIER_BG: Record<CountryRiskTier, string> = {
  1: "bg-green-50 text-green-800 border-green-200",
  2: "bg-amber-50 text-amber-800 border-amber-200",
  3: "bg-orange-50 text-orange-800 border-orange-200",
  4: "bg-red-50 text-red-800 border-red-200",
};

const NATO_COUNTRIES = new Set<string>([
  "AL", "BE", "BG", "CA", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS",
  "IT", "LV", "LT", "LU", "ME", "NL", "MK", "NO", "PL", "PT", "RO", "SK", "SI", "ES",
  "SE", "TR", "GB", "US",
]);

const HIGH_RISK_TIER4 = new Set<string>([
  "AF", "BY", "CU", "IR", "KP", "RU", "SY",
]);

const ELEVATED_TIER3 = new Set<string>([
  "DZ", "AM", "AZ", "CN", "EG", "GE", "IQ", "JO", "KZ", "KG", "LB", "LY", "MD", "MM",
  "NG", "PK", "PS", "QA", "RS", "SA", "SO", "SD", "TJ", "TM", "TR", "UA", "AE", "UZ",
  "VE", "YE",
]);

function fallbackCountryCodes(): string[] {
  return [
    "AD", "AE", "AF", "AG", "AL", "AM", "AO", "AR", "AT", "AU", "AZ", "BA", "BB", "BD",
    "BE", "BF", "BG", "BH", "BI", "BJ", "BN", "BO", "BR", "BS", "BT", "BW", "BY", "BZ",
    "CA", "CD", "CF", "CG", "CH", "CI", "CL", "CM", "CN", "CO", "CR", "CU", "CV", "CY",
    "CZ", "DE", "DJ", "DK", "DM", "DO", "DZ", "EC", "EE", "EG", "ER", "ES", "ET", "FI",
    "FJ", "FM", "FR", "GA", "GB", "GE", "GH", "GM", "GN", "GQ", "GR", "GT", "GW", "GY",
    "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IN", "IQ", "IR", "IS", "IT", "JM", "JO",
    "JP", "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW", "KZ", "LA", "LB", "LC",
    "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MG", "MH",
    "MK", "ML", "MM", "MN", "MR", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NE",
    "NG", "NI", "NL", "NO", "NP", "NZ", "OM", "PA", "PE", "PG", "PH", "PK", "PL", "PT",
    "PW", "PY", "QA", "RO", "RS", "RU", "RW", "SA", "SB", "SC", "SD", "SE", "SG", "SI",
    "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV", "SY", "SZ", "TD", "TG", "TH",
    "TJ", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TZ", "UA", "UG", "US", "UY", "UZ",
    "VA", "VC", "VE", "VN", "VU", "WS", "YE", "ZA", "ZM", "ZW",
  ];
}

function allCountryCodes(): string[] {
  // Intl.supportedValuesOf("region") er ikke standard og kaster RangeError i Chrome/Edge
  // når funksjonen finnes men ikke støtter "region"-nøkkelen.
  // Optional chaining hjelper IKKE her (kaster, ikke returnerer undefined).
  // try-catch er det eneste som sikrer fallback til den statiske listen.
  try {
    const intlWithExtra = Intl as typeof Intl & {
      supportedValuesOf?: (key: string) => string[];
    };
    if (typeof intlWithExtra.supportedValuesOf !== "function") {
      return fallbackCountryCodes();
    }
    const fromIntl = intlWithExtra.supportedValuesOf("region");
    if (fromIntl && fromIntl.length > 0) {
      const codes = fromIntl
        .filter((value) => /^[A-Z]{2}$/.test(value))
        .map((value) => value.toUpperCase());
      const result = Array.from(new Set(codes));
      if (result.length > 0) return result;
    }
  } catch {
    // "region" er ikke en gyldig nøkkel i denne nettleseren — bruk statisk fallback
  }
  return fallbackCountryCodes();
}

function buildRiskMap(): Record<string, CountryRiskTier> {
  const map: Record<string, CountryRiskTier> = {};
  for (const code of allCountryCodes()) {
    map[code] = 2;
  }
  for (const code of NATO_COUNTRIES) {
    map[code] = 1;
  }
  for (const code of ELEVATED_TIER3) {
    map[code] = 3;
  }
  for (const code of HIGH_RISK_TIER4) {
    map[code] = 4;
  }
  return map;
}

export const ALL_COUNTRY_RISKS: Record<string, CountryRiskTier> = buildRiskMap();

export function isNatoCountry(countryCode: string | null | undefined): boolean {
  if (!countryCode) return false;
  return NATO_COUNTRIES.has(countryCode.trim().toUpperCase());
}

export function getCountryRisk(countryCode: string | null | undefined): {
  code: string;
  tier: CountryRiskTier;
  label: string;
} {
  const code = (countryCode ?? "").trim().toUpperCase();
  const tier = (ALL_COUNTRY_RISKS[code] ?? 2) as CountryRiskTier;
  return {
    code,
    tier,
    label: TIER_LABELS[tier],
  };
}

export function getTierFillColor(tier: CountryRiskTier): string {
  if (tier === 1) return "#dcfce7";
  if (tier === 2) return "#fef3c7";
  if (tier === 3) return "#ffedd5";
  return "#fee2e2";
}

export function getTierStrokeColor(tier: CountryRiskTier): string {
  return TIER_COLORS[tier];
}
