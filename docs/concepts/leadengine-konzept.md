# LeadEngine Konzept

## 1. Zweck

Die LeadEngine ist der zentrale Motor von Target Radar.

Sie erzeugt aus einem Suchprofil viele kleine, praezise Suchanfragen, sammelt Kandidaten aus externen Quellen, filtert unpassende Treffer, dedupliziert Domains und uebergibt nur brauchbare Targets an die weitere Pipeline.

Die LeadEngine ersetzt nicht das Scoring und erzeugt keine Drafts. Sie entscheidet zuerst nur:

- Welche Queries werden gestellt?
- Welche Quellen werden genutzt?
- Welche Treffer sind Kandidaten?
- Welche Treffer werden blockiert oder verworfen?
- Welche Domains werden als Targets importiert?

## 2. Grundidee

Die bisherige SERP-Discovery baut eine grosse Query aus allen Attributen eines Suchprofils.

Das ist fuer echte Suche unguenstig, weil Provider wie Brave kurze Query-Limits haben und lange Queries oft unscharfe Ergebnisse liefern. Stattdessen erzeugt die LeadEngine kontrolliert viele kurze Queries aus Attribut-Kombinationen.

Nicht die Query-Laenge wird groesser, sondern die Anzahl relevanter Suchversuche.

## 3. Arbeitsweise

```text
Suchprofil
  -> Attribute normalisieren
  -> Query-Kandidaten erzeugen
  -> Query-Budget anwenden
  -> Provider ausfuehren
  -> SERP-Ergebnisse speichern
  -> Domain-Denylist anwenden
  -> Ergebnisse deduplizieren
  -> Targets importieren
  -> Pipeline/Scoring starten oder zur Review bereitstellen
```

## 4. Eingaben

Die LeadEngine nutzt die bestehenden Suchprofil-Attribute:

- Rollenbegriffe
- Tech-Keywords
- Branchenbegriffe
- Regionen
- Ausschlussbegriffe
- optionaler manueller Query-Override

Zusaetzlich bekommt sie eigene Laufzeitparameter:

- `request_budget`: maximale Anzahl Provider-Requests pro Lauf
- `results_per_query`: Anzahl Treffer pro Query
- `provider`: z. B. `brave`
- `mode`: z. B. `explore`, `focused`, `refresh`
- `auto_import`: ob brauchbare Treffer direkt als Targets importiert werden

## 5. Kontrolliertes kartesisches Produkt

Ein vollstaendiges kartesisches Produkt aller Attribute waere zu gross und zu verrauscht.

Beispiel:

```text
6 Rollen x 6 Techs x 6 Branchen x 7 Regionen x 4 Intents = 6048 Queries
```

Die LeadEngine nutzt deshalb Query-Templates, die nur sinnvolle Kombinationen bilden.

## 6. Query-Templates

Templates sind nicht global gleich. Die LeadEngine waehlt ein Template-Set anhand von Preset, Suchprofiltyp und optionalem Laufparameter.

MVP-Entscheidung:

- `template_set` kann im LeadEngine-Lauf gesetzt werden.
- Wenn kein `template_set` gesetzt ist, wird es aus dem aktiven Preset und den Suchprofilbegriffen abgeleitet.
- Fuer den ersten MVP reichen `application_general` und `application_student`.
- Weitere Sets wie `freelance`, `sales` oder `supplier_search` werden spaeter ergaenzt.

### `application_student`

Passend fuer Werkstudenten, Praktika, Abschlussarbeiten und studentische Hilfskraft.

```text
{role} {region} Karriere
{role} {region} Jobs
{role} {tech} {region}
{role} {industry} {region}
{role} {tech} Karriere
{role} {region} Unternehmen
{tech} {industry} {region}
```

Beispiele fuer das Werkstudentinnen-Profil:

```text
"Werkstudentin" IT Essen Karriere
"Werkstudent" Softwareentwicklung Ruhrgebiet Jobs
"Studentische Hilfskraft" Informatik Essen Unternehmen
"Werkstudent" Webentwicklung Bochum Karriere
"Working Student IT" Datenbanken Essen
"Junior IT" IT Dienstleister Essen Karriere
```

