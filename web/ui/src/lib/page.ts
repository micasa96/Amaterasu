// Server data handed from Jinja to Svelte. Each template renders
//   <script type="application/json" id="page-data">{{ data|tojson }}</script>
// and main.ts passes the parsed object to the page as its `data` prop.
export function readPageData<T = Record<string, unknown>>(): T {
  const node = document.getElementById("page-data");
  if (!node?.textContent) return {} as T;
  try {
    return JSON.parse(node.textContent) as T;
  } catch {
    return {} as T;
  }
}

/** Current query parameters (signed links carry user_id/token/gid). */
export function query(name: string): string {
  return new URLSearchParams(location.search).get(name) ?? "";
}
