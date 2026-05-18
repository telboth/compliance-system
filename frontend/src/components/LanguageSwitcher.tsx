import { useTranslation } from "react-i18next";
import clsx from "clsx";

/**
 * Tospråklig velger — vises i nav-baren.
 * Bruker tekstforkortelser (NO / EN) siden Windows ikke rendrer landflagg-emojis.
 * Valgt språk lagres i localStorage (nøkkel: "xlent-lang").
 */
export function LanguageSwitcher({ variant = "light" }: { variant?: "light" | "dark" }) {
  const { i18n, t } = useTranslation("common");
  const current = i18n.resolvedLanguage ?? i18n.language;
  const isNorsk = current === "nb" || current === "no";

  function switchTo(lang: string) {
    void i18n.changeLanguage(lang);
  }

  return (
    <div
      className={clsx(
        "flex items-center overflow-hidden rounded text-xs font-medium",
        variant === "dark"
          ? "border border-white/35 bg-white/10 text-white"
          : "border border-gray-200 bg-white",
      )}
      role="group"
      aria-label={t("language.switch_aria")}
    >
      <button
        onClick={() => switchTo("nb")}
        title={t("language.nb")}
        aria-pressed={isNorsk}
        className={clsx(
          "px-2.5 py-1 transition-colors",
          isNorsk
            ? "bg-xlent-primary text-white"
            : variant === "dark"
              ? "text-white/85 hover:bg-white/10 hover:text-white"
              : "text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink",
        )}
      >
        NO
      </button>
      <span className={clsx("w-px self-stretch", variant === "dark" ? "bg-white/25" : "bg-gray-200")} aria-hidden />
      <button
        onClick={() => switchTo("en")}
        title={t("language.en")}
        aria-pressed={!isNorsk}
        className={clsx(
          "px-2.5 py-1 transition-colors",
          !isNorsk
            ? "bg-xlent-primary text-white"
            : variant === "dark"
              ? "text-white/85 hover:bg-white/10 hover:text-white"
              : "text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink",
        )}
      >
        EN
      </button>
    </div>
  );
}
