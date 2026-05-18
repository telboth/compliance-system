import type { Config } from "tailwindcss";

// XLENT-fargepalett. Justeres mot offisiell brand guide når den er tilgjengelig.
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        xlent: {
          primary: "#0A2540",
          accent: "#FF6B35",
          surface: "#F7F8FA",
          ink: "#1A2332",
          muted: "#6B7280",
        },
        traffic: {
          green: "#16A34A",
          yellow: "#F59E0B",
          red: "#DC2626",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
