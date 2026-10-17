"use client";

import { useMemo, useState } from "react";
import { ChevronRight, File as FileIcon, FileCode2, Folder, FolderOpen } from "lucide-react";

import type { FileNode } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";

interface Props {
  tree: FileNode[];
  selectedPath?: string | null;
  onSelect: (path: string) => void;
}

/**
 * Collapsible repository file tree.
 *
 * Directories start expanded at the top level so the first screen is useful
 * without any interaction.
 */
export function FileTree({ tree, selectedPath, onSelect }: Props) {
  return (
    <nav aria-label="Repository files" className="text-sm">
      <ul className="space-y-0.5">
        {tree.map((node) => (
          <TreeRow
            key={node.path}
            node={node}
            depth={0}
            selectedPath={selectedPath ?? null}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </nav>
  );
}

function TreeRow({
  node,
  depth,
  selectedPath,
  onSelect,
}: {
  node: FileNode;
  depth: number;
  selectedPath: string | null;
  onSelect: (path: string) => void;
}) {
  const [open, setOpen] = useState(depth < 1);
  const isDirectory = node.type === "tree";
  const isSelected = !isDirectory && node.path === selectedPath;

  const padding = { paddingLeft: `${depth * 12 + 8}px` };

  if (isDirectory) {
    const children = node.children ?? [];
    return (
      <li>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          style={padding}
          className="flex w-full items-center gap-1.5 rounded-md py-1 pr-2 text-left text-fg-muted transition hover:bg-canvas-subtle hover:text-fg"
          aria-expanded={open}
        >
          <ChevronRight
            className={cn("h-3.5 w-3.5 shrink-0 transition-transform", open && "rotate-90")}
          />
          {open ? (
            <FolderOpen className="h-3.5 w-3.5 shrink-0 text-accent" />
          ) : (
            <Folder className="h-3.5 w-3.5 shrink-0 text-accent" />
          )}
          <span className="truncate">{node.name}</span>
          <span className="ml-auto shrink-0 text-2xs text-fg-subtle">{children.length}</span>
        </button>

        {open && children.length > 0 && (
          <ul className="space-y-0.5">
            {children.map((child) => (
              <TreeRow
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedPath={selectedPath}
                onSelect={onSelect}
              />
            ))}
          </ul>
        )}
      </li>
    );
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(node.path)}
        style={padding}
        title={node.path}
        className={cn(
          "flex w-full items-center gap-1.5 rounded-md py-1 pr-2 text-left transition",
          isSelected
            ? "bg-accent/15 text-accent"
            : "text-fg hover:bg-canvas-subtle",
        )}
      >
        <span className="w-3.5 shrink-0" />
        {node.language && node.language !== "Text" ? (
          <FileCode2 className="h-3.5 w-3.5 shrink-0 text-fg-subtle" />
        ) : (
          <FileIcon className="h-3.5 w-3.5 shrink-0 text-fg-subtle" />
        )}
        <span className="truncate">{node.name}</span>
        {node.size !== null && (
          <span className="ml-auto shrink-0 text-2xs text-fg-subtle">{formatBytes(node.size)}</span>
        )}
      </button>
    </li>
  );
}

/** Total file count in a tree (used in the repo header). */
export function countFiles(nodes: FileNode[]): number {
  return nodes.reduce(
    (total, node) => total + (node.type === "blob" ? 1 : countFiles(node.children ?? [])),
    0,
  );
}

/** Flatten a tree into blob paths (used by the search panel). */
export function useFilePaths(tree: FileNode[]): string[] {
  return useMemo(() => {
    const paths: string[] = [];
    const walk = (nodes: FileNode[]) => {
      for (const node of nodes) {
        if (node.type === "blob") paths.push(node.path);
        else walk(node.children ?? []);
      }
    };
    walk(tree);
    return paths;
  }, [tree]);
}
