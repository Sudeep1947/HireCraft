/**
 * Skill2Job / AI Hiring Copilot — Design tokens
 * "Futuristic AI Premium + Clean SaaS + Subtle Glassmorphism"
 *
 * Blue-violet primary scale, cool slate neutrals, layered indigo-tinted
 * shadows, premium radii and motion tokens. Overriding these tokens
 * restyles every page consistently because the whole codebase consumes
 * them through standard Tailwind utilities (text-primary-600, shadow-lg,
 * rounded-lg, text-gray-500 ...).
 *
 * @type {import('tailwindcss').Config}
 */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f1f3ff",
          100: "#e4e8ff",
          200: "#cbd2ff",
          300: "#a9b4ff",
          400: "#8691f8",
          500: "#6a6df1",
          600: "#5557e6",
          700: "#4647cc",
          800: "#3a3ba5",
          900: "#33357f",
          950: "#1f204c",
        },
        gray: {
          50: "#f7f8fc",
          100: "#eef0f7",
          200: "#e1e5f0",
          300: "#cbd1e2",
          400: "#9aa4c0",
          500: "#667398",
          600: "#566184",
          700: "#414b6b",
          800: "#2d3552",
          900: "#1e2440",
          950: "#030719",
        },
        /* Semantic text colors (alias of the neutral scale). */
        ink: {
          DEFAULT: "#1e2440",
          muted: "#566184",
          subtle: "#9aa4c0",
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
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        display: [
          "Sora",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        DEFAULT: "0 1px 3px 0 rgba(31,32,76,0.07), 0 1px 2px -1px rgba(31,32,76,0.06)",
        xs: "0 1px 2px 0 rgba(31,32,76,0.05)",
        sm: "0 1px 2px 0 rgba(31,32,76,0.05)",
        md: "0 4px 10px -2px rgba(31,32,76,0.08), 0 2px 4px -2px rgba(31,32,76,0.05)",
        lg: "0 12px 24px -8px rgba(31,32,76,0.10), 0 4px 8px -4px rgba(31,32,76,0.05)",
        xl: "0 24px 48px -16px rgba(31,32,76,0.14), 0 8px 16px -8px rgba(31,32,76,0.06)",
        "2xl": "0 32px 64px -24px rgba(31,32,76,0.20)",
        inner: "inset 0 1px 2px 0 rgba(31,32,76,0.06)",
        card: "0 1px 2px rgba(31,32,76,0.04), 0 8px 24px -12px rgba(31,32,76,0.10)",
        elevated: "0 2px 4px rgba(31,32,76,0.04), 0 16px 40px -16px rgba(31,32,76,0.16)",
        soft: "0 2px 8px -2px rgba(31,32,76,0.10), 0 1px 2px rgba(31,32,76,0.06)",
        glass: "0 8px 32px -12px rgba(31,32,76,0.18)",
        glow: "0 0 0 1px rgba(85,87,230,0.14), 0 8px 32px -8px rgba(85,87,230,0.40)",
        "glow-sm": "0 0 0 1px rgba(85,87,230,0.12), 0 4px 16px -6px rgba(85,87,230,0.35)",
      },
      borderRadius: {
        none: "0px",
        sm: "0.375rem",
        DEFAULT: "0.5rem",
        md: "0.625rem",
        lg: "0.75rem",
        xl: "1rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #3b82f6 0%, #5557e6 45%, #8b5cf6 100%)",
        "brand-gradient-soft":
          "linear-gradient(135deg, rgba(59,130,246,0.14) 0%, rgba(85,87,230,0.16) 50%, rgba(139,92,246,0.14) 100%)",
        "brand-gradient-strong":
          "linear-gradient(135deg, #030719 0%, #060d2e 45%, #0a1548 75%, #121644 100%)",
        "surface-mesh":
          "radial-gradient(60rem 40rem at 8% -10%, rgba(85,87,230,0.10), transparent 60%), radial-gradient(52rem 36rem at 102% 0%, rgba(139,92,246,0.10), transparent 55%), radial-gradient(48rem 42rem at 50% 120%, rgba(59,130,246,0.08), transparent 60%)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.65" },
        },
        entrance: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.45s cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in": "fade-in 0.4s ease-out both",
        "scale-in": "scale-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) both",
        "slide-in-right": "slide-in-right 0.4s cubic-bezier(0.16, 1, 0.3, 1) both",
        shimmer: "shimmer 1.6s linear infinite",
        float: "float 7s ease-in-out infinite",
        "pulse-soft": "pulse-soft 2.4s ease-in-out infinite",
        entrance: "entrance 0.5s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
