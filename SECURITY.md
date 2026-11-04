# Security policy

## Reporting a vulnerability

Do not publish credentials, workspace keys, personal data, or exploit details in a public issue.
For a private report, contact the repository maintainer through the contact method listed in the
GitHub profile. Include the affected version, impact, and reproducible steps where safe.

## Deployment checklist

- Use HTTPS and keep the reverse proxy in front of the application.
- Set unique, long `APP_SECRET`, `ADMIN_SECRET`, and PostgreSQL credentials.
- Keep `.env`, TLS private keys, database dumps, and workspace keys out of Git.
- Restrict access to the admin secret and rotate it if exposure is suspected.
- Back up PostgreSQL regularly and test restoration.
- Apply OS, Docker, Python dependency, and database security updates.
- Do not treat publication redaction as guaranteed anonymization: manually review content,
  document metadata, images, and attachments before publishing.

## Current security limitations

The project currently uses `Base.metadata.create_all()` rather than versioned database migrations.
There is no built-in API rate limiting, MFA for administrators, or automated secret rotation.
Workspace creation is public and should be protected by infrastructure-level controls before
opening the service to the public internet.
