import { basicCatalog } from "@a2ui/react/v0_9";

const SPEC_VERSION = "v0.9" as const;

type Component = Record<string, unknown> & { id: string; component: string };

/** Strips inline Markdown emphasis for plain-text rendering (Text components here don't run a Markdown pipeline). */
function stripEmphasis(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, "$1").replace(/(?<!\*)\*(?!\*)(.+?)\*(?!\*)/g, "$1");
}

/**
 * Deterministically converts a trip report (Markdown) into the same A2UI message shape
 * `generate_report_ui` produces on the backend, so both paths render through the identical
 * <A2uiSurface> pipeline. Used when research_report_ui is null (generation not yet run, or
 * failed after retries) — no LLM call, so it can't itself fail.
 */
export function markdownToA2uiMessages(markdown: string, surfaceId: string) {
  const lines = markdown.split("\n");
  const components: Component[] = [];
  let idCounter = 0;
  const nextId = (prefix: string) => `${prefix}_${idCounter++}`;

  let title: string | null = null;
  const cardIds: string[] = [];

  type Section = { heading: string; bodyLines: string[] };
  const sections: Section[] = [];
  let current: Section | null = null;

  for (const raw of lines) {
    const h1 = raw.match(/^#\s+(.*)/);
    const h2 = raw.match(/^##\s+(.*)/);
    if (h1 && title === null) {
      title = h1[1].trim();
    } else if (h2) {
      current = { heading: h2[1].trim(), bodyLines: [] };
      sections.push(current);
    } else if (current) {
      current.bodyLines.push(raw);
    }
  }

  const titleId = title ? nextId("title") : null;
  if (title && titleId) {
    components.push({ id: titleId, component: "Text", variant: "h1", text: title });
  }

  for (const section of sections) {
    const cardId = nextId("card");
    const colId = nextId("col");
    const headingId = nextId("heading");
    const childIds: string[] = [headingId];

    components.push({ id: headingId, component: "Text", variant: "h2", text: section.heading });

    // Group body lines into paragraph blocks and consecutive-bullet blocks.
    let paragraph: string[] = [];
    let bullets: string[] = [];
    const flushParagraph = () => {
      const text = stripEmphasis(paragraph.join(" ").trim());
      paragraph = [];
      if (!text) return;
      const pId = nextId("p");
      components.push({ id: pId, component: "Text", variant: "body", text });
      childIds.push(pId);
    };
    const flushBullets = () => {
      if (bullets.length === 0) return;
      const itemIds = bullets.map((b) => {
        const liId = nextId("li");
        components.push({ id: liId, component: "Text", variant: "body", text: stripEmphasis(b) });
        return liId;
      });
      bullets = [];
      const listId = nextId("list");
      components.push({ id: listId, component: "List", direction: "vertical", children: itemIds });
      childIds.push(listId);
    };

    for (const raw of section.bodyLines) {
      if (/^\s*(-{3,}|\*{3,})\s*$/.test(raw)) continue; // Markdown horizontal rule, not content.
      const bullet = raw.match(/^\s*[-*]\s+(.*)/);
      if (bullet) {
        flushParagraph();
        bullets.push(bullet[1].trim());
      } else if (raw.trim() === "") {
        flushParagraph();
        flushBullets();
      } else {
        flushBullets();
        paragraph.push(raw.trim());
      }
    }
    flushParagraph();
    flushBullets();

    components.push({ id: colId, component: "Column", children: childIds });
    components.push({ id: cardId, component: "Card", child: colId });
    cardIds.push(cardId);
  }

  components.push({
    id: "root",
    component: "Column",
    children: [...(titleId ? [titleId] : []), ...cardIds],
  });

  return [
    { version: SPEC_VERSION, createSurface: { surfaceId, catalogId: basicCatalog.id } },
    { version: SPEC_VERSION, updateComponents: { surfaceId, components } },
  ];
}
