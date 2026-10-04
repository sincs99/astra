import { t } from "../../i18n";

/** "Zur Bestätigung den Namen <code>X</code> eingeben" – Wortstellung je Sprache aus dem Text. */
export function TypeName({ name }: { name: string }) {
  const [before, after] = t("sform.typeName", { name: "\u0001" }).split("\u0001");
  return <>{before}<code>{name}</code>{after}</>;
}
