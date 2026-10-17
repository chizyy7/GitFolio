import type { Config } from "tailwindcss";

/**
 * GitFolio theme.
 *
 * Dark-mode-first, tuned to sit close to GitHub's dark palette so the product
 * feels instantly familiar to developers. Every surface colour is also exposed
 * as a CSS variable in `globals.css`, which lets the heatmap scale colours and
 * the chat bubbles reuse the same tokens.
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/context/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: "rgb(var(--canvas) / <alpha-value>)",
          subtle: "rgb(var(--canvas-subtle) / <alpha-value>)",
          inset: "rgb(var(--canvas-inset) / <alpha-value>)",
          overlay: "rgb(var(--canvas-overlay) / <alpha-value>)",
        },
        border: {
          DEFAULT: "rgb(var(--border-default) / <alpha-value>)",
          muted: "rgb(var(--border-muted) / <alpha-value>)",
        },
        fg: {
          DEFAULT: "rgb(var(--fg-default) / <alpha-value>)",
          muted: "rgb(var(--fg-muted) / <alpha-value>)",
          subtle: "rgb(var(--fg-subtle) / <alpha-value>)",
          onEmphasis: "rgb(var(--fg-on-emphasis) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          emphasis: "rgb(var(--accent-emphasis) / <alpha-value>)",
          muted: "rgb(var(--accent-muted) / <alpha-value>)",
        },
        success: {
          DEFAULT: "rgb(var(--success) / <alpha-value>)",
          emphasis: "rgb(var(--success-emphasis) / <alpha-value>)",
        },
        danger: {
          DEFAULT: "rgb(var(--danger) / <alpha-value>)",
          emphasis: "rgb(var(--danger-emphasis) / <alpha-value>)",
        },
        attention: {
          DEFAULT: "rgb(var(--attention) / <alpha-value>)",
          emphasis: "rgb(var(--attention-emphasis) / <alpha-value>)",
        },
        done: {
          DEFAULT: "rgb(var(--done) / <alpha-value>)",
          emphasis: "rgb(var(--done-emphasis) / <alpha-value>)",
        },
        // Contribution heatmap ramp (empty -> hottest).
        heat: {
          0: "rgb(var(--heat-0) / <alpha-value>)",
          1: "rgb(var(--heat-1) / <alpha-value>)",
          2: "rgb(var(--heat-2) / <alpha-value>)",
          3: "rgb(var(--heat-3) / <alpha-value>)",
          4: "rgb(var(--heat-4) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        DEFAULT: "6px",
        lg: "12px",
        xl: "16px",
      },
      boxShadow: {
        card: "0 1px 0 rgba(27,31,36,0.04)",
        popover: "0 8px 24px rgba(1,4,9,0.5)",
        glow: "0 0 0 1px rgb(var(--accent) / 0.4), 0 0 24px -6px rgb(var(--accent) / 0.45)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 180ms ease-out",
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
