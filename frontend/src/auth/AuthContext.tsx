/**
 * AuthContext — kjernen i tilgangsstyringen.
 *
 * PROD-MIGRERING:
 *   Bytt ut `useLocalStorageRole()` med en `useQuery` mot `/api/v1/me`
 *   som returnerer `User` fra en dekodet JWT. Resten av appen er uendret.
 *
 * Eksempel (prod):
 *   const { data: user } = useQuery({ queryFn: () => api.get('/me') });
 *   // Pakk inn i AuthContext med denne user-verdien.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import type { Permission, Role, User } from "./permissions";
import { DEV_USERS, hasPermission } from "./permissions";

// ── Context-shape ─────────────────────────────────────────────────────────────

interface AuthContextValue {
  user: User;
  role: Role;
  /** Sjekk om innlogget bruker har en bestemt rettighet. */
  can: (permission: Permission) => boolean;
  /**
   * Bytt aktiv rolle (kun i dev-modus).
   * I prod: fjern denne funksjonen og vei den ned til undefined.
   */
  _devSetRole: (role: Role) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

const STORAGE_KEY = "xlent_dev_role";
const DEFAULT_ROLE: Role = "admin";

function loadRole(): Role {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) as Role | null;
    if (stored && stored in DEV_USERS) return stored;
  } catch {
    /* localStorage ikke tilgjengelig */
  }
  return DEFAULT_ROLE;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(loadRole);

  const _devSetRole = useCallback((newRole: Role) => {
    setRoleState(newRole);
    try {
      localStorage.setItem(STORAGE_KEY, newRole);
    } catch {
      /* ignore */
    }
  }, []);

  const user = DEV_USERS[role];

  const can = useCallback(
    (permission: Permission) => hasPermission(role, permission),
    [role],
  );

  const value = useMemo(
    () => ({ user, role, can, _devSetRole }),
    [user, role, can, _devSetRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/** Hent auth-kontekst. Kaster hvis brukt utenfor AuthProvider. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth() må brukes innenfor <AuthProvider>");
  }
  return ctx;
}
