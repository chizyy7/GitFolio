"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Bot,
  FolderTree,
  GitCommitHorizontal,
  Info,
  Lock,
  Star,
  Upload,
} from "lucide-react";

import { AIChat } from "@/components/AIChat";
import { CodeSearch } from "@/components/CodeSearch";
import { CodeViewer } from "@/components/CodeViewer";
import { CommitList } from "@/components/CommitList";
import { FileTree } from "@/components/FileTree";
import { PushPanel } from "@/components/PushPanel";
import { useAuth } from "@/context/AuthContext";
import type { CommitRead, PushResponse, RepoDetail } from "@/lib/types";
import { cn, formatRelative, languageColor } from "@/lib/utils";

interface Props {
  repo: RepoDetail;
  commits: CommitRead[];
  username: string;
  /** Re-fetch repository + commit data (e.g. after a push). */
  onRefresh?: () => void;
}

type TabKey = "code" | "commits" | "ai" | "push" | "about";

/**
 * Repository workspace.
 *
 * Tabs: Code (file tree + highlighted viewer), Commits (history), AI (RAG chat
 * + semantic search), Push (owner only) and About.
 *
 * It also coordinates "jump to file:line" requests coming from AI citations
 * and search results, which is the detail that makes the AI feel wired into
 * the code instead of bolted on.
 *
 * Ownership is derived from the auth context so the Push tab and index controls
 * appear only for the signed-in owner.
 */
