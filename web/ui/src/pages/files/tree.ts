// File-tree model for the selector. The tree is the exact JSON the server
// sends (web/nodes.py create_list) and the exact JSON posted back for
// mode=selection: folders {id, name, type:"folder", children} and files
// {id, name, type:"file", size, selected, progress}. The server only reads
// files' `selected`; folders carry `selected` as the old page did.

export interface FileNode {
  id: string | number;
  name: string;
  type: "file" | "folder";
  size?: number;
  selected?: boolean;
  progress?: number;
  children?: FileNode[];
}

export type SortBy = "name" | "size";

export function formatSize(size: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = size || 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(2)} ${units[i]}`;
}

export function folderSize(folder: FileNode): number {
  let total = 0;
  const queue = [folder];
  while (queue.length) {
    const node = queue.pop()!;
    if (node.type === "file") total += node.size ?? 0;
    else if (node.children) queue.push(...node.children);
  }
  return total;
}

export function nodeSize(node: FileNode): number {
  return node.type === "folder" ? folderSize(node) : (node.size ?? 0);
}

export function allSelected(folder: FileNode): boolean {
  return (folder.children ?? []).every((c) =>
    c.type === "folder" ? allSelected(c) : !!c.selected,
  );
}

export function someSelected(folder: FileNode): boolean {
  return (folder.children ?? []).some((c) =>
    c.type === "folder" ? someSelected(c) : !!c.selected,
  );
}

export function isChecked(node: FileNode): boolean {
  return node.type === "folder" ? allSelected(node) : !!node.selected;
}

export function isMixed(node: FileNode): boolean {
  return node.type === "folder" && !allSelected(node) && someSelected(node);
}

/** Folders first, then by name (case-insensitive) or size. */
export function sortNodes(nodes: FileNode[], by: SortBy, asc: boolean): FileNode[] {
  const values = new Map<FileNode, string | number>();
  for (const node of nodes) {
    values.set(node, by === "name" ? node.name.toLowerCase() : nodeSize(node));
  }
  return [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    const av = values.get(a)!;
    const bv = values.get(b)!;
    if (av < bv) return asc ? -1 : 1;
    if (av > bv) return asc ? 1 : -1;
    return 0;
  });
}

export function setFolder(folder: FileNode, value: boolean) {
  const queue = [folder];
  while (queue.length) {
    const node = queue.pop()!;
    node.selected = value;
    if (node.children) queue.push(...node.children);
  }
}

export function setNode(node: FileNode, value: boolean) {
  if (node.type === "folder") setFolder(node, value);
  else node.selected = value;
}

export function invert(node: FileNode) {
  node.selected = !node.selected;
  if (node.type === "folder") node.children?.forEach(invert);
}

/** Keep each folder's `selected` equal to "every file inside is selected". */
export function syncFolders(nodes: FileNode[]) {
  for (const node of nodes) {
    if (node.type === "folder") {
      syncFolders(node.children ?? []);
      node.selected = allSelected(node);
    }
  }
}

export function stats(nodes: FileNode[]) {
  let selectedCount = 0;
  let totalCount = 0;
  let selectedSize = 0;
  let totalSize = 0;
  const queue = [...nodes];
  while (queue.length) {
    const node = queue.pop()!;
    if (node.type === "file") {
      totalCount++;
      totalSize += node.size ?? 0;
      if (node.selected) {
        selectedCount++;
        selectedSize += node.size ?? 0;
      }
    }
    if (node.children) queue.push(...node.children);
  }
  return { selectedCount, totalCount, selectedSize, totalSize };
}
