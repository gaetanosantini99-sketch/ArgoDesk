#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Genera i PDF del set documentale demo di ArgoDesk.

Uso:
    venv\\Scripts\\python demo-data\\genera_pdf.py

Idempotente: riscrive i PDF in ``*/documenti-pdf/``. Richiede ``fpdf2``
(installabile con ``pip install fpdf2 --no-compile``). Usa il font Arial di
Windows per supportare il simbolo euro e gli accenti italiani; in mancanza
ripiega sul font core Helvetica sostituendo i caratteri fuori latin-1.
"""
import os
import sys

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
except ImportError:
    sys.exit("Manca fpdf2. Installa con:  venv\\Scripts\\pip install fpdf2 --no-compile")

BASE = os.path.dirname(os.path.abspath(__file__))

# --- Font ------------------------------------------------------------------
WIN_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
ARIAL = os.path.join(WIN_FONTS, "arial.ttf")
ARIAL_B = os.path.join(WIN_FONTS, "arialbd.ttf")
ARIAL_I = os.path.join(WIN_FONTS, "ariali.ttf")
USE_UNICODE = all(os.path.exists(f) for f in (ARIAL, ARIAL_B, ARIAL_I))
FONT = "Arial" if USE_UNICODE else "Helvetica"


def _sanitize(text):
    """Senza font unicode, rendi il testo compatibile con latin-1."""
    if USE_UNICODE:
        return text
    repl = {"€": "EUR", "’": "'", "‘": "'", "“": '"',
            "”": '"', "–": "-", "—": "-", "…": "...",
            " ": " ", "→": "->"}
    for k, v in repl.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class Doc(FPDF):
    def __init__(self, mittente):
        super().__init__(format="A4")
        self.mittente = mittente
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(20, 18, 20)
        if USE_UNICODE:
            self.add_font("Arial", "", ARIAL)
            self.add_font("Arial", "B", ARIAL_B)
            self.add_font("Arial", "I", ARIAL_I)
        self.add_page()

    # intestazione mittente in alto su ogni pagina
    def header(self):
        self.set_font(FONT, "B", 11)
        self.cell(0, 6, _sanitize(self.mittente),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(180, 180, 180)
        self.line(20, self.get_y() + 1, 190, self.get_y() + 1)
        self.ln(5)

    def footer(self):
        self.set_y(-14)
        self.set_font(FONT, "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 5, _sanitize("Documento dimostrativo ArgoDesk - dati fittizi"),
                  align="C")
        self.set_text_color(0, 0, 0)

    # --- blocchi ----------------------------------------------------------
    def h1(self, text):
        self.set_font(FONT, "B", 15)
        self.multi_cell(0, 8, _sanitize(text))
        self.ln(2)

    def h2(self, text):
        self.ln(1)
        self.set_font(FONT, "B", 12)
        self.multi_cell(0, 7, _sanitize(text))
        self.ln(1)

    def p(self, text):
        self.set_font(FONT, "", 10.5)
        self.multi_cell(0, 5.5, _sanitize(text))
        self.ln(1)

    def kv(self, pairs):
        self.set_font(FONT, "", 10.5)
        for k, v in pairs:
            self.set_font(FONT, "B", 10.5)
            self.cell(45, 6, _sanitize(k))
            self.set_font(FONT, "", 10.5)
            self.multi_cell(0, 6, _sanitize(v),
                            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def table(self, headers, rows, widths):
        self.set_font(FONT, "B", 9.5)
        self.set_fill_color(235, 235, 235)
        for h, w in zip(headers, widths):
            self.cell(w, 7, _sanitize(h), border=1, fill=True, align="C")
        self.ln()
        self.set_font(FONT, "", 9.5)
        for row in rows:
            for val, w in zip(row, widths):
                self.cell(w, 6.5, _sanitize(str(val)), border=1)
            self.ln()
        self.ln(2)

    def signature(self, text="Timbro e firma _______________________"):
        self.ln(8)
        self.set_font(FONT, "", 10.5)
        self.cell(0, 6, _sanitize(text), align="R",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def save(doc, scenario, filename):
    out_dir = os.path.join(BASE, scenario, "documenti-pdf")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    doc.output(path)
    print("  scritto:", os.path.relpath(path, BASE))


# ===========================================================================
# PMI - ROSSI IMPIANTI S.r.l.
# ===========================================================================
ROSSI = "Rossi Impianti S.r.l. - Via dell'Industria 14, 06034 Foligno (PG) - P.IVA 02841560543"


def preventivo():
    d = Doc(ROSSI)
    d.h1("Preventivo n. PR-2026-118")
    d.kv([("Data:", "8 giugno 2026"),
          ("Cliente:", "Sig. Andrea Tagliaferri"),
          ("Indirizzo:", "Via dei Lecci 5, 06038 Spello (PG)"),
          ("Oggetto:", "Fornitura e posa impianto fotovoltaico 6 kW con accumulo")])
    d.h2("Dettaglio delle lavorazioni")
    rows = [
        ["1", "Moduli FV 450W monocristallini (n. 14)", "n.", "14", "€ 3.080,00"],
        ["2", "Inverter ibrido 6 kW", "n.", "1", "€ 1.450,00"],
        ["3", "Sistema di accumulo 5 kWh", "n.", "1", "€ 2.900,00"],
        ["4", "Struttura, cablaggi e quadri", "corpo", "1", "€ 1.350,00"],
        ["5", "Manodopera installazione e collaudo", "corpo", "1", "€ 1.420,00"],
        ["6", "Pratica GSE e connessione", "corpo", "1", "€ 350,00"],
    ]
    d.table(["#", "Descrizione", "U.M.", "Q.tà", "Importo"], rows,
            [10, 88, 16, 16, 40])
    d.kv([("Imponibile:", "€ 10.550,00"),
          ("IVA 10%:", "€ 1.055,00"),
          ("TOTALE:", "€ 11.605,00")])
    d.h2("Condizioni")
    d.p("Pagamento: 30% all'ordine (€ 3.481,50), saldo 70% a fine lavori. "
        "Validità preventivo: 30 giorni. Garanzia 24 mesi sull'installazione, "
        "garanzia produttore sui materiali. Tempo di realizzazione stimato: 3-4 settimane "
        "dalla conferma. Detrazione fiscale applicabile secondo normativa vigente.")
    d.signature()
    save(d, "pmi-rossi-impianti", "preventivo-PR-2026-118.pdf")


def fattura():
    d = Doc(ROSSI)
    d.h1("Fattura n. 2026-0042")
    d.kv([("Data:", "31 maggio 2026"),
          ("Cliente:", "Tagliaferri Andrea"),
          ("C.F.:", "TGLNDR75H12G478K"),
          ("Indirizzo:", "Via dei Lecci 5, 06038 Spello (PG)"),
          ("Commessa:", "COM-2026-031"),
          ("Pagamento:", "Bonifico - saldo a 30 gg")])
    d.h2("Descrizione")
    rows = [
        ["Acconto 30% impianto FV 6 kW (PR-2026-031)", "€ 3.150,00", "10%", "€ 315,00"],
        ["Sopralluogo e progettazione preliminare", "€ 250,00", "22%", "€ 55,00"],
    ]
    d.table(["Descrizione", "Imponibile", "IVA", "Imposta"], rows,
            [100, 30, 18, 22])
    d.kv([("Totale imponibile:", "€ 3.400,00"),
          ("Totale IVA:", "€ 370,00"),
          ("TOTALE FATTURA:", "€ 3.770,00")])
    d.p("Coordinate per il pagamento: IBAN IT60 X054 2811 1010 0000 0123 456 - "
        "Banca dell'Umbria, intestato a Rossi Impianti S.r.l. "
        "Causale: Fattura 2026-0042 COM-2026-031.")
    d.p("Documento emesso in formato dimostrativo. In esercizio reale la fattura "
        "elettronica transita via Sistema di Interscambio (SdI).")
    save(d, "pmi-rossi-impianti", "fattura-2026-0042.pdf")


def contratto_fornitore():
    d = Doc(ROSSI)
    d.h1("Contratto quadro di fornitura materiale elettrico")
    d.p("Tra Rossi Impianti S.r.l. (di seguito \"Committente\") e "
        "ElettroForniture S.p.A., con sede in Via Tiberina 220, 06078 Pian di Massiano (PG), "
        "P.IVA 01998870548 (di seguito \"Fornitore\").")
    d.h2("Art. 1 - Oggetto")
    d.p("Il Fornitore si impegna a fornire materiale elettrico (cavi, quadri, apparecchiature "
        "di protezione e accessori) secondo il listino allegato e gli ordini di volta in volta "
        "emessi dal Committente.")
    d.h2("Art. 2 - Prezzi e revisione")
    d.p("I prezzi sono quelli del listino in vigore. Eventuali variazioni vanno comunicate con "
        "almeno 30 giorni di preavviso. Per ordini superiori a € 5.000 si applica uno sconto del 7%.")
    d.h2("Art. 3 - Consegne")
    d.p("Consegna entro 5 giorni lavorativi dall'ordine per materiale a magazzino, 15 giorni per "
        "materiale su commessa. La merce viaggia a rischio del Fornitore fino alla consegna.")
    d.h2("Art. 4 - Pagamenti")
    d.p("Pagamento a 60 giorni data fattura fine mese, mediante bonifico bancario.")
    d.h2("Art. 5 - Durata")
    d.p("Il contratto ha durata annuale con rinnovo tacito salvo disdetta da inviarsi a mezzo PEC "
        "almeno 60 giorni prima della scadenza.")
    d.h2("Art. 6 - Foro competente")
    d.p("Per ogni controversia è competente il Foro di Perugia.")
    d.signature("Il Committente ____________     Il Fornitore ____________")
    save(d, "pmi-rossi-impianti", "contratto-fornitore-elettroforniture.pdf")


# ===========================================================================
# STUDIO LEGALE - documenti per analisi clausole
# ===========================================================================
PARTE = "Contratto in analisi - Studio Legale Bianchi & Associati (uso interno, dati fittizi)"


def contratto_locazione():
    d = Doc(PARTE)
    d.h1("Contratto di locazione ad uso commerciale")
    d.p("Tra il sig. Roberto Pellegrini (Locatore) e la societa' Omega Retail S.r.l. (Conduttore), "
        "per l'immobile sito in Perugia, Via Mazzini 30, ad uso negozio.")
    d.h2("Art. 1 - Durata")
    d.p("La locazione ha durata di anni 6 (sei) con rinnovo automatico per ulteriori 6 anni, "
        "salvo disdetta del Conduttore da comunicarsi almeno 12 mesi prima della scadenza.")
    d.h2("Art. 2 - Canone")
    d.p("Il canone annuo e' di € 24.000,00, da corrispondersi in rate mensili anticipate di "
        "€ 2.000,00. Il canone e' aggiornato annualmente nella misura del 100% della variazione ISTAT.")
    d.h2("Art. 3 - Deposito cauzionale")
    d.p("Il Conduttore versa un deposito cauzionale pari a 3 mensilita', non produttivo di interessi.")
    d.h2("Art. 4 - Risoluzione e penali")
    d.p("In caso di recesso anticipato del Conduttore prima dei 4 anni, lo stesso e' tenuto al "
        "pagamento di una penale pari a 6 mensilita'. Il Locatore puo' invece recedere in qualsiasi "
        "momento con preavviso di 30 giorni senza alcuna penale.")
    d.h2("Art. 5 - Manutenzioni")
    d.p("Tutte le manutenzioni, ordinarie e straordinarie, sono integralmente a carico del Conduttore, "
        "ivi comprese quelle relative alle strutture e all'impianto di riscaldamento.")
    d.h2("Art. 6 - Limitazione di responsabilita'")
    d.p("Il Locatore non risponde in alcun caso di danni a cose o persone derivanti da vizi "
        "dell'immobile, anche se preesistenti e a lui noti.")
    d.h2("Art. 7 - Foro competente")
    d.p("Per ogni controversia e' competente in via esclusiva il Foro di Milano.")
    d.p("Le parti dichiarano di approvare il contratto in ogni sua parte.")
    d.signature("Il Locatore ____________     Il Conduttore ____________")
    save(d, "studio-legale-bianchi", "contratto-locazione-commerciale.pdf")


def contratto_fornitura():
    d = Doc(PARTE)
    d.h1("Bozza - Contratto di fornitura di servizi informatici")
    d.p("Tra TechServ S.r.l. (Fornitore) e Delta Logistica S.r.l. (Cliente). "
        "Bozza sottoposta a revisione legale.")
    d.h2("Art. 1 - Oggetto")
    d.p("Il Fornitore eroga servizi di gestione e manutenzione dell'infrastruttura informatica "
        "del Cliente secondo i livelli di servizio (SLA) descritti nell'allegato A.")
    d.h2("Art. 2 - Durata e rinnovo")
    d.p("Durata 36 mesi con rinnovo automatico per ulteriori 36 mesi, salvo disdetta da inviarsi "
        "almeno 6 mesi prima della scadenza.")
    d.h2("Art. 3 - Corrispettivo")
    d.p("Canone mensile di € 1.800,00 oltre IVA, rivedibile annualmente dal Fornitore a propria "
        "discrezione fino a un massimo del 10%.")
    d.h2("Art. 4 - Limitazione di responsabilita'")
    d.p("La responsabilita' del Fornitore e' in ogni caso limitata all'importo di una mensilita' "
        "del canone, con esclusione di qualsiasi danno indiretto, anche da perdita di dati.")
    d.h2("Art. 5 - Recesso")
    d.p("Il Fornitore puo' recedere in qualsiasi momento con preavviso di 15 giorni. Il Cliente "
        "puo' recedere solo alla scadenza naturale; il recesso anticipato comporta il pagamento "
        "dei canoni residui fino a scadenza.")
    d.h2("Art. 6 - Clausola compromissoria")
    d.p("Ogni controversia sara' devoluta ad arbitrato rituale secondo il regolamento di una camera "
        "arbitrale indicata dal Fornitore, con sede in citta' scelta dal Fornitore.")
    d.h2("Art. 7 - Trattamento dati")
    d.p("Il Fornitore tratta i dati del Cliente secondo la propria informativa, che il Cliente "
        "dichiara di accettare.")
    d.signature("Il Fornitore ____________     Il Cliente ____________")
    save(d, "studio-legale-bianchi", "contratto-fornitura-clausole.pdf")


def diffida():
    d = Doc("Studio Legale Bianchi & Associati - Corso Vannucci 88, 06121 Perugia - studiobianchi@pec.giustizia.it")
    d.h1("Diffida e messa in mora")
    d.kv([("Spett.le:", "Gamma Srl, Via del Commercio 12, Perugia (PEC)"),
          ("Per conto di:", "Verdi S.r.l."),
          ("Pratica:", "PRA-2026-025"),
          ("Data:", "13 giugno 2026")])
    d.p("Il sottoscritto Avv. Elena Bianchi, in nome e per conto della societa' Verdi S.r.l., "
        "espone quanto segue.")
    d.p("La Vostra societa' risulta debitrice nei confronti della mia assistita della somma di "
        "€ 8.450,00 a titolo di corrispettivo per le forniture di cui alle fatture n. 112/2025 "
        "e n. 137/2025, regolarmente emesse e ad oggi insolute nonostante i solleciti.")
    d.p("Tanto premesso, con la presente FORMALMENTE DIFFIDO la Vostra societa' a provvedere al "
        "pagamento della suddetta somma, oltre interessi di mora ex D.lgs. 231/2002, entro e non "
        "oltre 15 (quindici) giorni dal ricevimento della presente.")
    d.p("In difetto, saro' costretto, mio malgrado, ad adire le vie giudiziarie per il recupero "
        "del credito, con aggravio di spese, competenze e interessi a Vostro esclusivo carico. "
        "La presente vale altresi' quale costituzione in mora ai sensi e per gli effetti degli "
        "artt. 1219 e 1454 c.c.")
    d.signature("Avv. Elena Bianchi ____________")
    save(d, "studio-legale-bianchi", "diffida-pagamento.pdf")


def main():
    print("Generazione PDF (font:", FONT, "unicode:", USE_UNICODE, ")")
    print("PMI Rossi Impianti:")
    preventivo()
    fattura()
    contratto_fornitore()
    print("Studio Legale Bianchi:")
    contratto_locazione()
    contratto_fornitura()
    diffida()
    print("Fatto.")


if __name__ == "__main__":
    main()
