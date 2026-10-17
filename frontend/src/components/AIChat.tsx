"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Database,
  Send,
  Sparkles,
  Trash2,
  User as UserIcon,
} from "lucide-react";

import { ApiError, aiApi } from "@/lib/api";
import type { ChatTurn, Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

import { AnswerRenderer } from "@/components/AnswerRenderer";

interface Props {
  repoId: string;
  repoName: string;
  /** Whether the current user may (re)build the index. */
  canIndex?: boolean;
  onOpenFile?: (path: string, line?: number) => void;
}

const SUGGESTIONS = [
  "How does authentication work in this repository?",
  "Explain the main entry point and the request flow.",
  "What does the data model look like, and how do the tables relate?",
  "Where is error handling implemented, and is it consistent?",
  "Summarise how the AI pipeline ingests code.",
];

/**
 * AI Repo Explainer — the RAG chat panel.
 *
 * Sends the question to `POST /api/ai/chat`, which embeds it, retrieves the
 * top-K code chunks from ChromaDB and asks Llama 3.2 to explain them with
 * citations. Citation pills jump straight to the file and line.
 */
export function AIChat({ repoId, repoName, canIndex = false, onOpenFile }: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [needsIndex, setNeedsIndex] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Keep the transcript pinned to the newest message.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, pending]);

  const history = useMemo(
    () => turns.filter((turn) => !turn.error).map(({ role, content }) => ({ role, content })),
    [turns],
  );

  const ask = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || pending) return;

    setTurns((current) => [...current, { role: "user", content: trimmed }]);
    setInput("");
    setPending(true);
    setStatus(null);
    setNeedsIndex(false);

    try {
      const response = await aiApi.chat({
        repo_id: repoId,
        question: trimmed,
        top_k: 5,
        history: history.slice(-6) as ChatTurn[],
      });

      setTurns((current) => [
        ...current,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          elapsedMs: response.elapsed_ms,
        },
      ]);
      setStatus(
        `${response.citations.length} snippet${response.citations.length === 1 ? "" : "s"} retrieved · ${
          response.model
        } · ${(response.elapsed_ms / 1000).toFixed(1)}s${response.cached ? " · cached" : ""}`,
      );
    } catch (error) {
      const apiError = error instanceof ApiError ? error : null;
      const notIndexed =
        apiError?.status === 409 || (apiError?.detail ?? "").toLowerCase().includes("not been indexed");

      setNeedsIndex(notIndexed);
      setTurns((current) => [
        ...current,
        {
          role: "assistant",
          content: notIndexed
            ? "This repository has not been indexed for AI search yet. Build the vector index and try again — the button is below the transcript."
            : `I could not reach the AI backend.\n\n**${apiError?.detail ?? "Unknown error"}**\n\nMake sure Ollama is running (\`ollama serve\`) with \`llama3.2\` and \`nomic-embed-text\` pulled, and that ChromaDB is up.`,
          error: true,
        },
      ]);
    } finally {
      setPending(false);
    }
  };

  const buildIndex = async () => {
    setIndexing(true);
    setStatus("Indexing repository — embedding code chunks…");
    try {
      const result = await aiApi.index(repoId, { sync: true, force: true });
      setNeedsIndex(false);
      setStatus(
        `Indexed ${result.indexed_chunks} chunks from ${result.indexed_files} files in ${(
          result.elapsed_ms / 1000
        ).toFixed(1)}s.`,
      );
    } catch (error) {
      setStatus(error instanceof ApiError ? error.detail : "Indexing failed.");
    } finally {
      setIndexing(false);
    }
  };

  const openCitation = (citation: Citation) => onOpenFile?.(citation.file_path, citation.start_line);

  return (
    <section className="card flex h-[640px] flex-col overflow-hidden" aria-label="AI repository explainer">
      <header className="card-header shrink-0">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <Sparkles className="h-3.5 w-3.5 text-done" /> Ask about {repoName}
        </h2>
        <div className="flex items-center gap-2">
          {turns.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setTurns([]);
                setStatus(null);
              }}
              className="btn btn-ghost h-6 !px-1.5 text-2xs"
              title="Clear conversation"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          )}
          <span className="hidden items-center gap-1 text-2xs text-fg-muted sm:inline-flex">
            <Database className="h-3 w-3" /> RAG · llama3.2
          </span>
        </div>
      </header>

      {/* Transcript */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {turns.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <span className="grid h-12 w-12 place-items-center rounded-full border border-done/40 bg-done/10 text-done">
              <Bot className="h-6 w-6" />
            </span>
            <div>
              <p className="text-sm font-medium">Ask your codebase a question</p>
              <p className="mx-auto mt-1 max-w-sm text-xs text-fg-muted">
                Llama 3.2 reads the most relevant functions and classes from this repository
                and explains them, citing files and line numbers.
              </p>
            </div>
            <div className="flex w-full max-w-lg flex-col gap-1.5">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => ask(suggestion)}
                  className="rounded-md border border-border bg-canvas px-3 py-2 text-left text-xs text-fg-muted transition hover:border-accent/50 hover:text-fg"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          turns.map((turn, index) => (
            <article
              key={index}
              className={cn(
                "flex gap-3",
                turn.role === "user" ? "flex-row-reverse" : "flex-row",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border",
                  turn.role === "user"
                    ? "border-border bg-canvas text-fg-muted"
                    : "border-done/40 bg-done/10 text-done",
                )}
              >
                {turn.role === "user" ? <UserIcon className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
              </span>

              <div
                className={cn(
                  "min-w-0 max-w-[88%] rounded-lg border px-3.5 py-2.5",
                  turn.role === "user"
                    ? "border-accent/30 bg-accent/10"
                    : turn.error
                      ? "border-danger/40 bg-danger/5"
                      : "border-border bg-canvas",
                )}
              >
                {turn.role === "assistant" ? (
                  <AnswerRenderer
                    answer={turn.content}
                    citations={turn.citations}
                    onCitationClick={openCitation}
                  />
                ) : (
                  <p className="whitespace-pre-wrap text-sm">{turn.content}</p>
                )}

                {turn.citations && turn.citations.length > 0 && (
                  <details className="mt-3 border-t border-border pt-2">
                    <summary className="cursor-pointer list-none text-2xs text-fg-muted hover:text-fg">
                      {turn.citations.length} source snippet{turn.citations.length === 1 ? "" : "s"}
                    </summary>
                    <ul className="mt-2 space-y-1">
                      {turn.citations.map((citation, citationIndex) => (
                        <li key={citationIndex}>
                          <button
                            type="button"
                            onClick={() => openCitation(citation)}
                            className="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left text-2xs hover:bg-canvas-subtle"
                          >
                            <span className="font-mono text-accent">
                              {citation.file_path}:{citation.start_line}
                            </span>
                            {citation.symbol && <span className="text-fg-muted">{citation.symbol}()</span>}
                            <span className="ml-auto shrink-0 font-mono text-fg-subtle">
                              {(citation.score * 100).toFixed(0)}%
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            </article>
          ))
        )}

        {pending && (
          <div className="flex items-center gap-2 text-xs text-fg-muted">
            <span className="grid h-7 w-7 place-items-center rounded-full border border-done/40 bg-done/10 text-done">
              <Bot className="h-3.5 w-3.5" />
            </span>
            <span className="flex items-center gap-1">
              Reading your code
              <span className="typing-dot">.</span>
              <span className="typing-dot">.</span>
              <span className="typing-dot">.</span>
            </span>
          </div>
        )}

        {needsIndex && canIndex && (
          <button
            type="button"
            onClick={buildIndex}
            disabled={indexing}
            className="btn btn-primary w-full text-xs"
          >
            {indexing ? "Indexing…" : "Build the vector index for this repository"}
          </button>
        )}
      </div>

      {/* Composer */}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          ask(input);
        }}
        className="shrink-0 border-t border-border p-3"
      >
        {status && (
          <p className="mb-2 flex items-center gap-1.5 text-2xs text-fg-muted">
            <AlertTriangle className="h-3 w-3 shrink-0" /> {status}
          </p>
        )}
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                ask(input);
              }
            }}
            rows={2}
            placeholder={`Ask about ${repoName}…  (Enter to send, Shift+Enter for a newline)`}
            className="input max-h-32 min-h-[42px] resize-y"
            disabled={pending}
          />
          <button
            type="submit"
            disabled={pending || !input.trim()}
            className="btn btn-primary h-[42px] w-[42px] shrink-0 !px-0"
            aria-label="Send question"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </section>
  );
}
