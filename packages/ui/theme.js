/**
 * Shared theme preference and palette (`packages/ui/theme.js`).
 *
 * The public assistant (`apps/web/server.js`) and the operations console (`packages/ui/ops-console.js`)
 * read one stored choice, so picking System, Light, Dark or High contrast on any page applies everywhere
 * on the same origin. Dark pairs Gemini's dark sidebar and cards (#1F1F1F, #1E1F20) with the dark variant of
 * 21st.dev gradient-background-4: an indigo top glow over a #0A0A0A canvas, the light theme's gradient in black.
 * High contrast follows GitHub's "Dark high contrast" palette.
 */

// Values: "system", "light", "dark", "high-contrast". An absent key falls back to older per-page settings.
export const SSRA_THEME_STORAGE_KEY = "ssra-theme";
export const SSRA_THEMES = ["light", "dark", "high-contrast"];

// Browser UI colour for <meta name="theme-color">.
export const SSRA_THEME_COLORS = {
  light: "#FFFFFF",
  dark: "#0A0A0A",
  "high-contrast": "#0A0C10",
};

export const SSRA_PALETTE = {
  dark: {
    canvas: "#0A0A0A",
    card: "#1E1F20",
    popover: "#282A2C",
    surface2: "#26272A",
    surface3: "#2E2F33",
    surface4: "#37393D",
    inset: "#18191A",
    border0: "rgba(255, 255, 255, 0.08)",
    border1: "rgba(255, 255, 255, 0.14)",
    border2: "rgba(255, 255, 255, 0.22)",
    text0: "#E3E3E3",
    text1: "#C4C7C5",
    text2: "#A8ABAF",
    text3: "#9AA0A6",
    accent: "#A8C7FA",
    accentSoft: "rgba(168, 199, 250, 0.12)",
    accentPill: "rgba(168, 199, 250, 0.18)",
    primary: "#1F3B9B",
    primaryHover: "#2A4BB8",
    primaryInk: "#FFFFFF",
    good: "#6DD58C",
    warn: "#FDD663",
    bad: "#F2B8B5",
    focus: "#A8C7FA",
    ghostHover: "rgba(255, 255, 255, 0.08)",
    ghostActive: "rgba(255, 255, 255, 0.12)",
    rowHover: "rgba(255, 255, 255, 0.04)",
    scrim: "rgba(0, 0, 0, 0.6)",
    // Top-glow stop: indigo-500 at 0x36 alpha (gradient-background-4, dark). Light uses #C7D2FE.
    glow: "#6366F136",
    railBg: "#1F1F1F",
    railText: "#E3E3E3",
    railMuted: "#9A9A9A",
    railCurrent: "rgba(0, 0, 0, 0.25)",
    railHover: "rgba(255, 255, 255, 0.08)",
    railActive: "rgba(255, 255, 255, 0.12)",
    railField: "rgba(255, 255, 255, 0.08)",
    railFieldHover: "rgba(255, 255, 255, 0.12)",
    tooltipBg: "#E3E3E3",
    tooltipInk: "#1F1F1F",
    switchOff: "#5F6368",
    switchOnKnob: "#062E6F",
    avatarBg: "#A8C7FA",
    avatarInk: "#062E6F",
  },
  "high-contrast": {
    canvas: "#0A0C10",
    card: "#0A0C10",
    popover: "#0A0C10",
    surface2: "#151B23",
    surface3: "#1F2630",
    surface4: "#2A323D",
    inset: "#151B23",
    border0: "#7A828E",
    border1: "#9EA7B3",
    border2: "#F0F3F6",
    text0: "#F0F3F6",
    text1: "#F0F3F6",
    text2: "#D1D7E0",
    text3: "#9EA7B3",
    accent: "#71B7FF",
    accentSoft: "rgba(113, 183, 255, 0.16)",
    accentPill: "rgba(113, 183, 255, 0.2)",
    primary: "#71B7FF",
    primaryHover: "#9ACBFF",
    primaryInk: "#0A0C10",
    good: "#26CD4D",
    warn: "#F0B72F",
    bad: "#FF9492",
    focus: "#FFD60A",
    ghostHover: "#262C36",
    ghostActive: "#313A47",
    rowHover: "#151B23",
    scrim: "rgba(0, 0, 0, 0.8)",
    railBg: "#010409",
    railText: "#F0F3F6",
    railMuted: "#D1D7E0",
    railCurrent: "rgba(113, 183, 255, 0.2)",
    railHover: "rgba(255, 255, 255, 0.12)",
    railActive: "rgba(255, 255, 255, 0.18)",
    railField: "rgba(255, 255, 255, 0.08)",
    railFieldHover: "rgba(255, 255, 255, 0.14)",
    tooltipBg: "#F0F3F6",
    tooltipInk: "#0A0C10",
    switchOff: "#3D444D",
    switchOnKnob: "#0A0C10",
    avatarBg: "#71B7FF",
    avatarInk: "#0A0C10",
  },
};

/**
 * Inline <head> script that sets `data-theme` and the theme-color metas before first paint.
 * Order: shared choice ("system" stops the lookup), the public assistant's saved store, the console's legacy key,
 * then the device setting.
 * Written on one line without `//` comments because the page minifiers drop comment lines.
 */
export function renderThemeBootstrapScript() {
  return `(function(){try{var d=document.documentElement,ok={"light":1,"dark":1,"high-contrast":1},t=null;try{t=localStorage.getItem(${JSON.stringify(SSRA_THEME_STORAGE_KEY)});if(t!=="system"&&!ok[t]){var s=JSON.parse(localStorage.getItem("ssra-chat-store-v2")||"null");t=s&&s.theme;if(!ok[t])t=localStorage.getItem("ssra-ops-theme");}}catch(e){}if(!ok[t]){var m=window.matchMedia;t=m&&m("(prefers-contrast: more)").matches?"high-contrast":m&&m("(prefers-color-scheme: light)").matches?"light":"dark";}d.setAttribute("data-theme",t);var c=${JSON.stringify(SSRA_THEME_COLORS)}[t],ms=document.querySelectorAll('meta[name="theme-color"]');for(var i=0;i<ms.length;i++)ms[i].setAttribute("content",c);}catch(e){}})();`;
}
