/**
 * TypeScript mirrors of the FastAPI Pydantic schemas.
 *
 * Keeping these in one place means a schema change surfaces as a compile error
 * in exactly the components that need updating.
 */

// --------------------------------------------------------------------------- //
// Shared
// --------------------------------------------------------------------------- //
export type Visibility = "Public" | "Private";
export type Severity = "Bug" | "Security" | "Style" | "Suggestion";
export type Proficiency = "Beginner" | "Intermediate" | "Advanced";
export type ChangeType = "Added" | "Modified" | "Deleted" | "Renamed";

// --------------------------------------------------------------------------- //
// Users / auth
// --------------------------------------------------------------------------- //
export interface UserBase {
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  location: string | null;
  company: string | null;
  website: string | null;
}

export interface UserRead extends UserBase {
  id: string;
  followers_count: number;
  following_count: number;
  created_at: string;
}

export interface UserMe extends UserRead {
  email: string;
  is_superuser: boolean;
  skills_analyzed_at: string | null;
}

export interface SkillRead {
  id: string;
  skill_name: string;
  proficiency: Proficiency;
  category: string;
  confidence: number;
  evidence: string | null;
}

export interface UserProfile extends UserRead {
  skills: SkillRead[];
  languages: Record<string, number>;
  total_commits: number;
  total_repos: number;
  total_stars: number;
  followers: string[];
  following: string[];
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserMe;
}

export interface SkillProfile {
  languages: string[];
  frameworks: string[];
  tools: string[];
  databases: string[];
  proficiency: Proficiency;
  summary: string | null;
  username: string;
  generated_at: string;
}

// --------------------------------------------------------------------------- //
// Repositories
// --------------------------------------------------------------------------- //
export interface RepoRead {
  id: string;
  name: string;
  description: string | null;
  visibility: Visibility;
  primary_language: string | null;
  topics: string[];
  owner_username: string;
  star_count: number;
  is_pinned: boolean;
  commit_count: number;
  file_count: number;
  default_branch: string;
  indexed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FileNode {
  name: string;
  path: string;
  type: "blob" | "tree";
  size: number | null;
  language: string | null;
  children: FileNode[] | null;
}

export interface CommitRead {
  id: string;
  commit_hash: string;
  short_hash: string;
  parent_hash: string | null;
  message: string;
  summary: string;
  author: { id: string; username: string; avatar_url: string | null } | null;
  timestamp: string;
  files_changed: number;
  additions: number;
  deletions: number;
  ai_reviewed: boolean;
  message_generated: boolean;
}

export interface RepoDetail extends RepoRead {
  owner_avatar_url: string | null;
  tree: FileNode[];
  latest_commit: CommitRead | null;
}

export interface FileContent {
  id: string;
  file_path: string;
  content: string;
  size_bytes: number;
  line_count: number;
  language: string | null;
  is_binary: boolean;
  blob_hash: string | null;
  updated_at: string;
}

export interface RepoLanguageStat {
  language: string;
  bytes: number;
  percentage: number;
}

export interface RepoLanguages {
  total_bytes: number;
  languages: RepoLanguageStat[];
}

// --------------------------------------------------------------------------- //
// Push / version control
// --------------------------------------------------------------------------- //
export interface PushFilePayload {
  path: string;
  content: string;
}

export interface PushRequest {
  files: PushFilePayload[];
  deleted_paths?: string[];
  commit_message?: string | null;
  branch?: string | null;
  run_ai?: boolean;
}

export interface PushFileResult {
  path: string;
  change_type: ChangeType;
  additions: number;
  deletions: number;
  blob_hash: string;
}

export interface PushResponse {
  commit_hash: string;
  short_hash: string;
  message: string;
  message_generated: boolean;
  files_changed: number;
  additions: number;
  deletions: number;
  files: PushFileResult[];
  ai_queued: boolean;
}

export interface CommitListResponse {
  items: CommitRead[];
  total: number;
  page: number;
  per_page: number;
}

export interface AIReviewRead {
  id: string;
  review_text: string;
  line_number: number | null;
  file_path: string | null;
  severity: Severity;
  title: string | null;
  created_at: string;
}

export interface CommitDetail extends CommitRead {
  diff: string | null;
  reviews: AIReviewRead[];
}

// --------------------------------------------------------------------------- //
// Dashboard
// --------------------------------------------------------------------------- //
export interface HeatmapDay {
  date: string;
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
  additions: number;
  deletions: number;
}

export interface StreakStats {
  total_commits: number;
  total_additions: number;
  total_deletions: number;
  current_streak: number;
  longest_streak: number;
  active_days: number;
  first_commit_at: string | null;
  last_commit_at: string | null;
  repos_contributed_to: number;
}

export interface HeatmapResponse {
  days: HeatmapDay[];
  stats: StreakStats;
  yearly_totals: Record<string, number>;
}

export interface ActivityPoint {
  week_start: string;
  commits: number;
  additions: number;
  deletions: number;
}

export interface LanguageStat {
  language: string;
  repo_count: number;
  percentage: number;
}

export interface DashboardResponse {
  heatmap: HeatmapResponse;
  activity: ActivityPoint[];
  languages: LanguageStat[];
  pinned_repos: RepoRead[];
}

// --------------------------------------------------------------------------- //
// AI
// --------------------------------------------------------------------------- //
export interface Citation {
  file_path: string;
  start_line: number;
  end_line: number;
  language: string | null;
  symbol: string | null;
  score: number;
  snippet: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  model: string;
  elapsed_ms: number;
  cached: boolean;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  elapsedMs?: number;
  error?: boolean;
}

export interface SearchHit {
  file_path: string;
  start_line: number;
  end_line: number;
  language: string | null;
  symbol: string | null;
  score: number;
  snippet: string;
  summary: string | null;
}

export interface SearchResponse {
  query: string;
  results: SearchHit[];
  elapsed_ms: number;
}

export interface ReviewResponse {
  commit_id: string;
  commit_hash: string;
  status: "pending" | "complete" | "failed" | "disabled";
  reviews: Omit<AIReviewRead, "created_at">[];
  error: string | null;
}

export interface IndexStatus {
  repo_id: string;
  indexed_files: number;
  indexed_chunks: number;
  skipped_files: number;
  collection: string;
  elapsed_ms: number;
}

export interface AIHealth {
  ai_enabled: boolean;
  ollama: {
    available: boolean;
    host: string;
    chat_model: string;
    embed_model: string;
    models: string[];
  };
  chroma: { enabled: boolean; available: boolean; host: string; port: number };
  hint: string | null;
}

export interface ApiValidationError {
  detail: string;
  errors?: { field: string; message: string; type: string }[];
}
