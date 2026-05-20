/**
 * About — systemdokumentasjon for XLENT Compliance.
 *
 * Forklarer hva systemet er, hvordan arbeidsflyten fungerer,
 * hvilke sider som finnes, roller/tilganger og teknisk stack.
 */

import { useState } from "react";
import clsx from "clsx";

// ── Tab-definisjon ─────────────────────────────────────────────────────────────

const TABS = [
  { id: "overview",  label: "Oversikt" },
  { id: "workflow",  label: "Arbeidsflyt" },
  { id: "pages",     label: "Sider" },
  { id: "roles",     label: "Roller" },
  { id: "technical", label: "Teknisk" },
] as const;
type TabId = (typeof TABS)[number]["id"];

// ── Generiske layout-hjelpere ──────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-4 text-lg font-semibold text-xlent-ink">{children}</h2>
  );
}

function SectionText({ children }: { children: React.ReactNode }) {
  return <p className="mb-4 max-w-3xl text-sm leading-relaxed text-xlent-ink">{children}</p>;
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded-lg border border-gray-200 bg-white p-5", className)}>
      {children}
    </div>
  );
}

// ── OVERSIKT ──────────────────────────────────────────────────────────────────

const KEY_FEATURES = [
  {
    icon: "📄",
    title: "Automatisk faktura-innlesing",
    desc: "PDF-fakturaer lastes opp og leses inn automatisk med OCR og dokumentparsing. Relevante felter ekstraheres uten manuell registrering.",
  },
  {
    icon: "🤖",
    title: "AI-drevet ekstraksjon",
    desc: "En stor språkmodell (Claude / GPT-4o) trekker ut alle nøkkelfelt: selger, kjøper, speditør, land, HS-koder, beløp og varebeskrivelse – med konfidensscore for hvert felt.",
  },
  {
    icon: "🔎",
    title: "Sanksjonsskjerming",
    desc: "Alle involverte parter sjekkes mot OpenSanctions-databasen via Yente med fuzzy matching. Systemet finner treff selv ved stavefeil eller navnevarianter.",
  },
  {
    icon: "⚙️",
    title: "Regelmotor",
    desc: "YAML-baserte compliance-regler evalueres automatisk etter ekstraksjon. Reglene kan sjekke destinasjonsland, HS-koder, entitetsnavn m.m. og sette score grønn/gul/rød.",
  },
  {
    icon: "✅",
    title: "Manuell review-kø",
    desc: "Fakturaer med gul eller rød score havner i en prioritert review-kø. Compliance-offiserer kan godkjenne eller avvise med begrunnelse og fullstendig revisjonsspor.",
  },
  {
    icon: "🌍",
    title: "Landrisikoklassifisering",
    desc: "Alle land er klassifisert i fire risikonivåer (Lav/Normal/Forhøyet/Høy) basert på NATO-medlemskap og internasjonale sanksjonsregimer.",
  },
  {
    icon: "🕸️",
    title: "Utvidet screening",
    desc: "Dypere analyse av enkeltentiteter via Wikidata-grafer. Avdekker eierskap, styremedlemmer og andre relasjoner til sanksjonerte parter.",
  },
  {
    icon: "📋",
    title: "Rammeavtale-sjekk",
    desc: "Lastede PDF-rammeavtaler ekstraheres av AI og sjekkes mot fakturaene – bl.a. tillatte destinasjonsland, produktbegrensninger og verdimaksima.",
  },
];