### `application_general`

Passend fuer normale Bewerbungsprofile.

```text
{role} {region} Karriere
{role} {tech} {region}
{role} {industry} {region}
{role} {region} Unternehmen
{tech} {region} Karriere
```

### Spaetere Template-Sets

Freelance-Profile wuerden andere Intents brauchen:

```text
{role} Freelancer {region}
{tech} Freelancer Projekt {region}
{industry} externer Entwickler {region}
```

Sales-/Lead-Profile wuerden keine Karriere-Intents nutzen:

```text
{industry} Unternehmen {region}
{pain_keyword} Dienstleister {region}
{target_group} Software {region}
```

## 7. Priorisierung

Nicht jede Kombination ist gleich wichtig.

Die LeadEngine bewertet Query-Kandidaten vor dem Ausfuehren:

- Rolle + Region hat hohe Prioritaet.
- Rolle + Tech + Region hat hohe Prioritaet.
- Rolle + Branche + Region hat mittlere Prioritaet.
- Tech + Branche + Region ist ergaenzend.
- Queries mit zu vielen generischen Begriffen werden abgewertet.
- Bereits ausgefuehrte oder sehr aehnliche Queries werden uebersprungen.

Dadurch kann ein Lauf mit 100 Requests trotzdem kontrolliert bleiben.

## 8. Query-Budget

Jeder Lauf hat ein festes Budget.

Beispiel fuer private Nutzung:

```text
request_budget = 100
results_per_query = 10
max_raw_results = 1000
```

Das Budget wird nicht gleichmaessig blind verteilt, sondern nach Prioritaet:

```text
60 Prozent: Rolle + Region / Rolle + Tech + Region
25 Prozent: Rolle + Branche + Region
15 Prozent: Explore-Queries und Varianten
```

## 9. Provider-Abstraktion

Die LeadEngine bleibt provider-neutral.

V1:

- `mock`: Tests und Demo
- `brave`: echte private Suche

Spaeter optional:

- Google-SERP-Drittanbieter
- Bing
- spezialisierte Quellen
- lokale Listen
- Branchenverzeichnisse

Wichtig: Provider sind nur Datenquellen. Die LeadEngine definiert die Query-Strategie, Normalisierung und Filterlogik.

## 10. Provider-Parameter

Provider-spezifische Parameter sollen genutzt werden, ohne sie in die Query zu pressen.

Beispiel Brave:

- Land: Deutschland
- Sprache: Deutsch
- SafeSearch: moderate
- Ergebnisanzahl pro Query

Dadurch bleiben Queries kurz und fachlich sauber.

## 11. Ergebnisfilter

Die LeadEngine filtert nach dem SERP-Result, nicht nur in der Query.

Grund:

Query-Ausschluesse wie `-StepStone -Indeed -Jooble` verbrauchen Query-Budget und funktionieren nicht bei jedem Provider gleich gut.

Stattdessen bekommt die LeadEngine eine Domain-Denylist.

Erste Denylist-Kategorien:

- Jobboersen
- Meta-Jobboersen
- Recruiting-Agenturen
- Bewertungsportale
- Social-Media-Profile
- reine Verzeichnisse
- bekannte irrelevante Domains

Beispiele:

```text
stepstone.de
indeed.com
de.indeed.com
jooble.org
de.jooble.org
kimeta.de
xing.com
jobmensa.de
meinpraktikum.de
get-in-it.de
```

Treffer werden nicht zwingend geloescht. Sie koennen mit einem Status markiert werden:

- `candidate`
- `review_source`
- `blocked_source`
- `duplicate_domain`
- `imported`
- `existing`
- `blacklisted`
- `invalid`

Status-Abgrenzung:

