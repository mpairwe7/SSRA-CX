/**
 * SSRA Assist Official Vector Icon Library (`packages/ui/icons.js`).
 *
 * Provides crisp, accessible 24x24 Lucide/Feather-compatible inline SVG icons
 * (`stroke="currentColor"`, `aria-hidden="true"`) matching `FinalYearProject` (`urabot`)
 * `components/Icons.tsx` and `components/ops/icons.tsx` — zero emoji dependencies.
 */

function svgWrap(inner, size = 15) {
  return `<svg class="ui-icon" aria-hidden="true" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}

export const ICONS = {
  ssraCrest: svgWrap(
    '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><polygon points="12 7.5 13.3 10.3 16.3 10.7 14.1 12.8 14.6 15.8 12 14.3 9.4 15.8 9.9 12.8 7.7 10.7 10.7 10.3 12 7.5" fill="currentColor" stroke="none"/>',
    16,
  ),
  search: svgWrap('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>', 15),
  panelLeft: svgWrap('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>', 16),
  chevronsLeft: svgWrap('<path d="m12.5 17-5-5 5-5"/><path d="m18 17-5-5 5-5"/>', 15),
  chevronsRight: svgWrap('<path d="m11.5 7 5 5-5 5"/><path d="m6 7 5 5-5 5"/>', 15),
  chevronUpDown: svgWrap('<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>', 14),
  plus: svgWrap('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>', 15),
  close: svgWrap('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>', 15),
  check: svgWrap('<polyline points="20 6 9 17 4 12"/>', 14),
  arrowUpRight: svgWrap('<path d="M8 16 16 8"/><path d="M9.5 8H16v6.5"/>', 14),
  refresh: svgWrap(
    '<path d="M20 11a8 8 0 0 0-13.7-5.3L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 13.7 5.3L20 16"/><path d="M20 20v-4h-4"/>',
    14,
  ),
  phone: svgWrap(
    '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    15,
  ),
  mic: svgWrap(
    '<path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z"/><path d="M19 12a7 7 0 0 1-14 0"/><path d="M12 19v3"/>',
    15,
  ),
  speaker: svgWrap(
    '<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
    14,
  ),
  speakerOff: svgWrap(
    '<path d="M11 5 6 9H2v6h4l5 4V5Z"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/>',
    14,
  ),
  stop: svgWrap('<rect x="6" y="6" width="12" height="12" rx="2"/>', 14),
  copy: svgWrap(
    '<rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2"/>',
    14,
  ),
  thumbUp: svgWrap(
    '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/>',
    14,
  ),
  thumbDown: svgWrap(
    '<path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/>',
    14,
  ),
  pin: svgWrap(
    '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16h14v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1 1 1 0 0 1 1 1z"/>',
    13,
  ),
  edit: svgWrap('<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>', 13),
  trash: svgWrap(
    '<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
    13,
  ),
  messageSquare: svgWrap(
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z"/>',
    14,
  ),
  sun: svgWrap(
    '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    15,
  ),
  moon: svgWrap('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z"/>', 15),
  contrast: svgWrap(
    '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18Z" fill="currentColor" stroke="none"/>',
    15,
  ),
  globe: svgWrap(
    '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20Z"/>',
    15,
  ),
  gauge: svgWrap(
    '<path d="M4 18a8 8 0 1 1 16 0"/><path d="m14.5 10.5-2.9 4"/><circle cx="12" cy="18" r="1.2"/>',
    15,
  ),
  inbox: svgWrap(
    '<path d="M4 13h4l1.5 3h5L16 13h4"/><path d="M5.5 5h13l1.5 8v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4l1.5-8Z"/>',
    15,
  ),
  list: svgWrap(
    '<path d="M8 6h12"/><path d="M8 12h12"/><path d="M8 18h12"/><path d="M4 6h.01"/><path d="M4 12h.01"/><path d="M4 18h.01"/>',
    15,
  ),
  clipboardCheck: svgWrap(
    '<path d="M9 4h6v3H9z"/><path d="M15 5h2a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
    15,
  ),
  shieldCheck: svgWrap(
    '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
    15,
  ),
  history: svgWrap(
    '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    15,
  ),
  flag: svgWrap('<path d="M5 21V4"/><path d="M5 5h11l-1.6 3.5L16 12H5"/>', 15),
  alertTriangle: svgWrap(
    '<path d="M10.3 4.3 2.7 17.2A1.6 1.6 0 0 0 4.1 19.6h15.8a1.6 1.6 0 0 0 1.4-2.4L13.7 4.3a1.6 1.6 0 0 0-2.8 0Z"/><path d="M12 9.5v4"/><path d="M12 16.6h.01"/>',
    15,
  ),
  sliders: svgWrap(
    '<path d="M4 6h9"/><path d="M17 6h3"/><path d="M4 12h3"/><path d="M11 12h9"/><path d="M4 18h9"/><path d="M17 18h3"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="15" cy="18" r="2"/>',
    15,
  ),
  send: svgWrap('<path d="M20 4 3 10.5l6.5 2.6L12 20l8-16Z"/><path d="M9.5 13.1 20 4"/>', 15),
  plug: svgWrap(
    '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    15,
  ),
  chart: svgWrap(
    '<path d="M4 20V6"/><path d="M4 20h16"/><path d="M8 20v-6"/><path d="M13 20V9"/><path d="M18 20v-9"/>',
    15,
  ),
  beaker: svgWrap(
    '<path d="M9.5 3v6.2L4.6 17a2 2 0 0 0 1.7 3h11.4a2 2 0 0 0 1.7-3l-4.9-7.8V3"/><path d="M8 3h8"/><path d="M7 14h10"/>',
    15,
  ),
  settings: svgWrap(
    '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/>',
    15,
  ),
  bookOpen: svgWrap(
    '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    14,
  ),
  lock: svgWrap(
    '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    14,
  ),
  clock: svgWrap('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', 14),
  sparkles: svgWrap(
    '<path d="M12 3v3"/><path d="M12 18v3"/><path d="M3 12h3"/><path d="M18 12h3"/><path d="m9 12 3 3 3-3-3-3-3 3Z"/>',
    14,
  ),
  wifi: svgWrap(
    '<path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1"/>',
    14,
  ),
  chevronDown: svgWrap('<path d="m6 9 6 6 6-6"/>', 13),
  kebab:
    '<svg class="ui-icon" aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="12" cy="5" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="19" r="1.7"/></svg>',
  voiceWave: svgWrap(
    '<path d="M3 11v2"/><path d="M7.5 7.5v9"/><path d="M12 4v16"/><path d="M16.5 7.5v9"/><path d="M21 11v2"/>',
    16,
  ),
  sendUp: svgWrap('<line x1="12" y1="17" x2="12" y2="7"/><polyline points="7 12 12 7 17 12"/>', 16),
  helpCircle: svgWrap(
    '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 0 1 4.9.6c0 1.7-2.5 2-2.5 3.6"/><path d="M12 17.3h.01"/>',
    15,
  ),
  inboxEmpty: svgWrap(
    '<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><path d="M3.5 12.5h4l1.4 2.4h6.2l1.4-2.4h4"/>',
    18,
  ),
  externalLink: svgWrap(
    '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
    14,
  ),
  micOff: svgWrap(
    '<line x1="2" y1="2" x2="22" y2="22"/><path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2"/><path d="M5 10v2a7 7 0 0 0 12 5"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12"/><line x1="12" y1="19" x2="12" y2="22"/>',
    15,
  ),
  phoneOff: svgWrap(
    '<path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7 2 2 0 0 1 1.72 2v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.42 19.42 0 0 1-3.33-2.67m-2.67-3.34a19.79 19.79 0 0 1-3.07-8.63A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91"/><line x1="22" y1="2" x2="2" y2="22"/>',
    15,
  ),
  pause: svgWrap(
    '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>',
    14,
  ),
  play: svgWrap('<polygon points="5 3 19 12 5 21 5 3"/>', 14),
  user: svgWrap(
    '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    15,
  ),
};
