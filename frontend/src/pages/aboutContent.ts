/**
 * aboutContent.ts
 *
 * All text content for the About page in Norwegian (nb) and English (en).
 * The About component imports ABOUT_CONTENT and selects the active language at runtime.
 * Keep code/identifiers in English; all user-visible strings here are translated.
 */

// ── Interfaces ────────────────────────────────────────────────────────────────

export type TabId = "overview" | "workflow" | "pages" | "roles" | "technical" | "compliance";

export interface TabDef { id: TabId; label: string }

export interface FeatureItem { icon: string; title: string; desc: string }

export interface WorkflowStep {
  step: number;
  icon: string;
  /** Tailwind colour classes — language-neutral */
  color: string;
  title: string;
  desc: string;
  detail: string | string[];
}

export interface PageDoc {
  icon: string;
  name: string;
  path: string;
  access: string;
  desc: string;
}

export interface RoleDef {
  name: string;
  /** Tailwind colour classes — language-neutral */
  colorClass: string;
  desc: string;
  perms: string[];
}

export interface TechItem { name: string; desc: string }
export interface TechCategory { category: string; items: TechItem[] }

export interface TierRow {
  tier: string;
  /** Tailwind colour classes — language-neutral */
  colorClass: string;
  examples: string;
  rule: string;
}

export interface ThresholdRow { label: string; value: string; consequence: string }

export interface CompliancePoint { label: string; desc: string }
export interface ComplianceSection {
  icon: string;
  title: string;
  subtitle: string;
  points: CompliancePoint[];
}

export interface AboutContent {
  subtitle: string;
  tabs: TabDef[];

  // Overview
  overviewTitle: string;
  overviewParas: string[];
  featuresTitle: string;
  features: FeatureItem[];

  // Workflow
  workflowTitle: string;
  workflowIntro: string;
  workflowSteps: WorkflowStep[];

  // Pages
  pagesTitle: string;
  pagesIntro: string;
  pageDocs: PageDoc[];

  // Roles
  rolesTitle: string;
  rolesIntro: string;
  roles: RoleDef[];

  // Technical
  techTitle: string;
  techStack: TechCategory[];
  tierTitle: string;
  tierIntro: string;
  tiers: TierRow[];
  /** Column headers for the tier table: [tier, examples, criterion] */
  tierTableHeaders: [string, string, string];
  thresholdTitle: string;
  thresholds: ThresholdRow[];
  /** Column headers for the threshold table: [label, value, consequence] */
  thresholdTableHeaders: [string, string, string];
  thresholdNote: string;

  // Regulatory compliance
  complianceTitle: string;
  complianceIntro: string;
  complianceSections: ComplianceSection[];
}

// ── Shared colour constants (language-neutral) ────────────────────────────────

const STEP_COLORS = [
  "bg-blue-100 text-blue-700 border-blue-200",
  "bg-purple-100 text-purple-700 border-purple-200",
  "bg-indigo-100 text-indigo-700 border-indigo-200",
  "bg-amber-100 text-amber-700 border-amber-200",
  "bg-orange-100 text-orange-700 border-orange-200",
  "bg-green-100 text-green-700 border-green-200",
  "bg-red-100 text-red-700 border-red-200",
  "bg-teal-100 text-teal-700 border-teal-200",
];

const ROLE_COLORS: { admin: string; c_level: string; compliance_officer: string; controller: string; readonly: string } = {
  admin:              "bg-red-100 text-red-800",
  c_level:            "bg-indigo-100 text-indigo-800",
  compliance_officer: "bg-purple-100 text-purple-800",
  controller:         "bg-blue-100 text-blue-800",
  readonly:           "bg-gray-100 text-gray-700",
};

const TIER_COLORS = [
  "bg-green-100 text-green-800",
  "bg-amber-100 text-amber-800",
  "bg-orange-100 text-orange-800",
  "bg-red-100 text-red-800",
];

// ── Norwegian (nb) ────────────────────────────────────────────────────────────

