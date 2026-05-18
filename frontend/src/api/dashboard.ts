import { apiClient } from "@/api/client";

export interface DashboardTotals {
  invoices_total: number;
  invoices_this_week: number;
  invoices_this_month: number;
  open_flags: number;
  avg_processing_seconds: number;
}

export interface WeeklyTrendPoint {
  week_start: string | null;
  total: number;
  red_flags: number;
  yellow_flags: number;
  green_count: number;
}

export interface TopCustomer {
  customer_id: string;
  customer_name: string;
  flag_count: number;
}

export interface SanctionsStats {
  total_screenings_this_month: number;
  confirmed_matches: number;
  potential_matches: number;
}

export interface AuditAction {
  action: string;
  count: number;
}

export interface DashboardResponse {
  generated_at: string;
  totals: DashboardTotals;
  score_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  weekly_trend: WeeklyTrendPoint[];
  top_customers_with_flags: TopCustomer[];
  sanctions: SanctionsStats;
  recent_audit_actions: AuditAction[];
}

export async function getDashboard(): Promise<DashboardResponse> {
  const { data } = await apiClient.get<DashboardResponse>("/dashboard");
  return data;
}
