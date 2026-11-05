/** Set ikon garis 20×20 (stroke currentColor). Dekoratif kecuali diberi label oleh pemanggil. */
const P = {
  home: '<path d="M3.5 9 10 3.8 16.5 9"/><path d="M5.2 7.8V16h3.6v-4.2h2.4V16h3.6V7.8"/>',
  plus: '<path d="M10 4.5v11M4.5 10h11"/>',
  minus: '<path d="M4.5 10h11"/>',
  check: '<path d="m4.8 10.4 3.3 3.2 7.1-7.4"/>',
  dash: '<path d="M5.5 10h9"/>',
  search: '<circle cx="8.8" cy="8.8" r="5"/><path d="m12.6 12.6 3.9 3.9"/>',
  calendar: '<rect x="3.5" y="4.8" width="13" height="11.7" rx="2"/><path d="M3.5 8.6h13M7 3.2v3M13 3.2v3"/>',
  chevDown: '<path d="m5.5 8 4.5 4.5L14.5 8"/>',
  chevUp: '<path d="m5.5 12 4.5-4.5 4.5 4.5"/>',
  chevRight: '<path d="m8 5.5 4.5 4.5L8 14.5"/>',
  chevLeft: '<path d="M12 5.5 7.5 10l4.5 4.5"/>',
  reset: '<path d="M4.4 10a5.6 5.6 0 1 0 1.7-4"/><path d="M5.6 3.4v3.2h3.2"/>',
  close: '<path d="m5.5 5.5 9 9M14.5 5.5l-9 9"/>',
  panel: '<rect x="3.2" y="4" width="13.6" height="12" rx="2"/><path d="M11.6 4v12"/>',
  layers: '<path d="m10 3.6 6.6 3.6L10 10.8 3.4 7.2 10 3.6Z"/><path d="m3.4 10.4 6.6 3.6 6.6-3.6M3.4 13.4 10 17l6.6-3.6"/>',
  chart: '<path d="M3.5 16.5h13"/><path d="M6 13.5V9M10 13.5V5.5M14 13.5V8"/>',
  sliders: '<path d="M4 6h7M14.5 6H16M4 14h2M9.5 14H16"/><circle cx="12.7" cy="6" r="1.8"/><circle cx="7.7" cy="14" r="1.8"/>',
  external: '<path d="M8.2 4.5H4.5v11h11v-3.7"/><path d="M11.5 4.5h4v4M15.2 4.8 9.3 10.7"/>',
  target: '<circle cx="10" cy="10" r="6"/><circle cx="10" cy="10" r="2.2"/>',
  arrowLeft: '<path d="M15.5 10h-11M9 5.5 4.5 10 9 14.5"/>',
  minimize: '<path d="M5 10h10"/>',
  sparkle: '<path d="M10 2.8c.5 3.6 1.6 4.7 5.2 5.2-3.6.5-4.7 1.6-5.2 5.2-.5-3.6-1.6-4.7-5.2-5.2 3.6-.5 4.7-1.6 5.2-5.2Z"/><path d="M15.4 13.2c.2 1.4.7 1.9 2.1 2.1-1.4.2-1.9.7-2.1 2.1-.2-1.4-.7-1.9-2.1-2.1 1.4-.2 1.9-.7 2.1-2.1Z"/>',
  send: '<path d="M10 16V4.5M5.2 9.2 10 4.4l4.8 4.8"/>',
  link: '<path d="M8.6 11.4a3.2 3.2 0 0 0 4.5 0l2.3-2.3a3.2 3.2 0 0 0-4.5-4.5l-1 1"/><path d="M11.4 8.6a3.2 3.2 0 0 0-4.5 0l-2.3 2.3a3.2 3.2 0 0 0 4.5 4.5l1-1"/>',
  download: '<path d="M10 3.8v9M6 9l4 4 4-4"/><path d="M4 15.8h12"/>',
  image: '<rect x="3.4" y="4.2" width="13.2" height="11.6" rx="2"/><circle cx="7.6" cy="8.3" r="1.3"/><path d="m4 14.4 3.9-3.6 2.6 2.3 2.2-1.9 3.4 3"/>',
  table: '<rect x="3.4" y="4.2" width="13.2" height="11.6" rx="2"/><path d="M3.4 8.4h13.2M3.4 12.1h13.2M8.2 8.4v7.4"/>',
  info: '<circle cx="10" cy="10" r="6.6"/><path d="M10 9.2v4.1M10 6.7v.1"/>',
  alert: '<path d="M10 3.6 17 16H3L10 3.6Z"/><path d="M10 8.4v3.4M10 13.9v.1"/>',
  copy: '<rect x="6.6" y="6.6" width="9.4" height="9.4" rx="2"/><path d="M13.2 4.4H5.8A1.6 1.6 0 0 0 4.2 6v7.4"/>',
  retry: '<path d="M15.6 10a5.6 5.6 0 1 1-1.7-4"/><path d="M14.4 3.4v3.2h-3.2"/>',
} as const;

export type IconName = keyof typeof P;

export function iconSvg(name: IconName, size = 16, cls = ""): string {
  return `<svg class="ic${cls ? ` ${cls}` : ""}" viewBox="0 0 20 20" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${P[name]}</svg>`;
}

/** Ikon sebagai elemen <span> (untuk dirangkai dengan h()). */
export function ico(name: IconName, size = 16, cls = ""): HTMLSpanElement {
  const el = document.createElement("span");
  el.className = "ic-wrap";
  el.setAttribute("aria-hidden", "true");
  el.innerHTML = iconSvg(name, size, cls);
  return el;
}
