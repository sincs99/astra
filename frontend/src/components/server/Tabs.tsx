import { useRef } from "react";

export interface TabDef<K extends string> { key: K; label: string }

/** Tabs als Textlinks mit Unterstrich (design/DESIGN.md); Pfeiltasten wechseln, Inhalt über role=tabpanel. */
export function Tabs<K extends string>({ tabs, active, onChange, label, idPrefix }: {
  tabs: TabDef<K>[]; active: K; onChange: (key: K) => void; label: string; idPrefix: string;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const next = e.key === "ArrowRight" ? (i + 1) % tabs.length : e.key === "ArrowLeft" ? (i - 1 + tabs.length) % tabs.length
      : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault();
    onChange(tabs[next].key);
    refs.current[tabs[next].key]?.focus();
  };
  return (
    <div role="tablist" aria-label={label} className="tabs">
      {tabs.map((tab, i) => (
        <button key={tab.key} type="button" role="tab" id={`${idPrefix}-tab-${tab.key}`} className="tab"
          ref={(el) => { refs.current[tab.key] = el; }}
          aria-selected={active === tab.key} aria-controls={`${idPrefix}-panel`} tabIndex={active === tab.key ? 0 : -1}
          onClick={() => onChange(tab.key)} onKeyDown={(e) => onKey(e, i)}>
          {tab.label}
        </button>
      ))}
    </div>
  );
}
