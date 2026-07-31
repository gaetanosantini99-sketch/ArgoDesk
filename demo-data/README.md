# Set documentale demo — ArgoDesk

Materiale fittizio per simulare l'uso reale del prodotto durante le **demo di vendita**.
Tutti i nomi, P.IVA, importi e indirizzi sono inventati. Nessun dato reale.

Due scenari pronti:

| Cartella | Persona / cliente tipo | Verticale | Skill collegate |
|---|---|---|---|
| `pmi-rossi-impianti/` | PMI 15 dipendenti (impiantistica) | Generico PMI | — |
| `studio-legale-bianchi/` | Studio legale 3 avvocati | Legale | `legale/analisi-contratto-clausole`, `legale/confronto-versioni-contratto` |

Ogni scenario contiene:

- `knowledge/` → file **Markdown** da caricare come **Conoscenza aziendale** (tool Conoscenza → Documenti → *Carica*, opzione *condivisa/aziendale*). Sono la base su cui l'agente risponde in chat.
- `documenti-pdf/` → **PDF** realistici (fatture, contratti, preventivi, diffide) per mostrare l'estrazione testo da PDF e l'analisi clausole.
- `note/` (dove presente) → testi brevi da incollare come **Note** o promemoria.

## Come caricarlo in una demo (server nativo)

1. Avvia: `venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 7000`
2. Login come admin → imposta `instance_mode`:
   - `azienda` per lo scenario PMI
   - `freelance` per lo Studio legale (singolo professionista)
3. Tool **Conoscenza** → *Carica documenti* → seleziona i file di `knowledge/` e dei PDF.
   - Spunta **condivisa/aziendale** così l'agente li usa per tutti.
   - Campo *purpose*: es. "policy interna", "contratto fornitore" — viene indicizzato e usato dal grafo.
   - Campo *category*: es. `procedure`, `contratti`, `fatture`.
4. (Studio legale) Attiva le skill `legale/*` già seedate e prova: *"Analizza il contratto di locazione ed elenca le clausole vessatorie"*.

## Rigenerare i PDF

```
venv\Scripts\python demo-data\genera_pdf.py
```

Lo script è idempotente: riscrive i PDF in `*/documenti-pdf/`. Il contenuto testuale dei
PDF è verificabile con `pypdf` (lo stesso estrattore usato dall'app).

## Tracce di demo suggerite (prompt da provare in chat)

**PMI Rossi Impianti**
- "Qual è la nostra politica su ferie e permessi?"
- "Riassumi il verbale dell'ultima riunione e i punti aperti."
- "Genera un preventivo simile a PR-2026-118 ma per un impianto fotovoltaico da 6 kW."
- "Quali sono le condizioni di pagamento col fornitore ElettroForniture?"

**Studio legale Bianchi**
- "Analizza il contratto di locazione commerciale ed evidenzia clausole vessatorie ex art. 1341 c.c."
- "Confronta la bozza di fornitura con la nostra checklist clausole."
- "Prepara una bozza di diffida di pagamento sul modello che abbiamo in archivio."
- "Quali scadenze processuali ho questo mese?"
