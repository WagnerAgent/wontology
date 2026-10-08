export type Provider = "aws" | "azure" | "gcp";
export type Resource = {
  canonical_id: string;
  provider: Provider;
  provider_id: string;
  provider_type: string;
  cloud_scope_id: string;
  semantic_type: string;
  category: string;
  name: string;
  location: string;
  tags: Record<string, string>;
  properties: Record<string, unknown>;
  health: { state: string };
  observed_at: string;
};
export type Relationship = {
  source_id: string;
  target_id: string;
  kind: string;
  rule_id: string;
  evidence: { source: string; path?: string; value?: unknown }[];
  confidence: number;
};
export type Coverage = {
  service: string;
  location: string;
  status: string;
  resources_found: number;
  error_message?: string;
};
export type Snapshot = {
  id?: string;
  provider?: Provider;
  scope?: string;
  demo?: boolean;
  complete?: boolean;
  resources: Resource[];
  relationships: Relationship[];
  coverage: Coverage[];
  unresolved_relationships: unknown[];
  schema_version: string;
};
export type Saved = {
  id: string;
  provider: Provider;
  scope: string;
  created_at: string;
  complete: boolean;
};
export type Job = {
  id: string;
  provider: Provider;
  status: string;
  snapshot: Snapshot | null;
  progress?: Coverage;
  error?: string;
};
