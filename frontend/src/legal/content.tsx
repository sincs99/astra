import type { ReactNode } from "react";
import { type Operator, isPlaceholder } from "./operator";

/**
 * Inhalte der Rechtsseiten je Rechtsraum (DE/CH) und Sprache (Deutsch/Englisch).
 * Die Texte sind eine Struktur mit Platzhaltern und ersetzen keine Rechtsberatung; der Betreiber muss sie prüfen.
 */
export interface LegalSection { title: string; body: ReactNode }
export interface LegalDoc { title: string; sections: LegalSection[] }
export interface LegalContext { en: boolean; ch: boolean; o: Operator }

/** Betreiber-Wert; offene Platzhalter werden hervorgehoben. */
export function Value({ children }: { children: string }) {
  if (!isPlaceholder(children)) return <>{children}</>;
  return (
    <mark style={{ background: "var(--warn-soft)", color: "var(--text)", padding: "0 4px", borderRadius: 3 }}>{children}</mark>
  );
}

/** Platzhalter für Angaben, die der Betreiber im Text selbst ergänzt. */
const Fill = ({ children }: { children: string }) => <Value>{children}</Value>;
const ul: React.CSSProperties = { margin: 0, paddingLeft: 20 };

export function impressum({ en, ch, o }: LegalContext): LegalDoc {
  const V = Value;
  if (ch) {
    return {
      title: en ? "Provider identification / contact" : "Anbieterkennzeichnung / Kontakt",
      sections: [
        {
          title: en ? "Provider" : "Anbieter",
          body: (
            <p style={{ margin: 0 }}>
              <V>{o.name}</V> (<V>{o.legalForm}</V>)<br />
              <V>{o.street}</V><br />
              <V>{o.zipCity}</V><br />
              <V>{o.country}</V>
            </p>
          ),
        },
        {
          title: en ? "Contact" : "Kontakt",
          body: <p style={{ margin: 0 }}>{en ? "Email" : "E-Mail"}: <V>{o.email}</V>{" "}<br />{en ? "Phone (optional)" : "Telefon (optional)"}: <V>{o.phone}</V></p>,
        },
        {
          title: en ? "Register and tax" : "Register und Steuern",
          body: (
            <p style={{ margin: 0 }}>
              {en ? "Commercial register (if registered)" : "Handelsregister (falls eingetragen)"}: <V>{o.register}</V><br />
              {en ? "UID / VAT number (if any)" : "UID / MWST-Nummer (falls vorhanden)"}: <V>{o.vatId}</V>
            </p>
          ),
        },
        {
          title: en ? "Legal basis" : "Rechtsgrundlage",
          body: en
            ? "Identity and contact details including an email address are given in accordance with Art. 3 para. 1 lit. s of the Swiss Federal Act against Unfair Competition (UWG)."
            : "Diese Angaben (Identität und Kontaktadresse inklusive E-Mail) erfolgen nach Art. 3 Abs. 1 lit. s des Bundesgesetzes gegen den unlauteren Wettbewerb (UWG).",
        },
      ],
    };
  }
  return {
    title: en ? "Legal notice" : "Impressum",
    sections: [
      {
        title: en ? "Provider" : "Anbieter",
        body: (
          <p style={{ margin: 0 }}>
            <V>{o.name}</V> (<V>{o.legalForm}</V>)<br />
            <V>{o.street}</V><br />
            <V>{o.zipCity}</V><br />
            <V>{o.country}</V>
          </p>
        ),
      },
      {
        title: en ? "Contact" : "Kontakt",
        body: <p style={{ margin: 0 }}>{en ? "Email" : "E-Mail"}: <V>{o.email}</V><br />{en ? "Phone" : "Telefon"}: <V>{o.phone}</V></p>,
      },
      { title: en ? "Represented by" : "Vertretungsberechtigt", body: <V>{o.representative}</V> },
      {
        title: en ? "Register and taxes" : "Register und Steuern",
        body: (
          <p style={{ margin: 0 }}>
            {en ? "Commercial register" : "Handelsregister"}: <V>{o.register}</V><br />
            {en ? "VAT identification number" : "Umsatzsteuer-Identifikationsnummer"}: <V>{o.vatId}</V>
          </p>
        ),
      },
    ],
  };
}

