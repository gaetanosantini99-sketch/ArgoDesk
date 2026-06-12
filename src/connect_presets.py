"""connect_presets.py

Static data backing the guided email/calendar connection wizard
(`static/js/connectWizard.js`). **No OAuth**: every provider is reached through
the IMAP/SMTP/CalDAV credentials the app already supports, plus an app-password
where the provider requires one. This module is the single source of truth for
the host/port/security defaults and the Italian app-password walkthroughs; the
wizard renders it and saves through the existing `/api/email/accounts` and
`/api/calendar/config` endpoints.

CalDAV note: `src/caldav_sync.py` performs PROPFIND principal discovery before
treating the URL as a direct calendar, so a provider's base/principal URL is
enough — we don't have to hardcode per-user calendar collection paths. Where a
provider needs the address inline, use the `{email}` placeholder (substituted
client-side). `calendar.supported = False` means CalDAV via app-password is not
reliable for that provider and the wizard offers email-only.
"""

from typing import Any, Dict

CONNECT_PRESETS: Dict[str, Dict[str, Any]] = {
    "google": {
        "label": "Google / Gmail",
        "icon": "google",
        "email": {
            "imap_host": "imap.gmail.com",
            "imap_port": 993,
            "imap_starttls": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 465,
            "smtp_security": "ssl",
        },
        "calendar": {
            "supported": True,
            # Primary calendar collection. Principal discovery also works from
            # this host; we point at /events so it resolves even if discovery
            # is blocked on the account.
            "url": "https://apidata.googleusercontent.com/caldav/v2/{email}/events",
        },
        "app_password": {
            "required": True,
            "needs_2fa": True,
            "url": "https://myaccount.google.com/apppasswords",
            "title": "Google richiede una password per le app",
            "steps": [
                "Attiva la verifica in due passaggi sul tuo account Google (obbligatoria).",
                "Apri myaccount.google.com/apppasswords (link qui sotto).",
                "Crea una nuova password per le app: dai un nome come \"ArgoDesk\".",
                "Copia la password di 16 caratteri generata.",
                "Incollala qui sotto come Password (non usare la password normale dell'account).",
            ],
        },
    },
    "outlook": {
        "label": "Outlook / Microsoft 365",
        "icon": "outlook",
        "email": {
            "imap_host": "outlook.office365.com",
            "imap_port": 993,
            "imap_starttls": False,
            "smtp_host": "smtp.office365.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
        },
        "calendar": {
            # Microsoft 365 / Outlook.com dropped reliable basic-auth CalDAV;
            # the wizard sets up email only and explains the calendar caveat.
            "supported": False,
            "note": (
                "Microsoft non supporta più CalDAV con password per app in modo affidabile. "
                "Per il calendario usa una sincronizzazione manuale o un provider CalDAV dedicato."
            ),
        },
        "app_password": {
            "required": True,
            "needs_2fa": True,
            "url": "https://account.microsoft.com/security",
            "title": "Outlook/Microsoft 365 richiede una password per le app",
            "steps": [
                "Attiva l'autenticazione a due fattori sul tuo account Microsoft.",
                "Vai su Sicurezza dell'account → Opzioni di sicurezza avanzate → Password per le app.",
                "Crea una nuova password per le app per \"ArgoDesk\".",
                "Copia la password generata.",
                "Incollala qui sotto come Password (non la password normale dell'account).",
            ],
        },
    },
    "thunderbird": {
        "label": "Thunderbird / IMAP generico",
        "icon": "generic",
        # Thunderbird is a client, not a server: there is no Thunderbird host.
        # This preset is the generic manual path — the user enters the host/port
        # their own mail provider gave them.
        "email": {
            "imap_host": "",
            "imap_port": 993,
            "imap_starttls": False,
            "smtp_host": "",
            "smtp_port": 465,
            "smtp_security": "ssl",
        },
        "calendar": {
            "supported": True,
            "url": "",
        },
        "app_password": {
            "required": False,
            "needs_2fa": False,
            "url": "",
            "title": "IMAP/SMTP/CalDAV generico (manuale)",
            "steps": [
                "Thunderbird è un programma di posta, non un server: non ha un host proprio.",
                "Inserisci i dati IMAP/SMTP che usi già in Thunderbird (host, porta, sicurezza).",
                "Li trovi in Thunderbird: Impostazioni account → Impostazioni server (IMAP) e Server in uscita (SMTP).",
                "Per il calendario inserisci l'URL CalDAV del tuo provider e le relative credenziali.",
                "Usa \"Verifica connessione\" prima di salvare.",
            ],
        },
    },
}
