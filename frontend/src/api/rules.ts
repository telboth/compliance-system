import { apiClient } from "@/api/client";

export interface RuleVersion {
  id: string;
  version: number;
  rule_yaml: string;
  created_by: string;
  created_at: string;
  comment: string | null;
}

export interface Rule {
  id: string;
  name: string;
  description: string | null;
  severity: "green" | "yellow" | "red";
  is_active: boolean;
  active_version: number;
  versions: RuleVersion[];
  created_at: string;
  updated_at: string;
}

export interface RuleCreate {
  name: string;
  description?: string;
  severity?: string;
  rule_yaml: string;
  comment?: string;
}

export interface RuleUpdate {
  rule_yaml: string;
  name?: string;
  description?: string;
  severity?: string;
  comment?: string;
}

export interface RuleTestRequest {
  rule_yaml: string;
  context: Record<string, unknown>;
}

export interface RuleTestResponse {
  triggered: boolean;
  error: string | null;
}

export async function listRules(): Promise<Rule[]> {
  const { data } = await apiClient.get<Rule[]>("/rules");
  return data;
}

export async function createRule(body: RuleCreate): Promise<Rule> {
  const { data } = await apiClient.post<Rule>("/rules", body);
  return data;
}

export async function updateRule(id: string, body: RuleUpdate): Promise<Rule> {
  const { data } = await apiClient.put<Rule>(`/rules/${id}`, body);
  return data;
}

export async function toggleRule(id: string): Promise<Rule> {
  const { data } = await apiClient.patch<Rule>(`/rules/${id}/toggle`);
  return data;
}

export async function testRule(body: RuleTestRequest): Promise<RuleTestResponse> {
  const { data } = await apiClient.post<RuleTestResponse>("/rules/test", body);
  return data;
}

export interface RerunResponse {
  evaluated: number;
  score_changed: number;
  details: Array<{
    invoice_id: string;
    filename: string | null;
    old_score: string;
    new_score: string;
  }>;
}

export async function rerunRules(limit = 500): Promise<RerunResponse> {
  const { data } = await apiClient.post<RerunResponse>(`/rules/rerun?limit=${limit}`);
  return data;
}
