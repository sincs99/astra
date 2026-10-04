import { PageLayout } from "../components/ui";
import { BillingTickCard } from "../components/BillingTickCard";
import { OverviewTiles } from "../components/admin/OverviewTiles";

/** Admin-Startseite: Umsatz, offene Bestellungen, Node-Auslastung, Billing-Tick und Zahlungsereignisse. */
export function AdminOverviewPage() {
  return (
    <PageLayout title="Übersicht" maxWidth={1100}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))", gap: 16, alignItems: "start" }}>
        <OverviewTiles />
        <div>
          <BillingTickCard />
        </div>
      </div>
    </PageLayout>
  );
}
