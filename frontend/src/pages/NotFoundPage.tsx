import { Link } from "react-router-dom";
import { t } from "../i18n";
import { PageLayout, EmptyState, linkStyle } from "../components/ui";

export function NotFoundPage() {
  return (
    <PageLayout title={t("shop.nf.title")}>
      <EmptyState message={t("shop.nf.text")} icon="🧭" />
      <p style={{ textAlign: "center" }}>
        <Link to="/" style={linkStyle}>{t("shop.nf.home")}</Link>
      </p>
    </PageLayout>
  );
}