- `candidate`: SERP-Ergebnis ist grundsaetzlich brauchbar und kann an den Target Import gehen.
- `review_source`: SERP-Ergebnis ist als Kontextquelle nuetzlich, soll aber nicht automatisch als primaeres Target importiert werden.
- `blocked_source`: SERP-Ergebnis wurde durch Denylist oder Source-Regel blockiert, z. B. Jobportal, Aggregator oder Social-Media-Profil.
- `duplicate_domain`: dieselbe normalisierte Domain wurde im Discovery-Lauf bereits durch ein besseres SERP-Ergebnis vertreten.
- `imported`: der Target Import hat daraus ein neues lokales Target erzeugt.
- `existing`: der Target Import hat ein vorhandenes lokales Target wiederverwendet.
- `blacklisted`: der Target Import hat die Domain wegen einer Nutzer-Blacklist abgewiesen.
- `invalid`: URL oder Domain ist nicht sinnvoll normalisierbar.

Damit unterscheiden sich Kontextquellen (`review_source`), Source-Filter (`blocked_source`), Nutzerentscheidungen (`blacklisted`) und LeadEngine-Dedupe (`duplicate_domain`) von Import-Payload-Dubletten (`duplicate_input` im Target Import).

Kontextquellen bleiben in `serp_results` gespeichert und koennen spaeter einem
Target zugeordnet werden. Die Zuordnung nutzt `serp_results.target_id`; daraus
erzeugte Evidence behaelt `context_source_id`, Query-Herkunft,
Pipeline-Run-Bezug und Source-Quality-Metadaten. Dadurch kann ein Directory-,
News- oder Registry-Treffer als Beleg dienen, ohne selbst als Zielunternehmen
importiert zu werden.

### Source Quality Heuristik

Jeder SERP-Treffer bekommt vor dem Import transparente Qualitaets-Metadaten:

- `source_type`
- `source_quality_score`
- `recommended_import_action`
- `source_signals`
- `source_risks`

Erste Source Types:

- `official_site`
- `company_site`
- `directory`
- `job_board`
- `social`
- `repository`
- `news`
- `registry`
- `marketplace`
- `unknown`

Positive Signale:

- `direct_domain` (`+20`): `source_type` ist `company_site` oder `official_site`.
- `relevant_path` (`+15`): Pfad enthaelt `career`, `careers`, `karriere`, `jobs`, `kontakt`, `contact`, `impressum`, `about`, `ueber`, `uber`, `team` oder `services`; wird nicht fuer geblockte Source Types vergeben.
- `concrete_title` (`+5`): Titel ist mindestens 8 Zeichen lang, enthaelt Buchstaben und ist nicht generisch.
- `provider_rank` (`+8`/`+5`/`+2`): Provider-Rang ist 1, 2-3 oder 4-7.

Negative Signale:

- `configured_blocked_domain` (Score `0`): Domain steht in `TARGET_RADAR_BLOCKED_SOURCE_DOMAINS`.
- `secondary_source` (`-20`): `source_type = directory`.
- `context_source` (`-10`): `source_type` ist in `context_source_types`, z. B. `repository`, `news`, `registry` oder im OSINT-Use-Case `directory`.
- `blocked_source_type` (`-40`): `source_type` ist `job_board`, `social` oder `marketplace`.
- `listing_or_search_page` (`-25`): Pfad enthaelt `search`, `suche`, `ranking`, `rankings`, `topliste`, `toplisten`, `branchenbuch`, `stellenangebote`, `jobboerse`, `jobsuche`, `vacancies`, `results` oder `listing`; Query-Parameter-Key ist `q`, `query`, `search`, `s` oder `keyword`; oder Titel/Snippet enthalten mindestens 4 Jobboersen-Tokens.
- `login_or_tracking_page` (`-20`): Pfad enthaelt `login`, `signin`, `signup`, `register` oder `bewerben`; oder Query enthaelt `utm_`, `fbclid=` oder `gclid=`.
- `deep_url` (`-10`): Pfad hat mindestens 4 Segmente.
- `generic_title` (`-10`): Titel existiert, ist aber nicht konkret genug.

Domain-Klassifizierung:

