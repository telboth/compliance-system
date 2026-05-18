/**
 * Persistent lagring av valgt modell.
 *
 * Modellvalget lagres i localStorage slik at det huskes mellom refreshes.
 * Sendes som parameter til LLM-endepunkter i Sprint 2.
 */

const STORAGE_KEY = "xlent_selected_model";

export interface SelectedModel {
  provider: string;
  model_id: string;
  display_name: string;
}

const DEFAULT_MODEL: SelectedModel = {
  provider: "openai",
  model_id: "gpt-4o",
  display_name: "GPT-4o",
};

export function getSelectedModel(): SelectedModel {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored) as SelectedModel;
  } catch {
    // Korrupt localStorage — bruk default
  }
  return DEFAULT_MODEL;
}

export function setSelectedModel(model: SelectedModel): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(model));
}

export function clearSelectedModel(): void {
  localStorage.removeItem(STORAGE_KEY);
}
