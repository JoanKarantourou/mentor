"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api/health";
import type { HealthStatus } from "@/lib/api/types";

type HealthState = "ok" | "degraded" | "unreachable";

export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [state, setState] = useState<HealthState>("ok");

  function check() {
    getHealth()
      .then((h) => {
        setHealth(h);
        const ok =
          h.status === "ok" &&
          h.database === "ok";
        setState(ok ? "ok" : "degraded");
      })
      .catch(() => {
        setState("unreachable");
        setHealth(null);
      });
  }

  useEffect(() => {
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { health, state };
}
