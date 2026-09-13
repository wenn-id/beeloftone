# Secure browser session milestone

Source: Beeloft One Concept Blueprint, V1 Technical Implementation. V1 requires single sign-on and
role-based access. This milestone establishes the browser authentication boundary needed before an
external identity provider is connected.

## Contract

- The dashboard exchanges a local API key once for an eight-hour server-side browser session.
- The browser receives an `HttpOnly`, `SameSite=Strict` session cookie and a separate CSRF cookie.
  HTTPS responses mark both cookies `Secure`.
- Only SHA-256 hashes of session and CSRF tokens are stored. Expired sessions and sessions belonging
  to disabled users cannot authenticate.
- Session-authenticated state changes require the matching `X-CSRF-Token` header.
- Logout revokes the server-side session and clears both cookies.
- Page reload restores the current actor without retaining or resending the API key.
- Header-based API-key authentication remains available for workers and non-browser clients.

## Deliberate limits

The local API key remains the initial browser credential. This milestone does not add an identity
provider, OIDC discovery, authorization redirects, callbacks, claim mapping, MFA, or SSO. Those require
provider configuration and deployment behind HTTPS.
