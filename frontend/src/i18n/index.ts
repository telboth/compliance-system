import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import nbCommon from "./locales/nb/common.json";
import enCommon from "./locales/en/common.json";
import nbInvoices from "./locales/nb/invoices.json";
import enInvoices from "./locales/en/invoices.json";
import nbPages from "./locales/nb/pages.json";
import enPages from "./locales/en/pages.json";
import nbRules from "./locales/nb/rules.json";
import enRules from "./locales/en/rules.json";
import nbWatchlist from "./locales/nb/watchlist.json";
import enWatchlist from "./locales/en/watchlist.json";
import nbComponents from "./locales/nb/components.json";
import enComponents from "./locales/en/components.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      nb: { common: nbCommon, invoices: nbInvoices, pages: nbPages, rules: nbRules, watchlist: nbWatchlist, components: nbComponents },
      en: { common: enCommon, invoices: enInvoices, pages: enPages, rules: enRules, watchlist: enWatchlist, components: enComponents },
    },
    // Norsk bokmål som fallback dersom nettleserspråket ikke støttes
    fallbackLng: "nb",
    supportedLngs: ["nb", "no", "en"],
    // "no" og "nb" er samme språk i praksis
    load: "languageOnly",
    detection: {
      // Sjekk localStorage først, så nettleserspråk
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "xlent-lang",
      caches: ["localStorage"],
    },
    defaultNS: "common",
    interpolation: {
      // React escaper allerede XSS — ikke dobbelt-escape
      escapeValue: false,
    },
  });

export default i18n;
