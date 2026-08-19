import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F6F4F0",
        ink: "#1C2430",
        muted: "#5C6778",
        line: "#E4E0D8",
        teal: {
          DEFAULT: "#0F766E",
          50: "#F0FDFA",
          100: "#CCFBF1",
          700: "#0F766E",
          800: "#115E59",
          900: "#134E4A",
        },
        clinical: {
          warning: "#B45309",
          danger: "#B91C1C",
          ok: "#047857",
          info: "#1D4ED8",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(28,36,48,0.04), 0 8px 24px rgba(28,36,48,0.06)",
      },
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem",
      },
    },
  },
  plugins: [],
};

export default config;
