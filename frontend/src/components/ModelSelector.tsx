import { useModels, useModelSelection } from "@/hooks/useModels";
import type { ProviderResponse } from "@/api/models";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

/**
 * Modellvelger i navigasjonslinjen.
 *
 * Viser en dropdown gruppert per provider (Anthropic, OpenAI, Ollama).
 * Utilgjengelige providers vises nedtonet med hint om manglende API-nøkkel.
 * Valget lagres i localStorage og vil brukes ved LLM-ekstraksjon i Sprint 2.
 */
export function ModelSelector({ variant = "light" }: { variant?: "light" | "dark" }) {
  const { t } = useTranslation("components");
  const { data, isLoading } = useModels();
  const { selected, select } = useModelSelection();

  if (isLoading || !data) {
    return (
      <span className={clsx("text-xs", variant === "dark" ? "text-white/80" : "text-xlent-muted")}>
        {t("model_selector.loading")}
      </span>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className={clsx("hidden text-xs sm:inline", variant === "dark" ? "text-white/90" : "text-xlent-muted")}>
        {t("model_selector.label")}
      </span>
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
        className={clsx(
          "max-w-[220px] rounded px-2 py-1 text-xs",
          variant === "dark"
            ? "border border-white/35 bg-white/10 text-white"
            : "border border-gray-300 bg-white text-xlent-ink",
        )}
        style={{ colorScheme: variant === "dark" ? "dark" : "light" }}
      >
        {data.providers.map((provider) => (
          <ProviderGroup key={provider.provider_id} provider={provider} />
        ))}
      </select>

      {!isProviderAvailable(data.providers, selected.provider) && (
        <span
          className={clsx("cursor-help text-xs", variant === "dark" ? "text-amber-200" : "text-traffic-yellow")}
          title={t("model_selector.missing_key_title", { provider: selected.provider })}
        >
          {t("model_selector.missing_key_badge")}
        </span>
      )}
    </div>
  );
}

function ProviderGroup({ provider }: { provider: ProviderResponse }) {
  const { t } = useTranslation("components");
  if (provider.models.length === 0) return null;

  return (
    <optgroup
      className="bg-white text-gray-900"
      label={
        provider.available
          ? provider.display_name
          : `${provider.display_name} (${t("model_selector.no_key")})`
      }
    >
      {provider.models.map((model) => (
        <option
          key={`${model.provider}::${model.model_id}`}
          value={`${model.provider}::${model.model_id}`}
          disabled={!model.available}
          className="bg-white text-gray-900"
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
