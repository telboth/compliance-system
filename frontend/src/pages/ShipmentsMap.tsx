import { Fragment, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip } from "react-leaflet";

import { useShipmentMap } from "@/hooks/useInvoices";
import type { ShipmentMapRoute } from "@/api/types";

type RiskFilter = "all" | "low" | "medium" | "high";

const INPUT_CLS =
  "rounded border border-gray-200 bg-white px-2 py-1.5 text-sm text-xlent-ink focus:outline-none focus:ring-1 focus:ring-xlent-primary";

function riskColor(level: ShipmentMapRoute["risk_level"]): string {
  if (level === "high") return "#dc2626";
  if (level === "medium") return "#ca8a04";
  return "#16a34a";
}

export function ShipmentsMapPage() {
  const navigate = useNavigate();
  const [risk, setRisk] = useState<RiskFilter>("all");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [maxLookups, setMaxLookups] = useState<number>(30);

  const filters = useMemo(
    () => ({
      limit: 500,
      risk: risk === "all" ? null : risk,
      date_from: dateFrom || null,
      date_to: dateTo || null,
      max_geocode_lookups: maxLookups,
    }),
    [risk, dateFrom, dateTo, maxLookups],
  );
  const mapQuery = useShipmentMap(filters, true);
  const routes = mapQuery.data?.items ?? [];

  const center: [number, number] = useMemo(() => {
    if (routes.length === 0) return [20, 10];
    const lat = routes.reduce((acc, r) => acc + r.source.lat + r.destination.lat, 0) / (routes.length * 2);
    const lon = routes.reduce((acc, r) => acc + r.source.lon + r.destination.lon, 0) / (routes.length * 2);
    return [lat, lon];
  }, [routes]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-xlent-ink">Forsendelseskart</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          Viser avsender og mottaker med linje mellom. Stiplet linje betyr lav lokasjonspresisjon (kun landnivå).
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="grid gap-3 md:grid-cols-5">
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">Risiko</label>
            <select className={INPUT_CLS} value={risk} onChange={(e) => setRisk(e.target.value as RiskFilter)}>
              <option value="all">Alle</option>
              <option value="low">Lav</option>
              <option value="medium">Medium</option>
              <option value="high">Hoy</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">Fra dato</label>
            <input type="date" className={INPUT_CLS} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">Til dato</label>
            <input type="date" className={INPUT_CLS} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-xlent-muted">Maks eksterne geokoding-kall</label>
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
            {mapQuery.isFetching ? "Laster kartdata …" : `Ruter: ${mapQuery.data?.total_routes ?? 0}`}
          </div>
        </div>
        {mapQuery.data && (
          <p className="mt-2 text-xs text-xlent-muted">
            Mangler lokasjon: {mapQuery.data.missing_location_count} · Cache-treff: {mapQuery.data.geocode_cache_hits} · Eksterne kall: {mapQuery.data.geocode_external_calls}
          </p>
        )}
        {mapQuery.error && (
          <p className="mt-2 text-xs text-traffic-red">Kunne ikke hente forsendelseskart-data.</p>
        )}
      </section>

      <div className="overflow-hidden rounded-lg border border-gray-200" style={{ height: "560px" }}>
        <MapContainer center={center} zoom={2} minZoom={1} maxZoom={8} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            opacity={0.5}
          />

          {routes.map((route) => {
            const color = riskColor(route.risk_level);
            return (
              <Fragment key={route.invoice_id}>
                <Polyline
                  positions={[
                    [route.source.lat, route.source.lon],
                    [route.destination.lat, route.destination.lon],
                  ]}
                  pathOptions={{
                    color,
                    weight: route.risk_level === "high" ? 2.2 : 1.4,
                    opacity: 0.9,
                    dashArray: route.low_precision_line ? "7 6" : undefined,
                  }}
                >
                  <Tooltip sticky>
                    <div className="text-xs">
                      <div className="font-semibold">{route.original_filename ?? route.invoice_number ?? route.invoice_id}</div>
                      <div>
                        {route.source.name ?? "Ukjent avsender"} → {route.destination.name ?? "Ukjent mottaker"}
                      </div>
                      <div>Risiko: {route.risk_level}</div>
                    </div>
                  </Tooltip>
                  <Popup>
                    <div className="space-y-1 text-xs">
                      <div className="font-semibold text-sm">{route.original_filename ?? route.invoice_number ?? route.invoice_id}</div>
                      <div>
                        <span className="font-medium">Fra:</span> {route.source.name ?? "—"} ({route.source.country ?? "—"})
                      </div>
                      <div>
                        <span className="font-medium">Til:</span> {route.destination.name ?? "—"} ({route.destination.country ?? "—"})
                      </div>
                      <div>
                        <span className="font-medium">Presisjon:</span> {route.source.geo_precision} / {route.destination.geo_precision}
                      </div>
                      <div>
                        <span className="font-medium">Sanksjonstreff:</span> {route.screening_hits}
                      </div>
                      <button
                        onClick={() => navigate(`/invoices/${route.invoice_id}`)}
                        className="mt-2 rounded bg-xlent-primary px-2 py-1 text-xs font-medium text-white hover:bg-xlent-primary/90"
                      >
                        Apne invoice
                      </button>
                    </div>
                  </Popup>
                </Polyline>

                <CircleMarker
                  center={[route.source.lat, route.source.lon]}
                  radius={5}
                  pathOptions={{ color: "#1d4ed8", fillColor: "#1d4ed8", fillOpacity: 0.85 }}
                >
                  <Tooltip direction="top">Avsender: {route.source.name ?? "Ukjent"}</Tooltip>
                </CircleMarker>
                <CircleMarker
                  center={[route.destination.lat, route.destination.lon]}
                  radius={5}
                  pathOptions={{ color: "#9333ea", fillColor: "#9333ea", fillOpacity: 0.85 }}
                >
                  <Tooltip direction="top">Mottaker: {route.destination.name ?? "Ukjent"}</Tooltip>
                </CircleMarker>
              </Fragment>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}
