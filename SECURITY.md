# Security

Secrets storage

- Store secrets such as Telegram tokens and site credentials in the `.env` file only. Do not commit `.env` to version control.
- Use a secure secret store (Vault, AWS Secrets Manager, etc.) for production.

Files that must never be committed

- `/.env`
- `/accounts/accounts.json`
- `/cookies/*.json`
- `/profiles/*`
- `/screenshots/*`
- `/logs/*`
- `/results/*`

Reporting security issues

- To report a security issue, create a private issue in the repository or contact the repository owner directly. Do not post secrets in issue trackers.

Responsible use

- Only use this automation on websites where you have explicit authorization to automate actions. Misuse may violate terms of service or laws.