export function datenschutz({ en, ch, o }: LegalContext): LegalDoc {
  const V = Value;
  const accountData = en
    ? "Account data: username, email address, password (as a hash only), optionally two-factor data and SSH public keys."
    : "Kontodaten: Benutzername, E-Mail-Adresse, Passwort (nur als Hash), optional Zwei-Faktor-Daten und SSH-Public-Keys.";
  const orderData = en
    ? "Order data: product, price, term, payment status and reference."
    : "Bestelldaten: Produkt, Preis, Laufzeit, Zahlungsstatus und -referenz.";
  const usageData = en
    ? "Usage data: activity log for your account and servers, server contents (files, backups, databases), technical logs (e.g. IP address, time)."
    : "Nutzungsdaten: Aktivitätsprotokoll zu deinem Konto und deinen Servern, Server-Inhalte (Dateien, Backups, Datenbanken), technische Protokolle (z. B. IP-Adresse, Zeitpunkt).";
  const browserStorage = (
    <>
      {en
        ? "This application stores only technically necessary data in your browser's local storage: the sign-in token and display settings (e.g. language, colour scheme, automatic refresh). No tracking cookies are set."
        : "Diese Anwendung speichert im lokalen Speicher deines Browsers nur technisch notwendige Daten: das Anmelde-Token und Anzeigeeinstellungen (z. B. Sprache, Farbschema, automatische Aktualisierung). Es werden keine Tracking-Cookies gesetzt."}
      <br /><Fill>{en ? "[Adjust this section if further services (analytics, payment provider) are used]" : "[Bei Einsatz weiterer Dienste (Analyse, Zahlungsanbieter) diesen Abschnitt anpassen]"}</Fill>
    </>
  );

  if (ch) {
    return {
      title: en ? "Privacy policy" : "Datenschutzerklärung",
      sections: [
        {
          title: en ? "1. Controller" : "1. Verantwortlicher",
          body: <><V>{o.name}</V>, <V>{o.street}</V>, <V>{o.zipCity}</V>, <V>{o.country}</V>, {en ? "email" : "E-Mail"}: <V>{o.email}</V>. {en ? "This policy follows the Swiss Federal Act on Data Protection (FADP, revised 2023)." : "Diese Erklärung richtet sich nach dem Schweizer Bundesgesetz über den Datenschutz (DSG, revidiert 2023)."}</>,
        },
        {
          title: en ? "2. Which data we process" : "2. Welche Daten wir bearbeiten",
          body: (
            <ul style={ul}>
              <li>{accountData}</li>
              <li>{orderData}</li>
              <li>{usageData}</li>
              <li><Fill>{en ? "[add further data categories]" : "[weitere Datenkategorien ergänzen]"}</Fill></li>
            </ul>
          ),
        },
        {
          title: en ? "3. Purposes" : "3. Zwecke",
          body: en
            ? "We process personal data to provide and bill the contracted services (game servers and related functions), to operate and secure the platform and prevent abuse, to communicate with you about your account and orders, and to meet legal obligations (e.g. bookkeeping). Processing is lawful, in good faith and proportionate, and limited to these purposes."
            : "Wir bearbeiten Personendaten, um die vereinbarten Leistungen (Gameserver und zugehörige Funktionen) zu erbringen und abzurechnen, die Plattform zu betreiben und zu sichern, Missbrauch zu verhindern, mit dir zu Konto und Bestellungen zu kommunizieren und gesetzliche Pflichten (z. B. Buchführung) zu erfüllen. Die Bearbeitung erfolgt rechtmässig, nach Treu und Glauben, verhältnismässig und nur zu diesen Zwecken.",
        },
        {
          title: en ? "4. Recipients and processors" : "4. Empfänger und Auftragsbearbeiter",
          body: (
            <>
              {en ? "Hosting" : "Hosting"}: <V>{o.hosting}</V><br />
              {en ? "Payment processing" : "Zahlungsabwicklung"}: <V>{o.paymentProvider}</V><br />
              {en ? "Email delivery" : "E-Mail-Versand"}: <Fill>{en ? "[enter provider]" : "[Anbieter eintragen]"}</Fill><br />
              {en
                ? "Spam protection (only if enabled): Cloudflare Turnstile or hCaptcha. Your browser then connects to the provider when you register or request a password reset."
                : "Missbrauchsschutz (nur wenn aktiviert): Cloudflare Turnstile oder hCaptcha. Dein Browser verbindet sich dann bei Registrierung und Passwort-Zurücksetzung mit dem Anbieter."}
              <br />
              {en ? "Disclosure abroad" : "Bekanntgabe ins Ausland"}: <Fill>{en ? "[countries, safeguards (Art. 16 FADP)]" : "[Länder und Garantien eintragen (Art. 16 DSG)]"}</Fill>
            </>
          ),
        },
        {
          title: en ? "5. Retention" : "5. Aufbewahrung",
          body: (
            <>
              {en
                ? "Accounting records and invoices are kept for ten years (Art. 958f Swiss Code of Obligations). Other data is deleted when it is no longer needed for the purposes above, e.g. after the contract has ended."
                : "Buchungsbelege und Rechnungen werden zehn Jahre aufbewahrt (Art. 958f OR). Übrige Daten werden gelöscht, sobald sie für die genannten Zwecke nicht mehr erforderlich sind, z. B. nach Vertragsende."}
              <br /><Fill>{en ? "[add specific retention periods]" : "[weitere Aufbewahrungsfristen eintragen]"}</Fill>
            </>
          ),
        },
        { title: en ? "6. Local storage in the browser" : "6. Lokaler Speicher im Browser", body: browserStorage },
        {
          title: en ? "7. Your rights" : "7. Deine Rechte",
          body: (
            <>
              {en
                ? "You have the right to information about your data, to correction, deletion, restriction of processing, to data release or transfer, and to object to processing. Contact "
                : "Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Bearbeitung, Herausgabe bzw. Übertragung deiner Daten und auf Widerspruch. Wende dich dafür an "}
              <V>{o.email}</V>.{" "}
              {en
                ? "You may also lodge a complaint with the Federal Data Protection and Information Commissioner (FDPIC / EDÖB), www.edoeb.admin.ch."
                : "Du kannst dich ausserdem beim Eidgenössischen Datenschutz- und Öffentlichkeitsbeauftragten (EDÖB), www.edoeb.admin.ch, beschweren."}
            </>
          ),
        },
        {
          title: en ? "8. Customers in the EU" : "8. Kunden in der EU",
          body: en
            ? "For customers in the European Union, the GDPR applies in addition, insofar as its territorial scope covers our processing."
            : "Für Kunden in der EU gilt zusätzlich die DSGVO, soweit ihr räumlicher Anwendungsbereich unsere Bearbeitung erfasst.",
        },
      ],
    };
  }

  return {
    title: en ? "Privacy policy" : "Datenschutzerklärung",
    sections: [
      {
        title: en ? "1. Controller" : "1. Verantwortlicher",
        body: <><V>{o.name}</V>, <V>{o.street}</V>, <V>{o.zipCity}</V>, {en ? "email" : "E-Mail"}: <V>{o.email}</V></>,
      },
      {
        title: en ? "2. Which data we process" : "2. Welche Daten wir verarbeiten",
        body: (
          <ul style={ul}>
            <li>{accountData}</li>
            <li>{orderData}</li>
            <li>{usageData}</li>
            <li><Fill>{en ? "[add further data categories]" : "[weitere Datenkategorien ergänzen]"}</Fill></li>
          </ul>
        ),
      },
      {
        title: en ? "3. Purposes and legal bases" : "3. Zwecke und Rechtsgrundlagen",
        body: <Fill>{en ? "[enter purposes (contract performance, security, statutory retention) and the respective legal basis]" : "[Zwecke (Vertragserfüllung, Sicherheit, gesetzliche Aufbewahrung) und die jeweilige Rechtsgrundlage eintragen]"}</Fill>,
      },
      {
        title: en ? "4. Recipients and processors" : "4. Empfänger und Auftragsverarbeiter",
        body: (
          <>
            Hosting: <V>{o.hosting}</V><br />
            {en ? "Payment processing" : "Zahlungsabwicklung"}: <V>{o.paymentProvider}</V><br />
            {en ? "Email delivery" : "E-Mail-Versand"}: <Fill>{en ? "[enter provider]" : "[Anbieter eintragen]"}</Fill>
          </>
        ),
      },
      {
        title: en ? "5. Retention" : "5. Speicherdauer",
        body: <Fill>{en ? "[enter retention periods, e.g. deletion after the contract ends, statutory retention periods]" : "[Speicherfristen eintragen, z. B. Löschung nach Vertragsende, gesetzliche Aufbewahrungsfristen]"}</Fill>,
      },
      { title: en ? "6. Local storage in the browser" : "6. Lokaler Speicher im Browser", body: browserStorage },
      {
        title: en ? "7. Your rights" : "7. Deine Rechte",
        body: (
          <>
            {en
              ? "You have the right to access, rectification, erasure, restriction of processing, data portability and to object. Contact "
              : "Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch. Wende dich dafür an "}
            <V>{o.email}</V>.{" "}
            {en ? "You can also complain to the competent supervisory authority: " : "Du kannst dich außerdem bei der zuständigen Aufsichtsbehörde beschweren: "}
            <V>{o.supervisoryAuthority}</V>.
          </>
        ),
      },
    ],
  };
}

