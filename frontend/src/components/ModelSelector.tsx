import { useModels, useModelSelection } from "@/hooks/useModels";
import type { ProviderResponse } from "@/api/models";

/**
 * Modellvelger i navigasjonslinjen.
 *
 * Viser en dropdown gruppert per provider (Anthropic, OpenAI, Ollama).
 * Utilgjengelige providers vises nedtonet med hint om manglende API-nøkkel.
 * Valget lagres i localStorage og vil brukes ved LLM-ekstraksjon i Sprint 2.
 */
export function ModelSelector() {
  const { data, isLoading } = useModels();
  const { selected, select } = useModelSelection();

  if (isLoading || !data) {
    return (
      <span className="text-xs text-xlent-muted">Laster modeller…</span>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-xs text-xlent-muted sm:inline">Modell:</span>
      <select
        value={`${selected.provider}::${selected.model_id}`}
        onChange={(e) => {
          const [provider, ...rest] = e.target.value.split("::");
          const model_id = rest.join("::");
          const allModels = data.providers.flatMap((p) => p.models);
          const found = allModels.find(
            (m) => m.provider === provider && m.model_id === model_id,
          );
          if (found) select(found);
        }}
        className="max-w-[200px] rounded border border-gray-300 bg-white px-2 py-1 text-xs text-xlent-ink"
      >
        {data.providers.map((provider) => (
          <ProviderGroup key={provider.provider_id} provider={provider} />
        ))}
      </select>

      {!isProviderAvailable(data.providers, selected.provider) && (
        <span
          className="cursor-help text-xs text-traffic-yellow"
          title={`Legg til API-nøkkel i .secrets for å bruke ${selected.provider}`}
        >
          ⚠ Ingen nøkkel
        </span>
      )}
    </div>
  );
}

function ProviderGroup({ provider }: { provider: ProviderResponse }) {
  if (provider.models.length === 0) return null;

  return (
    <optgroup
      label={
        provider.available
          ? provider.display_name
          : `${provider.display_name} (ingen nøkkel)`
      }
    >
      {provider.models.map((model) => (
        <option
          key={`${model.provider}::${model.model_id}`}
          value={`${model.provider}::${model.model_id}`}
          disabled={!model.available}
        >
          {model.display_name}
          {model.local ? " 🖥" : ""}
          {model.multimodal ? " 👁" : ""}
        </option>
      ))}
    </optgroup>
  );
}

function isProviderAvailable(
  providers: ProviderResponse[],
  providerId: string,
): boolean {
  return providers.find((p) => p.provider_id === providerId)?.available ?? false;
}
