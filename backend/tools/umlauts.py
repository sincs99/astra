"""Umlaute in Kundenmeldungen (M50).

Kunden sehen API-Meldungen aus Auth, Client, Billing und den Services dahinter. Diese sollen echte Umlaute
tragen ("Ungültige Anmeldedaten", nicht "Ungueltige Anmeldedaten"). Das Werkzeug arbeitet mit einem festen
Wörterbuch ganzer Wörter und fasst nur Meldungstexte an: keine Docstrings, keine Kommentare, keine Log-Aufrufe.
Wörter wie "neue", "zuerst", "aktuell", "Blueprint" oder "queue" sind kein Ersatz-Kandidat und bleiben unberührt.

    python tools/umlauts.py            # Trockenlauf: zeigt noch vorhandene ASCII-Schreibweisen
    python tools/umlauts.py --write    # schreibt die Korrekturen in die Dateien

Neue Wörter einfach in WORDS ergänzen. `test_m50.py` schlägt fehl, wenn in den Kundendateien noch eine
Schreibweise aus dem Wörterbuch steckt.
"""
import ast, glob, os, re, sys

WORDS = {
 "abhaengiger":"abhängiger","aendern":"ändern","Aendert":"Ändert","Aenderung":"Änderung","aenderungen":"änderungen",
 "Aufraeumen":"Aufräumen","Ausfuehrung":"Ausführung","ausgefuehrt":"ausgeführt","ausgeloest":"ausgelöst",
 "bestaetige":"bestätige","bestaetigen":"bestätigen","bestaetigt":"bestätigt","Bestaetigt":"Bestätigt",
 "Bestaetigung":"Bestätigung","Bestaetigungs":"Bestätigungs","Binaerdaten":"Binärdaten","Binaerformat":"Binärformat",
 "Eintraege":"Einträge","Enthaelt":"Enthält","Fremdschluessel":"Fremdschlüssel","Fuegt":"Fügt","Fuehrt":"Führt",
 "fuer":"für","Fuer":"Für","geaendert":"geändert","gehoert":"gehört","gekuendigte":"gekündigte","gekuendigt":"gekündigt",
 "geloescht":"gelöscht","geprueft":"geprüft","gewaehlt":"gewählt","gueltig":"gültig","gueltige":"gültige",
 "gueltigen":"gültigen","gueltiges":"gültiges","haelt":"hält","hinzugefuegt":"hinzugefügt","hinzufuegen":"hinzufügen",
 "ausfuehren":"ausführen","hoechstens":"höchstens","Kapazitaet":"Kapazität","koennen":"können","Kuendigung":"Kündigung",
 "laengenpraefixierten":"längenpräfixierten","laenger":"länger","laeuft":"läuft","Loeschen":"Löschen","loeschen":"löschen",
 "Loeschhinweis":"Löschhinweis","Loescht":"Löscht","loescht":"löscht","Loeschung":"Löschung","Loest":"Löst","loest":"löst",
 "moechte":"möchte","moeglich":"möglich","naechsten":"nächsten","noetig":"nötig","Noetig":"Nötig",
 "Oeffentlich":"Öffentlich","Oeffentliche":"Öffentliche","pruefen":"prüfen","Prueft":"Prüft","prueft":"prüft",
 "Rueckgabe":"Rückgabe","schluesselbasierte":"schlüsselbasierte","Signaturpruefung":"Signaturprüfung",
 "spaeter":"später","spaetere":"spätere","Sperrpruefung":"Sperrprüfung","tatsaechlicher":"tatsächlicher",
 "ueber":"über","ueberein":"überein","ueberfaellig":"überfällig","ueberfaellige":"überfällige",
 "Ueberfaellige":"Überfällige","ueberfaelliger":"überfälliger","Ueberweisung":"Überweisung","unbestaetigt":"unbestätigt",
 "ungueltig":"ungültig","Ungueltige":"Ungültige","Ungueltiger":"Ungültiger","ungueltiger":"ungültiger",
 "Ungueltiges":"Ungültiges","ungueltiges":"ungültiges","Unterstuetzt":"Unterstützt","unterstuetzt":"unterstützt",
 "Unterstuetzte":"Unterstützte","unterstuetzter":"unterstützter","veraendern":"verändern","verfuegbar":"verfügbar",
 "verlaengern":"verlängern","Verlaengert":"Verlängert","verlaengert":"verlängert","Verlaengerung":"Verlängerung",
 "Verraet":"Verrät","verspaetete":"verspätete","vollstaendig":"vollständig","vollstaendige":"vollständige",
 "Vorgaenge":"Vorgänge","Waehrung":"Währung","zaehlt":"zählt","Zugaenge":"Zugänge","zugehoerigen":"zugehörigen",
 "zurueck":"zurück","zurueckgegeben":"zurückgegeben","zurueckgesetzt":"zurückgesetzt","zuruecksetzen":"zurücksetzen",
 "Passwoerter":"Passwörter","zusaetzlich":"zusätzlich","Zurueck":"Zurück","Ueber":"Über",
}
PATTERN = re.compile(r"\b(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")\b")
LOG_ATTRS = {"debug","info","warning","warn","error","critical","exception","log"}

