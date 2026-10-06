// Mirrors the FastAPI response models in backend/app. Phase 1 can replace these with a generated client.

export interface Settings {
  base_url: string;
  model: string;
  extraction_model: string;
  rewrite_model: string;
}

export interface SettingsOut extends Settings {
  has_api_key: boolean;
}

export interface ModelInfo {
  id: string;
  name: string;
  context_length: number | null;
  prompt_price: number | null;
  completion_price: number | null;
  supports_json: boolean | null;
}

export interface ConnectionResult {
  ok: boolean;
  message: string;
}

export interface Health {
  status: string;
  version: string;
}
