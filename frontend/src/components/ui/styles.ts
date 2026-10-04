/**
 * Gemeinsame Styles fuer konsistentes UI (M26).
 */

export const cardStyle: React.CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 16,
  marginBottom: 16,
  backgroundColor: "var(--bg-card)",
};

export const inputStyle: React.CSSProperties = {
  padding: "6px 12px",
  minHeight: "var(--control-h)",
  boxSizing: "border-box",
  width: "100%",
  borderRadius: "var(--radius-btn)",
  border: "1px solid var(--border)",
  backgroundColor: "var(--surface-2)",
  color: "var(--text)",
  fontSize: 14,
  lineHeight: 1.5,
};

export const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: 4,
  fontWeight: 600,
  fontSize: 13,
  color: "var(--fg-soft)",
};

export const btnPrimary: React.CSSProperties = {
  padding: "8px 20px",
  cursor: "pointer",
  whiteSpace: "nowrap",
  minHeight: "var(--control-h)",
  borderRadius: "var(--radius-btn)",
  border: "none",
  backgroundColor: "var(--accent)",
  color: "var(--on-accent)",
  fontSize: 14,
  fontWeight: 500,
};

export const btnDanger: React.CSSProperties = {
  padding: "8px 20px",
  cursor: "pointer",
  whiteSpace: "nowrap",
  minHeight: "var(--control-h)",
  borderRadius: "var(--radius-btn)",
  border: "none",
  backgroundColor: "var(--danger)",
  color: "var(--on-danger)",
  fontSize: 14,
  fontWeight: 500,
};

export const btnDefault: React.CSSProperties = {
  padding: "8px 20px",
  cursor: "pointer",
  whiteSpace: "nowrap",
  minHeight: "var(--control-h)",
  borderRadius: "var(--radius-btn)",
  border: "1px solid var(--border)",
  backgroundColor: "var(--surface-2)",
  color: "var(--text)",
  fontSize: 14,
  fontWeight: 500,
};

export const thStyle: React.CSSProperties = {
  padding: 10,
  textAlign: "left",
  borderBottom: "2px solid var(--border)",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--fg-soft)",
  whiteSpace: "nowrap",
};

export const tdStyle: React.CSSProperties = {
  padding: 10,
  verticalAlign: "middle",
  borderBottom: "1px solid var(--bg-subtle)",
};

export const linkStyle: React.CSSProperties = {
  color: "var(--c-blue)",
  textDecoration: "none",
  fontWeight: 500,
};