def fix(text):
    return PATTERN.sub(lambda m: WORDS[m.group(1)], text)

def is_log_call(node):
    f = node.func
    return isinstance(f, ast.Attribute) and f.attr in LOG_ATTRS

def collect(tree):
    """Knoten (Constant/JoinedStr) mit Meldungstexten, ohne Docstrings und Log-Aufrufe."""
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                skip.add(id(body[0].value))
        if isinstance(node, ast.Call) and is_log_call(node):
            for sub in ast.walk(node):
                skip.add(id(sub))
    out = []
    def visit(node, inside_joined=False):
        if isinstance(node, ast.JoinedStr) and id(node) not in skip and not inside_joined:
            out.append(node); return
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip and not inside_joined:
            out.append(node); return
        for child in ast.iter_child_nodes(node):
            visit(child, inside_joined or isinstance(node, ast.JoinedStr))
    visit(tree)
    return out

def process(path, write):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    lines = src.encode("utf-8").split(b"\n")
    starts = [0]
    for l in lines: starts.append(starts[-1] + len(l) + 1)
    data = src.encode("utf-8")
    edits = []
    for n in collect(tree):
        a = starts[n.lineno - 1] + n.col_offset
        b = starts[n.end_lineno - 1] + n.end_col_offset
        seg = data[a:b].decode("utf-8")
        new = fix(seg)
        if new != seg:
            edits.append((a, b, new))
    changed = len(edits)
    for a, b, new in sorted(edits, reverse=True):
        data = data[:a] + new.encode("utf-8") + data[b:]
    if changed and write:
        open(path, "wb").write(data)
    return changed

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOMER_FACING = [
    "app/api/auth/routes.py", "app/api/client/routes.py", "app/api/payments/routes.py",
    "app/domain/billing/*.py", "app/domain/accounts/*.py", "app/domain/auth/*.py",
    "app/domain/instances/service.py", "app/domain/backups/service.py", "app/domain/databases/service.py",
    "app/domain/collaborators/*.py", "app/domain/routines/*.py", "app/domain/ssh_keys/*.py",
    "app/infrastructure/mail.py",
]


def customer_files():
    out = []
    for pattern in CUSTOMER_FACING:
        out += glob.glob(os.path.join(BACKEND, pattern))
    return sorted(set(out))


if __name__ == "__main__":
    write = "--write" in sys.argv
    files = [f for f in sys.argv[1:] if f != "--write"] or customer_files()
    total = 0
    for f in files:
        n = process(f, write)
        if n: print(f"{n:3d}  {f}")
        total += n
    print("Stellen:", total, "(geschrieben)" if write else "(Trockenlauf)")
