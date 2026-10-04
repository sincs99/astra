import type { ReactNode } from "react";
import { PageLayout } from "../components/ui";
import { OPERATOR, isPlaceholder } from "../legal/operator";

/** Zeigt einen Betreiber-Wert; offene Platzhalter werden hervorgehoben. */
function Value({ children }: { children: string }) {
  if (!isPlaceholder(children)) return <>{children}</>;
  return (
    <mark style={{ background: "var(--warn-soft)", color: "var(--warn)", padding: "0 4px", borderRadius: 3 }}>{children}</mark>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: 18, margin: "0 0 8px" }}>{title}</h2>
      <div style={{ fontSize: 14, lineHeight: 1.6, color: "var(--text)" }}>{children}</div>
    </section>
  );
}

function Notice() {
  return (
    <div role="note" style={{ padding: "12px 16px", marginBottom: 24, backgroundColor: "var(--warn-soft)", border: "1px solid var(--warn-border)", borderRadius: 8, color: "var(--warn)", fontSize: 14 }}>
      <strong>Vom Betreiber auszufüllen.</strong> Dieser Text ist nur eine Struktur mit Platzhaltern und ersetzt keine
      Rechtsberatung. Die Angaben trägt der Betreiber in <code>frontend/src/legal/operator.ts</code> ein; die Texte
      müssen vor dem Echtbetrieb rechtlich geprüft und angepasst werden.
    </div>
  );
}

function LegalLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <PageLayout title={title} maxWidth={800}>
      <Notice />
      {children}
      <p style={{ fontSize: 12, color: "var(--text-3)" }}>Stand: <Value>{OPERATOR.lastUpdated}</Value></p>
    </PageLayout>
  );
}

export function ImpressumPage() {
  const o = OPERATOR;
  return (
    <LegalLayout title="Impressum">
      <Section title="Anbieter">
        <p style={{ margin: 0 }}>
          <Value>{o.name}</Value> (<Value>{o.legalForm}</Value>)<br />
          <Value>{o.street}</Value><br />
          <Value>{o.zipCity}</Value><br />
          <Value>{o.country}</Value>
        </p>
      </Section>
      <Section title="Kontakt">
        <p style={{ margin: 0 }}>E-Mail: <Value>{o.email}</Value><br />Telefon: <Value>{o.phone}</Value></p>
      </Section>
      <Section title="Vertretungsberechtigt">
        <Value>{o.representative}</Value>
      </Section>
      <Section title="Register und Steuern">
        <p style={{ margin: 0 }}>
          Handelsregister: <Value>{o.register}</Value><br />
          Umsatzsteuer-Identifikationsnummer: <Value>{o.vatId}</Value>
        </p>
      </Section>
    </LegalLayout>
  );
}

