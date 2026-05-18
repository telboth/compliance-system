/**
 * useNotifications — henter in-app varsler for gjeldende brukerrolle.
 *
 * Poller hvert 30. sekund for nye varsler.
 * Read-tracking skjer i localStorage (Set av notification-IDs).
 */
import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listNotifications } from "@/api/notifications";
import type { AppNotification } from "@/api/types";

// ── LocalStorage read-tracking ────────────────────────────────────────────────

const LS_KEY = "xlent_read_notifications";

function loadReadIds(): Set<string> {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return new Set(JSON.parse(raw) as string[]);
  } catch {
    /* ignore */
  }
  return new Set();
}

function saveReadIds(ids: Set<string>): void {
  try {
    // Behold maks 500 ID-er for å unngå at localStorage vokser ubegrenset
    const arr = [...ids].slice(-500);
    localStorage.setItem(LS_KEY, JSON.stringify(arr));
  } catch {
    /* ignore */
  }
}

// ── Query-nøkler ──────────────────────────────────────────────────────────────

export const notificationKeys = {
  all: ["notifications"] as const,
  list: (role: string) => [...notificationKeys.all, role] as const,
};

// ── Hook ──────────────────────────────────────────────────────────────────────

export interface UseNotificationsResult {
  notifications: AppNotification[];
  unreadCount: number;
  markRead: (id: string) => void;
  markAllRead: () => void;
  isLoading: boolean;
}

export function useNotifications(
  role: string,
  options: { enabled?: boolean } = {},
): UseNotificationsResult {
  const [readIds, setReadIds] = useState<Set<string>>(loadReadIds);

  const { data, isLoading } = useQuery({
    queryKey: notificationKeys.list(role),
    queryFn: () => listNotifications({ role, limit: 30 }),
    enabled: options.enabled !== false && Boolean(role),
    // Poll hvert 30. sekund
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const notifications = data?.items ?? [];
  const unreadCount = notifications.filter((n) => !readIds.has(n.id)).length;

  const markRead = useCallback((id: string) => {
    setReadIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      saveReadIds(next);
      return next;
    });
  }, []);

  const markAllRead = useCallback(() => {
    setReadIds((prev) => {
      const next = new Set(prev);
      for (const n of notifications) next.add(n.id);
      saveReadIds(next);
      return next;
    });
  }, [notifications]);

  return { notifications, unreadCount, markRead, markAllRead, isLoading };
}
