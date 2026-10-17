import { cn } from "@/lib/utils";

interface Props {
  diff: string | null;
  className?: string;
}

interface ParsedLine {
  kind: "add" | "del" | "hunk" | "meta" | "context";
  text: string;
}

/**
 * Unified-diff renderer.
 *
 * Classifies every line of a `git diff`-style payload and maps it onto the
 * `.diff-line-*` classes in `globals.css`, giving GitHub's green/red gutter
 * look without any third-party diff viewer.
 */
export function CommitDiff({ diff, className }: Props) {
  if (!diff || !diff.trim()) {
    return (
      <div className="card p-6 text-center text-sm text-fg-muted">
        No diff recorded for this commit.
      </div>
    );
  }

  const files = splitDiff(diff);

  return (
    <div className={cn("space-y-4", className)}>
      {files.map((file) => (
        <section key={file.path} className="card overflow-hidden">
          <header className="card-header bg-canvas">
            <code className="truncate text-xs">{file.path}</code>
            <div className="flex shrink-0 items-center gap-2 font-mono text-2xs">
              <span className="text-success">+{file.additions}</span>
              <span className="text-danger">-{file.deletions}</span>
            </div>
          </header>

          <div className="max-h-[60vh] overflow-auto bg-canvas-inset py-2">
            {file.lines.map((line, index) => (
              <span
                key={`${file.path}-${index}`}
                className={cn(
                  "diff-line",
                  line.kind === "add" && "diff-line-add",
                  line.kind === "del" && "diff-line-del",
                  line.kind === "hunk" && "diff-line-hunk",
                  line.kind === "meta" && "diff-line-meta",
                )}
              >
                {line.text || " "}
              </span>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

interface ParsedFile {
  path: string;
  additions: number;
  deletions: number;
  lines: ParsedLine[];
}

/** Split a concatenated unified diff into per-file sections with stats. */
export function splitDiff(diff: string): ParsedFile[] {
  const files: ParsedFile[] = [];
  let current: ParsedFile | null = null;

  for (const rawLine of diff.split("\n")) {
    if (rawLine.startsWith("diff --git ")) {
      const match = /diff --git a\/(.*?) b\/(.*)$/.exec(rawLine);
      current = {
        path: match?.[2] ?? rawLine.replace("diff --git ", ""),
        additions: 0,
        deletions: 0,
        lines: [],
      };
      files.push(current);
      continue;
    }

    // Skip the plumbing headers; the file header already shows the path.
    if (
      rawLine.startsWith("index ") ||
      rawLine.startsWith("--- ") ||
      rawLine.startsWith("+++ ") ||
      rawLine.startsWith("new file mode") ||
      rawLine.startsWith("deleted file mode") ||
      rawLine.startsWith("similarity index") ||
      rawLine.startsWith("rename from") ||
      rawLine.startsWith("rename to")
    ) {
      continue;
    }

    if (!current) {
      current = { path: "diff", additions: 0, deletions: 0, lines: [] };
      files.push(current);
    }

    let kind: ParsedLine["kind"] = "context";
    if (rawLine.startsWith("@@")) kind = "hunk";
    else if (rawLine.startsWith("+")) {
      kind = "add";
      current.additions += 1;
    } else if (rawLine.startsWith("-")) {
      kind = "del";
      current.deletions += 1;
    } else if (rawLine.startsWith("\\")) kind = "meta";

    current.lines.push({ kind, text: rawLine });
  }

  return files;
}

/** Count added/removed lines in a diff (used by headers). */
export function diffStats(diff: string | null): { additions: number; deletions: number } {
  if (!diff) return { additions: 0, deletions: 0 };
  let additions = 0;
  let deletions = 0;
  for (const line of diff.split("\n")) {
    if (line.startsWith("+") && !line.startsWith("+++")) additions += 1;
    else if (line.startsWith("-") && !line.startsWith("---")) deletions += 1;
  }
  return { additions, deletions };
}
