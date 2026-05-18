import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import { CircleMarker, GeoJSON, MapContainer, Polyline, Popup, TileLayer, Tooltip } from "react-leaflet";
import type { Feature, GeoJsonObject } from "geojson";
import type { Layer, Path } from "leaflet";
import clsx from "clsx";
import { useTranslation } from "react-i18next";

import { useInvoiceSearch, useShipmentMap } from "@/hooks/useInvoices";
import type { ShipmentMapRoute } from "@/api/types";
import { resolveCountryToIso2 } from "@/lib/country";
import {
  ALL_COUNTRY_RISKS,
  TIER_BG,
  TIER_COLORS,
  getTierFillColor,
  getTierStrokeColor,
  type CountryRiskTier,
} from "@/data/countryRisk";

const GEOJSON_URL =
  "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson";

const NAME_TO_ISO2: Record<string, string> = {
  France: "FR",
  Norway: "NO",
  Kosovo: "XK",
  Somaliland: "SO",
  "Northern Cyprus": "TR",
};

type RiskFilter = "all" | "low" | "medium" | "high";
interface ShipmentSearchFormState {
  q: string;
  entity_q: string;
  line_q: string;
  serial_number: string;
  destination_country: string;
}

interface CountryTooltipInfo {
  name: string;
  iso2: string;
  tier: CountryRiskTier;
}

const INPUT_CLS =
  "rounded border border-gray-200 bg-white px-2 py-1.5 text-sm text-xlent-ink focus:outline-none focus:ring-1 focus:ring-xlent-primary";

function resolveIso2(props: Record<string, string>): string {
  const iso2 = props["ISO3166-1-Alpha-2"] ?? "";
  if (iso2 !== "-99" && iso2 !== "") return iso2;
  return NAME_TO_ISO2[props.name ?? ""] ?? "";
}

function tierStats(): Record<CountryRiskTier, number> {
  const counts = { 1: 0, 2: 0, 3: 0, 4: 0 } as Record<CountryRiskTier, number>;
  for (const t of Object.values(ALL_COUNTRY_RISKS)) counts[t as CountryRiskTier] += 1;
  return counts;
}

function routeColor(level: ShipmentMapRoute["risk_level"]): string {
  if (level === "high") return "#dc2626";
  if (level === "medium") return "#ca8a04";
  return "#16a34a";
}

function routeWeight(level: ShipmentMapRoute["risk_level"]): number {
  return level === "high" ? 2.3 : 1.6;
}

