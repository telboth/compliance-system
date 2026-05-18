import { apiClient } from "@/api/client";

export interface ModelResponse {
  provider: string;
  model_id: string;
  display_name: string;
  multimodal: boolean;
  local: boolean;
  available: boolean;
  tags: string[];
}

export interface ProviderResponse {
  provider_id: string;
  display_name: string;
  available: boolean;
  models: ModelResponse[];
}

export interface ModelsListResponse {
  providers: ProviderResponse[];
  docling_pipeline: string;
}

export async function fetchModels(): Promise<ModelsListResponse> {
  const { data } = await apiClient.get<ModelsListResponse>("/models");
  return data;
}
