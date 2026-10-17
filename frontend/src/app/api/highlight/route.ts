import { NextResponse } from "next/server";

import { highlightCode } from "@/lib/highlight";

/**
 * Server-side syntax highlighting endpoint.
 *
 * `POST /api/highlight  { code, language, highlightLines? } -> { html }`
 *
 * Keeping Shiki on the server means the browser never downloads the grammars
 * and themes — a large win for a code-heavy UI.
 */
export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const body = payload as {
    code?: unknown;
    language?: unknown;
    highlightLines?: unknown;
  };

  if (typeof body.code !== "string") {
    return NextResponse.json({ error: "'code' must be a string." }, { status: 422 });
  }

  const language = typeof body.language === "string" ? body.language : "text";
  const highlightLines = Array.isArray(body.highlightLines)
    ? body.highlightLines.filter((line): line is number => typeof line === "number")
    : [];

  try {
    const html = await highlightCode({ code: body.code, language, highlightLines });
    if (html === null) {
      // File too large — the client falls back to a plain <pre>.
      return NextResponse.json({ html: null, reason: "too-large" });
    }
    return NextResponse.json(
      { html },
      { headers: { "Cache-Control": "public, max-age=60, s-maxage=300" } },
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Highlighting failed." },
      { status: 500 },
    );
  }
}
