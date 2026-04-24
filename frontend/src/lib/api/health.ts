import { apiFetch } from "./client";
import type { HealthStatus } from "./types";

export function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health");
}
