"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Copy, Download, FileWarning, Loader2 } from "lucide-react";

import { ApiError, reposApi } from "@/lib/api";
import type { FileContent } from "@/lib/types";
import { cn, formatBytes, toShikiLang } from "@/lib/utils";

interface Props {
  username: string;
  repoName: string;
  path: string;
  ref?: string | null;
  /** 1-based lines to highlight (used by AI review comments). */
  highlightLines?: number[];
}

/**
 * Source-code viewer.
 *
 * Fetches the file from the API, asks the Next server to highlight it with
 * Shiki (`POST /api/highlight`) and renders the resulting HTML. Very large
 * files fall back to a plain `<pre>` so the page never hangs.
 */
export function CodeViewer({ username, repoName, path, ref, highlightLines = [] }: Props) {
  const [file, setFile] = useState<FileContent | null>(null);
  const [html, setHtml] = useState<string | null>(null);
  const [plainFallback, setPlainFallback] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // ------------------------------------------------------------- fetch file
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setHtml(null);
    setPlainFallback(false);

    (async () => {
      try {
        const content = await reposApi.file(username, repoName, path, ref ?? null);
        if (cancelled) return;
        setFile(content);

        if (content.is_binary) {
          setPlainFallback(true);
          return;
        }

        const response = await fetch("/api/highlight", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            code: content.content,
            language: toShikiLang(content.language),
            highlightLines,
          }),
        });
        const payload = (await response.json()) as { html: string | null };
        if (cancelled) return;
        if (!payload.html) setPlainFallback(true);
        else setHtml(payload.html);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : "Could not load this file.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // `highlightLines` is compared by content to avoid re-fetch loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username, repoName, path, ref, highlightLines.join(",")]);

  // ------------------------------------------------------------ scroll to line
  useEffect(() => {
    if (!html || highlightLines.length === 0) return;
    const target = document.getElementById(`L${highlightLines[0]}`);
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [html, highlightLines]);

  const copy = useCallback(async () => {
    if (!file) return;
    await navigator.clipboard.writeText(file.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }, [file]);

  const download = useCallback(() => {
    if (!file) return;
    const blob = new Blob([file.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = path.split("/").pop() ?? "file.txt";
    anchor.click();
    URL.revokeObjectURL(url);
  }, [file, path]);

  // ------------------------------------------------------------------ render
  if (loading) {
    return (
      <div className="card overflow-hidden">
        <div className="card-header">
          <div className="h-3.5 w-40 skeleton" />
          <div className="h-3 w-20 skeleton" />
        </div>
        <div className="space-y-2 p-4">
          {Array.from({ length: 12 }).map((_, index) => (
            <div
              key={index}
              className="h-3 skeleton"
              style={{ width: `${35 + ((index * 13) % 55)}%` }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card flex items-center gap-2 p-4 text-sm text-danger">
        <AlertTriangle className="h-4 w-4" /> {error}
      </div>
    );
  }

  if (!file) return null;

  return (
    <div className="card overflow-hidden">
      <header className="card-header">
        <div className="flex min-w-0 items-center gap-2">
          <FileWarning className="hidden h-4 w-4 shrink-0 text-fg-subtle sm:block" />
          <code className="truncate text-xs text-fg" title={path}>
            {path}
          </code>
          {file.language && (
            <span className="badge shrink-0 border-border bg-canvas text-fg-muted">
              {file.language}
            </span>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2 text-2xs text-fg-muted">
          <span>{formatBytes(file.size_bytes)}</span>
          <span aria-hidden>·</span>
          <span>{file.line_count} lines</span>
          {file.blob_hash && (
            <span className="hidden font-mono sm:inline" title={`Git blob ${file.blob_hash}`}>
              {file.blob_hash.slice(0, 7)}
            </span>
          )}
          <button type="button" onClick={copy} className="btn btn-ghost h-6 !px-1.5" title="Copy contents">
            {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
          </button>
          <button
            type="button"
            onClick={download}
            className="btn btn-ghost h-6 !px-1.5"
            title="Download file"
          >
            <Download className="h-3 w-3" />
          </button>
        </div>
      </header>

      {file.is_binary ? (
        <div className="flex flex-col items-center gap-2 p-10 text-center text-sm text-fg-muted">
          <FileWarning className="h-6 w-6" />
          This is a binary file and cannot be displayed.
        </div>
      ) : plainFallback ? (
        <pre className="max-h-[70vh] overflow-auto bg-canvas-inset p-4 text-xs leading-6">
          <code>{file.content}</code>
        </pre>
      ) : (
        <div
          className={cn("max-h-[70vh] overflow-auto bg-canvas-inset")}
          // Shiki output is generated on our own server from a fixed palette;
          // it is not user-controlled HTML.
          dangerouslySetInnerHTML={{ __html: html ?? "" }}
        />
      )}
    </div>
  );
}

/** Inline spinner used by panels that load data on demand. */
export function InlineLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-fg-muted">
      <Loader2 className="h-3.5 w-3.5 animate-spin" /> {label}
    </span>
  );
}
