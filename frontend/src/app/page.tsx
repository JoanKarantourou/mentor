"use client";

import { useEffect, useState } from "react";

type HealthStatus = {
  status: string;
  database: string;
  llm_provider: string;
  embedding_provider: string;
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export default function Home() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<HealthStatus>;
      })
      .then(setHealth)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Unknown error")
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold mb-2">mentor</h1>
        <p className="text-gray-400 mb-8 text-sm">Internal RAG assistant</p>

        <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-4">
            Backend health
          </h2>

          {loading && (
            <p className="text-gray-400 text-sm">Checking backend…</p>
          )}

          {error && (
            <div className="rounded bg-red-950 border border-red-800 px-4 py-3 text-sm text-red-300">
              Could not reach backend: {error}
            </div>
          )}

          {health && (
            <dl className="space-y-3 text-sm">
              <Row label="status" value={health.status} ok={health.status === "ok"} />
              <Row label="database" value={health.database} ok={health.database === "ok"} />
              <Row label="llm_provider" value={health.llm_provider} />
              <Row label="embedding_provider" value={health.embedding_provider} />
            </dl>
          )}
        </div>

        <p className="mt-4 text-xs text-gray-600 text-center">
          {BACKEND_URL}
        </p>
      </div>
    </main>
  );
}

function Row({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok?: boolean;
}) {
  const dot =
    ok === undefined
      ? "bg-gray-500"
      : ok
        ? "bg-green-500"
        : "bg-red-500";

  return (
    <div className="flex items-center justify-between">
      <dt className="text-gray-400">{label}</dt>
      <dd className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        <span className="font-mono">{value}</span>
      </dd>
    </div>
  );
}
