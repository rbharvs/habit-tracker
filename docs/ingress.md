# Ingress Architecture

How requests flow from browser to Lambda.

```
Browser
   │
   ▼
┌─────────────────────────────────┐
│  Cloudflare Access              │  Authentication (email OTP)
│  habits.yourdomain.com          │  Restricted to specific email
└─────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────┐
│  Cloudflare DNS (Proxied)       │  CNAME → d-xxx.execute-api...
│  Orange cloud enabled           │  Hides origin, provides DDoS protection
└─────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────┐
│  API Gateway Custom Domain      │  habits.brettharvey.sh
│  Regional endpoint              │  ACM certificate for TLS
│  Base path mapping → Prod stage │  Eliminates /Prod prefix
└─────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────┐
│  API Gateway REST API           │  IP whitelist: Cloudflare IPs only
│  Resource policy                │  Blocks direct access to origin
└─────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────┐
│  Lambda (habit-tracker)         │  Mangum wraps FastAPI
│  ARM64, Python 3.12             │  STORAGE_BACKEND=dynamodb
└─────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────┐
│  DynamoDB (habit-tracker)       │  Single-table design
│  On-demand billing              │  pk=USER#default, sk=HABIT#/ENTRY#
└─────────────────────────────────┘
```

## Security Layers

1. **Cloudflare Access** - Requires authentication before any request reaches origin
2. **IP Whitelist** - API Gateway only accepts requests from Cloudflare IPs
3. **HTTPS everywhere** - TLS termination at Cloudflare and API Gateway

## Key Configuration

| Component | Config Location |
|-----------|-----------------|
| Cloudflare DNS | Cloudflare dashboard → DNS |
| Cloudflare Access | Cloudflare dashboard → Zero Trust → Access |
| Custom Domain | `template.yaml` → CustomDomain, ApiMapping |
| IP Whitelist | `template.yaml` → HabitApi.Auth.ResourcePolicy |
| ACM Certificate | AWS Console (manual, DNS validation via Cloudflare) |

## Environment Variables

Stored in `.env` (gitignored), loaded via direnv:

```bash
ALLOWED_IPS=...        # Cloudflare IP ranges + your IP for testing
DOMAIN_NAME=...        # Custom domain (e.g., habits.yourdomain.com)
CERTIFICATE_ARN=...    # ACM certificate ARN
```

## Bypassing for Local Development

Run locally with JSON storage:
```bash
make dev  # Uses STORAGE_BACKEND=json (default), no auth
```

## Cloudflare Access Policy

Single-user app: Access policy allows only one specific email address. Authentication via email OTP (one-time passcode sent to email).
