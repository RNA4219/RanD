# Security Policy

## Supported versions

Security fixes are applied to the latest released minor version. RanD v0.3.x and
tracker-bridge v1.1.x are the supported lines for the live GitHub delivery path.

## Reporting a vulnerability

Do not open a public issue for credential exposure, arbitrary command execution,
path traversal, unsafe redirect handling, or unintended external issue creation.
Report privately through GitHub Security Advisories with reproduction steps,
affected version, and impact.

## Secret handling

Tracker credentials must be referenced by tracker_connection.secret_ref and
provided through the named environment variable. Tokens must not be stored in
RanD artifacts, taskstate, tracker-bridge SQLite data, exception text, or logs.

Live delivery requires both --delivery-mode live and --confirm-live (or
RAND_CONFIRM_LIVE_DELIVERY=1). CI must never use real tracker credentials or
create external issues.