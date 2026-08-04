/** @type {import('tailwindcss').Config} */
module.exports = {
  // ─── Scan all templates for class names ───────────────────────────────────
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
  ],

  // ─── Safelist: dynamic classes built at runtime via JS ────────────────────
  // These are classes injected via JS template literals, classList.add(),
  // or string concatenation — Tailwind's scanner cannot detect them statically.
  safelist: [
    // call_room.html — colorClass variable (status/role indicators)
    "text-green-600", "text-green-500",
    "text-yellow-600",
    "text-blue-500", "text-blue-600",
    "text-purple-500",
    "text-orange-500", "text-orange-600",
    "text-red-400", "text-red-600", "text-red-700", "text-red-900",
    "text-gray-500",

    // consultant_dashboard.html — labelCls, dotCls
    "bg-orange-400", "bg-blue-400", "bg-green-400",

    // signup_simple.html, daily_journal.html — toast colors
    "bg-green-600", "bg-red-600", "bg-green-500", "bg-red-500",
    "text-white",

    // ai_chat.html — message layout
    "justify-end",
    "message-fade-in",

    // protected.html — lock toast (JS string concat with arbitrary values)
    "z-[10000]", "max-w-[90vw]",

    // call_room.html — arbitrary sizes
    "text-[10px]", "text-[9px]", "text-[8px]", "text-[11px]", "text-[0.6rem]",
    "min-w-[18px]", "min-w-[50px]",
    "h-[18px]", "h-[60px]", "h-[600px]",
    "min-h-[120px]",
    "max-h-[90vh]", "max-h-[85vh]",

    // admin pages — arbitrary widths
    "min-w-[150px]", "min-w-[180px]", "min-w-[200px]", "min-w-[240px]",

    // consultant_messages.html, ai_chat.html
    "max-w-[80%]", "max-w-[60%]",

    // call_room.html — classList.add
    "bg-purple-600", "bg-gray-100", "text-gray-600",
    "opacity-100", "translate-y-0", "opacity-0", "-translate-y-4",

    // consultant_appointment_details.html
    "border-primary-600", "text-primary-600",

    // animate-in pattern (tailwindcss-animate)
    "animate-in", "fade-in", "slide-in-from-top-2",

    // primary/secondary/accent color classes used dynamically via JS
    { pattern: /^(bg|text|border|from|to|ring|shadow)-(primary|secondary|accent)-\d{2,3}$/ },
  ],

  theme: {
    extend: {
      // ─── Custom colour palettes (must match tailwind.config in base.html) ──
      colors: {
        primary: {
          50:  "#fff1f2",
          100: "#ffe4e6",
          200: "#fecdd3",
          300: "#fda4af",
          400: "#fb7185",
          500: "#f43f5e",
          600: "#e11d48",
          700: "#be123c",
          800: "#9f1239",
          900: "#881337",
        },
        secondary: {
          50:  "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          300: "#5eead4",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
          800: "#115e59",
          900: "#134e4a",
        },
        accent: {
          50:  "#fefce8",
          100: "#fef9c3",
          200: "#fef08a",
          300: "#fde047",
          400: "#facc15",
          500: "#eab308",
          600: "#ca8a04",
          700: "#a16207",
          800: "#854d0e",
          900: "#713f12",
        },
      },

      // ─── Font families (must match tailwind.config in base.html) ──────────
      fontFamily: {
        sans:    ["Inter", "system-ui", "sans-serif"],
        display: ["Outfit", "Inter", "sans-serif"],
      },
    },
  },

  // ─── Plugins ──────────────────────────────────────────────────────────────
  plugins: [
    // @tailwindcss/typography — powers `prose` classes on blog pages
    require("@tailwindcss/typography"),
  ],
};