export function agb({ en, ch, o }: LegalContext): LegalDoc {
  const V = Value;
  const scope = (
    <>
      {en ? "These terms apply to all contracts between " : "Diese AGB gelten für alle Verträge zwischen "}
      <V>{o.name}</V>
      {en ? " (provider) and its customers for the provision of game servers and related services." : " (Anbieter) und seinen Kunden über die Bereitstellung von Gameservern und zugehörigen Leistungen."}
    </>
  );
  const contract = <Fill>{en ? "[describe when the contract is concluded (order, confirmation, payment received, provisioning)]" : "[Beschreiben, wann der Vertrag zustande kommt (Bestellung, Bestätigung, Zahlungseingang, Bereitstellung)]"}</Fill>;
  const services = (
    <>
      {en
        ? "Type and scope of the service result from the product description at the time of the order (memory, storage, CPU share). "
        : "Art und Umfang der Leistung ergeben sich aus der Produktbeschreibung zum Zeitpunkt der Bestellung (Arbeitsspeicher, Speicherplatz, CPU-Anteil). "}
      <Fill>{en ? "[add availability, maintenance windows, fair-use rules]" : "[Verfügbarkeit, Wartungsfenster, Fair-Use-Regeln ergänzen]"}</Fill>
    </>
  );
  const prices = (
    <>
      {en
        ? "The prices shown in the shop for the respective term apply"
        : "Es gelten die im Shop angezeigten Preise für die jeweilige Laufzeit"}
      {ch ? (en ? " (in Swiss francs unless stated otherwise; VAT is shown where it applies)" : " (in Schweizer Franken, sofern nicht anders angegeben; die MWST wird ausgewiesen, soweit sie anfällt)") : ""}
      {en ? ". Payment method and due date: " : ". Zahlungsweise und Fälligkeit: "}
      <Fill>{en ? "[enter]" : "[eintragen]"}</Fill>
      {en ? ". Payment provider: " : ". Zahlungsanbieter: "}
      <V>{o.paymentProvider}</V>.
    </>
  );
  const term = (
    <>
      {en
        ? "Customers can cancel active orders at the end of the term; the server stays usable until then. "
        : "Der Kunde kann aktive Bestellungen zum Ende der Laufzeit kündigen; der Server bleibt bis dahin nutzbar. "}
      <Fill>{en ? "[enter renewal, notice periods, consequences of late payment (suspension, deletion)]" : "[Verlängerung, Fristen, Folgen bei Zahlungsverzug (Sperrung, Löschung) eintragen]"}</Fill>
    </>
  );
  const duties = <Fill>{en ? "[permitted use, prohibited content, safeguarding credentials, responsibility for own data and backups]" : "[Zulässige Nutzung, verbotene Inhalte, Sicherung der Zugangsdaten, Verantwortung für eigene Daten und Backups]"}</Fill>;
  const liability = <Fill>{en ? "[enter liability provisions]" : "[Haftungsregelung eintragen]"}</Fill>;

  if (ch) {
    return {
      title: en ? "Terms and conditions" : "Allgemeine Geschäftsbedingungen",
      sections: [
        { title: en ? "1. Scope" : "1. Geltungsbereich", body: scope },
        { title: en ? "2. Conclusion of contract" : "2. Vertragsschluss", body: contract },
        { title: en ? "3. Services" : "3. Leistungen", body: services },
        { title: en ? "4. Prices and payment" : "4. Preise und Zahlung", body: prices },
        { title: en ? "5. Term and cancellation" : "5. Laufzeit und Kündigung", body: term },
        { title: en ? "6. Customer obligations" : "6. Pflichten des Kunden", body: duties },
        { title: en ? "7. Liability" : "7. Haftung", body: liability },
        {
          title: en ? "8. Start of service, no right of withdrawal" : "8. Leistungsbeginn, kein Widerrufsrecht",
          body: en
            ? "The service starts immediately once payment has been received (or the order has been confirmed). In Switzerland there is no general right of withdrawal for online purchases; the order is therefore binding as soon as it is placed. This notice is also shown before every purchase."
            : "Die Leistung beginnt sofort nach Zahlungseingang (bzw. Bestätigung der Bestellung). In der Schweiz besteht für Online-Käufe kein allgemeines Widerrufsrecht; die Bestellung ist daher mit dem Absenden verbindlich. Dieser Hinweis wird auch vor jedem Kauf angezeigt.",
        },
        {
          title: en ? "9. Applicable law and jurisdiction" : "9. Anwendbares Recht und Gerichtsstand",
          body: en
            ? "Swiss law applies. The place of jurisdiction is the registered office of the provider, unless mandatory law provides for another jurisdiction."
            : "Es gilt Schweizer Recht. Gerichtsstand ist der Sitz des Anbieters, soweit zwingendes Recht keinen anderen Gerichtsstand vorsieht.",
        },
      ],
    };
  }
  return {
    title: en ? "Terms and conditions" : "Allgemeine Geschäftsbedingungen",
    sections: [
      { title: en ? "1. Scope" : "1. Geltungsbereich", body: scope },
      { title: en ? "2. Conclusion of contract" : "2. Vertragsschluss", body: contract },
      { title: en ? "3. Services" : "3. Leistungen", body: services },
      { title: en ? "4. Prices and payment" : "4. Preise und Zahlung", body: prices },
      { title: en ? "5. Term and cancellation" : "5. Laufzeit und Kündigung", body: term },
      { title: en ? "6. Customer obligations" : "6. Pflichten des Kunden", body: duties },
      { title: en ? "7. Liability" : "7. Haftung", body: liability },
      {
        title: en ? "8. Right of withdrawal" : "8. Widerrufsrecht",
        body: <Fill>{en ? "[enter the withdrawal notice or the notice on exclusion/expiry of the right of withdrawal]" : "[Widerrufsbelehrung bzw. Hinweis auf den Ausschluss/Verfall des Widerrufsrechts eintragen]"}</Fill>,
      },
      {
        title: en ? "9. Final provisions" : "9. Schlussbestimmungen",
        body: <Fill>{en ? "[applicable law, place of jurisdiction, severability clause]" : "[Anwendbares Recht, Gerichtsstand, salvatorische Klausel]"}</Fill>,
      },
    ],
  };
}
