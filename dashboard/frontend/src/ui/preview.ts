/**
 * Pratinjau hover lintas komponen (panel ↔ peta ↔ legenda ↔ linimasa).
 *
 * Ringan: tidak menyentuh state, URL, atau lapisan Leaflet; hanya satu <style> berisi aturan CSS yang
 * diganti per kunci dan ditulis paling banyak sekali per frame. Pratinjau = hanya tampilan; klik tetap aksi utama.
 */
const rules = new Map<string, string>();
let el: HTMLStyleElement | null = null;
let raf = 0;

function flush(): void {
  raf = 0;
  el ??= document.head.appendChild(Object.assign(document.createElement("style"), { id: "pv-rules" }));
  el.textContent = [...rules.values()].join("\n");
  document.documentElement.classList.toggle("has-pv", rules.size > 0);
}

export function setPv(key: string, css: string | null): void {
  if (css === null ? !rules.has(key) : rules.get(key) === css) return;
  if (css === null) rules.delete(key); else rules.set(key, css);
  raf ||= requestAnimationFrame(flush);
}

export function clearPv(): void {
  if (!rules.size) return;
  rules.clear();
  raf ||= requestAnimationFrame(flush);
}

/** Nilai aman untuk selektor atribut CSS (dalam tanda kutip). */
export const q = (v: string): string => `"${v.replace(/["\\]/g, "\\$&")}"`;

/** Pasang pratinjau pada hover mouse (bukan sentuh) dan fokus keyboard. */
export function onPreview(target: HTMLElement, on: () => void, off: () => void): void {
  target.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") on(); });
  target.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") off(); });
  target.addEventListener("focusin", (e) => { if ((e.target as HTMLElement).matches(":focus-visible")) on(); });
  target.addEventListener("focusout", off);
}