- Bekannte Domains und deren Subdomains werden zuerst ueber eine feste Mapping-Liste klassifiziert.
- `official_site`: Domain endet auf `.gov`, `.edu`, `.bund.de` oder enthaelt `.ac.`.
- `news`: bekannte News-Domain oder artikeltypischer Pfad wie `/news/`, `/article/`, `/artikel/`, `/meldung/`, `/story/` oder Datumsartikelpfad.
- `directory`: bekannte Verzeichnis-/Publisher-Domain oder rankingtypischer Pfad wie `/ranking/`, `/rankings/`, `/topliste/`, `/toplisten/` oder `/branchenbuch/`.
- `job_board`: bekannte Jobboerse oder Domain-Tokens enthalten `jobs`, `stellen`, `karriere` oder `career`; Tokens entstehen durch Split an `.`, `-` und `_`.
- `marketplace`: Domain-Tokens enthalten `marketplace`, `shop` oder `store`.
- `company_site`: Fallback fuer direkte Domains.

Die LeadEngine nutzt diese Heuristik nur fuer Discovery-Priorisierung und
Import-Entscheidung. Die finale fachliche Passung bleibt Aufgabe der
RatingEngine.

## 12. Dedupe

Die wichtigste Dedupe-Einheit ist die normalisierte Domain.

Mehrere SERP-Ergebnisse koennen auf dieselbe Domain zeigen. Die LeadEngine soll daraus einen Target-Kandidaten machen und die besten Fundstellen als Belege behalten.

Dedupe-Ebenen:

- exakte URL
- normalisierte URL
- Domain
- optional spaeter: Unternehmensname

### Query-Dedupe zwischen Laeufen

Die LeadEngine darf identische Queries nicht blind erneut stellen.

Jede Query bekommt einen stabilen Fingerprint:

```text
query_hash = sha256(provider + normalized_query_text)
```

Normalisierung:

- Whitespace vereinheitlichen
- Klein-/Grossschreibung ignorieren
- einfache Anfuehrungszeichen-Varianten vereinheitlichen
- Template-Parameter vor dem Hash final rendern

Deduping passiert auf zwei Ebenen:

- innerhalb eines Laufs: keine Query doppelt in die Queue legen
- zwischen Laeufen: bereits gespeicherte `source_queries.query_hash` pruefen

Verhalten je Modus:

- `explore`: Query ueberspringen, wenn sie fuer dasselbe Suchprofil und denselben Provider schon erfolgreich lief, ausser `force=true`.
- `focused`: Query ueberspringen, wenn sie schon erfolgreich lief und juenger als `refresh_after_days` ist.
- `refresh`: Query erneut ausfuehren, wenn sie aelter als `refresh_after_days` ist oder bisher keine brauchbaren Targets erzeugt hat.
- `rerun`: nur explizit ausgewaehlte Queries oder Targets erneut verarbeiten.

Fehlgeschlagene Queries werden nicht sofort permanent blockiert. Sie bekommen `error_type` und koennen nach Backoff erneut versucht werden.

### Query-Qualitaet pro Use Case

Use Cases duerfen `query_policy.exclude_terms` definieren. Der QueryBuilder
haengt diese Terme an generierte Template-Queries als negative Suchterme an,
z. B. `-jobs` oder `-"ranking portal"`. Profil-spezifische
`exclude_keywords` werden zusaetzlich angehaengt.

Regeln:

- Manuelle Queries bleiben unveraendert.
- Dedupe und `query_hash` nutzen den finalen Query-Text inklusive negativer
  Terme.
- `company_osint` nutzt direkte Unternehmens-, Kontakt-, Impressum- und
  Services-Templates statt breiter Anbieter-Queries.
- `application_student` behaelt Bewerbungs-/Karriere-Templates und bekommt
  keine OSINT-Default-Ausschluesse.

## 13. Scoring-Handoff

Die LeadEngine bewertet keine finale Passung.

Sie uebergibt brauchbare Domains an die bestehende Pipeline:

```text
LeadEngine
  -> Target Import
  -> Shallow Fetch
  -> Rule Score
  -> AI Score
  -> Draft Generator
  -> Review Queue
```

