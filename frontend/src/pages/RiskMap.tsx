/**
 * Risikokart — interaktivt verdenskart med landrisiko-klassifisering.
 *
 * Bruker react-leaflet (MapContainer/TileLayer/GeoJSON) med OpenStreetMap.
 * GeoJSON-landgrenser hentes fra CDN ved første besøk.
 * Land farges etter risikotier fra countryRisk.ts.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import type { Layer, Path } from "leaflet";
import type { Feature, GeoJsonObject } from "geojson";
import clsx from "clsx";
import {
  ALL_COUNTRY_RISKS,
  TIER_LABELS,
  TIER_COLORS,
  TIER_BG,
  TIER_DESCRIPTION,
  getTierFillColor,
  getTierStrokeColor,
  type CountryRiskTier,
} from "@/data/countryRisk";

// ── GeoJSON-kilde (Natural Earth via datasets/geo-countries, ~6 MB) ───────────
const GEOJSON_URL =
  "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson";

// ── Navn-basert fallback for land med ISO2="-99" i Natural Earth-data ─────────
// (Frankrike og Norge mangler ISO-kode i dette GeoJSON-settet)
const NAME_TO_ISO2: Record<string, string> = {
  "France": "FR",
  "Norway": "NO",
  "Kosovo": "XK",
  "Somaliland": "SO",          // del av Somalia (TIER 4)
  "Northern Cyprus": "TR",     // tyrkisk-kontrollert (TIER 2 via TR)
};

function resolveIso2(props: Record<string, string>): string {
  const iso2 = props["ISO3166-1-Alpha-2"] ?? "";
  if (iso2 !== "-99" && iso2 !== "") return iso2;
  return NAME_TO_ISO2[props.name ?? ""] ?? "";
}

// ── Statistikk ────────────────────────────────────────────────────────────────
function tierStats(): Record<CountryRiskTier, number> {
  const counts = { 1: 0, 2: 0, 3: 0, 4: 0 } as Record<CountryRiskTier, number>;
  for (const t of Object.values(ALL_COUNTRY_RISKS)) {
    counts[t as CountryRiskTier]++;
  }
  return counts;
}

// ── Stil-funksjon ─────────────────────────────────────────────────────────────
function featureStyle(
  iso2: string,
  activeTier: CountryRiskTier | null,
  highlight = false,
) {
  const tier = (ALL_COUNTRY_RISKS[iso2] ?? 2) as CountryRiskTier;
  const filtered = activeTier !== null && tier !== activeTier;
  if (filtered) {
    return { fillColor: "#e5e7eb", fillOpacity: 0.25, color: "#d1d5db", weight: 0.4, opacity: 0.4 };
  }
  return {
    fillColor: getTierFillColor(tier),
    fillOpacity: highlight ? 0.95 : 0.75,
    color: getTierStrokeColor(tier),
    weight: highlight ? 2.5 : 0.8,
    opacity: 0.9,
  };
}

// ── Tooltip-type ──────────────────────────────────────────────────────────────
interface TooltipInfo {
  name: string;
  iso2: string;
  tier: CountryRiskTier;
}

// ── Hovedelement ──────────────────────────────────────────────────────────────
export function RiskMap() {
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipInfo | null>(null);
  const [activeTier, setActiveTier] = useState<CountryRiskTier | null>(null);

  // Ref slik at event-handlers alltid ser siste activeTier (unngår stale closure)
  const activeTierRef = useRef<CountryRiskTier | null>(null);
  useEffect(() => { activeTierRef.current = activeTier; }, [activeTier]);

  const stats = tierStats();

  // Hent GeoJSON én gang
  useEffect(() => {
    fetch(GEOJSON_URL)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<GeoJsonObject>;
      })
      .then((data) => { setGeojson(data); setLoading(false); })
      .catch((err: Error) => { setFetchError(err.message); setLoading(false); });
  }, []);

  // Stil-funksjon for GeoJSON-laget (re-kalkuleres når activeTier endres)
  const styleFunc = useCallback(
    (feature: Feature | undefined) => {
      const iso2 = resolveIso2((feature?.properties ?? {}) as Record<string, string>);
      return featureStyle(iso2, activeTier);
    },
    [activeTier],
  );

  // Event-handlers per feature
  const onEachFeature = useCallback((feature: Feature, layer: Layer) => {
    const props = (feature?.properties ?? {}) as Record<string, string>;
    const iso2 = resolveIso2(props);
    const name = props.name ?? iso2;
    const tier = (ALL_COUNTRY_RISKS[iso2] ?? 2) as CountryRiskTier;

    layer.on({
      mouseover: () => {
        (layer as Path).setStyle({ weight: 2.5, fillOpacity: 0.95 });
        setTooltip({ name, iso2, tier });
      },
      mouseout: () => {
        (layer as Path).setStyle(featureStyle(iso2, activeTierRef.current));
        setTooltip(null);
      },
    });
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      {/* Overskrift */}
      <div>
        <h1 className="text-2xl font-semibold text-xlent-ink">Landrisikoark</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          Interaktivt kart over eksportkontroll-risikonivå per destinasjonsland. Basert på
          NATO-tilhørighet, US EAR Country Groups, OECD landrisikokategori og EU/FN-sanksjoner.
          Hold over et land for detaljer.
        </p>
      </div>

      {/* Tier-kort / filter */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {([1, 2, 3, 4] as CountryRiskTier[]).map((tier) => (
          <button
            key={tier}
            onClick={() => setActiveTier((cur) => (cur === tier ? null : tier))}
            className={clsx(
              "rounded-lg border p-3 text-left transition-all",
              TIER_BG[tier],
              activeTier === tier && "ring-2 ring-offset-1",
              activeTier !== null && activeTier !== tier && "opacity-40",
            )}
          >
            <div className="flex items-center gap-2">
              <span
                className="inline-block h-3 w-3 flex-shrink-0 rounded-full"
                style={{ backgroundColor: TIER_COLORS[tier] }}
              />
              <span className="text-xs font-semibold">{TIER_LABELS[tier]}</span>
              <span className="ml-auto text-xs font-medium opacity-70">{stats[tier]}</span>
            </div>
            <p className="mt-1 text-xs leading-snug opacity-75">{TIER_DESCRIPTION[tier]}</p>
          </button>
        ))}
      </div>

      {activeTier !== null && (
        <div className="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
          Viser kun <strong>{TIER_LABELS[activeTier]}</strong> — klikk samme boks igjen for å fjerne filter.
        </div>
      )}

      {/* Kart-boks */}
      <div
        className="relative overflow-hidden rounded-lg border border-gray-200"
        style={{ height: "520px" }}
      >
        {/* Laste-overlay */}
        {loading && (
          <div className="absolute inset-0 z-[1001] flex items-center justify-center bg-white/90">
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
              <p className="text-sm text-xlent-muted">Laster landgrenser …</p>
            </div>
          </div>
        )}

        {/* Feil-overlay */}
        {fetchError && (
          <div className="absolute inset-0 z-[1001] flex items-center justify-center bg-red-50 p-6 text-center">
            <div>
              <p className="text-sm font-medium text-traffic-red">Kunne ikke laste kartdata</p>
              <p className="mt-1 text-xs text-traffic-red/80">{fetchError}</p>
              <p className="mt-2 text-xs text-xlent-muted">Sjekk internettforbindelsen og last siden på nytt.</p>
            </div>
          </div>
        )}

        {/* react-leaflet MapContainer — håndterer livssyklus korrekt */}
        {!fetchError && (
          <MapContainer
            center={[20, 10]}
            zoom={2}
            minZoom={1}
            maxZoom={7}
            style={{ height: "100%", width: "100%" }}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              opacity={0.35}
            />
            {/* GeoJSON-lag — key tvinger re-mount ved tier-filterendring */}
            {geojson && (
              <GeoJSON
                key={String(activeTier)}
                data={geojson}
                style={styleFunc}
                onEachFeature={onEachFeature}
              />
            )}
          </MapContainer>
        )}

        {/* Tooltip — vises inni kart-boksen */}
        {tooltip && (
          <div className="pointer-events-none absolute bottom-4 left-4 z-[1000] min-w-52 rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-lg">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold uppercase text-xlent-muted">
                {tooltip.iso2}
              </span>
              <span className="font-medium text-xlent-ink">{tooltip.name}</span>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span
                className="inline-block h-3 w-3 flex-shrink-0 rounded-full"
                style={{ backgroundColor: TIER_COLORS[tooltip.tier] }}
              />
              <span className="text-xs font-medium" style={{ color: TIER_COLORS[tooltip.tier] }}>
                {TIER_LABELS[tooltip.tier]}
              </span>
            </div>
            <p className="mt-1 text-xs leading-snug text-xlent-muted">
              {TIER_DESCRIPTION[tooltip.tier]}
            </p>
          </div>
        )}
      </div>

      {/* Datakilder */}
      <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-xs text-xlent-muted">
        <p className="mb-1 font-semibold">Datakilder og metodikk</p>
        <ul className="list-inside list-disc space-y-0.5">
          <li>
            <strong>Grønn:</strong> NATO-land + nære allierte (AU, NZ, JP, KR, IL, SG, TW, AT, CH, IE)
          </li>
          <li>
            <strong>Gul:</strong> Stabile demokratier og nøytrale land — standard aktsomhetsregler
          </li>
          <li>
            <strong>Oransje:</strong> US EAR Country Group D — Kina, Vietnam, Pakistan, sentral-Asia, deler av Midtøsten
          </li>
          <li>
            <strong>Rød:</strong> Totale/brede sanksjoner (RU, BY, KP, IR, SY, CU) og land under FN/EU/US våpenembargo
          </li>
          <li>
            Kartet er informativt og ikke juridisk rådgivning.{" "}
            <a
              href="https://deksa.no/en/export-control/"
              target="_blank"
              rel="noreferrer"
              className="text-xlent-primary hover:underline"
            >
              Se DEKSA for gjeldende norsk eksportkontroll.
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
}
