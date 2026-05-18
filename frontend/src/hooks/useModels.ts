import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchModels, type ModelResponse } from "@/api/models";
import {
  getSelectedModel,
  setSelectedModel,
  type SelectedModel,
} from "@/lib/modelStore";

export function useModels() {
  return useQuery({
    queryKey: ["models"],
    queryFn: fetchModels,
    staleTime: 60_000,
  });
}

export function useModelSelection() {
  const [selected, setSelected] = useState<SelectedModel>(getSelectedModel);

  const select = useCallback((model: ModelResponse) => {
    const next: SelectedModel = {
      provider: model.provider,
      model_id: model.model_id,
      display_name: model.display_name,
    };
    setSelectedModel(next);
    setSelected(next);
  }, []);

  return { selected, select };
}

export function useAvailableModels(): ModelResponse[] {
  const { data } = useModels();
  return useMemo(
    () =>
      (data?.providers ?? []).flatMap((p) =>
        p.models.filter((m) => m.available),
      ),
    [data],
  );
}
