# OIDC single sign-on milestone

Source: Beeloft One Concept Blueprint, Recommended V1. V1 requires single sign-on and role-based
access. Browser sessions and application roles already exist; this milestone connects them to one
external OpenID Connect provider.

## Contract

- OIDC is disabled unless issuer, client ID, client secret, and redirect URI are all configured.
- Login uses Authorization Code Flow with PKCE, state, and nonce. A short-lived `HttpOnly`,
  `SameSite=Lax` cookie binds state to the initiating browser.
- Discovery must return the exact configured issuer and HTTPS authorization, token, and JWKS endpoints.
- The callback verifies the ID-token signature and requires matching issuer, audience, expiry, issued-at,
  subject, nonce, and authorized party where applicable. Only RS256 and ES256 are accepted.
- An `(issuer, subject)` mapping selects an existing Beeloft user. The provider cannot create accounts
  or assign roles. Disabled users cannot sign in.
- Successful SSO creates the same eight-hour browser session and CSRF protection as local-key login.
- Local API-key login remains available for recovery, workers, and non-browser clients.

## Operations

Administrators create and remove identity mappings through the local CLI. Secrets remain in environment
variables and never enter SQLite, browser storage, redirect URLs, or API responses.

## Deliberate limits

This milestone supports one configured provider. It excludes automatic user provisioning, claim-based
role mapping, multi-provider selection, refresh tokens, single logout at the provider, internal MFA,
and a mapping-management screen.
