/**
 * ProtectedRoute — rute-vakt basert på rettigheter.
 *
 * Brukes i Routes for å redirecte brukere som mangler en rettighet.
 * Ved prod-auth: bytt `useAuth()` mot en hook som henter fra JWT.
 */

import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";
import type { Permission } from "./permissions";

interface Props {
  /** Rettigheten som kreves for å se denne siden. */
  require: Permission;
  /** Rute å redirecte til ved manglende tilgang. Default: /dashboard */
  fallback?: string;
  children: ReactNode;
}

export function ProtectedRoute({ require, fallback = "/dashboard", children }: Props) {
  const { can } = useAuth();

  if (!can(require)) {
    return <Navigate to={fallback} replace />;
  }

  return <>{children}</>;
}
