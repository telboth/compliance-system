import { ALL_COUNTRY_RISKS } from "@/data/countryRisk";

const LOCALES = ["en", "nb", "no"] as const;

let lookupCache: Map<string, string> | null = null;
const optionsByLocale = new Map<string, CountryOption[]>();

export interface CountryOption {
  code: string;
  name: string;
}

function normalizeCountryName(raw: string): string {
  return raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z]/g, "");
}

function buildCountryLookup(): Map<string, string> {
  const codes = new Set<string>(Object.keys(ALL_COUNTRY_RISKS));
  const lookup = new Map<string, string>();

  for (const code of codes) {
    lookup.set(code.toLowerCase(), code);
    for (const locale of LOCALES) {
      try {
        const dn = new Intl.DisplayNames([locale], { type: "region" });
        const name = dn.of(code);
        if (!name) continue;
        const key = normalizeCountryName(name);
        if (key) lookup.set(key, code);
      } catch {
        // Ignore Intl locale support issues in older browsers.
      }
    }
  }

  // Common aliases + known Norwegian variants.
  lookup.set("usa", "US");
  lookup.set("unitedstates", "US");
  lookup.set("uk", "GB");
  lookup.set("greatbritain", "GB");
  lookup.set("storbritannia", "GB");
  lookup.set("england", "GB");
  lookup.set("northkorea", "KP");
  lookup.set("nordkorea", "KP");
  lookup.set("russia", "RU");
  lookup.set("russland", "RU");
  lookup.set("frankrike", "FR");
  lookup.set("frankriket", "FR");
  lookup.set("france", "FR");

  return lookup;
}

function getLookup(): Map<string, string> {
  if (lookupCache) return lookupCache;
  lookupCache = buildCountryLookup();
  return lookupCache;
}

export function getCountryAutocompleteOptions(locale: string): CountryOption[] {
  const normalizedLocale = (locale || "en").toLowerCase();
  const cached = optionsByLocale.get(normalizedLocale);
  if (cached) return cached;

  const codes = Object.keys(ALL_COUNTRY_RISKS).sort();
  let dn: Intl.DisplayNames | null = null;
  try {
    dn = new Intl.DisplayNames([locale || "en"], { type: "region" });
  } catch {
    dn = null;
  }
  const options = codes
    .map((code) => ({
      code,
      name: dn?.of(code) || code,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  optionsByLocale.set(normalizedLocale, options);
  return options;
}

export function resolveCountryToIso2(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";

  const isoCandidate = trimmed.toUpperCase().replace(/[^A-Z]/g, "");
  if (isoCandidate.length === 2) return isoCandidate;

  const norm = normalizeCountryName(trimmed);
  if (!norm) return "";

  const lookup = getLookup();
  const direct = lookup.get(norm);
  if (direct) return direct;

  const suffixCandidates = [norm];
  if (norm.endsWith("et") && norm.length > 4) suffixCandidates.push(norm.slice(0, -2));
  if (norm.endsWith("en") && norm.length > 4) suffixCandidates.push(norm.slice(0, -2));
  if (norm.endsWith("a") && norm.length > 4) suffixCandidates.push(norm.slice(0, -1));
  if (norm.endsWith("s") && norm.length > 4) suffixCandidates.push(norm.slice(0, -1));

  for (const key of suffixCandidates) {
    const match = lookup.get(key);
    if (match) return match;
  }
  return "";
}
