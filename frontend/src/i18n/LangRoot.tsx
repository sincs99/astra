import { Fragment, type ReactNode } from "react";
import { useLang } from "./index";

/** Baut den Baum bei Sprachwechsel neu auf, damit alle t()-Aufrufe die neue Sprache verwenden. */
export function LangRoot({ children }: { children: ReactNode }) {
  const lang = useLang();
  return <Fragment key={lang}>{children}</Fragment>;
}