export function MapsPage() {
  const { t } = useTranslation("pages");
  const navigate = useNavigate();

  const [showRiskLayer, setShowRiskLayer] = useState(true);
  const [showShipmentsLayer, setShowShipmentsLayer] = useState(true);
  const [activeTier, setActiveTier] = useState<CountryRiskTier | null>(null);
  const [countryTooltip, setCountryTooltip] = useState<CountryTooltipInfo | null>(null);

  const [risk, setRisk] = useState<RiskFilter>("all");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [maxLookups, setMaxLookups] = useState<number>(30);

  const [searchForm, setSearchForm] = useState<ShipmentSearchFormState>({
    q: "",
    entity_q: "",
    line_q: "",
    serial_number: "",
    destination_country: "",
  });
  const [submittedSearch, setSubmittedSearch] = useState<ShipmentSearchFormState>({
    q: "",
    entity_q: "",
    line_q: "",
    serial_number: "",
    destination_country: "",
  });
  const [searchCountryError, setSearchCountryError] = useState<string | null>(null);

  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const [geojsonLoading, setGeojsonLoading] = useState(true);
  const [geojsonError, setGeojsonError] = useState<string | null>(null);

  const activeTierRef = useRef<CountryRiskTier | null>(null);
  const showRiskRef = useRef<boolean>(showRiskLayer);
  useEffect(() => {
    activeTierRef.current = activeTier;
  }, [activeTier]);
  useEffect(() => {
    showRiskRef.current = showRiskLayer;
  }, [showRiskLayer]);

  const stats = tierStats();
  const tierLabel = useCallback((tier: CountryRiskTier) => t(`risk_map.tier.${tier}.label`), [t]);
  const tierDescription = useCallback((tier: CountryRiskTier) => t(`risk_map.tier.${tier}.description`), [t]);

  const filters = useMemo(
    () => ({
      limit: 1000,
      risk: risk === "all" ? null : risk,
      date_from: dateFrom || null,
      date_to: dateTo || null,
      max_geocode_lookups: maxLookups,
    }),
    [risk, dateFrom, dateTo, maxLookups],
  );

  const mapQuery = useShipmentMap(filters, true);
  const rawRoutes = mapQuery.data?.items ?? [];

  const hasSearchCriteria = useMemo(
    () =>
      Boolean(submittedSearch.q) ||
      Boolean(submittedSearch.entity_q) ||
      Boolean(submittedSearch.line_q) ||
      Boolean(submittedSearch.serial_number) ||
      Boolean(submittedSearch.destination_country) ||
      Boolean(dateFrom) ||
      Boolean(dateTo),
    [submittedSearch, dateFrom, dateTo],
  );

  const searchParams = useMemo(
    () => ({
      q: submittedSearch.q,
      entity_q: submittedSearch.entity_q,
      line_q: submittedSearch.line_q,
      serial_number: submittedSearch.serial_number,
      destination_country: submittedSearch.destination_country,
      date_from: dateFrom || "",
      date_to: dateTo || "",
      limit: 1000,
      offset: 0,
    }),
    [submittedSearch, dateFrom, dateTo],
  );
  const invoiceSearch = useInvoiceSearch(searchParams, hasSearchCriteria);

  const matchedInvoiceIds = useMemo(() => {
    if (!invoiceSearch.data) return null;
    return new Set(invoiceSearch.data.hits.map((hit) => hit.invoice_id));
  }, [invoiceSearch.data]);

  const routes = useMemo(() => {
    if (!hasSearchCriteria || !matchedInvoiceIds) return rawRoutes;
    return rawRoutes.filter((route) => matchedInvoiceIds.has(route.invoice_id));
  }, [hasSearchCriteria, matchedInvoiceIds, rawRoutes]);

  const mapCenter: [number, number] = useMemo(() => {
    if (!showShipmentsLayer || routes.length === 0) return [20, 10];
    const lat = routes.reduce((acc, r) => acc + r.source.lat + r.destination.lat, 0) / (routes.length * 2);
    const lon = routes.reduce((acc, r) => acc + r.source.lon + r.destination.lon, 0) / (routes.length * 2);
    return [lat, lon];
  }, [routes, showShipmentsLayer]);

  useEffect(() => {
    fetch(GEOJSON_URL)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<GeoJsonObject>;
      })
      .then((data) => {
        setGeojson(data);
        setGeojsonLoading(false);
      })
      .catch((err: Error) => {
        setGeojsonError(err.message);
        setGeojsonLoading(false);
      });
  }, []);

  const riskStyle = useCallback(
    (feature: Feature | undefined) => {
      const iso2 = resolveIso2((feature?.properties ?? {}) as Record<string, string>);
      const tier = (ALL_COUNTRY_RISKS[iso2] ?? 2) as CountryRiskTier;
      const filtered = activeTier !== null && tier !== activeTier;
      if (!showRiskLayer) {
        return { fillColor: "#f3f4f6", fillOpacity: 0.08, color: "#d1d5db", weight: 0.3, opacity: 0.3 };
      }
      if (filtered) {
        return { fillColor: "#e5e7eb", fillOpacity: 0.15, color: "#d1d5db", weight: 0.35, opacity: 0.5 };
      }
      return {
        fillColor: getTierFillColor(tier),
        fillOpacity: showShipmentsLayer ? 0.45 : 0.72,
        color: getTierStrokeColor(tier),
        weight: 0.75,
        opacity: 0.8,
      };
    },
    [activeTier, showRiskLayer, showShipmentsLayer],
  );

  const onEachCountry = useCallback((feature: Feature, layer: Layer) => {
    const props = (feature?.properties ?? {}) as Record<string, string>;
    const iso2 = resolveIso2(props);
    const name = props.name ?? iso2;
    const tier = (ALL_COUNTRY_RISKS[iso2] ?? 2) as CountryRiskTier;
    layer.on({
      mouseover: () => {
        if (!showRiskRef.current) return;
        (layer as Path).setStyle({ weight: 2.2, fillOpacity: 0.85 });
        setCountryTooltip({ name, iso2, tier });
      },
      mouseout: () => {
        (layer as Path).setStyle(riskStyle(feature));
        setCountryTooltip(null);
      },
    });
  }, [riskStyle]);

  function updateSearchField<K extends keyof ShipmentSearchFormState>(key: K, value: string) {
    setSearchForm((prev) => ({ ...prev, [key]: value }));
  }

  function submitSearch() {
    const resolvedCountry = resolveCountryToIso2(searchForm.destination_country);
    if (searchForm.destination_country.trim() && !resolvedCountry) {
      setSearchCountryError(t("shipments_map.country_invalid"));
      return;
    }
    setSearchCountryError(null);
    setSubmittedSearch({
      q: searchForm.q.trim(),
      entity_q: searchForm.entity_q.trim(),
      line_q: searchForm.line_q.trim(),
      serial_number: searchForm.serial_number.trim(),
      destination_country: resolvedCountry,
    });
  }

  function resetSearch() {
    const empty: ShipmentSearchFormState = {
      q: "",
      entity_q: "",
      line_q: "",
      serial_number: "",
      destination_country: "",
    };
    setSearchForm(empty);
    setSubmittedSearch(empty);
    setSearchCountryError(null);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-xlent-ink">{t("maps.title")}</h1>
        <p className="mt-1 text-sm text-xlent-muted">{t("maps.subtitle")}</p>
        {hasSearchCriteria && (
          <p className="mt-1 text-xs text-xlent-muted">
            {t("shipments_map.filtered_routes", {
              shown: routes.length,
              total: mapQuery.data?.total_routes ?? rawRoutes.length,
            })}
          </p>
        )}
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
          {t("maps.layers_title")}
        </h2>
        <div className="flex flex-wrap items-center gap-4">
          <label className="inline-flex items-center gap-2 text-sm text-xlent-ink">
            <input
              type="checkbox"
              checked={showRiskLayer}
              onChange={(e) => setShowRiskLayer(e.target.checked)}
            />
            {t("maps.show_risk_layer")}
          </label>
          <label className="inline-flex items-center gap-2 text-sm text-xlent-ink">
            <input
              type="checkbox"
              checked={showShipmentsLayer}
              onChange={(e) => setShowShipmentsLayer(e.target.checked)}
            />
            {t("maps.show_shipments_layer")}
          </label>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
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
                <span className="text-xs font-semibold">{tierLabel(tier)}</span>
                <span className="ml-auto text-xs font-medium opacity-70">{stats[tier]}</span>
              </div>
              <p className="mt-1 text-xs leading-snug opacity-75">{tierDescription(tier)}</p>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
          {t("maps.shipment_filters_title")}
        </h2>
        <div className="grid gap-3 md:grid-cols-5">
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.risk")}</label>
            <select className={INPUT_CLS} value={risk} onChange={(e) => setRisk(e.target.value as RiskFilter)}>
              <option value="all">{t("shipments_map.all")}</option>
              <option value="low">{t("shipments_map.low")}</option>
              <option value="medium">{t("shipments_map.medium")}</option>
              <option value="high">{t("shipments_map.high")}</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.from_date")}</label>
            <input type="date" className={INPUT_CLS} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.to_date")}</label>
            <input type="date" className={INPUT_CLS} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.max_lookups")}</label>
            <input
              type="number"
              min={0}
              max={200}
              className={INPUT_CLS}
              value={maxLookups}
              onChange={(e) => setMaxLookups(Math.max(0, Math.min(200, Number(e.target.value) || 0)))}
            />
          </div>
          <div className="self-end text-xs text-xlent-muted">
            {mapQuery.isFetching ? t("shipments_map.loading_map") : t("shipments_map.routes_count", { count: mapQuery.data?.total_routes ?? 0 })}
          </div>
        </div>
        {mapQuery.data && (
          <p className="mt-2 text-xs text-xlent-muted">
            {t("shipments_map.stats", {
              missing: mapQuery.data.missing_location_count,
              cache: mapQuery.data.geocode_cache_hits,
              external: mapQuery.data.geocode_external_calls,
            })}
          </p>
        )}
        {mapQuery.error && (
          <p className="mt-2 text-xs text-traffic-red">{t("shipments_map.error")}</p>
        )}
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
          {t("maps.shipment_search_title")}
        </h2>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.global_search")}</label>
            <input
              className={INPUT_CLS}
              value={searchForm.q}
              onChange={(e) => updateSearchField("q", e.target.value)}
              placeholder={t("shipments_map.global_placeholder")}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.entity_fuzzy")}</label>
            <input
              className={INPUT_CLS}
              value={searchForm.entity_q}
              onChange={(e) => updateSearchField("entity_q", e.target.value)}
              placeholder={t("shipments_map.example_rosneft")}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.line_fuzzy")}</label>
            <input
              className={INPUT_CLS}
              value={searchForm.line_q}
              onChange={(e) => updateSearchField("line_q", e.target.value)}
              placeholder={t("shipments_map.example_navigation")}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.serial_exact")}</label>
            <input
              className={INPUT_CLS}
              value={searchForm.serial_number}
              onChange={(e) => updateSearchField("serial_number", e.target.value)}
              placeholder={t("shipments_map.example_serial")}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">{t("shipments_map.destination_iso2")}</label>
            <input
              className={INPUT_CLS}
              value={searchForm.destination_country}
              onChange={(e) => {
                updateSearchField("destination_country", e.target.value);
                setSearchCountryError(null);
              }}
              placeholder={t("shipments_map.example_fr")}
              maxLength={32}
            />
            {searchCountryError && (
              <p className="mt-1 text-xs text-traffic-red">{searchCountryError}</p>
            )}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            onClick={submitSearch}
            className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90"
          >
            {t("shipments_map.search_button")}
          </button>
          <button
            onClick={resetSearch}
            className="rounded border border-gray-200 px-3 py-1.5 text-sm text-xlent-muted hover:bg-gray-50"
          >
            {t("shipments_map.reset_button")}
          </button>
          {hasSearchCriteria && (
            <span className="text-xs text-xlent-muted">
              {invoiceSearch.isFetching
                ? t("shipments_map.searching")
                : t("shipments_map.search_hits", { count: invoiceSearch.data?.total ?? 0 })}
            </span>
          )}
        </div>
        {hasSearchCriteria && invoiceSearch.error && (
          <p className="mt-2 text-xs text-traffic-red">{t("shipments_map.search_failed")}</p>
        )}
      </section>

      <div className="relative overflow-hidden rounded-lg border border-gray-200" style={{ height: "640px" }}>
        {(geojsonLoading || mapQuery.isFetching) && (
          <div className="pointer-events-none absolute right-3 top-3 z-[1000] rounded bg-white/90 px-2 py-1 text-xs text-xlent-muted shadow">
            {geojsonLoading ? t("risk_map.loading_borders") : t("shipments_map.loading_map")}
          </div>
        )}
        {geojsonError && (
          <div className="absolute inset-0 z-[1001] flex items-center justify-center bg-red-50 p-6 text-center">
            <div>
              <p className="text-sm font-medium text-traffic-red">{t("risk_map.load_error_title")}</p>
              <p className="mt-1 text-xs text-traffic-red/80">{geojsonError}</p>
            </div>
          </div>
        )}

        <MapContainer center={mapCenter} zoom={2} minZoom={1} maxZoom={8} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            opacity={0.45}
          />

          {geojson && (
            <GeoJSON
              key={`${String(showRiskLayer)}-${String(activeTier)}`}
              data={geojson}
              style={riskStyle}
              onEachFeature={onEachCountry}
            />
          )}

          {showShipmentsLayer && routes.map((route) => {
            const color = routeColor(route.risk_level);
            return (
              <Fragment key={route.invoice_id}>
                <Polyline
                  positions={[
                    [route.source.lat, route.source.lon],
                    [route.destination.lat, route.destination.lon],
                  ]}
                  pathOptions={{
                    color,
                    weight: routeWeight(route.risk_level),
                    opacity: 0.9,
                    dashArray: route.low_precision_line ? "7 6" : undefined,
                    interactive: false,
                  }}
                />
                <Polyline
                  positions={[
                    [route.source.lat, route.source.lon],
                    [route.destination.lat, route.destination.lon],
                  ]}
                  pathOptions={{
                    color,
                    weight: 12,
                    opacity: 0.01,
                    dashArray: route.low_precision_line ? "7 6" : undefined,
                    interactive: true,
                  }}
                >
                  <Tooltip sticky>
                    <div className="text-xs">
                      <div className="font-semibold">{route.original_filename ?? route.invoice_number ?? route.invoice_id}</div>
                      <div>
                        {route.source.name ?? t("shipments_map.unknown_sender")} → {route.destination.name ?? t("shipments_map.unknown_receiver")}
                      </div>
                      <div>{t("shipments_map.risk")}: {route.risk_level}</div>
                    </div>
                  </Tooltip>
                  <Popup>
                    <div className="space-y-1 text-xs">
                      <div className="font-semibold text-sm">{route.original_filename ?? route.invoice_number ?? route.invoice_id}</div>
                      <div>
                        <span className="font-medium">{t("shipments_map.from")}:</span> {route.source.name ?? "—"} ({route.source.country ?? "—"})
                      </div>
                      <div>
                        <span className="font-medium">{t("shipments_map.to")}:</span> {route.destination.name ?? "—"} ({route.destination.country ?? "—"})
                      </div>
                      <div>
                        <span className="font-medium">{t("shipments_map.precision")}:</span> {route.source.geo_precision} / {route.destination.geo_precision}
                      </div>
                      <div>
                        <span className="font-medium">{t("shipments_map.sanction_hits")}:</span> {route.screening_hits}
                      </div>
                      <button
                        onClick={() => navigate(`/invoices/${route.invoice_id}`)}
                        className="mt-2 rounded bg-xlent-primary px-2 py-1 text-xs font-medium text-white hover:bg-xlent-primary/90"
                      >
                        {t("shipments_map.open_invoice")}
                      </button>
                    </div>
                  </Popup>
                </Polyline>
                <CircleMarker
                  center={[route.source.lat, route.source.lon]}
                  radius={5}
                  pathOptions={{ color: "#1d4ed8", fillColor: "#1d4ed8", fillOpacity: 0.85 }}
                >
                  <Tooltip direction="top">{t("shipments_map.sender")}: {route.source.name ?? t("shipments_map.unknown")}</Tooltip>
                </CircleMarker>
                <CircleMarker
                  center={[route.destination.lat, route.destination.lon]}
                  radius={5}
                  pathOptions={{ color: "#9333ea", fillColor: "#9333ea", fillOpacity: 0.85 }}
                >
                  <Tooltip direction="top">{t("shipments_map.receiver")}: {route.destination.name ?? t("shipments_map.unknown")}</Tooltip>
                </CircleMarker>
              </Fragment>
            );
          })}
        </MapContainer>

        {showRiskLayer && countryTooltip && (
          <div className="pointer-events-none absolute bottom-4 left-4 z-[1000] min-w-52 rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-lg">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold uppercase text-xlent-muted">
                {countryTooltip.iso2}
              </span>
              <span className="font-medium text-xlent-ink">{countryTooltip.name}</span>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span
                className="inline-block h-3 w-3 flex-shrink-0 rounded-full"
                style={{ backgroundColor: TIER_COLORS[countryTooltip.tier] }}
              />
              <span className="text-xs font-medium" style={{ color: TIER_COLORS[countryTooltip.tier] }}>
                {tierLabel(countryTooltip.tier)}
              </span>
            </div>
            <p className="mt-1 text-xs leading-snug text-xlent-muted">
              {tierDescription(countryTooltip.tier)}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
