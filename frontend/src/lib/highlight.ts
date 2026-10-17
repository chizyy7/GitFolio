/**
 * Server-side syntax highlighting with Shiki.
 *
 * Highlighting happens on the Next server (see `app/api/highlight/route.ts`)
 * so the browser never downloads grammars — the client just receives HTML.
 * The highlighter instance is cached across requests.
 */

import { createHighlighter, type Highlighter } from "shiki";

const THEME = "github-dark-default";
const LIGHT_THEME = "github-light-default";

let highlighterPromise: Promise<Highlighter> | null = null;

/** Grammars we ship; anything else falls back to `text`. */
const ALLOWED_LANGUAGES = [
  "text",
  "python",
  "typescript",
  "tsx",
  "javascript",
  "jsx",
  "json",
  "yaml",
  "toml",
  "html",
  "css",
  "scss",
  "markdown",
  "sql",
  "bash",
  "docker",
  "ini",
  "xml",
  "go",
  "rust",
  "java",
  "c",
  "cpp",
  "csharp",
  "php",
  "ruby",
  "kotlin",
  "swift",
  "r",
  "lua",
  "diff",
  "graphql",
  "powershell",
] as const;

function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: [THEME, LIGHT_THEME],
      langs: [...ALLOWED_LANGUAGES],
    });
  }
  return highlighterPromise;
}

export interface HighlightOptions {
  code: string;
  language?: string | null;
  /** Render line numbers in a `<span class="line-number">` gutter. */
  lineNumbers?: boolean;
  /** Highlight specific 1-based lines (e.g. AI review comments). */
  highlightLines?: number[];
  maxChars?: number;
}

const DEFAULT_MAX_CHARS = 120_000;

/**
 * Return highlighted HTML for `code`, or `null` when the file is too large and
 * the caller should render plain text instead.
 */
export async function highlightCode(options: HighlightOptions): Promise<string | null> {
  const { code, language, highlightLines = [], maxChars = DEFAULT_MAX_CHARS } = options;

  if (code.length > maxChars) return null;

  const highlighter = await getHighlighter();
  const lang = (ALLOWED_LANGUAGES as readonly string[]).includes(language ?? "")
    ? (language as string)
    : "text";

  const html = highlighter.codeToHtml(code, {
    lang,
    theme: THEME,
    transformers: [
      {
        // Attach stable line ids so the client can anchor to `#L42`.
        line(node, line) {
          node.properties["id"] = `L${line}`;
          node.properties["data-line"] = String(line);
          if (highlightLines.includes(line)) {
            node.properties["class"] = `${node.properties["class"] ?? ""} highlighted-line`;
          }
        },
        pre(node) {
          node.properties["class"] = `${node.properties["class"] ?? ""} shiki-pre`;
        },
      },
    ],
  });

  return html;
}

/** Languages exposed to the client picker in the code viewer. */
export const SUPPORTED_LANGUAGES = ALLOWED_LANGUAGES;
