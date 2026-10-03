import { Link } from "react-router-dom";
import { PageLayout, EmptyState, linkStyle } from "../components/ui";

export function NotFoundPage() {
  return (
    <PageLayout title="Seite nicht gefunden">
      <EmptyState message="Diese Seite existiert nicht." icon="🧭" />
      <p style={{ textAlign: "center" }}>
        <Link to="/" style={linkStyle}>Zum Dashboard</Link>
      </p>
    </PageLayout>
  );
}