export function RepoWorkspace({ repo, commits, username, onRefresh }: Props) {
  const { user, loading: authLoading } = useAuth();
  const isOwner = user?.username === username;
  const [tab, setTab] = useState<TabKey>("code");
  const tabInitialised = useRef(false);
  const [selectedPath, setSelectedPath] = useState<string | null>(
    firstBlobPath(repo.tree) ?? null,
  );
  const [targetLine, setTargetLine] = useState<number | null>(null);

  // Default a brand-new owner repository to the Push tab — but only once auth
  // has resolved, since `isOwner` is briefly false during token hydration.
  useEffect(() => {
    if (tabInitialised.current || authLoading) return;
    tabInitialised.current = true;
    if (isOwner && commits.length === 0) setTab("push");
  }, [authLoading, isOwner, commits.length]);

  const filePaths = useMemo(() => {
    const paths: string[] = [];
    const walk = (nodes: RepoDetail["tree"]) => {
      for (const node of nodes) {
        if (node.type === "blob") paths.push(node.path);
        else walk(node.children ?? []);
      }
    };
    walk(repo.tree);
    return paths;
  }, [repo.tree]);

  /** Open a file (optionally scrolling to a line) from a citation or search hit. */
  const openFile = (path: string, line?: number) => {
    setSelectedPath(path);
    setTargetLine(line ?? null);
    setTab("code");
    // Let the viewer mount before scrolling.
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  const onPushed = (response: PushResponse) => {
    setSelectedPath(response.files.at(-1)?.path ?? selectedPath);
    setTargetLine(null);
    // The page owns repo/commit state; ask it to refetch so the tree, commit
    // list and header reflect the new commit.
    onRefresh?.();
  };

  const tabs: { key: TabKey; label: string; icon: React.ReactNode; count?: number; hidden?: boolean }[] = [
    { key: "code", label: "Code", icon: <FolderTree className="h-3.5 w-3.5" />, count: filePaths.length },
    { key: "commits", label: "Commits", icon: <GitCommitHorizontal className="h-3.5 w-3.5" />, count: commits.length },
    { key: "ai", label: "AI assistant", icon: <Bot className="h-3.5 w-3.5" /> },
    { key: "push", label: "Push", icon: <Upload className="h-3.5 w-3.5" />, hidden: !isOwner },
    { key: "about", label: "About", icon: <Info className="h-3.5 w-3.5" /> },
  ];

  const latest = repo.latest_commit;

  return (
    <div className="space-y-4">
      {/* Repo header */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <BookOpen className="h-4 w-4 text-fg-muted" />
          <h1 className="text-lg font-semibold">
            <Link href={`/${username}`} className="text-accent hover:underline">
              {username}
            </Link>
            <span className="mx-1 text-fg-muted">/</span>
            <span>{repo.name}</span>
          </h1>
          <span
            className={cn(
              "badge",
              repo.visibility === "Private"
                ? "border-border bg-canvas text-fg-muted"
                : "border-success/40 bg-success/10 text-success",
            )}
          >
            {repo.visibility === "Private" && <Lock className="h-2.5 w-2.5" />}
            {repo.visibility}
          </span>
          {repo.indexed_at && (
            <span className="badge border-done/40 bg-done/10 text-done" title="Embedded for AI search">
              AI indexed {formatRelative(repo.indexed_at)}
            </span>
          )}
          <span className="ml-auto flex items-center gap-3 text-2xs text-fg-muted">
            <span className="inline-flex items-center gap-1">
              <Star className="h-3 w-3" /> {repo.star_count}
            </span>
            <span>{repo.commit_count} commits</span>
          </span>
        </div>

        {repo.description && <p className="text-sm text-fg-muted">{repo.description}</p>}

        {latest && (
          <div className="card flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 text-xs">
            <span className="inline-flex items-center gap-1.5 font-medium">
              {latest.author?.avatar_url && (
                <img
                  src={latest.author.avatar_url}
                  alt=""
                  width={18}
                  height={18}
                  className="h-4.5 w-4.5 rounded-full border border-border"
                  style={{ width: 18, height: 18 }}
                />
              )}
              @{latest.author?.username ?? "unknown"}
            </span>
            <Link
              href={`/${username}/${repo.name}/commit/${latest.commit_hash}`}
              className="min-w-0 flex-1 truncate hover:text-accent hover:underline"
              title={latest.message}
            >
              {latest.summary}
            </Link>
            <code className="font-mono text-fg-muted">{latest.short_hash}</code>
            <span className="text-fg-subtle">{formatRelative(latest.timestamp)}</span>
            <span className="font-mono text-2xs">
              <span className="text-success">+{latest.additions}</span>{" "}
              <span className="text-danger">-{latest.deletions}</span>
            </span>
          </div>
        )}

        {repo.primary_language && (
          <div className="flex items-center gap-2 text-2xs text-fg-muted">
            <span
              aria-hidden
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: languageColor(repo.primary_language) }}
            />
            {repo.primary_language}
          </div>
        )}
      </header>

      {/* Tabs */}
      <nav className="flex gap-1 overflow-x-auto border-b border-border" role="tablist">
        {tabs
          .filter((item) => !item.hidden)
          .map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={tab === item.key}
              onClick={() => setTab(item.key)}
              className={cn(
                "-mb-px inline-flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-xs font-medium transition",
                tab === item.key
                  ? "border-attention text-fg"
                  : "border-transparent text-fg-muted hover:border-border hover:text-fg",
              )}
            >
              {item.icon}
              {item.label}
              {item.count !== undefined && (
                <span className="rounded-full bg-canvas-subtle px-1.5 text-2xs text-fg-muted">
                  {item.count}
                </span>
              )}
            </button>
          ))}
      </nav>

      {/* Panels */}
      {tab === "code" && (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <aside className="card max-h-[70vh] overflow-auto p-2">
            <p className="px-2 py-1 text-2xs uppercase tracking-wide text-fg-subtle">
              {repo.default_branch ?? "main"}
            </p>
            {repo.tree.length === 0 ? (
              <p className="p-3 text-xs text-fg-muted">
                This repository is empty.{" "}
                {isOwner ? "Use the Push tab to add your first files." : ""}
              </p>
            ) : (
              <FileTree tree={repo.tree} selectedPath={selectedPath} onSelect={openFile} />
            )}
          </aside>

          <div className="min-w-0">
            {selectedPath ? (
              <CodeViewer
                username={username}
                repoName={repo.name}
                path={selectedPath}
                highlightLines={targetLine ? [targetLine] : []}
              />
            ) : (
              <div className="card p-10 text-center text-sm text-fg-muted">
                Select a file to view its contents.
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "commits" && (
        <CommitList commits={commits} username={username} repoName={repo.name} />
      )}

      {tab === "ai" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <AIChat repoId={repo.id} repoName={repo.name} canIndex={isOwner} onOpenFile={openFile} />
          <CodeSearch repoId={repo.id} onOpenFile={openFile} />
        </div>
      )}

      {tab === "push" && isOwner && (
        <PushPanel
          repoId={repo.id}
          repoName={repo.name}
          username={username}
          existingPaths={filePaths}
          onPushed={onPushed}
        />
      )}

      {tab === "about" && (
        <section className="card space-y-3 p-4 text-sm">
          <h2 className="font-semibold">About this repository</h2>
          <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
            <Meta label="Visibility" value={repo.visibility} />
            <Meta label="Primary language" value={repo.primary_language ?? "—"} />
            <Meta label="Commits" value={String(repo.commit_count)} />
            <Meta label="Files" value={String(repo.file_count)} />
            <Meta label="Created" value={formatRelative(repo.created_at)} />
            <Meta label="Updated" value={formatRelative(repo.updated_at)} />
            <Meta label="Default branch" value={repo.default_branch ?? "main"} />
            <Meta
              label="AI index"
              value={repo.indexed_at ? formatRelative(repo.indexed_at) : "not indexed"}
            />
          </dl>

          {repo.topics.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {repo.topics.map((topic) => (
                <span key={topic} className="chip">
                  {topic}
                </span>
              ))}
            </div>
          )}

          <div className="rounded-md border border-border bg-canvas p-3 text-xs text-fg-muted">
            <p className="mb-1 font-medium text-fg">Push from your machine</p>
            <pre className="overflow-x-auto text-2xs leading-5">
              <code>{`# using the bundled CLI
python cli/gitfolio.py push ./my-project \\
  --api http://localhost:8000/api \\
  --token $GITFOLIO_TOKEN \\
  --repo ${repo.id} \\
  --message "feat: initial import"`}</code>
            </pre>
          </div>
        </section>
      )}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-2xs uppercase tracking-wide text-fg-subtle">{label}</dt>
      <dd className="truncate text-fg">{value}</dd>
    </div>
  );
}

/** First file in the tree, so the Code tab is never empty on load. */
function firstBlobPath(nodes: RepoDetail["tree"]): string | null {
  for (const node of nodes) {
    if (node.type === "blob") return node.path;
    const nested = firstBlobPath(node.children ?? []);
    if (nested) return nested;
  }
  return null;
}