export function DatenschutzPage() {
  const o = OPERATOR;
  return (
    <LegalLayout title="Datenschutzerklärung">
      <Section title="1. Verantwortlicher">
        <Value>{o.name}</Value>, <Value>{o.street}</Value>, <Value>{o.zipCity}</Value>, E-Mail: <Value>{o.email}</Value>
      </Section>
      <Section title="2. Welche Daten wir verarbeiten">
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          <li>Kontodaten: Benutzername, E-Mail-Adresse, Passwort (nur als Hash), optional Zwei-Faktor-Daten und SSH-Public-Keys.</li>
          <li>Bestelldaten: Produkt, Preis, Laufzeit, Zahlungsstatus und -referenz.</li>
          <li>Nutzungsdaten: Aktivitätsprotokoll zu deinem Konto und deinen Servern, Server-Inhalte (Dateien, Backups, Datenbanken), technische Protokolle (z. B. IP-Adresse, Zeitpunkt).</li>
          <li><Value>[weitere Datenkategorien ergänzen]</Value></li>
        </ul>
      </Section>
      <Section title="3. Zwecke und Rechtsgrundlagen">
        <Value>[Zwecke (Vertragserfüllung, Sicherheit, gesetzliche Aufbewahrung) und die jeweilige Rechtsgrundlage eintragen]</Value>
      </Section>
      <Section title="4. Empfänger und Auftragsverarbeiter">
        Hosting: <Value>{o.hosting}</Value><br />
        Zahlungsabwicklung: <Value>{o.paymentProvider}</Value><br />
        E-Mail-Versand: <Value>[Anbieter eintragen]</Value>
      </Section>
      <Section title="5. Speicherdauer">
        <Value>[Speicherfristen eintragen, z. B. Löschung nach Vertragsende, gesetzliche Aufbewahrungsfristen]</Value>
      </Section>
      <Section title="6. Lokaler Speicher im Browser">
        Diese Anwendung speichert im lokalen Speicher deines Browsers nur technisch notwendige Daten: das
        Anmelde-Token und Anzeigeeinstellungen (z. B. automatische Aktualisierung). Es werden keine Tracking-Cookies gesetzt.
        <br /><Value>[Bei Einsatz weiterer Dienste (Analyse, Zahlungsanbieter) diesen Abschnitt anpassen]</Value>
      </Section>
      <Section title="7. Deine Rechte">
        Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit
        und Widerspruch. Wende dich dafür an <Value>{o.email}</Value>. Du kannst dich außerdem bei der
        zuständigen Aufsichtsbehörde beschweren: <Value>{o.supervisoryAuthority}</Value>.
      </Section>
    </LegalLayout>
  );
}

export function AgbPage() {
  const o = OPERATOR;
  return (
    <LegalLayout title="Allgemeine Geschäftsbedingungen">
      <Section title="1. Geltungsbereich">
        Diese AGB gelten für alle Verträge zwischen <Value>{o.name}</Value> (Anbieter) und seinen Kunden über die
        Bereitstellung von Gameservern und zugehörigen Leistungen.
      </Section>
      <Section title="2. Vertragsschluss">
        <Value>[Beschreiben, wann der Vertrag zustande kommt (Bestellung, Bestätigung, Zahlungseingang, Bereitstellung)]</Value>
      </Section>
      <Section title="3. Leistungen">
        Art und Umfang der Leistung ergeben sich aus der Produktbeschreibung zum Zeitpunkt der Bestellung (Arbeitsspeicher,
        Speicherplatz, CPU-Anteil). <Value>[Verfügbarkeit, Wartungsfenster, Fair-Use-Regeln ergänzen]</Value>
      </Section>
      <Section title="4. Preise und Zahlung">
        Es gelten die im Shop angezeigten Preise für die jeweilige Laufzeit. Zahlungsweise und Fälligkeit:
        <Value>[eintragen]</Value>. Zahlungsanbieter: <Value>{o.paymentProvider}</Value>.
      </Section>
      <Section title="5. Laufzeit und Kündigung">
        Der Kunde kann aktive Bestellungen zum Ende der Laufzeit kündigen; der Server bleibt bis dahin nutzbar.
        <Value>[Verlängerung, Fristen, Folgen bei Zahlungsverzug (Sperrung, Löschung) eintragen]</Value>
      </Section>
      <Section title="6. Pflichten des Kunden">
        <Value>[Zulässige Nutzung, verbotene Inhalte, Sicherung der Zugangsdaten, Verantwortung für eigene Daten und Backups]</Value>
      </Section>
      <Section title="7. Haftung">
        <Value>[Haftungsregelung eintragen]</Value>
      </Section>
      <Section title="8. Widerrufsrecht">
        <Value>[Widerrufsbelehrung bzw. Hinweis auf den Ausschluss/Verfall des Widerrufsrechts eintragen]</Value>
      </Section>
      <Section title="9. Schlussbestimmungen">
        <Value>[Anwendbares Recht, Gerichtsstand, salvatorische Klausel]</Value>
      </Section>
    </LegalLayout>
  );
}
