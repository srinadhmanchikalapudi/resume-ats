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

export interface Link {
  label: string;
  url: string;
}

export interface Contact {
  name: string;
  email: string;
  phone: string;
  location: string;
  links: Link[];
}

export interface Experience {
  id: string;
  title: string;
  company: string;
  location: string;
  start: string;
  end: string;
  current: boolean;
  bullets: string[];
}

export interface Education {
  id: string;
  school: string;
  degree: string;
  field: string;
  location: string;
  start: string;
  end: string;
  details: string[];
}

export interface SkillGroup {
  category: string;
  items: string[];
}

export interface Certification {
  id: string;
  name: string;
  issuer: string;
  date: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  url: string;
  tech: string[];
  bullets: string[];
}

export interface Profile {
  contact: Contact;
  summary: string;
  experience: Experience[];
  education: Education[];
  skills: SkillGroup[];
  certifications: Certification[];
  projects: Project[];
}

export interface ProfileOut {
  profile: Profile;
  exists: boolean;
  updated_at: string | null;
}

export interface ImportResult {
  profile: Profile;
  warnings: string[];
}
