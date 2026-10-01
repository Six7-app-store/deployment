# 0008 — Das Design v2 hat die Tokens als einzige Quelle, Light ist Standard

**Status:** Angenommen
**Datum:** 01.10.2026
**Beteiligt:** Katrin Seeberg
<!-- TODO: Weitere Beteiligte eintragen, bevor das ADR in die Abgabe geht. -->

## Kontext

Das Frontend hatte mit „Aero v1" bereits Tokens (`tokens.css`),
Komponentenklassen (`components.css`), einen Theme-Schalter und einen
Anti-Flash-Block in `index.html`. Daneben standen Farben, Radien, Schatten
und Schriftgrößen verstreut in Views und Komponenten, einzelne Seiten
brachten eigenes Scoped-CSS mit, und die Seitenhülle war inline in
`AppLayout` gebaut.

Das Redesign „Design v2" liegt als Vorlage vor (`design-vorlage-v2/`, Light
und Dark je Seite). Es ist keine neue Optik auf einem alten Gerüst, sondern
ein anderes Maßsystem: eigene Schriftskala, 36px-Controls, ein
Panel-Radius, Linien statt Schatten, Statusfarben nur als Punkt oder
Text, kein Rot für Auslastung.

Zu klären war, wie das dauerhaft konsistent bleibt, wenn mehrere Personen
und Agenten weiter an den Seiten arbeiten.

## Entscheidung

Wir führen das Design v2 über die bestehende Token-Schicht ein und
verbieten Werte außerhalb davon:

- **Tokens sind die einzige Quelle.** Farben, Radien, Linien, Schatten,
  Schriftskala, Layoutmaße stehen nur in `src/styles/tokens.css`.
  `tailwind.config.js` mappt per CSS-Variablen darauf und wiederholt keinen
  Wert. `tests/unit/design/tokens.spec.ts` prüft, dass Light und Dark
  dieselben Token-Namen haben, die Textpaare Kontrast ≥ 4,5:1 erreichen und
  außerhalb von `tokens.css` kein Farbliteral steht.
- **Light ist Standard, Dark wird per Schalter in der Topbar gewählt.** Die
  Wahl liegt in `localStorage['theme']` (mit try/catch), der Anti-Flash-Block
  setzt sie vor dem ersten Paint. Es gibt keine Anpassung an die
  Systemeinstellung.
- **Ein festes Komponenten-Set.** Seiten bauen aus `BaseButton`, `Card`,
  `PageHeader`, `DataTable`, `StatusBadge`/`Badge`, `AlertBox`, `EmptyState`,
  `FormField`, `BaseSelect`, `SegmentedControl`, `InfoList`, `StatStrip`,
  `MeterBar`, `PageToc`, `ActionMenu`, `Modal`, `Toast` und der Shell
  (`AppSidebar`, `AppTopbar`, `Breadcrumb`). Scoped-CSS gibt es nicht mehr.
- **Klassen stehen wörtlich im Code.** Klassen aus `@layer components`
  werden nie per Template-String gebaut (`alert-${tone}`); Tailwind erzeugt
  sie sonst nicht. Zustände laufen über feste Maps in der Komponente.

Logik, API, Routing und State bleiben unverändert. Zwei Abweichungen von der
Vorlage sind bewusst: Controls sind 36px hoch (die Vorlage rendert ohne
`box-sizing: border-box` effektiv 38px), und die Freigaben bleiben ein
Akkordeon pro App, weil ihre Daten erst beim Aufklappen geladen werden.

## Konsequenzen

Leichter:

- Ein Wert ändert sich an genau einer Stelle; Dark ist keine zweite
  Stylesheet-Pflege, sondern ein zweiter Satz Tokens.
- Der Kontrast-Test fängt kaputte Farbpaare, bevor sie im Browser auffallen.
- Neue Seiten werden aus dem Set zusammengesetzt statt neu gestaltet.

Schwerer:

- Ein neuer Farbton oder eine neue Schriftgröße verlangt ein Token (und
  einen Eintrag in beiden Themes), kein Literal „nur für diese Stelle".
- Kein Rot für Auslastung heißt: kritische Quotas fallen visuell weniger auf.
  Die Zahl und die Legende tragen die Aussage.
- Feste Maps statt Template-Strings heißen: ein neuer Ton muss in der
  Komponente ausdrücklich eingetragen werden.
- Snapshot-Tests (Hilfe, Deployment-Detail) hängen an Klassen und müssen bei
  Gestaltungsänderungen nach Diff-Prüfung neu geschrieben werden.

## Verworfene Alternativen

**Werte direkt in `tailwind.config.js`.** Hätte die Werte in der Config
festgeschrieben und Dark über `dark:`-Varianten an den einzelnen Klassen
gelöst. Verworfen, weil Light und Dark dann nicht an einer Stelle
nebeneinanderstehen und der Kontrast-Test sie nicht vergleichen könnte.

**Systemeinstellung (`prefers-color-scheme`) als Standard.** Die Vorlage
behandelt Light als Hauptansicht; Dark ist eine bewusste Wahl über den
Schalter in der Topbar.

**Neubau statt Weiterentwicklung.** Das Repo hatte mit Aero v1 schon Tokens,
Komponentenklassen, Theme-Schalter und Anti-Flash. Ein neuer
Styling-Ansatz hätte das ersetzt, ohne dass die Vorlage es verlangt.
