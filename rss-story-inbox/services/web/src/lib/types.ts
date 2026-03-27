export type ClusterArticle = {
  id: number;
  title: string;
  url: string;
  source_name: string;
  published_at?: string;
  match_confidence?: number;
};

export type Cluster = {
  id: number;
  cluster_title: string;
  coverage_count: number;
  latest_published_at?: string;
  score: number;
  why: string;
  qualifying_terms: string[];
  canonical?: ClusterArticle;
  coverage: ClusterArticle[];
};

export type Profile = {
  id: number;
  audience_text: string;
  tone_text: string;
  include_terms: string;
  include_terms_2: string;
  exclude_terms: string;
};

export type PublishedItem = {
  cluster_id: number;
  title: string;
  coverage_count: number;
  latest_published_at?: string;
  summary?: string;
  url?: string;
  score: number;
};
