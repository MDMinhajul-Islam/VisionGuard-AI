# Session Security

Sessions are signed HS256 JWTs with issuer, audience, subject, role, issued/expiry times, unique JTI, and user session version. Every token must match a non-revoked `AuthSession` row. Logout revokes the JTI before deleting the cookie. Password changes increment the session version and revoke active sessions.

Cookies are HttpOnly and SameSite=Strict; `Secure` is configuration-controlled and mandatory behind HTTPS. Cookie-authenticated POST/PATCH/PUT/DELETE calls require an Origin in the configured frontend origin list. Bearer-authenticated local CLI requests are exempt from this browser defense.

Login uses Argon2id, a dummy hash for missing users, uniform failure responses, and a sliding-window limiter keyed by client address and normalized email. The limiter is process-local and must move to a shared store before multi-instance deployment.