const NB: AboutContent = {
  subtitle: "AI-drevet eksport- og handelscompliance for norske bedrifter",

  tabs: [
    { id: "overview",    label: "Oversikt" },
    { id: "workflow",    label: "Arbeidsflyt" },
    { id: "pages",       label: "Sider" },
    { id: "roles",       label: "Roller" },
    { id: "technical",   label: "Teknisk" },
    { id: "compliance",  label: "Regelverk" },
  ],

  // ── Overview ──────────────────────────────────────────────────────────────

  overviewTitle: "Hva er XLENT Compliance?",
  overviewParas: [
    "XLENT Compliance er et AI-drevet system for eksportkontroll og handelscompliance, utviklet " +
    "for norske bedrifter som eksporterer varer og tjenester. Systemet automatiserer arbeidet med " +
    "å sjekke fakturaer mot internasjonale sanksjonslister, interne regler og rammeavtale-vilkår, " +
    "og gir compliance-teamet et strukturert grunnlag for beslutninger.",

    "Kjernen er en pipeline der PDF-fakturaer lastes opp, all relevant informasjon ekstraheres " +
    "automatisk av en stor språkmodell, alle involverte parter sjekkes mot OpenSanctions-databasen " +
    "med over 100 sanksjonslister, og egendefinerte regler evalueres. Resultatet er en " +
    "trafikklys-score (gronn / gul / rod) som viser om fakturaen kan behandles direkte eller " +
    "trenger manuell vurdering.",

    "Systemet er utformet med menneskelig tilsyn som kjerneprinsipp: AI-en tilbyr " +
    "beslutningsstotte, men en autorisert compliance-offiser fatter alltid den endelige " +
    "beslutningen. Alle handlinger logges i et uforanderlig revisjonsspor som dokumenterer " +
    "complianceprosessen overfor myndigheter og revisorer.",

    "Datakildene for sanksjonsskjerming er OpenSanctions - en apen og kontinuerlig oppdatert " +
    "database som samler sanksjonsregister fra EU, USA (OFAC), FN, Storbritannia (OFSI) og " +
    "over 100 andre myndigheter og datakildene. Basen oppdateres automatisk daglig.",
  ],

  featuresTitle: "Nookelfunksjoner",
  features: [
    {
      icon: "📄",
      title: "Automatisk faktura-innlesing",
      desc: "PDF-fakturaer lastes opp og leses inn automatisk med OCR og dokumentparsing. " +
            "Relevante felter ekstraheres uten manuell registrering.",
    },
    {
      icon: "🤖",
      title: "AI-drevet ekstraksjon",
      desc: "Stor spraksmodell (Claude / GPT-4o) trekker ut alle nokkelfelter: selger, kjoper, " +
            "speditoor, destinasjonsland, HS-koder, linjebeloep og varebeskrivelse - med " +
            "konfidensscore (0-100%) for hvert felt.",
    },
    {
      icon: "🔎",
      title: "Sanksjonsskjerming",
      desc: "Alle parter sjekkes mot OpenSanctions via Yente med fuzzy matching. Finner treff " +
            "selv ved stavefeil eller navnevarianter. Dekker EU, OFAC, FN, UK og 100+ datakilder.",
    },
    {
      icon: "⚙️",
      title: "YAML-regelmotor",
      desc: "Egendefinerte compliance-regler evalueres automatisk etter ekstraksjon. Reglene " +
            "sjekker destinasjonsland, HS-koder, entitetsnavn, e-postdomener og beloepsgrenser. " +
            "Setter score gronn/gul/rod og kan kombineres med AND/OR-logikk.",
    },
    {
      icon: "✅",
      title: "Manuell review-koo",
      desc: "Gule og rode fakturaer prioriteres i en review-koo. Compliance-offiserer " +
            "godkjenner eller avviser med skriftlig begrunnelse. Koen er sortert rod-forst, " +
            "ubehandlede forst.",
    },
    {
      icon: "🌍",
      title: "Landrisikoklassifisering",
      desc: "Alle land er klassifisert i fire risikonivaaer (Lav/Normal/Forhooyet/Hooy) basert " +
            "paa NATO-medlemskap og internasjonale sanksjonsregimer. Brukes i regelmotor og kartvisning.",
    },
    {
      icon: "🕸️",
      title: "Utvidet screening",
      desc: "Graf-basert dypanalyse av enkeltentiteter via Wikidata avdekker eierstrukturer, " +
            "styremedlemmer og relasjoner til sanksjonerte parter. Brukeren kan gi tilbakemelding " +
            "paa hvert knutepunkt.",
    },
    {
      icon: "📜",
      title: "Rammeavtale-sjekk",
      desc: "PDF-rammeavtaler lastes opp og AI-en ekstraherer nokkelvil kaar: tillatte " +
            "destinasjonsland, produktbegrensninger og verdimaksima. Fakturaene sjekkes " +
            "automatisk mot disse vilkaarene.",
    },
    {
      icon: "📋",
      title: "Fullstendig revisjonsspor",
      desc: "Alle handlinger - ekstraksjon, skjerming, regelkjoring, review og beslutning - " +
            "logges med tidsstempel og brukeridentitet. Revisjonssporet er uforanderlig og " +
            "kan fremlegges for myndigheter og revisorer.",
    },
    {
      icon: "🚫",
      title: "Intern sperreliste",
      desc: "Virksomhetens egne sperrede navn, e-postdomener og HS-koder sjekkes i tillegg " +
            "til OpenSanctions. Hvert oppfoering har alvorlighetsgrad, begrunnelse og " +
            "kildehenvisning.",
    },
    {
      icon: "🔔",
      title: "Sanntidsvarsler",
      desc: "Compliance-offiserer mottar varsler om nye fakturaer i review-koen og " +
            "systemhendelser. Varslingsikoner vises i topplinjen.",
    },
    {
      icon: "👥",
      title: "Kunderegister",
      desc: "Motparter og kunder registreres med compliance-historikk. Gir oversikt over " +
            "hvilke fakturaer som er knyttet til hver part og om det finnes aapne funn.",
    },
    {
      icon: "🛡",
      title: "Eksportkontroll - DEKSAs varelister",
      desc: "Fakturalinjer sjekkes automatisk mot Vareliste I (militaere varer, ML1-ML22) " +
            "og Vareliste II (dual-use, kategoriene 0-9) fra DEKSA. Tre-lags matcher: " +
            "strukturmatch paa ECCN/ML-kode, HS-kodeforbro og nookkeldordleksikon. " +
            "Destinasjonsland avgjoor alvorlighetsgraden (rod / gul).",
    },
    {
      icon: "🎯",
      title: "Sluttbruker / catch-all-screening",
      desc: "Dedikert modul som flagger risikosignaler i sluttbruker, destinasjon og " +
            "tiltenkt bruk etter DEKSAs catch-all-prinsipp (eksportkontrolloven SS 5): " +
            "militaer/nukleoer sluttbruker, diversjonsrisiko, ikke-deklarert mottaker. " +
            "Seks signaltyper med eget alvorlighetsnivaao.",
    },
    {
      icon: "🗂",
      title: "Samlet arbeidsliste med flagg",
      desc: "Review-koen viser fargede merkelapper per faktura for alle sju flaggkilder: " +
            "sanksjon, embargo, vareliste, sluttbruker, dual-use, eierskap og MVA. " +
            "Egne hurtigfiltre per kilde gir ett sted for all compliance-oppfolging.",
    },

  ],

  // ── Workflow ──────────────────────────────────────────────────────────────

  workflowTitle: "Pipeline-oversikt",
  workflowIntro:
    "Hvert trinn kjores automatisk i bakgrunnen via en Celery-oppgavekoo. " +
    "Klikk paa et steg for aa se tekniske detaljer og regelverksrelevans.",

  workflowSteps: [
    {
      step: 1, icon: "📤", color: STEP_COLORS[0]!,
      title: "Opplasting",
      desc: "En PDF-faktura lastes opp via brukergrensesnittet. Filen lagres og et oppdrag " +
            "opprettes i systemet med status 'uploaded'.",
      detail: [
        "Stotter standard PDF-filer og skannede dokumenter (OCR-fallback).",
        "Filen oppbevares sikkert og tilknyttes en unik faktura-ID.",
        "Compliancelogg: opplastningstidspunkt og bruker registreres umiddelbart.",
      ],
    },
    {
      step: 2, icon: "🔍", color: STEP_COLORS[1]!,
      title: "Parsing",
      desc: "Systemet leser PDF-en og trekker ut raaatekst. OCR brukes ved behov for " +
            "skannede dokumenter. Status settes til 'parsing'.",
      detail: [
        "Bruker PyMuPDF for digital PDF og OCR-fallback for skannede dokumenter.",
        "Teksten normaliseres og forberedes for AI-ekstraksjon.",
      ],
    },
    {
      step: 3, icon: "🤖", color: STEP_COLORS[2]!,
      title: "AI-ekstraksjon",
      desc: "En stor spraksmodell analyserer fakturateksten og ekstraherer strukturerte data: " +
            "selger, kjoper, speditoor, destinasjonsland, HS-koder, linjebeloep og mer. " +
            "Status settes til 'extracted'.",
      detail: [
        "Primaermodell: Claude (Anthropic). Fallback: GPT-4o (OpenAI). Bytbar i UI-et.",
        "Hvert felt faar en konfidensscore 0-1. Lav konfidens (<0,8) markeres visuelt.",
        "AI Act Art. 13: Konfidensscore og feltdetaljer gir full transparens om AI-vurderingen.",
        "Alle ekstraherte felter er redigerbare av autorisert bruker og logges i revisjonsspor.",
      ],
    },
    {
      step: 4, icon: "🔎", color: STEP_COLORS[3]!,
      title: "Sanksjonsskjerming",
      desc: "Alle ekstraherte entiteter (selger, kjoper, speditoor m.fl.) sjekkes mot " +
            "OpenSanctions via Yente. Fuzzy matching finner treff selv ved navnevarianter. " +
            "Status settes til 'screening'.",
      detail: [
        "Matchterskel: 0,70 - Potensielt treff (score gul, til review).",
        "Bekreftet-terskel: 0,79 - Bekreftet treff (score rod, blokkering anbefalt).",
        "Dekker: EU-sanksjoner, OFAC SDN/CAPTA, FN, UK OFSI, og 100+ andre lister via OpenSanctions.",
        "Oppdateres daglig kl. 07:40 via Celery Beat.",
        "Relevant for: Eksportkontrolloven, EU Dual-Use 2021/821, Hvitvaskingsloven (KYC/CDD).",
      ],
    },
    {
      step: 5, icon: "⚙️", color: STEP_COLORS[4]!,
      title: "Regelkjoring",
      desc: "Alle aktive YAML-regler evalueres mot fakturadataene. Reglene kan sette flagg og " +
            "pavirke score.",
      detail: [
        "Regeltyper: destinasjonsland, HS-kode, entitetsnavn, e-postdomene, beloepsgrenser.",
        "Operatorer: in, not_in, equals, regex, gt, lt.",
        "Operator-kombinasjon: AND/OR paa tvers av betingelser.",
        "Reglene dokumenteres og logges - stotter revisjon etter AI Act Art. 9 og 12.",
      ],
    },
    {
      step: 6, icon: "🚦", color: STEP_COLORS[5]!,
      title: "Scoring",
      desc: "Systemet beregner en samlet compliance-score basert paa sanksjons-treff og " +
            "regelutslag. Status settes til 'screened'.",
      detail: [
        "Gronn - ingen treff, alle regler bestatt.",
        "Gul - potensielle treff eller advarselsregler utlost.",
        "Rod - bekreftet sanksjonstreff eller blokkerende regler.",
        "Scoren er forklart: brukeren ser hvilke enkeltfunn som bidrar.",
      ],
    },
    {
      step: 7, icon: "👤", color: STEP_COLORS[6]!,
      title: "Manuell review",
      desc: "Gule og rode fakturaer havner i review-koen. Compliance-offiseren ser alle " +
            "detaljer, sanksjons-treff, regelutslag og revisjonsspor foer beslutning. Fakturaen " +
            "kan 'claimes' for aa unngaa dobbeltbehandling.",
      detail: [
        "Prioritering: rode fakturaer vises forst, deretter gule.",
        "AI Act Art. 14: Menneskelig tilsyn er paalagt - ingen automatisk godkjenning.",
        "Revisjonsspor: hvem som har sett og behandlet fakturaen logges lopende.",
      ],
    },
    {
      step: 8, icon: "✅", color: STEP_COLORS[7]!,
      title: "Beslutning",
      desc: "Compliance-offiseren godkjenner eller avviser fakturaen med en skriftlig " +
            "begrunnelse. Beslutningen, brukeren og tidsstempelet lagres i revisjonssporet.",
      detail: [
        "Godkjent - status 'approved', faktura kan behandles videre.",
        "Avvist - status 'blocked', faktura sperres.",
        "Begrunnelsen er soekbar og kan fremlegges ved tilsyn.",
        "Stotter dokumentasjonskrav i Eksportkontrolloven og Hvitvaskingsloven.",
      ],
    },
  ],

  // ── Pages ─────────────────────────────────────────────────────────────────

  pagesTitle: "Sider og funksjoner",
  pagesIntro: "Systemet er delt i spesialiserte sider. Tilgangen styres av brukerens rolle.",

  pageDocs: [
    {
      icon: "📋", name: "Fakturaer", path: "/invoices",
      access: "Alle roller",
      desc: "Hoved-oversikten over alle fakturaer. Filtrer paa status, compliance-score, " +
            "retning (import/eksport), land og fritekst. Sanksjonsstatus vises i listen. " +
            "Last opp nye fakturaer direkte herfra.",
    },
    {
      icon: "🗂️", name: "Fakturadetalj", path: "/invoices/:id",
      access: "Alle roller",
      desc: "Detaljvisning av en faktura: PDF-forhåndsvisning, alle ekstraherte felter " +
            "med konfidensscore (redigerbare), entitetsliste med sanksjons-treff, " +
            "regelutslag, rammeavtale-sjekk og fullstendig revisjonsspor. Start skjerming, " +
            "utvidet screening eller review herfra.",
    },
    {
      icon: "📊", name: "Dashboard", path: "/dashboard",
      access: "Alle roller med dashboard:view",
      desc: "KPI-oversikt: totalt antall fakturaer, score-fordeling (gronn/gul/rod), " +
            "gjennomsnittlig prosesseringstid, antall i review-koo og ukentlig trendbilde. " +
            "Gir compliance-sjef raskt situasjonsbilde.",
    },
    {
      icon: "👥", name: "Kunder", path: "/customers",
      access: "Compliance officer, Controller, Admin",
      desc: "Liste over registrerte motparter og kunder med compliance-historikk. " +
            "Viser hvilke fakturaer som er knyttet til hver part og om det finnes aapne funn. " +
            "Stotter KYC-arbeid under Hvitvaskingsloven.",
    },
    {
      icon: "⏳", name: "Review-koo", path: "/review-queue",
      access: "Compliance officer, Admin",
      desc: "Samlet arbeidsliste for alle fakturaer som venter paa manuell beslutning. " +
            "Fargede flagg-merkelapper per faktura viser kildene (sanksjon, embargo, " +
            "vareliste, sluttbruker, dual-use, eierskap, MVA). Hurtigfiltre per kilde. " +
            "Sortert rod-forst, ubehandlede forst.",
    },
    {
      icon: "⚙️", name: "Regler", path: "/rules",
      access: "Compliance officer, Admin",
      desc: "Administrasjon av YAML-regelmotor. Skriv betingelser med alvorlighetsgrad " +
            "(gronn/gul/rod). Test regler mot eksempeldata uten aa lagre. Kjoor alle " +
            "aktive regler paa nytt mot eksisterende fakturaer.",
    },
    {
      icon: "🚫", name: "Intern sperreliste", path: "/watchlist",
      access: "Compliance officer, Admin",
      desc: "Administrasjon av virksomhetens interne sperreliste. Legg til navn, " +
            "e-postdomener og HS-koder med alvorlighetsgrad og begrunnelse. Treff vises " +
            "som screeningresultater i tillegg til OpenSanctions-funn.",
    },
    {
      icon: "📜", name: "Rammeavtaler", path: "/agreements",
      access: "Alle roller med agreements:view",
      desc: "Last opp og administrer PDF-rammeavtaler. AI-en ekstraherer nookkelvilkaar " +
            "automatisk: tillatte destinasjonsland, produktbegrensninger og verdimaksima. " +
            "Se hvilke fakturaer som er sjekket mot avtalen og resultatet.",
    },
    {
      icon: "🌍", name: "Kart", path: "/maps",
      access: "Alle roller",
      desc: "Interaktivt verdenskart med fargekodet landrisikoklassifisering (Tier 1-4). " +
            "Filtrer paa risikonivaa. Forsendelseskartlag viser handelsruter fra fakturaenes " +
            "opprinnelses- og destinasjonsland.",
    },
    {
      icon: "🔎", name: "Sanksjonerte entiteter", path: "/sanctioned-entities",
      access: "Compliance officer, Admin",
      desc: "Direkte soek i OpenSanctions-databasen. Soek paa navn, land eller type. " +
            "Viser alle sanksjonsregister der entiteten er opport, med datokilde. " +
            "Inneholder knapp for manuell oppdatering av sanksjonsdatabasen.",
    },
    {
      icon: "🔍", name: "Fakturasook", path: "/invoices/search",
      access: "Alle roller",
      desc: "Avansert fulltekstsook paa tvers av alle fakturaer og entiteter. Stotter soek " +
            "paa fakturanummer, serienummer, entitetsnavn, destinasjonsland og HS-kode.",
    },
    {
      icon: "🛠️", name: "Pipeline-drift", path: "/pipeline-ops",
      access: "Kun Admin",
      desc: "Driftsovervakning av bakgrunnspipelinen: gjennomstroomning, ventetid og " +
            "fakturaer som sitter fast. Admins kan trigge manuell re-prosessering.",
    },
    {
      icon: "🕸️", name: "Utvidet screening", path: "/invoices/:id/entities/:eId/extended-screen/:rId",
      access: "Compliance officer, Admin",
      desc: "Graf-basert relasjonsanalyse av en enkeltentitet via Wikidata. Avdekker " +
            "eierstrukturer og styremedlemmer med tilknytning til sanksjonerte parter. " +
            "Hvert knutepunkt kan gi tilbakemelding (relevant / ikke relevant).",
    },
    {
      icon: "🛡", name: "Eksportkontroll", path: "/review-queue?filter=export_control",
      access: "Compliance officer, Admin",
      desc: "Filter i review-køen for fakturaer flagget mot DEKSAs Vareliste I " +
            "(militaere varer, ML1-ML22) eller Vareliste II (dual-use, kategoriene 0-9). " +
            "Viser treff per linje med liste, kategori og konfidensnivaa (hoy/medium/lav).",
    },
    {
      icon: "📚", name: "Vareliste-referanse", path: "/export-control/reference",
      access: "Compliance officer, Admin",
      desc: "Bla i DEKSAs varelister: soek paa kode eller nookkeldord, se kategori-" +
            "oversikt og importstatus. Admin kan kjore backfill for aa re-evaluere " +
            "historiske fakturaer mot gjeldende listeversjons.",
    },
    {
      icon: "🎯", name: "Sluttbruker / catch-all", path: "/review-queue?filter=catch_all",
      access: "Compliance officer, Admin",
      desc: "Filter i review-køen for fakturaer med risikosignaler i sluttbruker, " +
            "destinasjon eller tiltenkt bruk etter DEKSAs catch-all-prinsipp. Viser " +
            "utloste signaler som militaer sluttbruker, diversjonsrisiko, nukleaer bruk m.fl.",
    },
  ],

  // ── Roles ─────────────────────────────────────────────────────────────────

  rolesTitle: "Roller og tilganger",
  rolesIntro:
    "Tilgangsstyring er rollebasert (RBAC). Hver bruker har en rolle som bestemmer " +
    "tilgjengelige sider og handlinger. I produksjon settes rollen via JWT-claims. " +
    "Under utvikling kan rollen byttes via rollevelgeren oeverst til hooyre.",

  roles: [
    {
      name: "Admin",
      colorClass: ROLE_COLORS.admin,
      desc: "Full tilgang til alle sider og funksjoner, inkludert drift og pipeline-administrasjon.",
      perms: [
        "Laste opp, redigere og slette fakturaer",
        "Kjore ekstraksjon og skjerming",
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
      colorClass: ROLE_COLORS.c_level,
      desc: "Samme tilgang som Admin. Beregnet paa ledere som trenger full oversikt.",
      perms: ["Alle sider og funksjoner (identisk med Admin)"],
    },
    {
      name: "Compliance officer",
      colorClass: ROLE_COLORS.compliance_officer,
      desc: "Hoved-brukerprofilen for daglig compliance-arbeid. Kan vurdere, beslutte og administrere regler.",
      perms: [
        "Laste opp og redigere fakturaer",
        "Kjore ekstraksjon og skjerming",
        "Godkjenne / avvise fakturaer (review-koo)",
        "Administrere regler og sperreliste",
        "Laste opp og administrere rammeavtaler",
        "Se kunder",
        "Soeke i sanksjonsdatabasen",
        "Dashboard, kart og fakturasook",
      ],
    },
    {
      name: "Controller",
      colorClass: ROLE_COLORS.controller,
      desc: "Regnskapsroller som arbeider med fakturaer, men ikke tar compliance-beslutninger.",
      perms: [
        "Laste opp og redigere fakturaer",
        "Kjore ekstraksjon",
        "Se og redigere kunder",
        "Se rammeavtaler",
        "Dashboard og fakturasook",
        "Kart (lesetilgang)",
      ],
    },
    {
      name: "Lesetilgang",
      colorClass: ROLE_COLORS.readonly,
      desc: "Lesetilgang til de viktigste sidene. Kan ikke utfoere handlinger.",
      perms: [
        "Se fakturaer",
        "Se dashboard",
        "Se regler (ikke redigere)",
        "Se rammeavtaler",
        "Se kunder",
      ],
    },
  ],

  // ── Technical ─────────────────────────────────────────────────────────────

  techTitle: "Teknisk stack",

  techStack: [
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
        { name: "SQLAlchemy (async)", desc: "ORM mot PostgreSQL med async-stootte" },
        { name: "Celery", desc: "Distribuert oppgavekoo for bakgrunnsprosessering" },
        { name: "Alembic", desc: "Databasemigrasjoner" },
        { name: "Pydantic v2", desc: "Validering og serialisering av data" },
      ],
    },
    {
      category: "AI / LLM",
      items: [
        { name: "Anthropic Claude", desc: "Primaer LLM for ekstraksjon og analyse" },
        { name: "OpenAI GPT-4o", desc: "Fallback-modell ved nedetid eller feil" },
        { name: "Modellvelger", desc: "Kan byttes live i UI-et via tannhjulet ooverst" },
      ],
    },
    {
      category: "Sanksjonsdatabase",
      items: [
        { name: "Yente (OpenSanctions)", desc: "Sanksjonsskjermings-API med fuzzy matching" },
        { name: "Elasticsearch 8", desc: "Sookeindeks bak Yente for rask oppslag" },
        { name: "OpenSanctions-data", desc: "Daglig oppdatert fra EU, OFAC, FN, UK m.fl. (100+ lister)" },
      ],
    },
    {
      category: "Infrastruktur",
      items: [
        { name: "Docker Compose", desc: "Orkestrering av alle tjenester lokalt og i dev" },
        { name: "PostgreSQL 16", desc: "Hoved-database for alle faktura- og brukerdata" },
        { name: "Redis 7", desc: "Broker og result-backend for Celery" },
        { name: "Celery Beat", desc: "Planlagt daglig oppdatering av sanksjonslister kl. 07:40" },
      ],
    },
  ],

  tierTitle: "Landrisikoklassifisering",
  tierIntro:
    "Alle land er forhaandsklassifisert i fire risikonivaaer. Nivaaene brukes av " +
    "regelmotor, kartvisning og fakturadetalj.",

  tiers: [
    { tier: "Tier 1 - Lav",      colorClass: TIER_COLORS[0]!, examples: "NATO-land (NO, DE, US, FR, GB, ...)", rule: "NATO-medlemskap" },
    { tier: "Tier 2 - Normal",   colorClass: TIER_COLORS[1]!, examples: "Flertallet av ovrige land",           rule: "Standardnivaa" },
    { tier: "Tier 3 - Forhooyet", colorClass: TIER_COLORS[2]!, examples: "CN, QA, SA, TR, UA, AZ, ...",       rule: "Geopolitisk risiko" },
    { tier: "Tier 4 - Hooy",     colorClass: TIER_COLORS[3]!, examples: "AF, BY, CU, IR, KP, RU, SY",         rule: "Aktive sanksjoner" },
  ],

  tierTableHeaders: ["Nivå", "Eksempler", "Kriterium"],

  thresholdTitle: "Konfidensterskler for sanksjonsskjerming",
  thresholds: [
    { label: "Match-terskel",     value: ">= 0,70", consequence: "Potensielt treff - score gul, sendes til review" },
    { label: "Bekreftet-terskel", value: ">= 0,79", consequence: "Bekreftet treff - score rod, blokkering anbefalt" },
  ],
  thresholdTableHeaders: ["Terskel", "Verdi", "Konsekvens"],
  thresholdNote:
    "Tersklene kan justeres via miljoovariablene SCREENING_MATCH_THRESHOLD og " +
    "SCREENING_CONFIRMED_THRESHOLD.",

  // ── Regulatory compliance ─────────────────────────────────────────────────

  complianceTitle: "Regelverk og overholdelse",
  complianceIntro:
    "XLENT Compliance er designet for aa stootte virksomheters etterlevelse av sentrale " +
    "norske og europeiske regelverk innen eksportkontroll, sanksjoner, personvern og " +
    "kunstig intelligens. Nedenfor beskrives hvordan systemet bidrar til etterlevelse av " +
    "hvert relevant regelverk.",

  complianceSections: [
    {
      icon: "📦",
      title: "Eksportkontroll",
      subtitle: "Eksportkontrolloven (2013) - EU Dual-Use forordning 2021/821",
      points: [
        {
          label: "Eksportkontrolloven",
          desc: "Norsk lov regulerer eksport av strategiske varer, programvare og teknologi med " +
                "mulig militaer sluttbruk. Eksportorer er forpliktet til aa identifisere om " +
                "varen krever lisens og om kjoper er sanksjonert. Systemet automatiserer " +
                "screeningdelen av denne plikten.",
        },
        {
          label: "EU Dual-Use 2021/821",
          desc: "EU-forordningen kontrollerer varer med baade sivile og militaere " +
                "bruksomraader. Annex I inneholder EU-kontrollisten. Systemet stotter kontroll " +
                "av HS-koder mot kjente risikokategorier og destinasjoner i regelmotor.",
        },
        {
          label: "Catch-all-klausul (SS 5)",
          desc: "Eksportkontrolloven SS 5 og EU Art. 4 gir myndighetene rett til aa nekte " +
                "eksport selv for ikke-listeoppsatte varer ved mistanke om militaer, nukleoer " +
                "eller MDE-relatert sluttbruk. Systemet har en dedikert catch-all-modul som " +
                "automatisk vurderer sluttbruker, destinasjon og bruk mot seks risikosignaler: " +
                "militaer/nukleoer sluttbruk, diversjonsrisiko, sensitiv bruk, meglerledd " +
                "og ikke-deklarert mottaker. Fakturaer med treff sendes til review.",
        },
        {
          label: "Revisjon og dokumentasjon",
          desc: "Alle compliancevurderinger med begrunnelse lagres i revisjonssporet. " +
                "Dette gjoer det mulig aa dokumentere due diligence overfor Utenriksdepartementet " +
                "og andre myndigheter ved en eventuell kontroll.",
        },
      ],
    },
    {
      icon: "🛡️",
      title: "Sanksjonsoverholdelse",
      subtitle: "EU-sanksjoner - OFAC - FN - UK OFSI - OpenSanctions",
      points: [
        {
          label: "EU-sanksjoner",
          desc: "EU vedtar sanksjonsregimer gjennom Raadsforordninger som er direkte bindende " +
                "i alle EU/EOES-stater. Inkluderer landregimer (Russland, Iran, Syria, " +
                "Nord-Korea, Hviterussland) og tematiske regimer (terror, WMD, cybersikkerhet, " +
                "menneskerettigheter).",
        },
        {
          label: "OFAC (US Treasury)",
          desc: "Office of Foreign Assets Control administrerer amerikanske sanksjoner. " +
                "SDN-listen (Specially Designated Nationals) forbyr handel med listede " +
                "individer og selskaper. Relevant for norske selskaper med USD-betalinger " +
                "eller annen USA-tilknytning.",
        },
        {
          label: "FN-sanksjoner",
          desc: "FNs sikkerhetsraad vedtar sanksjoner under Kapittel VII. Alle " +
                "FN-medlemmer er forpliktet til aa implementere disse, inkludert " +
                "reise- og handelsforbud mot spesifikke land og individer.",
        },
        {
          label: "UK OFSI",
          desc: "Office of Financial Sanctions Implementation administrerer britiske " +
                "sanksjoner etter Brexit. Inkluderer egne UK-lister i tillegg til de " +
                "som er basert paa FN og EU.",
        },
        {
          label: "OpenSanctions-integrasjon",
          desc: "Systemet bruker OpenSanctions-databasen som aggregerer 100+ sanksjonslister " +
                "fra myndigheter verden over. Basen oppdateres daglig og dekker PEP-lister " +
                "(politisk eksponerte personer) i tillegg til sanksjonslistene. " +
                "Fuzzy matching sikrer at treff oppdages selv ved navnevarianter.",
        },
      ],
    },
    {
      icon: "🤖",
      title: "EU AI-forordningen",
      subtitle: "Forordning 2024/1689 (EU AI Act) - i kraft august 2024",
      points: [
        {
          label: "Systemklassifisering",
          desc: "XLENT Compliance er et beslutningsst otteverkt oy der mennesket alltid " +
                "fatter den endelige beslutningen. AI-en tilbyr vurderinger og rangering - " +
                "ikke autonome beslutninger. Dette er i traad med kravet om human-in-the-loop " +
                "for systemer som paavirker forretningsmessige beslutninger.",
        },
        {
          label: "Transparens (Art. 13)",
          desc: "Alle AI-vurderinger vises med konfidensscore og detaljert begrunnelse. " +
                "Brukeren ser noyaktig hvilke felter som ble ekstrahert og med hvilken " +
                "sikkerhetsgrad. Modellinformasjon (primaaer/fallback) vises i topp-linja.",
        },
        {
          label: "Menneskelig tilsyn (Art. 14)",
          desc: "Review-koen sikrer at alle gule og rode fakturaer vurderes av en autorisert " +
                "compliance-offiser foer beslutning. Ingen faktura kan godkjennes uten " +
                "menneskelig vurdering. Offiseren kan overstyre systemets vurdering med " +
                "begrunnelse.",
        },
        {
          label: "Sporbarhet og revisjon (Art. 12)",
          desc: "Alle handlinger logges i et uforanderlig revisjonsspor med tidsstempel, " +
                "brukeridentitet og begrunnelse. Regelendringer og modellbytter logges " +
                "separat. Dette muliggjoor dokumentasjon overfor tilsynsmyndigheter.",
        },
        {
          label: "Risikostyring (Art. 9)",
          desc: "Konfidensterskler og regler er konfigurerbare av compliance-teamet og " +
                "dokumenteres i systemet. Alle regelendringer spores. Systemet har " +
                "watchdog-prosesser som fanger opp fakturaer som sitter fast i pipeline.",
        },
      ],
    },
    {
      icon: "🔒",
      title: "Personvern og GDPR",
      subtitle: "Forordning 2016/679 (GDPR) - Personopplysningsloven",
      points: [
        {
          label: "Behandlingsgrunnlag",
          desc: "Systemet behandler personopplysninger om motparter (navn, selskaper, " +
                "adresser) paa grunnlag av rettslig forpliktelse (Art. 6(1)(c)) - " +
                "eksportkontroll og hvitvaskingskrav - og berettiget interesse (Art. 6(1)(f)).",
        },
        {
          label: "Dataminimering",
          desc: "Kun de feltene som er nodvendige for compliancevurderingen ekstraheres " +
                "og lagres. Systemet er designet for aa behandle saa lite persondata " +
                "som mulig mens det oppfyller de regulatoriske pliktene.",
        },
        {
          label: "Rett til forklaring",
          desc: "Konfidensscore og matchdetaljer gir grunnlag for en forklaring paa " +
                "hvorfor en faktura fikk bestemt score. Dette stotter den registrertes " +
                "rett til forklaring ved automatisert behandling (Art. 22).",
        },
        {
          label: "Tilgangskontroll",
          desc: "Rollebasert tilgangsstyring (RBAC) sikrer at kun autoriserte brukere " +
                "kan se og behandle data. Alle datauttak logges i revisjonssporet.",
        },
        {
          label: "Revisjonsspor og dokumentasjon",
          desc: "Alle behandlingsaktiviteter logges og kan fremlegges for " +
                "Datatilsynet ved tilsyn. Systemet stotter virksomhetens plikt til aa " +
                "forer logg over behandlingsaktiviteter (Art. 30).",
        },
      ],
    },
    {
      icon: "💰",
      title: "Hvitvasking og KYC",
      subtitle: "Hvitvaskingsloven (2018) - EU AMLD5/AMLD6 - FATF anbefalinger",
      points: [
        {
          label: "Kundekontroll (CDD/KYC)",
          desc: "Sanksjonsskjermingen stotter CDD-plikten (Customer Due Diligence): " +
                "identifisering og verifisering av motpartens identitet samt sjekk mot " +
                "sanksjons- og PEP-lister. Kunderegister et gir oversikt over alle " +
                "motparter og compliancehistorikken deres.",
        },
        {
          label: "PEP-screening",
          desc: "OpenSanctions-databasen inkluderer PEP-lister (Politisk eksponerte " +
                "personer) som dekkes av screeningen. Treff rapporteres med matchdetaljer " +
                "og kilderegister.",
        },
        {
          label: "FATF-anbefaling 6",
          desc: "FATF (Financial Action Task Force) anbefaler at alle land implementerer " +
                "maalrettede finansielle sanksjoner (TFS) for bekjempelse av terrorfinansiering " +
                "og spredning av masseodeleggelsesvaaapen. Systemets sanksjonsskjerming " +
                "stotter denne anbefalingen direkte.",
        },
        {
          label: "Mistenkelige transaksjoner",
          desc: "Fakturaer med hoy risikoscore genererer varsler som stotter vurderingen " +
                "av om forholdet skal rapporteres til Okokrim (MT-rapport). Begrunnelsen " +
                "og revisjonssporet kan vedlegges rapporten.",
        },
        {
          label: "Dokumentasjon ved tilsyn",
          desc: "Compliancebeslutninger med begrunnelse kan fremlegges som dokumentasjon " +
                "ved tilsyn fra Finanstilsynet. Systemet gjoer det enkelt aa hente fram " +
                "historikk for spesifikke motparter og transaksjoner.",
        },
      ],
    },
  ],
};