Die LeadEngine kann aber Vor-Signale speichern:

- Query, die den Treffer erzeugt hat
- SERP-Rank
- Titel
- Snippet
- Quelle/Provider
- ob Jobportal oder echte Domain vermutet wird

Diese Signale koennen spaeter ins Scoring einfliessen.

## 14. Datenmodell-Idee

Bestehende Tabellen:

- `source_queries`
- `serp_results`
- `targets`

### MVP-Entscheidung

Der MVP bekommt eine kleine `lead_runs`-Tabelle als Laufklammer.

Es gibt im MVP keine separaten Tabellen `lead_queries` und `lead_results`.

Stattdessen werden die bestehenden Tabellen erweitert:

- `source_queries` wird zur ausgefuehrten LeadEngine-Query.
- `serp_results` bleibt das gespeicherte Provider-Ergebnis.
- `targets` bleibt die normalisierte Target-Domain.

Grund:

- Run-Status, Budget und Resume brauchen eine eigene Laufklammer.
- Query- und Result-Daten existieren bereits.
- Weniger Migrationen und weniger doppelte Datenmodelle.
- Spaetere Extraktion in `lead_queries`/`lead_results` bleibt moeglich.

### Neue Tabelle `lead_runs`

MVP-Spalten:

- `id`
- `search_profile_id`
- `provider`
- `mode`
- `template_set`
- `request_budget`
- `used_budget`
- `results_per_query`
- `status`
- `auto_import`
- `force`
- `refresh_after_days`
- `started_at`
- `finished_at`
- `error_message`
- `stats_json`

### Erweiterung `source_queries`

Neue Spalten:

- `lead_run_id`
- `query_hash`
- `query_template`
- `template_set`
- `query_score`
- `dedupe_status`
- `error_type`
- `retry_after`

### Erweiterung `serp_results`

Neue Spalten:

- `lead_status`
- `block_reason`
- `source_quality`

### Spaeter moeglich

- `lead_runs`
- `lead_queries`
- `lead_results`
- `lead_source_blocks`

Diese Tabellen werden erst noetig, wenn LeadEngine-Daten deutlich umfangreicher werden oder unabhaengig von SERP-Providern wachsen.

## 15. API-Idee

```text
POST /lead-engine/runs
GET  /lead-engine/runs
GET  /lead-engine/runs/{run_id}
POST /lead-engine/runs/{run_id}/import
GET  /lead-engine/blocked-domains
POST /lead-engine/blocked-domains
```

Payload fuer einen Lauf:

```json
{
  "search_profile_id": 3,
  "request_budget": 100,
  "results_per_query": 10,
  "provider": "brave",
  "mode": "focused",
  "auto_import": false
}
```

## 16. UI-Idee

Die UI sollte nicht nur eine flache Liste von SERP-Ergebnissen zeigen.

Sinnvolle Ansichten:

- LeadEngine Run mit Status und Budgetverbrauch
- ausgefuehrte Queries
- Treffer nach Domain gruppiert
- blockierte Quellen
- importierte Targets
- Top-Kandidaten fuer manuelle Pruefung

Wichtig fuer Vertrauen:

- Nutzer sieht, welche Query welchen Treffer gefunden hat.
- Nutzer sieht, warum eine Domain blockiert wurde.
- Nutzer kann blockierte Domains freigeben oder neue Domains blockieren.

## 17. Modi

### Explore

Breiter Lauf fuer neue Suchprofile.

- viele Query-Varianten
- groesseres Budget
- Auto-Import aus
- starker Fokus auf Review

### Focused

Gezielter Lauf fuer ein validiertes Suchprofil.

- weniger Varianten
- bekannte gute Templates bevorzugt
- Denylist hart anwenden
- Auto-Import optional

### Refresh

Wiederholung fuer bestehende Suchprofile.

- bereits bekannte schlechte Queries vermeiden
- neue Ergebnisse gegen bestehende Domains deduplizieren
- Fokus auf neue Targets
- erfolgreiche Queries nur nach `refresh_after_days` erneut ausfuehren

