# Globale Projektregeln

## Reference-Ordner ist schreibgeschützt

Der Ordner `reference/` und alle darin enthaltenen Dateien dürfen **ausschließlich gelesen** werden.

- **NIEMALS** Dateien in `reference/` erstellen, bearbeiten, umbenennen oder löschen.
- Der Ordner dient als Referenz-Codebasis und muss unverändert bleiben.
- Beim Lesen von Dateien aus `reference/` ist `read_file` erlaubt. Alle schreibenden Operationen (`write_to_file`, `apply_diff`, `execute_command` mit schreibenden Befehlen) auf Dateien in `reference/` sind **verboten**.
