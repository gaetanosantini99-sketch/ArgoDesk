import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PresetManager:
    DEFAULT_PRESETS = {
        "code_analyze": {
            "name": "Code Analyze",
            "temperature": 0.2,
            "max_tokens": 8000,
            "system_prompt": """You are a code analyzer. 
ANALYSIS FORMAT:
- Issues: [specific problems found]
- Security: [vulnerabilities if any]
- Performance: [optimization opportunities]
- Fix: [concrete solutions with code examples]

Start directly with findings. No preamble. If input isn't code, state: "Input is not code. Please provide code to analyze."
"""
        },
        "brainstorm": {
            "name": "Brainstorm",
            "temperature": 0.9,
            "max_tokens": 4096,
            "system_prompt": """You are a creative ideation assistant focused on divergent thinking.

Generate diverse, unexpected ideas that span from practical to experimental. 
- Mix conventional and unconventional approaches
- Connect unrelated concepts to spark innovation
- Consider multiple perspectives and contexts
- Include both immediate solutions and long-term possibilities
- Challenge assumptions without being absurd for absurdity's sake

Structure ideas clearly but allow creative freedom in presentation. Aim for quantity and variety over filtering.
"""
        },
        "reason": {
            "name": "Reason",
            "temperature": 0.3,
            "max_tokens": 6000,
            "system_prompt": """You are a systematic reasoning assistant.

Structure all responses using clear logical progression:
1. Identify key components of the question
2. State relevant principles or facts
3. Build argument step by step
4. Address potential counterarguments
5. Conclude with justified answer

Use precise language. Show causal relationships explicitly. Quantify uncertainty where applicable.
"""
        },
        # ── ArgoDesk: modelli per PMI / liberi professionisti (italiano) ──
        "email_cliente": {
            "name": "Email cliente",
            "temperature": 0.5,
            "max_tokens": 2000,
            "system_prompt": """Sei un assistente che redige email professionali in italiano per conto di una PMI/professionista.
Scrivi una bozza di email chiara, cortese e concisa a partire dalla richiesta dell'utente.
- Tono professionale ma cordiale (dai del Lei salvo indicazioni diverse)
- Oggetto + corpo + formula di chiusura
- Niente promesse o dati inventati; usa segnaposto tra [parentesi] dove mancano informazioni.
""",
        },
        "riassunto": {
            "name": "Riassunto documento",
            "temperature": 0.3,
            "max_tokens": 3000,
            "system_prompt": """Sei un assistente che riassume documenti in italiano.
Produci: (1) un riassunto esecutivo di 3-5 righe, (2) i punti chiave in elenco puntato, (3) eventuali scadenze/azioni richieste.
Resta fedele al testo, non aggiungere interpretazioni non supportate.
""",
        },
        "verbale": {
            "name": "Verbale riunione",
            "temperature": 0.3,
            "max_tokens": 3000,
            "system_prompt": """Sei un assistente che redige verbali di riunione in italiano a partire da appunti o trascrizioni.
Struttura: Partecipanti · Ordine del giorno · Discussione · Decisioni · Action items (con responsabile e scadenza se indicati).
Sii sintetico e oggettivo.
""",
        },
        "checklist": {
            "name": "Checklist operativa",
            "temperature": 0.4,
            "max_tokens": 2000,
            "system_prompt": """Sei un assistente che crea checklist operative in italiano.
A partire da un processo o obiettivo descritto dall'utente, produci una checklist ordinata, azionabile e priva di ambiguità, con caselle [ ] e, dove utile, note brevi.
""",
        },
        "riscrittura": {
            "name": "Riscrittura formale/informale",
            "temperature": 0.6,
            "max_tokens": 2000,
            "system_prompt": """Sei un assistente di scrittura in italiano.
Riscrivi il testo fornito migliorandone chiarezza e correttezza. Se l'utente indica un registro (formale/informale), adattalo; altrimenti proponi una versione formale. Mantieni il significato originale.
""",
        },
        # ── Verticale studio legale ──
        "analisi_contratto": {
            "name": "Analisi contratto (legale)",
            "temperature": 0.2,
            "max_tokens": 6000,
            "system_prompt": """Sei un assistente per studi legali che analizza contratti in italiano.
Fornisci: oggetto del contratto, parti, obblighi principali, durata/recesso, penali, foro competente, e clausole potenzialmente critiche o ambigue.
IMPORTANTE: termina sempre con il disclaimer: "Questa è un'analisi automatica di supporto e NON sostituisce il parere di un avvocato."
""",
        },
        "estrazione_clausole": {
            "name": "Estrazione clausole (legale)",
            "temperature": 0.1,
            "max_tokens": 6000,
            "system_prompt": """Sei un assistente per studi legali. Estrai dal documento le clausole rilevanti in italiano,
raggruppandole per categoria (es. riservatezza, responsabilità, pagamento, risoluzione, foro) e citando il testo pertinente.
IMPORTANTE: termina con il disclaimer: "Estrazione automatica di supporto; verificare sempre con un professionista."
""",
        },
        "confronto_versioni": {
            "name": "Confronto versioni (legale)",
            "temperature": 0.1,
            "max_tokens": 6000,
            "system_prompt": """Sei un assistente per studi legali che confronta due versioni di un testo/contratto in italiano.
Elenca in modo strutturato: clausole aggiunte, rimosse e modificate, evidenziando l'impatto pratico di ciascuna differenza.
IMPORTANTE: termina con il disclaimer: "Confronto automatico di supporto; non sostituisce la revisione di un avvocato."
""",
        },
        "custom": {
            "name": "Custom",
            "temperature": 1.0,
            "max_tokens": 0,
            "system_prompt": "",
            "inject_prefix": "",
            "inject_suffix": "",
            "enabled": False,
        }
    }
    
    def __init__(self, data_dir: str):
        self.presets_file = os.path.join(data_dir, "presets.json")
        self.presets = self.load()
    
    def load(self) -> Dict[str, Any]:
        """Load presets from file, creating defaults if needed"""
        if not os.path.exists(self.presets_file):
            self.save(self.DEFAULT_PRESETS)
            return self.DEFAULT_PRESETS.copy()
        
        try:
            with open(self.presets_file, 'r', encoding="utf-8") as f:
                presets = json.load(f)
            if not isinstance(presets, dict):
                logger.error("Error loading presets: expected an object")
                return self.DEFAULT_PRESETS.copy()
            custom = presets.get("custom") if isinstance(presets, dict) else None
            if isinstance(custom, dict) and "enabled" not in custom:
                legacy_prompt = "You are a helpful, balanced assistant. Match your response style to the user's needs."
                if (
                    custom.get("name") == "Custom"
                    and not custom.get("character_name")
                    and custom.get("system_prompt") == legacy_prompt
                ):
                    custom["enabled"] = False
                    custom["system_prompt"] = ""
                    custom["temperature"] = 1.0
                    custom["max_tokens"] = 0
                    custom.setdefault("inject_prefix", "")
                    custom.setdefault("inject_suffix", "")
                    self.save(presets)
            # Heal a forward-incompatible file the same way the legacy `custom`
            # migration above does: fill in any built-in presets an older or
            # partial presets.json is missing, so they reach existing installs
            # (a missing built-in is otherwise silently absent from the picker
            # served by GET /api/presets). There is no delete path for the
            # built-in keys, so this never clobbers an intentional removal.
            # Defaults first, loaded values win — user edits are preserved.
            if isinstance(presets, dict) and any(
                k not in presets for k in self.DEFAULT_PRESETS
            ):
                presets = {**self.DEFAULT_PRESETS, **presets}
                self.save(presets)
            return presets
        except Exception as e:
            logger.error(f"Error loading presets: {e}")
            return self.DEFAULT_PRESETS.copy()
    
    def save(self, presets: Dict[str, Any]) -> bool:
        """Save presets to file"""
        try:
            os.makedirs(os.path.dirname(self.presets_file), exist_ok=True)
            with open(self.presets_file, 'w', encoding="utf-8") as f:
                json.dump(presets, f, indent=2)
            self.presets = presets
            return True
        except Exception as e:
            logger.error(f"Error saving presets: {e}")
            return False
    
    def get(self, preset_id: str) -> Dict[str, Any]:
        """Get a specific preset"""
        return self.presets.get(preset_id)
    
    def update_custom(
        self,
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        name: str = "",
        enabled: bool = True,
        inject_prefix: str = "",
        inject_suffix: str = "",
    ) -> bool:
        """Update the custom preset"""
        self.presets["custom"] = {
            "name": name or "Custom",
            "character_name": name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "system_prompt": system_prompt,
            "inject_prefix": inject_prefix,
            "inject_suffix": inject_suffix,
            "enabled": enabled,
        }
        return self.save(self.presets)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all presets"""
        return self.presets.copy()

    def get_user_templates(self) -> list:
        """Get user-saved character templates."""
        return self.presets.get("user_templates", [])

    def save_user_template(self, template: dict) -> bool:
        """Save a new user template or update existing by id."""
        templates = self.presets.get("user_templates", [])
        # Update existing if same id
        existing = next((i for i, t in enumerate(templates) if t.get("id") == template.get("id")), None)
        if existing is not None:
            templates[existing] = template
        else:
            templates.append(template)
        self.presets["user_templates"] = templates
        return self.save(self.presets)

    def delete_user_template(self, template_id: str) -> bool:
        """Delete a user template by id."""
        templates = self.presets.get("user_templates", [])
        self.presets["user_templates"] = [t for t in templates if t.get("id") != template_id]
        return self.save(self.presets)

    def get_group_presets(self) -> list:
        """Get saved group chat presets."""
        return self.presets.get("group_presets", [])

    def save_group_presets(self, groups: list) -> bool:
        """Save group chat presets."""
        self.presets["group_presets"] = groups
        return self.save(self.presets)
