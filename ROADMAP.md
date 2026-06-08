# ArgoDesk Roadmap

This is a short, forward-looking roadmap for ArgoDesk, the self-hosted AI
workspace for Italian small businesses and freelancers (PMI e P.IVA). It is
maintained by the internal product team and reflects current priorities, not a
public help-wanted list.

## Near term

- Reliability hardening across chat, agent, email, and Deep Research flows.
- Cookbook (model download/serve) robustness across different machines, GPUs,
  drivers, and Python environments.
- Clearer error feedback and copyable logs for failed downloads, dependency
  installs, and serve jobs.
- Localized (Italian) onboarding, setup hints, and in-app guidance for PMI/P.IVA
  users.

## Product direction

- Deep Research model presets tuned by available hardware.
- Better AI integration for Notes and Tasks (read, update, summarize, act).
- Stronger admin-only tool safeguards and clearer documentation of their risk.
- Backup/restore guidance and helper flows for `data/`.
- Accessibility and mobile/editor polish.

## Internal quality

- Continued prompt-injection auditing of user-editable and fetched content.
- Performance profiling of email (IMAP/SMTP) and provider probing paths.
- Dead-code passes for stale routes, feature flags, and unused UI states.

---

> Note: ArgoDesk is a closed-source commercial product derived from an upstream
> open-source project. Third-party components and their original authors are
> credited in [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) and [LICENSE](LICENSE).
