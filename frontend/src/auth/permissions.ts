/**
 * Rolle- og rettighets-definisjon.
 *
 * Designet for enkel migrering til JWT-basert auth:
 *   - `Role` og `Permission` mapper direkte til JWT-claims
 *   - `ROLE_PERMISSIONS` kan byttes ut med en server-side policy
 *   - `User`-typen matcher /api/v1/me-responsen
 */

export type Role = "admin" | "c_level" | "compliance_officer" | "controller" | "readonly";

export type Permission =
  // Fakturaer
  | "invoices:view"
  | "invoices:upload"
  | "invoices:edit"
  | "invoices:delete"
  | "invoices:extract"
  | "invoices:screen"
  | "invoices:review" // godkjenn/avvis med begrunnelse
  // Regelmotor
  | "rules:view"
  | "rules:edit"
  // Rammeavtaler
  | "agreements:view"
  | "agreements:edit"
  // Dashboard
  | "dashboard:view"
  // Revisjonslogg
  | "audit:view"
  // Kunder
  | "customers:view"
  | "customers:edit"
  // System/drift
  | "system:admin";

/** Alle rettigheter samlet — brukes av admin-rollen. */
const ALL_PERMISSIONS: Permission[] = [
  "invoices:view",
  "invoices:upload",
  "invoices:edit",
  "invoices:delete",
  "invoices:extract",
  "invoices:screen",
  "invoices:review",
  "rules:view",
  "rules:edit",
  "agreements:view",
  "agreements:edit",
  "dashboard:view",
  "audit:view",
  "customers:view",
  "customers:edit",
  "system:admin",
];

export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  admin: ALL_PERMISSIONS,
  c_level: ALL_PERMISSIONS,

  compliance_officer: [
    "invoices:view",
    "invoices:upload",
    "invoices:edit",
    "invoices:extract",
    "invoices:screen",
    "invoices:review",
    "rules:view",
    "rules:edit",
    "agreements:view",
    "agreements:edit",
    "dashboard:view",
    "audit:view",
    "customers:view",
  ],

  controller: [
    "invoices:view",
    "invoices:upload",
    "invoices:edit",
    "invoices:extract",
    "dashboard:view",
    "audit:view",
    "customers:view",
    "customers:edit",
    "agreements:view",
  ],

  readonly: [
    "invoices:view",
    "dashboard:view",
    "rules:view",
    "agreements:view",
    "customers:view",
  ],
};

/** Sjekk om en rolle har en bestemt rettighet. */
export function hasPermission(role: Role, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role].includes(permission);
}

/** Brukerprofiler for dev-rollevelgeren. Byttes ut med /api/v1/me ved prod-auth. */
export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export const DEV_USERS: Record<Role, User> = {
  admin: {
    id: "dev-admin",
    name: "Ada Admin",
    email: "ada@technord.no",
    role: "admin",
  },
  c_level: {
    id: "dev-c-level",
    name: "Sigurd Sjef",
    email: "sigurd@technord.no",
    role: "c_level",
  },
  compliance_officer: {
    id: "dev-co",
    name: "Carl Compliance",
    email: "carl@technord.no",
    role: "compliance_officer",
  },
  controller: {
    id: "dev-ctrl",
    name: "Kari Controller",
    email: "kari@technord.no",
    role: "controller",
  },
  readonly: {
    id: "dev-ro",
    name: "Roy Readonly",
    email: "roy@technord.no",
    role: "readonly",
  },
};

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  c_level: "C-level",
  compliance_officer: "Compliance officer",
  controller: "Controller",
  readonly: "Lesetilgang",
};

export const ROLE_COLORS: Record<Role, string> = {
  admin: "bg-red-100 text-red-800",
  c_level: "bg-indigo-100 text-indigo-800",
  compliance_officer: "bg-purple-100 text-purple-800",
  controller: "bg-blue-100 text-blue-800",
  readonly: "bg-gray-100 text-gray-600",
};
