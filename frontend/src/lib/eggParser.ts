export interface EggPreview {
  name: string;
  author: string | null;
  image: string | null;
  variableCount: number;
}

/** Liest Egg-JSON und prueft nur die Grundform; die fachliche Pruefung macht das Backend. */
export function parseEgg(text: string): { egg: Record<string, unknown>; preview: EggPreview } {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("Kein gültiges JSON.");
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("Das Egg muss ein JSON-Objekt sein.");
  }
  const egg = data as Record<string, unknown>;
  if (typeof egg.name !== "string" || !egg.name.trim()) {
    throw new Error("Im Egg fehlt das Feld 'name'. Ist das wirklich ein Pterodactyl-Egg?");
  }
  const images = egg.docker_images;
  const firstImage =
    images && typeof images === "object"
      ? Object.values(images as Record<string, unknown>).find((v): v is string => typeof v === "string") ?? null
      : typeof egg.image === "string" ? egg.image : null;
  return {
    egg,
    preview: {
      name: egg.name,
      author: typeof egg.author === "string" ? egg.author : null,
      image: firstImage,
      variableCount: Array.isArray(egg.variables) ? egg.variables.length : 0,
    },
  };
}

