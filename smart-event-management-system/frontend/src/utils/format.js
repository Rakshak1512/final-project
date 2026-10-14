export function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

const rawApiUrl = import.meta.env.VITE_API_URL || "";
const backendBase = rawApiUrl ? rawApiUrl.replace(/\/api\/?$/, "").replace(/\/+$/, "") : "";

export function fileUrl(path) {
  if (!path) return null;
  const str = String(path).trim();
  if (!str) return null;

  // 1. Fully-qualified or data URL - NEVER prepend backend URL
  if (
    str.startsWith("http://") ||
    str.startsWith("https://") ||
    str.startsWith("data:") ||
    str.startsWith("blob:")
  ) {
    return str;
  }

  // 2. Normalize slashes
  const normalized = str.replace(/\\/g, "/").replace(/\/+/g, "/");

  // 3. Handle Firebase Storage gs:// URIs
  if (normalized.startsWith("gs://")) {
    const afterBucket = normalized.replace(/^gs:\/\/[^/]+\//, "");
    const cleanRel = afterBucket.replace(/^\/?(uploads\/)+/, "");
    return `/api/uploads/${cleanRel}`;
  }

  // 4. Handle paths that already start with /api/ or api/
  if (normalized.startsWith("/api/") || normalized.startsWith("api/")) {
    const cleanApi = normalized.startsWith("/") ? normalized : `/${normalized}`;
    return cleanApi;
  }

  // 5. Clean leading slashes and uploads/ prefix
  const cleanPath = normalized.replace(/^\/?(uploads\/)+/, "").replace(/^\/+/, "");
  if (!cleanPath) return null;

  // Route through /api/uploads/ which is handled by Vite proxy in dev and server rewrites in prod
  return `/api/uploads/${cleanPath}`;
}


export function initials(name = "") {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export function statusBadgeClass(status) {
  switch (status) {
    case "approved":
    case "completed":
      return "badge badge-success";
    case "cancelled":
    case "rejected":
      return "badge badge-danger";
    case "pending":
      return "badge badge-warning";
    default:
      return "badge badge-info";
  }
}