## 18. Provider-Fehlerverhalten

Provider-Fehler werden pro Query gespeichert und duerfen den gesamten Lauf nur stoppen, wenn Fortsetzen keinen Sinn mehr ergibt.

Moegliche `error_type`-Werte:

- `rate_limited`
- `auth_error`
- `timeout`
- `network_error`
- `provider_error`
- `invalid_response`
- `configuration_error`

Verhalten:

- `auth_error` oder `configuration_error`: Lauf wird `failed`, weil weitere Queries denselben Fehler erzeugen wuerden.
- `rate_limited`: aktuelle Query wird als `failed` mit `rate_limited` gespeichert, Lauf wird `paused`, `retry_after` wird gespeichert, verbleibendes Budget bleibt erhalten.
- `timeout` oder `network_error`: Query wird als `failed` gespeichert, verbrauchtes Budget steigt um 1, Lauf setzt mit der naechsten Query fort.
- `provider_error` oder `invalid_response`: Query wird als `failed` gespeichert; nach mehreren aufeinanderfolgenden Providerfehlern wird der Lauf `paused`.
- keine Ergebnisse: Query wird `completed` mit `0` Ergebnissen, Budget ist verbraucht, Lauf setzt fort.

Budget-Regel:

- Jeder tatsaechlich gestartete Provider-Request erhoeht `used_budget`.
- Bei `rate_limited` wird kein weiteres Budget verbrannt; der Lauf pausiert.
- Bei Resume werden nur Queries fortgesetzt, die noch nicht erfolgreich abgeschlossen wurden und nicht im Backoff sind.

Minimal fuer V1:

- kein komplexes Retry-System,
- aber Fehler pro Query speichern,
- Rate-Limits erkennen,
- Lauf bei Rate-Limit pausieren statt die restlichen 99 Requests zu verschwenden.

## 19. Qualitaetsmetriken

Die LeadEngine sollte pro Lauf messbar machen:

- Anzahl ausgefuehrter Queries
- Roh-Treffer
- eindeutige Domains
- blockierte Domains
- importierte Targets
- bestehende Targets
- Pipeline-Erfolgsquote
- Draft-Quote
- manuell akzeptierte Targets

Diese Metriken entscheiden spaeter, ob Brave reicht oder ein anderer Provider sinnvoll ist.

## 20. Warum nicht direkt Google?

Der Provider ist zweitrangig, solange die Query-Strategie schlecht ist.

Die aktuelle Hauptschwaeche ist nicht Brave, sondern:

- zu grosse Query
- zu wenig Query-Varianten
- fehlende Domain-Denylist
- fehlende Gruppierung nach echten Ziel-Domains

Darum zuerst LeadEngine bauen, dann Provider vergleichen.

## 21. MVP-Scope der LeadEngine

Erster umsetzbarer Slice:

- Query-Fanout aus bestehenden Suchprofilen
- `request_budget`
- Template-basierte Query-Erzeugung
- `template_set` fuer `application_general` und `application_student`
- Brave als bestehender Provider
- Domain-Denylist fuer Jobportale
- `lead_runs` als Laufklammer
- Query-Dedupe per `query_hash`
- Provider-Fehlerverhalten mit `rate_limited`, `auth_error`, `timeout`
- SERP-Ergebnisse weiterhin lokal speichern
- Ergebnisse nach Domain deduplizieren
- manuelle Import-Entscheidung in der UI

Noch nicht Teil des ersten Slices:

- automatische Provider-Auswahl
- selbstlernende Query-Gewichte
- komplexe Company-Name-Dedupe
- Hintergrundjobs
- automatische Massenverarbeitung ohne Review

## 22. Leitentscheidung

Die LeadEngine ist kein Crawler und kein Mailing-Automat.

Sie ist ein kontrollierter Target-Finder:

```text
Viele kleine Suchversuche
+ harte Quellenfilter
+ Domain-Dedupe
+ nachvollziehbarer Handoff
= bessere Targets fuer Scoring und Review
```
