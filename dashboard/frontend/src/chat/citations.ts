import { h } from "../dom";
import { tgl } from "../format";
import { ico } from "../ui/icons";
import type { Citation } from "./service";

/** Daftar sitasi jawaban: ID tweet, ID kejadian, tanggal — persis seperti dikirim backend. */
export function citationList(cs: Citation[]): HTMLElement | null {
  if (!cs.length) return null;
  return h("div", { class: "cites" },
    h("p", { class: "cites-t" }, `Sumber (${cs.length})`),
    h("ol", { class: "cites-l" }, ...cs.map((c, i) => h("li", { class: "cite" },
      h("span", { class: "cite-n", "aria-hidden": "true" }, String(i + 1)),
      h("span", { class: "cite-b" },
        h("span", { class: "cite-meta" },
          h("span", { class: "cite-k" }, "Tweet ", h("b", {}, c.tweet_id)),
          c.event_id ? h("span", { class: "cite-k" }, "Kejadian ", h("b", {}, c.event_id)) : null,
          c.mention_id ? h("span", { class: "cite-k" }, "Laporan ", h("b", {}, c.mention_id)) : null,
          c.tanggal ? h("span", { class: "cite-k" }, tgl(c.tanggal)) : null),
        c.teks ? h("q", { class: "cite-x", lang: "id" }, c.teks) : null,
        c.url ? h("a", { class: "tweet-a", href: c.url, target: "_blank", rel: "noopener noreferrer" }, "Buka tweet asli", ico("external", 12)) : null)))));
}
