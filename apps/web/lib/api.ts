import product from "../../../packages/contracts/product.json";

export const PRODUCT = product;

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "Request failed");
    this.status = status;
    this.detail = detail;
  }
}

function readCsrf() {
  if (typeof window === "undefined") return "";
  const match = document.cookie.match(/(?:^|; )cnip_csrf=([^;]*)/);
  return (match ? decodeURIComponent(match[1]) : "") || sessionStorage.getItem("cnip_csrf") || "";
}

export function persistCsrf(token?: string) {
  if (token && typeof sessionStorage !== "undefined") sessionStorage.setItem("cnip_csrf", token);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const csrf = readCsrf();
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && !path.startsWith("/auth/")) {
    if (!path.startsWith("/auth/refresh")) {
      try {
        const refreshed = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" });
        if (refreshed.ok) {
          const body = await refreshed.json();
          persistCsrf(body.csrf_token);
          return api<T>(path, init);
        }
      } catch {
        /* fall through */
      }
    }
    if (typeof window !== "undefined") window.location.href = "/login";
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail ?? body.message ?? response.statusText);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