function OverviewTab() {
  return (
    <div className="space-y-8">
      <div>
        <SectionTitle>Hva er XLENT Compliance?</SectionTitle>
        <SectionText>
          XLENT Compliance er et AI-drevet system for eksportkontroll og handelscompliance, utviklet
          for norske bedrifter som eksporterer varer og tjenester. Systemet automatiserer arbeidet
          med å sjekke fakturaer mot internasjonale sanksjonslister, interne regler og
          rammeavtale-vilkår – og gir compliance-teamet et strukturert grunnlag for beslutninger.
        </SectionText>
        <SectionText>
          Kjernen i systemet er en pipeline der PDF-fakturaer lastes opp, all relevant informasjon
          ekstraheres automatisk av en stor språkmodell, alle parter sjekkes mot
          OpenSanctions-databasen, og egendefinerte regler evalueres. Resultatet er en
          trafikklys-score (grønn / gul / rød) som viser om fakturaen kan behandles direkte eller
          trenger manuell vurdering.
        </SectionText>
        <SectionText>
          Datakilden for sanksjonsskjerming er{" "}
          <span className="font-medium">OpenSanctions</span> – en åpen og kontinuerlig oppdatert
          database som samler sanksjonsregister fra EU, USA (OFAC), FN, Storbritannia og en rekke
          andre myndigheter.
        </SectionText>
      </div>

      <div>
        <SectionTitle>Nøkkelfunksjoner</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-2">
          {KEY_FEATURES.map((f) => (
            <Card key={f.title} className="flex gap-3">
              <span className="mt-0.5 text-2xl leading-none">{f.icon}</span>
              <div>
                <p className="mb-1 text-sm font-semibold text-xlent-ink">{f.title}</p>
                <p className="text-sm leading-relaxed text-xlent-muted">{f.desc}</p>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── ARBEIDSFLYT ───────────────────────────────────────────────────────────────

const WORKFLOW_STEPS = [
  {
    step: 1,
    icon: "📤",
    title: "Opplasting",
    color: "bg-blue-100 text-blue-700 border-blue-200",
    desc: "En PDF-faktura lastes opp via brukergrensesnittet. Filen lagres og et oppdrag opprettes i systemet med status «uploaded».",
    detail: "Støtter standard PDF-filer. Filen oppbevares kryptert og tilknyttes faktura-ID.",
  },
  {
    step: 2,
    icon: "🔍",
    title: "Parsing",
    color: "bg-purple-100 text-purple-700 border-purple-200",
    desc: "Systemet leser PDF-en og trekker ut råtekst (OCR ved behov). Status settes til «parsing».",
    detail: "Bruker PyMuPDF for digital PDF og OCR-fallback for skannede dokumenter.",
  },
  {
    step: 3,
    icon: "🤖",
    title: "AI-ekstraksjon",
    color: "bg-indigo-100 text-indigo-700 border-indigo-200",
    desc: "En stor språkmodell analyserer fakturateksten og ekstraherer strukturerte data: selger, kjøper, speditør, destinasjonsland, HS-koder, linjebeløp og mer. Status settes til «extracted».",
    detail: "Primærmodell: Claude (Anthropic). Fallback: GPT-4o (OpenAI). Hvert felt får en konfidensscore 0–1. Felter med lav konfidens markeres med oransje prikk for manuell sjekk.",
  },
  {
    step: 4,
    icon: "🔎",
    title: "Sanksjonsskjerming",
    color: "bg-amber-100 text-amber-700 border-amber-200",
    desc: "Alle ekstraherte entiteter (selger, kjøper, speditør m.fl.) sjekkes mot OpenSanctions via Yente. Fuzzy matching finner treff selv ved navnevarianter. Status settes til «screening».",
    detail: [
      "Treff-terskel: 0.70 → Potensielt treff (krever manuell vurdering)",
      "Bekreftet-terskel: 0.79 → Bekreftet treff (rød score, blokkering anbefalt)",
      "Kilde: OpenSanctions med daglig oppdatering kl. 07:40",
    ],
  },
  {
    step: 5,
    icon: "⚙️",
    title: "Regelkjøring",
    color: "bg-orange-100 text-orange-700 border-orange-200",
    desc: "Alle aktive YAML-regler evalueres mot fakturadataene. Reglene kan sette flagg og endre score.",
    detail: [
      "Regeltyper: destinasjonsland, HS-kode, entitetsnavn, e-postdomene, beløpsgrenser",
      "Operatorer: in, not_in, equals, regex, gt, lt",
      "Operator-kombinasjon: AND / OR på tvers av betingelser",
    ],
  },
  {
    step: 6,
    icon: "🚦",
    title: "Scoring",
    color: "bg-green-100 text-green-700 border-green-200",
    desc: "Systemet beregner en samlet compliance-score basert på sanksjons-treff og regel-utslag. Status settes til «screened».",
    detail: [
      "🟢 Grønn – ingen treff, alle regler bestått",
      "🟡 Gul – potensielle treff eller advarslingsregler utløst",
      "🔴 Rød – bekreftet sanksjonstreff eller blokkerende regler",
    ],
  },
  {
    step: 7,
    icon: "👤",
    title: "Manuell review",
    color: "bg-red-100 text-red-700 border-red-200",
    desc: "Gule og røde fakturaer havner i review-køen og venter på en compliance-offisers vurdering. Køen er sortert rød-først, ueldte først.",
    detail: "Offiseren kan se alle detaljer, sanksjons-treff, regelutslag og revisjonsspor før beslutning. Fakturaen kan «claimes» for å unngå dobbeltbehandling.",
  },
  {
    step: 8,
    icon: "✅",
    title: "Beslutning",
    color: "bg-teal-100 text-teal-700 border-teal-200",
    desc: "Compliance-offiseren godkjenner eller avviser fakturaen med en skriftlig begrunnelse. Beslutningen, brukeren og tidsstempelet lagres i revisjonssporet.",
    detail: [
      "Godkjent → status «approved», faktura kan behandles videre",
      "Avvist → status «blocked», faktura sperres",
      "Alle handlinger logges uforanderlig i audit-loggen",
    ],
  },
];

function WorkflowStep({
  s,
  isLast,
}: {
  s: (typeof WORKFLOW_STEPS)[number];
  isLast: boolean;
}) {
  const [open, setOpen] = useState(false);
  const detailLines = Array.isArray(s.detail) ? s.detail : [s.detail];

  return (
    <div className="flex gap-4">
      {/* Linje-connector */}
      <div className="flex flex-col items-center">
        <div
          className={clsx(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-base font-bold",
            s.color,
          )}
        >
          {s.step}
        </div>
        {!isLast && <div className="mt-1 w-px flex-1 bg-gray-200" />}
      </div>

      {/* Innhold */}
      <div className="mb-6 min-w-0 flex-1">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-start gap-2 text-left"
        >
          <span className="text-xl leading-none">{s.icon}</span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-xlent-ink">{s.title}</p>
            <p className="mt-0.5 text-sm leading-relaxed text-xlent-muted">{s.desc}</p>
          </div>
          <span className="mt-0.5 text-xs text-xlent-muted">{open ? "▲" : "▼"}</span>
        </button>

        {open && (
          <div className="mt-3 rounded border border-gray-100 bg-gray-50 p-3">
            {detailLines.map((line, i) => (
              <p key={i} className="text-xs leading-relaxed text-xlent-ink">
                {line}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function WorkflowTab() {
  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>Pipeline-oversikt</SectionTitle>
        <SectionText>
          Hvert trinn kjøres automatisk i bakgrunnen via en Celery-oppgavekø. Klikk på et steg for
          å se tekniske detaljer.
        </SectionText>
      </div>
      <div className="max-w-2xl">
        {WORKFLOW_STEPS.map((s, i) => (
          <WorkflowStep key={s.step} s={s} isLast={i === WORKFLOW_STEPS.length - 1} />
        ))}
      </div>
    </div>
  );
}

// ── SIDER ─────────────────────────────────────────────────────────────────────

const PAGE_DOCS = [
  {
    icon: "📋",
    name: "Fakturaer",
    path: "/invoices",
    access: "Alle roller",
    desc: "Hoved-oversikten over alle fakturaer i systemet. Støtter filtrering på status, compliance-score, retning (import/eksport), land og fritekst. Viser sanksjonsstatus og gir direkte tilgang til opplasting.",
  },
  {
    icon: "🗂️",
    name: "Fakturadetalj",
    path: "/invoices/:id",
    access: "Alle roller",
    desc: "Detaljvisning av én faktura. Viser PDF-forhåndsvisning, alle ekstraherte felter med konfidensscore (redigerbare), entitetsliste, sanksjons-treff med matchdetaljer, regelutslag, rammeavtale-sjekk og fullstendig revisjonsspor. Herfra kan man starte skjerming, utvidet screening og review.",
  },
  {
    icon: "📊",
    name: "Dashboard",
    path: "/dashboard",
    access: "Alle roller med dashboard:view",
    desc: "KPI-oversikt med totalt antall fakturaer, score-fordeling (grønn/gul/rød), gjennomsnittlig prosesseringstid, antall i review-kø og ukentlig trendbilde. Gir raskt blikk på compliancestatus.",
  },
  {
    icon: "👥",
    name: "Kunder",
    path: "/customers",
    access: "Compliance officer, Controller, Admin",
    desc: "Liste over registrerte kunder/motparter med compliance-historikk. Viser hvilke fakturaer som er knyttet til hver kunde og om det finnes åpne funn.",
  },
  {
    icon: "⏳",
    name: "Review-kø",
    path: "/review-queue",
    access: "Compliance officer, Admin",
    desc: "Prioritert liste over fakturaer som venter på manuell beslutning (status «screened», score gul/rød). Sortert rød-først, ubehandlede først. Viser hvem som har tatt fakturaen, og om den er klar for review. Klikk for å gå direkte til fakturadetalj og fatte beslutning.",
  },
  {
    icon: "⚙️",
    name: "Regler",
    path: "/rules",
    access: "Compliance officer, Admin",
    desc: "Administrasjon av compliance-regelmotor. Regler skrives i YAML med betingelser og alvorlighetsgrad (grønn/gul/rød). Støtter inline testing mot eksempeldata uten å lagre, og kjøring av alle aktive regler på nytt mot eksisterende fakturaer.",
  },
  {
    icon: "🚫",
    name: "Intern sperreliste",
    path: "/watchlist",
    access: "Compliance officer, Admin",
    desc: "Administrasjon av virksomhetens interne sperreliste. Her legges til navn, e-postdomener og HS-koder som alltid skal gi utslag under skjerming – uavhengig av OpenSanctions-databasen. Hvert oppføring har alvorlighetsgrad, begrunnelse og kildehenvisning.",
  },
  {
    icon: "📜",
    name: "Rammeavtaler",
    path: "/agreements",
    access: "Alle roller med agreements:view",
    desc: "Opplasting og administrasjon av PDF-rammeavtaler. AI-en ekstraherer automatisk nøkkelvilkår som tillatte destinasjonsland, produktbegrensninger og verdimaksima. Herfra kan man se hvilke fakturaer som er sjekket mot avtalen og resultatet av sjekken.",
  },
  {
    icon: "🌍",
    name: "Kart",
    path: "/maps",
    access: "Alle roller",
    desc: "Interaktivt verdenskart med fargekodet landrisikoklassifisering (Tier 1–4). Kan filtreres på risikonivå. Har også et forsendelseskartlag som viser handelsruter basert på fakturaenes opprinnelses- og destinasjonsland.",
  },
  {
    icon: "🔎",
    name: "Sanksjonerte entiteter",
    path: "/sanctioned-entities",
    access: "Compliance officer, Admin",
    desc: "Direkte søk i OpenSanctions-databasen (via Yente). Søk på navn, land eller type. Viser alle sanksjonsregister der entiteten er oppført, med datokilde og tilleggsinfo. Inneholder knapp for å trigge manuell oppdatering av sanksjonsdatabasen.",
  },
  {
    icon: "🔍",
    name: "Fakturasøk",
    path: "/invoice-search",
    access: "Alle roller",
    desc: "Avansert fulltekstsøk på tvers av alle fakturaer og entiteter. Støtter søk på fakturanummer, serienummer, entitetsnavn, destinasjonsland og HS-kode. Resultater vises som liste med lenke til fakturadetalj.",
  },
  {
    icon: "🛠️",
    name: "Pipeline-drift",
    path: "/pipeline-ops",
    access: "Kun Admin",
    desc: "Driftsovervakning av bakgrunnspipelinen. Viser gjennomstrømning, gjennomsnittlig ventetid for ekstraksjon og skjerming, og fakturaer som sitter fast i en prosesseringsstatus. Admins kan trigge manuell re-prosessering av enkeltfakturaer.",
  },
  {
    icon: "🕸️",
    name: "Utvidet screening",
    path: "/invoices/:id/entities/:entityId/extended-screen/:runId",
    access: "Compliance officer, Admin",
    desc: "Nås fra fakturadetalj. Viser en relasjonsgraff for én entitet basert på Wikidata-data. Grafen avdekker eierstrukturer, styremedlemmer og andre tilknytninger til sanksjonerte parter. Hvert knutepunkt lenker til kildedata og kan gis tilbakemelding (relevant / ikke relevant).",
  },
];

function PagesTab() {
  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>Sider og funksjoner</SectionTitle>
        <SectionText>
          Systemet er delt i spesialiserte sider. Tilgangen til sidene styres av brukerens rolle.
        </SectionText>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {PAGE_DOCS.map((p) => (
          <Card key={p.path}>
            <div className="mb-2 flex items-start gap-2">
              <span className="text-xl leading-none">{p.icon}</span>
              <div className="flex-1">
                <p className="text-sm font-semibold text-xlent-ink">{p.name}</p>
                <p className="text-xs text-xlent-muted">{p.path}</p>
              </div>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
                {p.access}
              </span>
            </div>
            <p className="text-sm leading-relaxed text-xlent-muted">{p.desc}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ── ROLLER ────────────────────────────────────────────────────────────────────

const ROLES = [
  {
    name: "Admin",
    color: "bg-red-100 text-red-800",
    desc: "Full tilgang til alle sider og funksjoner, inkludert drift og pipeline-administrasjon.",
    perms: [
      "Laste opp, redigere og slette fakturaer",
      "Kjøre ekstraksjon og skjerming",
      "Godkjenne / avvise fakturaer",
      "Administrere regler og sperreliste",
      "Laste opp og administrere rammeavtaler",
      "Se og administrere kunder",
      "Pipeline-drift og re-prosessering",
      "Se alle kart og sanksjonerte entiteter",
    ],
  },
  {
    name: "C-level",
    color: "bg-indigo-100 text-indigo-800",
    desc: "Samme tilgang som Admin. Beregnet på ledere som trenger full oversikt uten å utføre driftsoppgaver.",
    perms: ["Alle sider og funksjoner (identisk med Admin)"],
  },
  {
    name: "Compliance officer",
    color: "bg-purple-100 text-purple-800",
    desc: "Hoved-brukerprofilen for daglig compliance-arbeid. Kan vurdere og beslutte, administrere regler og sperreliste.",
    perms: [
      "Laste opp og redigere fakturaer",
      "Kjøre ekstraksjon og skjerming",
      "Godkjenne / avvise fakturaer (review-kø)",
      "Administrere regler og sperreliste",
      "Laste opp og administrere rammeavtaler",
      "Se kunder",
      "Søke i sanksjonsdatabasen",
      "Dashboard, kart og fakturasøk",
    ],
  },
  {
    name: "Controller",
    color: "bg-blue-100 text-blue-800",
    desc: "Regnskapsroller som arbeider med fakturaer, men ikke tar compliance-beslutninger.",
    perms: [
      "Laste opp og redigere fakturaer",
      "Kjøre ekstraksjon",
      "Se og redigere kunder",
      "Se rammeavtaler",
      "Dashboard og fakturasøk",
      "Kart (lesetilgang)",
    ],
  },
  {
    name: "Readonly",
    color: "bg-gray-100 text-gray-700",
    desc: "Lesetilgang til de viktigste sidene. Kan ikke utføre noen handlinger.",
    perms: [
      "Se fakturaer",
      "Se dashboard",
      "Se regler (ikke redigere)",
      "Se rammeavtaler",
      "Se kunder",
    ],
  },
];

function RolesTab() {
  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>Roller og tilganger</SectionTitle>
        <SectionText>
          Tilgangsstyring er rollebasert (RBAC). Hver bruker har én rolle som bestemmer hvilke sider og handlinger som er tilgjengelige. I produksjon settes rollen via JWT-claims fra autentiseringsleverandøren. Under utvikling kan rollen byttes via rollevälgeren øverst til høyre.
        </SectionText>
      </div>
      <div className="space-y-4">
        {ROLES.map((r) => (
          <Card key={r.name}>
            <div className="mb-3 flex items-center gap-2">
              <span
                className={clsx(
                  "rounded-full px-2.5 py-0.5 text-xs font-semibold",
                  r.color,
                )}
              >
                {r.name}
              </span>
              <p className="text-sm text-xlent-muted">{r.desc}</p>
            </div>
            <ul className="grid gap-1 sm:grid-cols-2">
              {r.perms.map((p) => (
                <li key={p} className="flex items-start gap-1.5 text-xs text-xlent-ink">
                  <span className="mt-0.5 text-green-600">✓</span>
                  {p}
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ── TEKNISK ───────────────────────────────────────────────────────────────────

const TECH_STACK = [
  {
    category: "Frontend",
    items: [
      { name: "React 18", desc: "UI-rammeverk med Suspense og lazy-loading" },
      { name: "TypeScript", desc: "Statisk typing for hele frontend-kodebasen" },
      { name: "Vite", desc: "Bygge- og dev-server med rask HMR" },
      { name: "Tailwind CSS", desc: "Utility-first CSS med egendefinert designsystem" },
      { name: "React Query", desc: "Server-state og caching av API-kall" },
      { name: "React Router", desc: "Klient-side routing (SPA)" },
      { name: "react-leaflet", desc: "Interaktivt kart (OpenStreetMap-basert)" },
      { name: "i18next", desc: "Internasjonalisering (norsk / engelsk)" },
    ],
  },
  {
    category: "Backend",
    items: [
      { name: "FastAPI", desc: "Asynkront Python-API med OpenAPI-dokumentasjon" },
      { name: "SQLAlchemy (async)", desc: "ORM mot PostgreSQL med async-støtte" },
      { name: "Celery", desc: "Distribuert oppgavekø for bakgrunnsprosessering" },
      { name: "Alembic", desc: "Databasemigrasjoner" },
      { name: "Pydantic v2", desc: "Validering og serialisering av data" },
    ],
  },
  {
    category: "AI / LLM",
    items: [
      { name: "Anthropic Claude", desc: "Primær LLM for ekstraksjon og analyse" },
      { name: "OpenAI GPT-4o", desc: "Fallback-modell ved nedetid eller feil" },
      { name: "Modellvelger", desc: "Kan byttes live i UI-et via tannhjulet øverst" },
    ],
  },
  {
    category: "Sanksjonsdatabase",
    items: [
      { name: "Yente (OpenSanctions)", desc: "Sanksjonsskjermings-API med fuzzy matching" },
      { name: "Elasticsearch 8", desc: "Søkeindeks bak Yente for rask oppslag" },
      { name: "OpenSanctions-data", desc: "Daglig oppdatert fra EU, OFAC, FN, UK m.fl." },
    ],
  },
  {
    category: "Infrastruktur",
    items: [
      { name: "Docker Compose", desc: "Orkestrering av alle tjenester lokalt og i dev" },
      { name: "PostgreSQL 16", desc: "Hoved-database for alle faktura- og brukerdata" },
      { name: "Redis 7", desc: "Broker og result-backend for Celery" },
      { name: "Celery Beat", desc: "Planlagt daglig oppdatering av sanksjonslister" },
    ],
  },
];

const TIER_ROWS = [
  { tier: "Tier 1 – Lav", color: "bg-green-100 text-green-800", examples: "NATO-land (NO, DE, US, FR, GB, …)", rule: "NATO-medlemskap" },
  { tier: "Tier 2 – Normal", color: "bg-amber-100 text-amber-800", examples: "Flertallet av øvrige land", rule: "Standardnivå" },
  { tier: "Tier 3 – Forhøyet", color: "bg-orange-100 text-orange-800", examples: "CN, QA, SA, TR, UA, AZ, …", rule: "Geopolitisk risiko" },
  { tier: "Tier 4 – Høy", color: "bg-red-100 text-red-800", examples: "AF, BY, CU, IR, KP, RU, SY", rule: "Aktive sanksjoner / eksportkontroll" },
];

function TechnicalTab() {
  return (
    <div className="space-y-8">
      <div>
        <SectionTitle>Teknisk stack</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TECH_STACK.map((cat) => (
            <Card key={cat.category}>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-xlent-muted">
                {cat.category}
              </p>
              <ul className="space-y-2">
                {cat.items.map((item) => (
                  <li key={item.name}>
                    <p className="text-xs font-semibold text-xlent-ink">{item.name}</p>
                    <p className="text-xs text-xlent-muted">{item.desc}</p>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <SectionTitle>Landrisikoklassifisering</SectionTitle>
        <SectionText>
          Alle land er forhåndsklassifisert i fire risikonivåer. Nivåene brukes av regelmotor, kartvisning og fakturadetalj.
        </SectionText>
        <div className="max-w-2xl overflow-hidden rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">Nivå</th>
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">Eksempler</th>
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">Kriterium</th>
              </tr>
            </thead>
            <tbody>
              {TIER_ROWS.map((row, i) => (
                <tr
                  key={row.tier}
                  className={i < TIER_ROWS.length - 1 ? "border-b border-gray-100" : ""}
                >
                  <td className="px-4 py-2">
                    <span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", row.color)}>
                      {row.tier}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-xlent-ink">{row.examples}</td>
                  <td className="px-4 py-2 text-xs text-xlent-muted">{row.rule}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <SectionTitle>Konfidensterskler for sanksjonsskjerming</SectionTitle>
        <div className="max-w-xl overflow-hidden rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">Terskel</th>
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">Verdi</th>
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">Konsekvens</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-100">
                <td className="px-4 py-2 text-xs font-medium text-xlent-ink">Match-terskel</td>
                <td className="px-4 py-2 text-xs text-xlent-ink">≥ 0.70</td>
                <td className="px-4 py-2 text-xs text-xlent-muted">Potensielt treff — score gul, sendes til review</td>
              </tr>
              <tr>
                <td className="px-4 py-2 text-xs font-medium text-xlent-ink">Bekreftet-terskel</td>
                <td className="px-4 py-2 text-xs text-xlent-ink">≥ 0.79</td>
                <td className="px-4 py-2 text-xs text-xlent-muted">Bekreftet treff — score rød, blokkering anbefalt</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-xlent-muted">
          Tersklene kan justeres via miljøvariablene{" "}
          <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[11px]">
            SCREENING_MATCH_THRESHOLD
          </code>{" "}
          og{" "}
          <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[11px]">
            SCREENING_CONFIRMED_THRESHOLD
          </code>
          .
        </p>
      </div>
    </div>
  );
}

// ── HOVED-KOMPONENT ───────────────────────────────────────────────────────────

export function AboutPage() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  return (
    <div className="mx-auto max-w-6xl p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-xlent-ink">Om XLENT Compliance</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          AI-drevet eksport- og handelscompliance for norske bedrifter
        </p>
      </div>

      {/* Tab-meny */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                "border-b-2 pb-3 text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "border-xlent-primary text-xlent-primary"
                  : "border-transparent text-xlent-muted hover:text-xlent-ink",
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab-innhold */}
      {activeTab === "overview"  && <OverviewTab />}
      {activeTab === "workflow"  && <WorkflowTab />}
      {activeTab === "pages"     && <PagesTab />}
      {activeTab === "roles"     && <RolesTab />}
      {activeTab === "technical" && <TechnicalTab />}
    </div>
  );
}
