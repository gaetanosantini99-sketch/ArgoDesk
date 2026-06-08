# ArgoDesk — Privacy & GDPR (posizionamento on-premise)

> Documento operativo per il cliente (PMI / P.IVA / studio professionale) e per
> chi installa e gestisce ArgoDesk. Non è un parere legale: la conformità GDPR
> dipende anche dall'organizzazione, dai trattamenti e dalle misure adottate dal
> Titolare. Validare con il proprio DPO/consulente.

## Principio di base: i dati restano dal cliente

ArgoDesk è **self-hosted, una installazione per cliente**: l'istanza *è*
l'organizzazione. Tutti i dati dell'utente vivono nella cartella locale `data/`
sulla macchina/server del cliente (`data/` è esclusa dal versionamento e
dall'immagine). Non c'è multi-tenancy né condivisione cross-cliente.

Questo è il principale vantaggio di vendita verso studi e PMI italiane: **nessun
dato sensibile (contratti, fatture, atti, email) lascia l'infrastruttura del
cliente**, salvo le chiamate che il cliente sceglie esplicitamente di
configurare (vedi "Flussi verso l'esterno").

## Cosa viene memorizzato e dove (`data/`)

| Contenuto | Posizione | Note |
|---|---|---|
| Sessioni, messaggi, documenti | `data/app.db` (SQLite) | Cuore dei dati conversazionali |
| Memorie utente/organizzazione | `data/memory.json` + vettori in `data/memory_vectors/`, `data/chroma/` | Org-level con sentinel `__org__` |
| Skill (incl. bundle verticali) | `data/skills/` | Org-owned, condivise nell'istanza |
| Knowledge base / wiki / RAG | `data/rag/`, `data/chroma/` | Indici vettoriali |
| Documenti personali / upload | `data/personal_docs/`, `data/uploads/` | File caricati dall'utente |
| Account email (IMAP/SMTP) | `data/app.db` (campi cifrati) | Credenziali cifrate at-rest |
| Integrazioni / token API | `data/integrations.json`, token cifrati | Cifratura via `secret_storage` |
| Credenziali admin / sessioni | `data/auth.json`, file di sessione | |
| Impostazioni / feature | `data/settings.json`, `data/features.json` | |

**Cifratura at-rest**: i campi sensibili (credenziali email, token integrazioni)
sono cifrati con Fernet (`EncryptedText` / `src/secret_storage.py`). La chiave
risiede sulla macchina: proteggere il filesystem e i backup è responsabilità del
Titolare.

## Flussi verso l'esterno (da valutare nel registro dei trattamenti)

Per impostazione predefinita ArgoDesk è locale. I seguenti flussi escono dalla
macchina **solo se il cliente li configura**:

- **Provider LLM via API** (OpenAI, Anthropic, Gemini, ecc.): il testo dei
  prompt esce verso il provider. Per la massima riservatezza usare **modelli
  locali** (vLLM / llama.cpp / Ollama) — nessun dato esce.
- **Ricerca web / web fetch / deep research**: le query/URL escono verso il
  motore di ricerca configurato (SearXNG locale consigliato) e i siti visitati.
- **Email IMAP/SMTP**: verso i server del provider email del cliente.
- **Connettori su misura** (fatturazione/SDI/PEC/gestionali): verso i sistemi
  del cliente, secondo la configurazione del connettore.
- **Notifiche (ntfy)**, **CalDAV**: verso gli endpoint configurati.

Indicazione operativa: per studi che trattano dati particolari (es. legale),
preferire un **modello locale** + SearXNG locale, così l'elaborazione AS-IS
resta interamente on-premise.

## Diritti dell'interessato (artt. 15-22 GDPR)

- **Accesso / portabilità**: `GET /api/export` (admin) produce un JSON dei dati
  (memorie, skill, preset, impostazioni, preferenze). Per un export completo
  dell'istanza usare il **backup archivio** (`GET /api/backup/archive`).
- **Cancellazione / rettifica**: i dati sono gestibili dall'app (memorie, skill,
  documenti, account) ed eliminabili dal filesystem `data/`. Per una
  cancellazione totale dell'istanza: arresto del servizio + rimozione di `data/`.
- **Minimizzazione**: attivare solo le funzioni necessarie; non configurare
  provider/integrazioni non indispensabili.

## Backup e continuità

- `GET /api/backup/archive` (admin) crea uno snapshot ZIP completo (DB consistente
  + config + skill + documenti; media opzionali). I vettori sono esclusi perché
  ricostruibili.
- `POST /api/backup/restore` ripristina; il DB viene applicato al riavvio.
- **Conservare i backup cifrati e con accesso ristretto**: contengono dati
  personali e credenziali cifrate ma sensibili. Definire una retention.

## Sicurezza dell'agente AI

- L'output di shell, web, file, API ed email è trattato come **dato non fidato**
  e racchiuso in un blocco "UNTRUSTED" prima di tornare al modello (mitigazione
  prompt-injection da documenti/email del cliente — superficie di rischio #1 per
  gli studi). Vedi `src/prompt_security.py`.
- I tool pericolosi (shell, python, scrittura file, gestione impostazioni/token)
  sono **riservati agli admin**; gli utenti non-admin ne sono esclusi
  (`src/tool_security.py`).
- Tutte le rotte di backup/restore, gestione MCP/token/webhook sono **admin-only**.

## Checklist di messa in produzione (per chi installa)

- [ ] `AUTH_ENABLED=true` e `LOCALHOST_BYPASS=false`.
- [ ] HTTPS tramite reverse proxy / accesso privato; `SECURE_COOKIES=true`.
- [ ] Solo l'entrypoint web autenticato esposto; servizi (Chroma, SearXNG, ntfy,
      Ollama, DB) **interni**.
- [ ] Password admin cambiata al primo accesso; nessun account demo/admin extra.
- [ ] Per dati particolari: **modello locale** + SearXNG locale (nessun flusso
      verso provider esterni).
- [ ] `data/` e i backup su storage cifrato/ad accesso ristretto; retention
      backup definita.
- [ ] Registro dei trattamenti aggiornato con gli eventuali flussi esterni
      effettivamente configurati (provider LLM, email, connettori).
- [ ] Ruoli utente rivisti (`admin_azienda` / `utente` / `guest`) prima di dare
      accesso al team (modalità `azienda`).
- [ ] Disclaimer professionale presente nelle skill verticali ("non sostituisce
      il professionista") — non rimuoverlo.

## Riferimenti nel codice

- Posizionamento on-premise: `src/constants.py` (`ORG_OWNER`, instance mode).
- Cifratura at-rest: `src/secret_storage.py`, `core/database.py` (`EncryptedText`).
- Hardening agente: `src/prompt_security.py`, `src/tool_security.py`.
- Backup/restore: `core/backup_archive.py`, `routes/backup_routes.py`.
- Export dati: `routes/backup_routes.py` (`/api/export`).