// ── English (en) ──────────────────────────────────────────────────────────────

const EN: AboutContent = {
  subtitle: "AI-driven export and trade compliance for Norwegian businesses",

  tabs: [
    { id: "overview",   label: "Overview" },
    { id: "workflow",   label: "Workflow" },
    { id: "pages",      label: "Pages" },
    { id: "roles",      label: "Roles" },
    { id: "technical",  label: "Technical" },
    { id: "compliance", label: "Regulatory" },
  ],

  // ── Overview ──────────────────────────────────────────────────────────────

  overviewTitle: "What is XLENT Compliance?",
  overviewParas: [
    "XLENT Compliance is an AI-driven system for export control and trade compliance, " +
    "developed for Norwegian companies that export goods and services. The system automates " +
    "the process of checking invoices against international sanctions lists, internal rules, " +
    "and framework agreement terms, giving the compliance team a structured basis for decisions.",

    "At the core is a pipeline where PDF invoices are uploaded, all relevant information is " +
    "automatically extracted by a large language model, all involved parties are checked against " +
    "the OpenSanctions database covering more than 100 sanctions lists, and custom rules are " +
    "evaluated. The result is a traffic-light score (green / yellow / red) indicating whether " +
    "an invoice can be processed directly or requires manual review.",

    "The system is designed with human oversight as a core principle: AI provides decision " +
    "support, but an authorized compliance officer always makes the final determination. " +
    "All actions are recorded in an immutable audit trail that documents the compliance " +
    "process for regulators and auditors.",

    "The data source for sanctions screening is OpenSanctions - an open and continuously " +
    "updated database aggregating sanctions registers from the EU, USA (OFAC), UN, UK (OFSI) " +
    "and over 100 other authorities and data sources. The database is refreshed automatically " +
    "every day.",
  ],

  featuresTitle: "Key features",
  features: [
    {
      icon: "📄",
      title: "Automatic invoice ingestion",
      desc: "PDF invoices are uploaded and read automatically via OCR and document parsing. " +
            "Relevant fields are extracted without manual data entry.",
    },
    {
      icon: "🤖",
      title: "AI-driven extraction",
      desc: "A large language model (Claude / GPT-4o) extracts all key fields: seller, buyer, " +
            "freight forwarder, destination country, HS codes, line amounts and product " +
            "descriptions - with a confidence score (0-100%) for each field.",
    },
    {
      icon: "🔎",
      title: "Sanctions screening",
      desc: "All parties are checked against OpenSanctions via Yente with fuzzy matching. " +
            "Matches are found even with spelling variations or name aliases. " +
            "Covers EU, OFAC, UN, UK and 100+ data sources.",
    },
    {
      icon: "⚙️",
      title: "YAML rules engine",
      desc: "Custom compliance rules are evaluated automatically after extraction. Rules " +
            "check destination countries, HS codes, entity names, email domains and amount " +
            "thresholds. Sets scores green/yellow/red with AND/OR logic combinations.",
    },
    {
      icon: "✅",
      title: "Manual review queue",
      desc: "Yellow and red invoices are prioritised in a review queue. Compliance officers " +
            "approve or reject with a written justification. The queue is sorted red-first, " +
            "unhandled-first.",
    },
    {
      icon: "🌍",
      title: "Country risk classification",
      desc: "All countries are pre-classified into four risk tiers (Low/Normal/Elevated/High) " +
            "based on NATO membership and international sanctions regimes. " +
            "Used in the rules engine and map view.",
    },
    {
      icon: "🕸️",
      title: "Extended screening",
      desc: "Graph-based deep analysis of individual entities via Wikidata reveals ownership " +
            "structures, board members and relationships to sanctioned parties. " +
            "Users can provide feedback on each node.",
    },
    {
      icon: "📜",
      title: "Framework agreement checks",
      desc: "PDF framework agreements are uploaded and the AI extracts key terms: " +
            "permitted destination countries, product restrictions and value caps. " +
            "Invoices are automatically checked against these terms.",
    },
    {
      icon: "📋",
      title: "Full audit trail",
      desc: "All actions - extraction, screening, rule evaluation, review and decision - " +
            "are logged with timestamp and user identity. The audit trail is immutable and " +
            "can be presented to regulators and auditors.",
    },
    {
      icon: "🚫",
      title: "Internal watchlist",
      desc: "The company's own blocked names, email domains and HS codes are screened in " +
            "addition to OpenSanctions. Each entry includes severity, reason and source reference.",
    },
    {
      icon: "🔔",
      title: "Real-time notifications",
      desc: "Compliance officers receive real-time alerts about new invoices in the review " +
            "queue and system events. Notification icons are shown in the top bar.",
    },
    {
      icon: "👥",
      title: "Customer registry",
      desc: "Counterparties and customers are registered with compliance history, giving an " +
            "overview of associated invoices and any open findings.",
    },
    {
      icon: "🛡",
      title: "Export control lists (DEKSA)",
      desc: "Invoice lines are automatically checked against DEKSA Vareliste I (military " +
            "goods, ML1-ML22) and Vareliste II (dual-use, categories 0-9). Three-tier " +
            "matching: structural ECCN/ML code match, HS-code bridge, and keyword lexicon. " +
            "Destination country determines severity (red / yellow).",
    },
    {
      icon: "🎯",
      title: "End-user / catch-all screening",
      desc: "Dedicated module flagging risk signals in end-user, destination and intended " +
            "use under DEKSAs catch-all principle (Export Control Act section 5): " +
            "military/nuclear end-use, diversion risk, undeclared consignee. Six signal " +
            "types with individual severity levels.",
    },
    {
      icon: "🗂",
      title: "Unified worklist with flag badges",
      desc: "The review queue shows coloured flag badges per invoice for all seven signal " +
            "sources: sanctions, embargo, export control, end-user, dual-use, ownership " +
            "and VAT. Dedicated quick-filters per source in one single compliance view.",
    },
  ],

  // ── Workflow ──────────────────────────────────────────────────────────────

  workflowTitle: "Pipeline overview",
  workflowIntro:
    "Each step runs automatically in the background via a Celery task queue. " +
    "Click a step to see technical details and regulatory relevance.",

  workflowSteps: [
    {
      step: 1, icon: "📤", color: STEP_COLORS[0]!,
      title: "Upload",
      desc: "A PDF invoice is uploaded via the user interface. The file is stored and a " +
            "job is created with status 'uploaded'.",
      detail: [
        "Supports standard PDF files and scanned documents (OCR fallback).",
        "The file is stored securely and linked to a unique invoice ID.",
        "Compliance log: upload timestamp and user identity are recorded immediately.",
      ],
    },
    {
      step: 2, icon: "🔍", color: STEP_COLORS[1]!,
      title: "Parsing",
      desc: "The system reads the PDF and extracts raw text. OCR is applied as needed for " +
            "scanned documents. Status is set to 'parsing'.",
      detail: [
        "Uses PyMuPDF for digital PDF and an OCR fallback for scanned documents.",
        "Text is normalised and prepared for AI extraction.",
      ],
    },
    {
      step: 3, icon: "🤖", color: STEP_COLORS[2]!,
      title: "AI extraction",
      desc: "A large language model analyses the invoice text and extracts structured data: " +
            "seller, buyer, freight forwarder, destination country, HS codes, line amounts " +
            "and more. Status is set to 'extracted'.",
      detail: [
        "Primary model: Claude (Anthropic). Fallback: GPT-4o (OpenAI). Switchable in the UI.",
        "Each field receives a confidence score 0-1. Low confidence (<0.8) is flagged visually.",
        "AI Act Art. 13: Confidence scores and field details provide full transparency on AI assessments.",
        "All extracted fields are editable by authorised users and logged in the audit trail.",
      ],
    },
    {
      step: 4, icon: "🔎", color: STEP_COLORS[3]!,
      title: "Sanctions screening",
      desc: "All extracted entities (seller, buyer, freight forwarder etc.) are checked " +
            "against OpenSanctions via Yente. Fuzzy matching finds hits even for name " +
            "variations. Status is set to 'screening'.",
      detail: [
        "Match threshold: 0.70 - Potential match (yellow score, sent to review).",
        "Confirmed threshold: 0.79 - Confirmed match (red score, blocking recommended).",
        "Covers: EU sanctions, OFAC SDN/CAPTA, UN, UK OFSI, and 100+ lists via OpenSanctions.",
        "Updated daily at 07:40 via Celery Beat.",
        "Relevant for: Export Control Act, EU Dual-Use 2021/821, AML Act (KYC/CDD).",
      ],
    },
    {
      step: 5, icon: "⚙️", color: STEP_COLORS[4]!,
      title: "Rule evaluation",
      desc: "All active YAML rules are evaluated against the invoice data. Rules can set " +
            "flags and affect the score.",
      detail: [
        "Rule types: destination country, HS code, entity name, email domain, amount thresholds.",
        "Operators: in, not_in, equals, regex, gt, lt.",
        "Condition combination: AND/OR across conditions.",
        "Rules are documented and logged - supports audit under AI Act Art. 9 and 12.",
      ],
    },
    {
      step: 6, icon: "🚦", color: STEP_COLORS[5]!,
      title: "Scoring",
      desc: "The system calculates an overall compliance score based on sanctions hits and " +
            "rule outcomes. Status is set to 'screened'.",
      detail: [
        "Green - no hits, all rules passed.",
        "Yellow - potential hits or warning rules triggered.",
        "Red - confirmed sanctions hit or blocking rules.",
        "The score is explained: users see which individual findings contributed.",
      ],
    },
    {
      step: 7, icon: "👤", color: STEP_COLORS[6]!,
      title: "Manual review",
      desc: "Yellow and red invoices enter the review queue. The compliance officer sees all " +
            "details, sanctions hits, rule outcomes and audit trail before deciding. " +
            "The invoice can be 'claimed' to prevent double-handling.",
      detail: [
        "Priority: red invoices appear first, then yellow.",
        "AI Act Art. 14: Human oversight is mandatory - no automatic approval.",
        "Audit trail: who has viewed and processed the invoice is logged continuously.",
      ],
    },
    {
      step: 8, icon: "✅", color: STEP_COLORS[7]!,
      title: "Decision",
      desc: "The compliance officer approves or rejects the invoice with a written " +
            "justification. The decision, user and timestamp are stored in the audit trail.",
      detail: [
        "Approved - status 'approved', invoice can be processed further.",
        "Rejected - status 'blocked', invoice is blocked.",
        "The justification is searchable and can be presented at regulatory inspection.",
        "Supports documentation requirements of the Export Control Act and AML Act.",
      ],
    },
  ],

  // ── Pages ─────────────────────────────────────────────────────────────────

  pagesTitle: "Pages and features",
  pagesIntro: "The system is divided into specialised pages. Access is governed by the user's role.",

  pageDocs: [
    {
      icon: "📋", name: "Invoices", path: "/invoices",
      access: "All roles",
      desc: "Main overview of all invoices. Filter by status, compliance score, direction " +
            "(import/export), country and free text. Sanctions status is shown in the list. " +
            "Upload new invoices directly from here.",
    },
    {
      icon: "🗂️", name: "Invoice detail", path: "/invoices/:id",
      access: "All roles",
      desc: "Detailed view of a single invoice: PDF preview, all extracted fields with " +
            "confidence scores (editable), entity list with sanctions hits, rule outcomes, " +
            "framework agreement checks and full audit trail. Initiate screening, extended " +
            "screening or review from here.",
    },
    {
      icon: "📊", name: "Dashboard", path: "/dashboard",
      access: "All roles with dashboard:view",
      desc: "KPI overview: total invoices, score distribution (green/yellow/red), average " +
            "processing time, review queue size and weekly trend. Gives compliance managers " +
            "an instant situational picture.",
    },
    {
      icon: "👥", name: "Customers", path: "/customers",
      access: "Compliance Officer, Controller, Admin",
      desc: "List of registered counterparties and customers with compliance history. " +
            "Shows which invoices are linked to each party and any open findings. " +
            "Supports KYC work under the AML Act.",
    },
    {
      icon: "⏳", name: "Review queue", path: "/review-queue",
      access: "Compliance Officer, Admin",
      desc: "Unified worklist for all invoices awaiting manual decision. Coloured flag " +
            "badges per invoice show the sources (sanctions, embargo, export control, " +
            "end-user, dual-use, ownership, VAT). Quick-filters per source. " +
            "Sorted red-first, unhandled-first.",
    },
    {
      icon: "⚙️", name: "Rules", path: "/rules",
      access: "Compliance Officer, Admin",
      desc: "Manage the YAML rules engine. Write conditions with severity level " +
            "(green/yellow/red). Test rules against sample data without saving. Re-run all " +
            "active rules against existing invoices.",
    },
    {
      icon: "🚫", name: "Internal watchlist", path: "/watchlist",
      access: "Compliance Officer, Admin",
      desc: "Manage the company's internal watchlist. Add names, email domains and HS codes " +
            "with severity and justification. Hits appear as screening results in addition " +
            "to OpenSanctions findings.",
    },
    {
      icon: "📜", name: "Framework agreements", path: "/agreements",
      access: "All roles with agreements:view",
      desc: "Upload and manage PDF framework agreements. AI automatically extracts key terms: " +
            "permitted destination countries, product restrictions and value caps. See which " +
            "invoices have been checked against the agreement and the result.",
    },
    {
      icon: "🌍", name: "Maps", path: "/maps",
      access: "All roles",
      desc: "Interactive world map with colour-coded country risk classification (Tier 1-4). " +
            "Filter by risk level. A shipments layer shows trade routes derived from invoice " +
            "origin and destination countries.",
    },
    {
      icon: "🔎", name: "Sanctioned entities", path: "/sanctioned-entities",
      access: "Compliance Officer, Admin",
      desc: "Direct search in the OpenSanctions database. Search by name, country or type. " +
            "Shows all sanctions registers where the entity is listed, with date and source. " +
            "Includes a button to trigger a manual refresh of the sanctions database.",
    },
    {
      icon: "🔍", name: "Invoice search", path: "/invoices/search",
      access: "All roles",
      desc: "Advanced full-text search across all invoices and entities. Supports search by " +
            "invoice number, serial number, entity name, destination country and HS code.",
    },
    {
      icon: "🛠️", name: "Pipeline ops", path: "/pipeline-ops",
      access: "Admin only",
      desc: "Monitoring of the background pipeline: throughput, latency and stuck invoices. " +
            "Admins can trigger manual re-processing of individual invoices.",
    },
    {
      icon: "🕸️", name: "Extended screening", path: "/invoices/:id/entities/:eId/extended-screen/:rId",
      access: "Compliance Officer, Admin",
      desc: "Graph-based relationship analysis of a single entity via Wikidata. Reveals " +
            "ownership structures and board members linked to sanctioned parties. " +
            "Each node can be marked as relevant or not relevant.",
    },
    {
      icon: "🛡", name: "Export control", path: "/review-queue?filter=export_control",
      access: "Compliance Officer, Admin",
      desc: "Filter in the review queue for invoices flagged against DEKSA Vareliste I " +
            "(military goods, ML1-ML22) or Vareliste II (dual-use, categories 0-9). " +
            "Shows hits per line with list, category and confidence level (high/medium/low).",
    },
    {
      icon: "📚", name: "Export control reference", path: "/export-control/reference",
      access: "Compliance Officer, Admin",
      desc: "Browse DEKSA control lists: search by code or keyword, view category overview " +
            "and import status. Admins can run a backfill to re-evaluate historical " +
            "invoices against the current list version.",
    },
    {
      icon: "🎯", name: "End-user / catch-all", path: "/review-queue?filter=catch_all",
      access: "Compliance Officer, Admin",
      desc: "Filter in the review queue for invoices with risk signals in end-user, " +
            "destination or intended use under DEKSA's catch-all principle. Shows " +
            "triggered signals: military end-use, diversion risk, nuclear use, and more.",
    },
  ],

  // ── Roles ─────────────────────────────────────────────────────────────────

  rolesTitle: "Roles and permissions",
  rolesIntro:
    "Access control is role-based (RBAC). Each user has one role that determines which " +
    "pages and actions are available. In production the role is set via JWT claims from " +
    "the authentication provider. During development the role can be switched via the " +
    "role selector in the top right.",

  roles: [
    {
      name: "Admin",
      colorClass: ROLE_COLORS.admin,
      desc: "Full access to all pages and features, including operations and pipeline management.",
      perms: [
        "Upload, edit and delete invoices",
        "Run extraction and screening",
        "Approve / reject invoices",
        "Manage rules and watchlist",
        "Upload and manage framework agreements",
        "View and manage customers",
        "Pipeline ops and re-processing",
        "View all maps and sanctioned entities",
      ],
    },
    {
      name: "C-level",
      colorClass: ROLE_COLORS.c_level,
      desc: "Same access as Admin. Intended for executives who need full oversight.",
      perms: ["All pages and features (identical to Admin)"],
    },
    {
      name: "Compliance Officer",
      colorClass: ROLE_COLORS.compliance_officer,
      desc: "Primary profile for day-to-day compliance work. Can review, decide, and manage rules.",
      perms: [
        "Upload and edit invoices",
        "Run extraction and screening",
        "Approve / reject invoices (review queue)",
        "Manage rules and watchlist",
        "Upload and manage framework agreements",
        "View customers",
        "Search the sanctions database",
        "Dashboard, maps and invoice search",
      ],
    },
    {
      name: "Controller",
      colorClass: ROLE_COLORS.controller,
      desc: "Accounting roles working with invoices but not making compliance decisions.",
      perms: [
        "Upload and edit invoices",
        "Run extraction",
        "View and edit customers",
        "View framework agreements",
        "Dashboard and invoice search",
        "Maps (read access)",
      ],
    },
    {
      name: "Read-only",
      colorClass: ROLE_COLORS.readonly,
      desc: "Read access to the main pages. Cannot perform any actions.",
      perms: [
        "View invoices",
        "View dashboard",
        "View rules (not edit)",
        "View framework agreements",
        "View customers",
      ],
    },
  ],

  // ── Technical ─────────────────────────────────────────────────────────────

  techTitle: "Technical stack",

  techStack: [
    {
      category: "Frontend",
      items: [
        { name: "React 18", desc: "UI framework with Suspense and lazy-loading" },
        { name: "TypeScript", desc: "Static typing across the entire frontend codebase" },
        { name: "Vite", desc: "Build tool and dev server with fast HMR" },
        { name: "Tailwind CSS", desc: "Utility-first CSS with a custom design system" },
        { name: "React Query", desc: "Server state management and API call caching" },
        { name: "React Router", desc: "Client-side routing (SPA)" },
        { name: "react-leaflet", desc: "Interactive map (OpenStreetMap-based)" },
        { name: "i18next", desc: "Internationalisation (Norwegian / English)" },
      ],
    },
    {
      category: "Backend",
      items: [
        { name: "FastAPI", desc: "Async Python API with OpenAPI documentation" },
        { name: "SQLAlchemy (async)", desc: "ORM for PostgreSQL with async support" },
        { name: "Celery", desc: "Distributed task queue for background processing" },
        { name: "Alembic", desc: "Database migrations" },
        { name: "Pydantic v2", desc: "Data validation and serialisation" },
      ],
    },
    {
      category: "AI / LLM",
      items: [
        { name: "Anthropic Claude", desc: "Primary LLM for extraction and analysis" },
        { name: "OpenAI GPT-4o", desc: "Fallback model during downtime or errors" },
        { name: "Model selector", desc: "Switchable live in the UI via the gear icon" },
      ],
    },
    {
      category: "Sanctions database",
      items: [
        { name: "Yente (OpenSanctions)", desc: "Sanctions screening API with fuzzy matching" },
        { name: "Elasticsearch 8", desc: "Search index behind Yente for fast lookups" },
        { name: "OpenSanctions data", desc: "Daily updates from EU, OFAC, UN, UK and 100+ sources" },
      ],
    },
    {
      category: "Infrastructure",
      items: [
        { name: "Docker Compose", desc: "Orchestration of all services locally and in dev" },
        { name: "PostgreSQL 16", desc: "Primary database for all invoice and user data" },
        { name: "Redis 7", desc: "Broker and result backend for Celery" },
        { name: "Celery Beat", desc: "Scheduled daily sanctions list refresh at 07:40" },
      ],
    },
  ],

  tierTitle: "Country risk classification",
  tierIntro:
    "All countries are pre-classified into four risk tiers. The tiers are used by the " +
    "rules engine, map view and invoice detail page.",

  tiers: [
    { tier: "Tier 1 - Low",      colorClass: TIER_COLORS[0]!, examples: "NATO countries (NO, DE, US, FR, GB, ...)", rule: "NATO membership" },
    { tier: "Tier 2 - Normal",   colorClass: TIER_COLORS[1]!, examples: "Most other countries",                     rule: "Default level" },
    { tier: "Tier 3 - Elevated", colorClass: TIER_COLORS[2]!, examples: "CN, QA, SA, TR, UA, AZ, ...",             rule: "Geopolitical risk" },
    { tier: "Tier 4 - High",     colorClass: TIER_COLORS[3]!, examples: "AF, BY, CU, IR, KP, RU, SY",              rule: "Active sanctions" },
  ],

  tierTableHeaders: ["Tier", "Examples", "Criterion"],

  thresholdTitle: "Confidence thresholds for sanctions screening",
  thresholds: [
    { label: "Match threshold",     value: ">= 0.70", consequence: "Potential match - yellow score, sent to review" },
    { label: "Confirmed threshold", value: ">= 0.79", consequence: "Confirmed match - red score, blocking recommended" },
  ],
  thresholdTableHeaders: ["Threshold", "Value", "Consequence"],
  thresholdNote:
    "Thresholds can be adjusted via the environment variables SCREENING_MATCH_THRESHOLD " +
    "and SCREENING_CONFIRMED_THRESHOLD.",

  // ── Regulatory compliance ─────────────────────────────────────────────────

  complianceTitle: "Regulatory compliance",
  complianceIntro:
    "XLENT Compliance is designed to support businesses in meeting key Norwegian and " +
    "European regulatory requirements in export control, sanctions, data protection and " +
    "artificial intelligence. The sections below describe how the system contributes to " +
    "compliance with each relevant regulatory framework.",

  complianceSections: [
    {
      icon: "📦",
      title: "Export control",
      subtitle: "Norwegian Export Control Act (2013) - EU Dual-Use Regulation 2021/821",
      points: [
        {
          label: "Norwegian Export Control Act",
          desc: "Norwegian law regulates the export of strategic goods, software and " +
                "technology with potential military end-use. Exporters are obligated to " +
                "identify whether a licence is required and whether the buyer is sanctioned. " +
                "The system automates the screening part of this obligation.",
        },
        {
          label: "EU Dual-Use Regulation 2021/821",
          desc: "The EU regulation controls goods with both civilian and military " +
                "applications. Annex I contains the EU control list. The system supports " +
                "checking HS codes against known risk categories and destinations in the " +
                "rules engine.",
        },
        {
          label: "Catch-all clause (section 5)",
          desc: "Section 5 of the Export Control Act and EU Article 4 allow authorities " +
                "to deny export even for non-listed goods when there are grounds to suspect " +
                "military, nuclear or WMD-related end-use. The system has a dedicated catch-all " +
                "module that automatically evaluates end-user, destination and intended use " +
                "against six risk signals: military/nuclear end-use, diversion risk, sensitive " +
                "end-use, broker intermediaries, undeclared consignee. Flagged invoices are " +
                "routed to manual review.",
        },
        {
          label: "Audit and documentation",
          desc: "All compliance assessments with justifications are stored in the audit " +
                "trail. This makes it possible to document due diligence to the Ministry " +
                "of Foreign Affairs and other authorities during inspections.",
        },
      ],
    },
    {
      icon: "🛡️",
      title: "Sanctions compliance",
      subtitle: "EU sanctions - OFAC - UN - UK OFSI - OpenSanctions",
      points: [
        {
          label: "EU sanctions",
          desc: "EU sanctions regimes are enacted through Council Regulations directly " +
                "binding in all EU/EEA member states. These include country-specific regimes " +
                "(Russia, Iran, Syria, North Korea, Belarus) and thematic regimes " +
                "(terrorism, WMD, cybersecurity, human rights).",
        },
        {
          label: "OFAC (US Treasury)",
          desc: "The Office of Foreign Assets Control administers US economic sanctions. " +
                "The SDN (Specially Designated Nationals) list prohibits dealings with listed " +
                "individuals and entities. Relevant for Norwegian companies with USD " +
                "transactions or US nexus.",
        },
        {
          label: "UN sanctions",
          desc: "The UN Security Council imposes sanctions under Chapter VII. All UN members " +
                "are obligated to implement these, including travel bans and trade " +
                "prohibitions against specific countries and individuals.",
        },
        {
          label: "UK OFSI",
          desc: "The Office of Financial Sanctions Implementation manages UK sanctions " +
                "post-Brexit, including both UN-derived and UK-autonomous sanction lists.",
        },
        {
          label: "OpenSanctions integration",
          desc: "The system uses the OpenSanctions database, which aggregates 100+ " +
                "sanctions lists from authorities worldwide. The database includes PEP " +
                "(Politically Exposed Persons) lists and is updated daily. Fuzzy name " +
                "matching ensures hits are detected even with name variants.",
        },
      ],
    },
    {
      icon: "🤖",
      title: "EU AI Act",
      subtitle: "Regulation 2024/1689 - in force August 2024",
      points: [
        {
          label: "System classification",
          desc: "XLENT Compliance is a decision-support tool where humans always make the " +
                "final determination. The AI provides assessments and ranking - not autonomous " +
                "decisions. This is in line with the requirement for human-in-the-loop for " +
                "systems affecting business decisions.",
        },
        {
          label: "Transparency (Art. 13)",
          desc: "All AI assessments are displayed with confidence scores and detailed " +
                "explanations. Users see exactly which fields were extracted and with what " +
                "certainty. Model information (primary/fallback) is shown in the top bar.",
        },
        {
          label: "Human oversight (Art. 14)",
          desc: "The review queue ensures that all yellow and red invoices are assessed by " +
                "an authorised compliance officer before a decision. No invoice can be " +
                "approved without human review. The officer can override the system's " +
                "assessment with a written justification.",
        },
        {
          label: "Traceability and audit (Art. 12)",
          desc: "All actions are logged in an immutable audit trail with timestamp, user " +
                "identity and justification. Rule changes and model switches are logged " +
                "separately. This enables documentation for regulatory authorities.",
        },
        {
          label: "Risk management (Art. 9)",
          desc: "Confidence thresholds and rules are configurable by the compliance team " +
                "and documented in the system. All rule changes are tracked. The system " +
                "has watchdog processes that detect invoices stuck in the pipeline.",
        },
      ],
    },
    {
      icon: "🔒",
      title: "Data protection & GDPR",
      subtitle: "Regulation 2016/679 (GDPR) - Norwegian Personal Data Act",
      points: [
        {
          label: "Legal basis",
          desc: "The system processes personal data of counterparties (names, companies, " +
                "addresses) on the basis of legal obligation (Art. 6(1)(c)) - export " +
                "control and AML requirements - and legitimate interest (Art. 6(1)(f)).",
        },
        {
          label: "Data minimisation",
          desc: "Only the fields necessary for the compliance assessment are extracted and " +
                "stored. The system is designed to process as little personal data as " +
                "possible while meeting regulatory obligations.",
        },
        {
          label: "Right to explanation",
          desc: "Confidence scores and match details provide a basis for explaining why an " +
                "invoice received a particular score. This supports the data subject's " +
                "right to explanation for automated processing (Art. 22).",
        },
        {
          label: "Access control",
          desc: "Role-based access control (RBAC) ensures that only authorised users can " +
                "view and process data. All data access is logged in the audit trail.",
        },
        {
          label: "Audit trail and documentation",
          desc: "All processing activities are logged and can be presented to supervisory " +
                "authorities (national DPAs) during inspections. The system supports the " +
                "obligation to maintain records of processing activities (Art. 30).",
        },
      ],
    },
    {
      icon: "💰",
      title: "Anti-money laundering & KYC",
      subtitle: "Norwegian AML Act (2018) - EU AMLD5/AMLD6 - FATF recommendations",
      points: [
        {
          label: "Customer due diligence (CDD/KYC)",
          desc: "Sanctions screening supports the CDD obligation: identifying and verifying " +
                "counterparty identity and checking against sanctions and PEP lists. " +
                "The customer registry provides an overview of all counterparties and their " +
                "compliance history.",
        },
        {
          label: "PEP screening",
          desc: "The OpenSanctions database includes PEP (Politically Exposed Persons) " +
                "lists covered by the screening. Hits are reported with match details and " +
                "source register.",
        },
        {
          label: "FATF Recommendation 6",
          desc: "FATF recommends that all countries implement targeted financial sanctions " +
                "(TFS) to combat terrorist financing and proliferation of weapons of mass " +
                "destruction. The system's sanctions screening directly supports this " +
                "recommendation.",
        },
        {
          label: "Suspicious transactions",
          desc: "Invoices with high risk scores generate alerts that support the assessment " +
                "of whether a suspicious transaction report should be filed. The justification " +
                "and audit trail can be attached to the report.",
        },
        {
          label: "Documentation at inspection",
          desc: "Compliance decisions with justifications can be presented as documentation " +
                "during regulatory inspections. The system makes it easy to retrieve history " +
                "for specific counterparties and transactions.",
        },
      ],
    },
  ],
};

// ── Export ────────────────────────────────────────────────────────────────────

export const ABOUT_CONTENT: Record<"nb" | "en", AboutContent> = { nb: NB, en: EN };
