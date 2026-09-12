import { useCallback, useEffect, useState } from "react";

import { loadConsole } from "../api/client";
import type { ConsoleData } from "../types";

type LoadingStage = "quiet" | "connecting" | "skeleton";

export function useConsoleData() {
  const [data, setData] = useState<ConsoleData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [stage, setStage] = useState<LoadingStage>("quiet");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    setStage("quiet");
    const indicator = window.setTimeout(() => setStage("connecting"), 700);
    const skeleton = window.setTimeout(() => setStage("skeleton"), 3000);
    try {
      setData(await loadConsole());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The backend did not respond.");
    } finally {
      window.clearTimeout(indicator);
      window.clearTimeout(skeleton);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { data, error, loading, stage, refresh };
}
