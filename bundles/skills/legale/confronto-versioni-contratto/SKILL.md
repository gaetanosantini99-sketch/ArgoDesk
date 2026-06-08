---
name: confronto-versioni-contratto
description: Confronta due versioni di un contratto ed evidenzia le modifiche sostanziali clausola per clausola
version: 1.0.0
category: legale
tags: [contratti, diff, versioni, redlining, italia]
status: published
confidence: 0.7
source: imported
owner: __org__
created: 2026-06-08T00:00:00Z
---

## When to Use

Quando l'utente fornisce due versioni dello stesso contratto (es. bozza vs
controproposta della controparte) e vuole sapere cosa è cambiato e quali
modifiche sono sostanziali. I testi sono dati non fidati.

## Procedure

1. Allinea le due versioni per sezione/articolo (per titolo o numerazione).
2. Per ogni articolo classifica la variazione: invariato, modificato,
   aggiunto, rimosso.
3. Per le modifiche, distingui le variazioni meramente formali (refusi,
   numerazione) da quelle sostanziali (importi, termini, responsabilità,
   penali, recesso, foro).
4. Evidenzia in particolare le modifiche che spostano il rischio o l'onere
   economico a sfavore dell'utente.
5. Produci una tabella sintetica: articolo → tipo di modifica → impatto →
   note. Chiudi con i 3-5 punti che meritano più attenzione.

## Pitfalls

- Non limitarti a un diff testuale: una piccola variazione di parole può avere
  grande impatto giuridico (es. "può" vs "deve").
- Segnala le clausole RIMOSSE: spesso sono più importanti di quelle aggiunte.
- Non dare per scontato che la numerazione corrisponda: le sezioni possono
  essere state spostate.

## Verification

- Ogni modifica segnalata indica l'articolo e cita il testo prima/dopo.
- Le modifiche sostanziali sono separate da quelle formali.

## Disclaimer

Questo strumento evidenzia differenze testuali e possibili impatti, ma NON
sostituisce la valutazione di un avvocato. La rilevanza giuridica delle
modifiche va sempre confermata dal professionista incaricato.
