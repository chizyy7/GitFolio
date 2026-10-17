"use client";

import { Fragment, type ReactNode } from "react";

import type { Citation } from "@/lib/types";

interface Props {
  answer: string;
  citations?: Citation[];
  onCitationClick?: (citation: Citation) => void;
}

const CODE_FENCE = /```([a-zA-Z0-9+#-]*)\n?([\s\S]*?)```/g;
const INLINE_CODE = /`([^`]+)`/g;
const BOLD = /\*\*([^*]+)\*\*/g;
const FILE_REFERENCE = /(?:^|\s)([\w./-]+\.\w{1,8}):(\d+)(?:-(\d+))?/g;

/**
 * Renders a Llama 3.2 answer.
 *
 * The model emits light Markdown, so we parse the small subset it actually
 * uses (fenced code, inline code, bold, bullet/numbered lists) and turn
 * `path/to/file.py:42` references into clickable citation pills that jump to
 * the relevant file and line.
 */
export function AnswerRenderer({ answer, citations = [], onCitationClick }: Props) {
  const citationIndex = new Map(citations.map((citation) => [citation.file_path, citation]));
  const blocks = splitIntoBlocks(answer);

  return (
    <div className="chat-prose">
      {blocks.map((block, index) =>
        block.type === "code" ? (
          <pre key={index}>
            <code>{block.content}</code>
          </pre>
        ) : (
          <Fragment key={index}>{renderText(block.content, citationIndex, onCitationClick)}</Fragment>
        ),
      )}
    </div>
  );
}

interface Block {
  type: "text" | "code";
  content: string;
  language?: string;
}

/** Split raw text into fenced-code blocks and everything else. */
function splitIntoBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  let cursor = 0;

  for (const match of text.matchAll(CODE_FENCE)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      blocks.push({ type: "text", content: text.slice(cursor, start) });
    }
    blocks.push({ type: "code", content: (match[2] ?? "").replace(/\s+$/, ""), language: match[1] });
    cursor = start + match[0].length;
  }

  if (cursor < text.length) {
    blocks.push({ type: "text", content: text.slice(cursor) });
  }
  return blocks;
}

/** Render a text block: lists, inline code, bold and file references. */
function renderText(
  text: string,
  citations: Map<string, Citation>,
  onCitationClick?: (citation: Citation) => void,
): ReactNode {
  const lines = text.split("\n");
  const nodes: ReactNode[] = [];
  let listBuffer: { ordered: boolean; items: string[] } | null = null;

  const flushList = (key: string) => {
    if (!listBuffer) return;
    const items = listBuffer.items.map((item, itemIndex) => (
      <li key={itemIndex}>{renderInline(item, citations, onCitationClick)}</li>
    ));
    nodes.push(
      listBuffer.ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>,
    );
    listBuffer = null;
  };

  lines.forEach((line, index) => {
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);

    if (bullet) {
      if (!listBuffer || listBuffer.ordered) flushList(`list-${index}`);
      listBuffer = listBuffer ?? { ordered: false, items: [] };
      listBuffer.items.push(bullet[1]);
      return;
    }
    if (numbered) {
      if (!listBuffer || !listBuffer.ordered) flushList(`list-${index}`);
      listBuffer = listBuffer ?? { ordered: true, items: [] };
      listBuffer.items.push(numbered[1]);
      return;
    }

    flushList(`list-${index}`);

    const heading = /^\s*(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const content = renderInline(heading[2], citations, onCitationClick);
      nodes.push(
        level === 1 ? (
          <h3 key={index}>{content}</h3>
        ) : level === 2 ? (
          <h4 key={index}>{content}</h4>
        ) : (
          <h5 key={index}>{content}</h5>
        ),
      );
      return;
    }

    if (line.trim() === "") {
      // Collapse runs of blank lines into a single spacer.
      if (nodes.length && index < lines.length - 1) nodes.push(<div key={index} className="h-2" />);
      return;
    }

    nodes.push(<p key={index}>{renderInline(line, citations, onCitationClick)}</p>);
  });

  flushList("list-final");
  return nodes;
}

/** Inline formatting: `code`, **bold**, `file.py:12` citation pills. */
function renderInline(
  text: string,
  citations: Map<string, Citation>,
  onCitationClick?: (citation: Citation) => void,
): ReactNode {
  const parts: ReactNode[] = [];
  let remaining = text;
  let key = 0;

  // Inline code first — it also carries most of our file references.
  INLINE_CODE.lastIndex = 0;
  let match: RegExpExecArray | null;
  let cursor = 0;

  while ((match = INLINE_CODE.exec(remaining)) !== null) {
    if ((match.index ?? 0) > cursor) {
      parts.push(
        <Fragment key={`t-${key++}`}>
          {renderEmphasis(remaining.slice(cursor, match.index), citations, onCitationClick, key)}
        </Fragment>,
      );
    }

    const inner = match[1];
    const citation = lookupCitation(inner, citations);
    if (citation && onCitationClick) {
      parts.push(
        <button
          key={`c-${key++}`}
          type="button"
          onClick={() => onCitationClick(citation)}
          className="citation-pill"
          title={`Jump to ${citation.file_path}:${citation.start_line}`}
        >
          {inner}
        </button>,
      );
    } else {
      parts.push(<code key={`i-${key++}`}>{inner}</code>);
    }

    cursor = (match.index ?? 0) + match[0].length;
  }

  if (cursor < remaining.length) {
    parts.push(
      <Fragment key={`t-${key++}`}>
        {renderEmphasis(remaining.slice(cursor), citations, onCitationClick, key)}
      </Fragment>,
    );
  }

  return parts.length ? parts : text;
}

/** Bold + bare file references (outside backticks). */
function renderEmphasis(
  text: string,
  citations: Map<string, Citation>,
  onCitationClick?: (citation: Citation) => void,
  keyBase = 0,
): ReactNode {
  // Bold
  const boldParts: ReactNode[] = [];
  BOLD.lastIndex = 0;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = BOLD.exec(text)) !== null) {
    if ((match.index ?? 0) > cursor) {
      boldParts.push(linkify(text.slice(cursor, match.index), citations, onCitationClick, keyBase));
    }
    boldParts.push(<strong key={`b-${keyBase}-${match.index}`}>{match[1]}</strong>);
    cursor = (match.index ?? 0) + match[0].length;
  }
  if (cursor < text.length) {
    boldParts.push(linkify(text.slice(cursor), citations, onCitationClick, keyBase));
  }

  return boldParts.length ? boldParts : text;
}

/** Turn bare `file.py:12` references into pills. */
function linkify(
  text: string,
  citations: Map<string, Citation>,
  onCitationClick?: (citation: Citation) => void,
  keyBase = 0,
): ReactNode {
  if (!onCitationClick) return text;

  FILE_REFERENCE.lastIndex = 0;
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = FILE_REFERENCE.exec(text)) !== null) {
    const reference = `${match[1]}:${match[2]}`;
    const citation = lookupCitation(reference, citations);
    if (!citation) continue;

    // Jump to the exact line the model cited, not just the chunk's start.
    const line = Number(match[2]);
    const endLine = match[3] ? Number(match[3]) : line;
    const target: Citation =
      Number.isFinite(line) && line > 0 ? { ...citation, start_line: line, end_line: endLine } : citation;

    const start = match.index + (match[0].startsWith(" ") ? 1 : 0);
    if (start > cursor) nodes.push(text.slice(cursor, start));
    nodes.push(
      <button
        key={`ref-${keyBase}-${index++}`}
        type="button"
        onClick={() => onCitationClick(target)}
        className="citation-pill"
      >
        {reference}
      </button>,
    );
    cursor = start + reference.length;
  }

  if (!nodes.length) return text;
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

/** Match a `file.py:12` reference against the retrieved citations. */
function lookupCitation(reference: string, citations: Map<string, Citation>): Citation | undefined {
  const path = reference.slice(0, reference.lastIndexOf(":"));
  if (!path) return undefined;

  const direct = citations.get(path);
  if (direct) return direct;

  // Fall back to a suffix match (the model may shorten the path).
  for (const [filePath, citation] of citations) {
    if (filePath.endsWith(path) || path.endsWith(filePath)) {
      return citation;
    }
  }
  return undefined;
}
