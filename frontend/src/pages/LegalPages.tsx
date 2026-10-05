import type { ReactNode } from "react";
import { PageLayout } from "../components/ui";
import { getLang, useLang } from "../i18n";
import { OPERATOR } from "../legal/operator";
import { Value, agb, datenschutz, impressum, type LegalContext, type LegalDoc } from "../legal/content";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: 18, margin: "0 0 8px" }}>{title}</h2>
      <div style={{ fontSize: 14, lineHeight: 1.6, color: "var(--text)" }}>{children}</div>
    </section>
  );
}

function Notice({ en }: { en: boolean }) {
  return (
    <div role="note" style={{ padding: "12px 16px", marginBottom: 24, backgroundColor: "var(--warn-soft)", border: "1px solid var(--warn-border)", borderRadius: 8, color: "var(--text)", fontSize: 14 }}>
      {en ? (
        <>
          <strong>To be completed by the operator.</strong> This text is only a structure with placeholders and is not legal
          advice. The operator enters the details in <code>frontend/src/legal/operator.ts</code>; the texts must be reviewed
          and adapted legally before going live.
        </>
      ) : (
        <>
          <strong>Vom Betreiber auszufüllen.</strong> Dieser Text ist nur eine Struktur mit Platzhaltern und ersetzt keine
          Rechtsberatung. Die Angaben trägt der Betreiber in <code>frontend/src/legal/operator.ts</code> ein; die Texte
          müssen vor dem Echtbetrieb rechtlich geprüft und angepasst werden.
        </>
      )}
    </div>
  );
}

/** Rechtstext in der Sprache der Oberfläche und der Fassung des Rechtsraums des Betreibers (DE oder CH). */
function LegalPage({ build }: { build: (c: LegalContext) => LegalDoc }) {
  useLang();
  const en = getLang() === "en";
  const doc = build({ en, ch: OPERATOR.jurisdiction === "CH", o: OPERATOR });
  return (
    <PageLayout title={doc.title} maxWidth={800}>
      <Notice en={en} />
      {doc.sections.map((s) => <Section key={s.title} title={s.title}>{s.body}</Section>)}
      <p style={{ fontSize: 12, color: "var(--text-3)" }}>{en ? "As of" : "Stand"}: <Value>{OPERATOR.lastUpdated}</Value></p>
    </PageLayout>
  );
}

export const ImpressumPage = () => <LegalPage build={impressum} />;
export const DatenschutzPage = () => <LegalPage build={datenschutz} />;
export const AgbPage = () => <LegalPage build={agb} />;
