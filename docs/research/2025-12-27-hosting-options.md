# Research: Hosting a Personal Habit Tracker

**Date**: 2025-12-27
**Git Commit**: 8da29ab8fa92e0ab82e6d2eda59d77fff5eed152
**Branch**: main

## Executive Summary

This document evaluates low-cost, low-maintenance hosting options for a personal FastAPI + HTMX habit tracker, considering compute, storage, latency, and authentication.

### Recommendation: Lambda + DynamoDB + Cloudflare Access

| Factor | Value |
|--------|-------|
| **Monthly Cost** | $0-2 |
| **Maintenance** | Low |
| **Warm Latency** | ~70ms p50 |
| **Cold Starts** | <1% of requests @ 500-800ms |
| **Auth** | Google login via Cloudflare Access (no code changes) |
| **Re-auth** | Every 30 days - 1 year (configurable) |
| **Storage** | Effectively unlimited (25 GB free) |
| **Code Changes** | Storage layer rewrite only (~1-2 hours) |

**Why this stack wins:**
- **Cost**: Always-free tier (not 12-month trial like EC2)
- **Latency**: DynamoDB adds only 1-3ms reads vs 40-60ms for S3
- **Storage limits**: DynamoDB free tier (25 GB, ~200M reads/mo) vs Vercel KV (256 MB transfer/mo)
- **Auth**: Cloudflare Access with Google—no Google Cloud Console setup, no code changes, zero JWT handling
- **Cold starts**: Shorter than Vercel (500-800ms vs 1-3s), eliminable with free EventBridge ping
- **Bonus**: Cloudflare provides CDN caching and DDoS protection for free

**Alternative**: EC2 + Tailscale if you want zero re-authentication and zero code changes, at $6-8/month after free tier.

---

## Current Application Architecture

### Technical Stack
- **Framework**: FastAPI 0.115.0+ (ASGI)
- **Server**: Uvicorn
- **Frontend**: HTMX + Jinja2 templates (CSS/JS from CDN)
- **Storage**: JSON files in `data/` directory
- **Python**: 3.12+
- **Features**: Auto-save on form changes via HTMX

### Key Files
| File | Purpose |
|------|---------|
| `src/habit_tracker/main.py` | FastAPI app entry point |
| `src/habit_tracker/storage.py` | JSON file operations (rewrite needed for serverless) |
| `src/habit_tracker/models.py` | Pydantic models with discriminated unions |

---

## Hosting Options Compared

### Quick Comparison

| Factor | Vercel | Lambda + DynamoDB | EC2 + Tailscale | Fargate + EFS |
|--------|--------|-------------------|-----------------|---------------|
| **Monthly Cost** | $0 | $0-2 | $0 → $6-8 | $15-20 |
| **Maintenance** | Very Low | Low | Medium | Medium |
| **Storage Rewrite** | Yes | Yes | No | No |
| **Cold Starts** | 0.6% @ 1-3s | <1% @ 500-800ms | None | Scale-up: 20-60s |
| **Warm Latency (p50)** | ~110ms | ~70ms | ~55ms | ~55ms |
| **Warm Latency (p99)** | ~330ms | ~150ms | ~100ms | ~100ms |
| **Best Auth Option** | Cloudflare Access | Cloudflare Access | Tailscale (no auth needed) | Cloudflare Access |
| **Re-auth Frequency** | 30d - 1yr | 30d - 1yr | Never | 30d - 1yr |
| **Free Tier Limits** | 256 MB transfer/mo | 25 GB storage | 12 months | N/A |

### Why Not Vercel?

Vercel is the simplest to deploy, but has restrictive free tier limits:

| Resource | Vercel KV (Hobby) | DynamoDB (Always Free) |
|----------|-------------------|------------------------|
| Requests | 30,000/month | ~200M reads/month |
| Storage | 256 MB | 25 GB |
| Data Transfer | **256 MB/month** | 100 GB |

With auto-save enabled, each habit toggle or journal edit triggers a request. The **256 MB monthly transfer limit** is the tightest constraint—one feature addition (history view, charts) could push you over, and exceeding limits **stops service until next month**.

### Why Not EC2?

EC2 is the simplest if you want zero code changes:
- Keep current JSON file storage
- No cold starts, fastest latency
- Full control

But:
- **Free tier expires** after 12 months ($6-8/month ongoing)
- **Higher maintenance**: OS updates, security patches, certificate renewal
- **10-year cost**: ~$720-960 vs ~$0-20 for Lambda

EC2 makes sense if you also run other projects on the same instance, or pair it with **Tailscale** for zero-auth access (see Authentication section).

### Why Lambda + DynamoDB?

Best balance of cost, performance, and scalability:

| Aspect | Benefit |
|--------|---------|
| **Always-free tier** | Not a 12-month trial |
| **DynamoDB latency** | 1-3ms reads (vs 40-60ms for S3) |
| **Headroom** | Effectively unlimited for personal use |
| **Cold starts** | Shorter than Vercel, eliminable for free |
| **Cognito auth** | Native AWS integration |

---

## Latency Deep Dive

### End-to-End Request Latency

| Component | Lambda + DynamoDB | Vercel + KV | EC2 |
|-----------|-------------------|-------------|-----|
| User → Server | 10-50ms | 5-20ms (edge) | 20-50ms |
| TLS Handshake | 10-50ms | 0 (edge terminates) | 10-50ms |
| Cold Start | 500-800ms (<1%) | 1-3s (0.6%) | None |
| Gateway/Proxy | <10ms | ~5ms | 1-2ms |
| Compute | 15-35ms | 5-20ms | 5-20ms |
| Storage | **1-3ms** | 2-5ms | <1ms |

### Storage Latency Comparison

| Storage | Read (p50) | Read (p99) | Write (p50) |
|---------|-----------|-----------|------------|
| Local disk (cached) | 0.01ms | 0.1ms | 0.01ms |
| EBS gp3 (EC2) | 1-5ms | 5-10ms | 1-5ms |
| **DynamoDB** | **1-3ms** | 10-20ms | 10-20ms |
| Vercel KV | 2-5ms | 15-40ms | 4-5ms |
| S3 Standard | 20-30ms | 80-140ms | 25-40ms |

**Key insight**: Avoid S3 for this use case. DynamoDB and Vercel KV have similar latency, but DynamoDB has far more generous free tier limits.

### Cold Start Mitigation (Lambda)

| Strategy | Cost | Effect |
|----------|------|--------|
| SnapStart (Python 3.12+) | Free | Reduces to <700ms |
| EventBridge ping every 5 min | Free | Keeps function warm |
| Provisioned Concurrency | ~$15-20/mo | Eliminates cold starts |

For personal use, the **free EventBridge ping** is sufficient—schedule a ping every 5-10 minutes during your typical usage hours.

---

## Authentication

### Threat Model

| Data | Sensitivity | Attacker Value |
|------|-------------|----------------|
| Habit completions | Low | None |
| Journal entries | Medium-High | Low (unless targeted) |
| Personal patterns | Medium | Low |

This is private data you don't want public, but not high-value to attackers. The main threats are:

| Threat | Risk | Mitigation |
|--------|------|------------|
| Brute force | Medium | OAuth (no password to brute force) |
| Credential stuffing | Low-Medium | OAuth (no password to stuff) |
| Phishing | Low | OAuth (attacker must phish Google, not your app) |
| Device theft | Low | Revoke sessions from Google account |

### Auth Options

| Method | Re-auth Frequency | Implementation | Platforms |
|--------|-------------------|----------------|-----------|
| **Cloudflare Access** | 30d - 1yr | **Zero code** | Any |
| Cognito + Google OAuth | 30d - 1yr | Medium (code + config) | AWS only |
| **Tailscale** | **Never** | Zero code | EC2 only |
| DIY password + cookie | 1 year | Simple | Any |

### Recommendation: Cloudflare Access

Cloudflare Access sits in front of your app and handles authentication at the edge—your app doesn't need any auth code.

**Why Cloudflare Access wins:**

| Aspect | Cloudflare Access | AWS Cognito |
|--------|-------------------|-------------|
| Google Cloud Console setup | **Not needed** | Required |
| OAuth credentials | **Not needed** | Required |
| Code changes | **None** | JWT handling required |
| Setup time | ~15 minutes | ~1-2 hours |
| Session duration | Up to 1 year | Up to 10 years |
| Extra benefits | CDN + DDoS protection | Native AWS |
| AJAX/HTMX apps | CORS config required | Works natively |

**How it works:**
```
User → Cloudflare Edge → [Auth Check] → API Gateway → Lambda
                ↓
        Google login (if not authenticated)
```

Cloudflare has its own registered Google OAuth app, so you don't need to touch Google Cloud Console.

**Setup steps:**
1. Add your domain to Cloudflare (free plan)
2. Go to Zero Trust → Access → Applications → Add Application
3. Select "Self-hosted", enter your subdomain (habits.mydomain.com)
4. Add policy: "Include" → "Emails" → your email address
5. **Configure CORS settings** (see below—required for HTMX/AJAX)
6. Identity providers → Add Google (one click, no credentials needed)
7. Done—Cloudflare handles the rest

**CORS Configuration (Required for HTMX):**

Since the habit tracker uses HTMX auto-save (AJAX requests), you must configure CORS in the Access application settings. Without this, browser preflight requests will fail with 403.

In the Access application → Settings → CORS:
- `Access-Control-Allow-Credentials`: **Enabled**
- `Access-Control-Max-Age`: **86400** (must not be blank)
- `Access-Control-Allow-Origin`: **https://habits.mydomain.com** (your exact origin, not "*")
- **Allow all HTTP request methods**: Enabled
- **Allow all HTTP headers**: Enabled

Why this is needed: Browsers send OPTIONS preflight requests before POST/PUT, and by design browsers never include cookies with OPTIONS requests. The CORS configuration tells Cloudflare to allow these preflight requests through.

**Session configuration:**
- Default: 24 hours
- Configurable: up to 1 month per session, longer with "WARP client required"
- Users stay logged in as long as they're logged into Google in their browser

### Alternative: EC2 + Tailscale

If "never re-authenticate" is a priority:

- Install Tailscale on your devices once
- App is only accessible via Tailscale network (invisible to public internet)
- No login screens ever, no auth code needed
- Trade-off: Requires always-on server ($6-8/month after free tier)

### Alternative: AWS Cognito (AWS-only)

If you want to stay entirely within AWS (no Cloudflare):

- More complex: Google Cloud Console setup, Cognito User Pool, JWT authorizer
- Requires frontend code to handle tokens
- Benefit: No external vendor dependency
- See [AWS Cognito Developer Guide](https://docs.aws.amazon.com/cognito/latest/developerguide/) for setup

---

## Deployment Guide: Lambda + DynamoDB + Cloudflare Access

### Project Structure

```
habit-tracker/
├── src/
│   └── habit_tracker/
│       ├── __init__.py
│       ├── main.py              # FastAPI app (unchanged)
│       ├── models.py            # Pydantic models (unchanged)
│       ├── storage.py           # Rewritten for DynamoDB
│       ├── handler.py           # New: Lambda entry point
│       └── templates/           # Jinja2 templates (unchanged)
├── template.yaml                # New: SAM template
├── samconfig.toml               # Generated by sam deploy --guided
└── pyproject.toml               # Updated dependencies
```

### 1. Dependencies

```toml
# pyproject.toml
dependencies = [
    "fastapi>=0.115.0",
    "mangum>=0.19.0",          # ASGI adapter for Lambda
    "boto3>=1.35.0",           # AWS SDK
    "pydantic>=2.0.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.9",
    # Remove: uvicorn (not needed in Lambda)
]
```

### 2. Lambda Handler

```python
# src/habit_tracker/handler.py
from mangum import Mangum
from habit_tracker.main import app

handler = Mangum(app, lifespan="off")
```

### 3. Storage Layer (Rewrite)

```python
# src/habit_tracker/storage.py
import os
import boto3
from datetime import date
from habit_tracker.models import Habit, HabitEntry

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "habit-tracker"))


def load_habits() -> list[Habit]:
    response = table.get_item(Key={"pk": "CONFIG", "sk": "habits"})
    if "Item" not in response:
        return []
    return [parse_habit(h) for h in response["Item"]["habits"]]


def save_habits(habits: list[Habit]) -> None:
    table.put_item(Item={
        "pk": "CONFIG",
        "sk": "habits",
        "habits": [h.model_dump() for h in habits]
    })


def load_entries(d: date) -> list[HabitEntry]:
    response = table.get_item(Key={"pk": "ENTRIES", "sk": str(d)})
    if "Item" not in response:
        return []
    return [parse_entry(e) for e in response["Item"]["entries"]]


def save_entries(d: date, entries: list[HabitEntry]) -> None:
    table.put_item(Item={
        "pk": "ENTRIES",
        "sk": str(d),
        "entries": [e.model_dump() for e in entries]
    })
```

### 4. SAM Template

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Timeout: 30
    Runtime: python3.12
    MemorySize: 256
    Environment:
      Variables:
        TABLE_NAME: !Ref HabitTable

Resources:
  # --- API Gateway (no auth - Cloudflare handles it) ---
  HabitApi:
    Type: AWS::Serverless::HttpApi

  # --- Lambda ---
  HabitFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: habit_tracker.handler.handler
      CodeUri: src/
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            ApiId: !Ref HabitApi
            Path: /{proxy+}
            Method: ANY
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref HabitTable

  # --- DynamoDB ---
  HabitTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: habit-tracker
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE

  # --- Keep Warm (Optional) ---
  WarmingRule:
    Type: AWS::Events::Rule
    Properties:
      ScheduleExpression: rate(5 minutes)
      Targets:
        - Id: WarmLambda
          Arn: !GetAtt HabitFunction.Arn

  WarmingPermission:
    Type: AWS::Lambda::Permission
    Properties:
      Action: lambda:InvokeFunction
      FunctionName: !Ref HabitFunction
      Principal: events.amazonaws.com
      SourceArn: !GetAtt WarmingRule.Arn

Outputs:
  ApiUrl:
    Description: API Gateway URL (point Cloudflare to this)
    Value: !Sub https://${HabitApi}.execute-api.${AWS::Region}.amazonaws.com
```

Note: No auth configuration in AWS—Cloudflare Access handles authentication before requests reach API Gateway.

### 5. Deploy to AWS

```bash
# Install SAM CLI
pip install aws-sam-cli

# Configure AWS credentials
aws configure

# Build and deploy
sam build
sam deploy --guided   # First time: interactive prompts

# Note the API URL from the output:
# https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com

# Subsequent deploys
sam build && sam deploy
```

### 6. Configure Cloudflare

#### Add Domain to Cloudflare

1. Sign up at [Cloudflare](https://dash.cloudflare.com/) (free)
2. Add your domain (mydomain.com)
3. Update nameservers at Namecheap to Cloudflare's nameservers
4. Wait for DNS propagation (up to 24 hours, usually faster)

#### Create DNS Record for Subdomain

1. In Cloudflare DNS → Add record:
   - Type: CNAME
   - Name: `habits`
   - Target: Your API Gateway URL (e.g., `xxxxxxxxxx.execute-api.us-east-1.amazonaws.com`)
   - Proxy status: **Proxied** (orange cloud) — required for Access to work

#### Configure Cloudflare Access

1. Go to **Zero Trust** → **Access** → **Applications**
2. Click **Add an application** → **Self-hosted**
3. Configure:
   - Application name: `Habit Tracker`
   - Session duration: `1 month` (or your preference)
   - Application domain: `habits.mydomain.com`
4. Add policy:
   - Policy name: `Allow me`
   - Action: `Allow`
   - Include: `Emails` → your email address
5. **Configure CORS** (required for HTMX auto-save):
   - Go to application **Settings** → **CORS**
   - `Access-Control-Allow-Credentials`: **Enabled**
   - `Access-Control-Max-Age`: **86400**
   - `Access-Control-Allow-Origin`: **https://habits.mydomain.com**
   - **Allow all HTTP request methods**: Enabled
   - **Allow all HTTP headers**: Enabled
6. Click **Save**

#### Enable Google Login

1. Go to **Settings** → **Authentication** → **Login methods**
2. Click **Add new** → **Google**
3. Click **Save** (no credentials needed—Cloudflare uses its own OAuth app)

That's it. Visit `habits.mydomain.com` and you'll be prompted to log in with Google.

#### Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| 403 on auto-save | CORS not configured | Add CORS settings above |
| 521 error | Wrong SSL mode | Set SSL/TLS to "Full" (not "Flexible") |
| Infinite redirect | Proxy not enabled | Enable orange cloud on DNS record |

### Effort Estimate

| Task | Time |
|------|------|
| Storage layer rewrite | 1-2 hours |
| SAM template setup | 30 min |
| First deployment + debugging | 1-2 hours |
| Cloudflare DNS + Access setup | 30 min |
| **Total** | **3-5 hours** |

---

## Alternative: EC2 + Tailscale

If you prioritize zero re-authentication and zero code changes:

### Setup

1. Launch t3.micro EC2 instance (free tier eligible)
2. Install Tailscale: `curl -fsSL https://tailscale.com/install.sh | sh`
3. Join your Tailnet: `sudo tailscale up`
4. Install app dependencies and run Uvicorn
5. Access via Tailscale IP (no public internet exposure)

### Security

- App is **invisible to the public internet**
- Only devices on your Tailnet can access
- No login screens, ever
- Tailscale handles device authentication

### Trade-offs

| Aspect | EC2 + Tailscale | Lambda + Cognito |
|--------|-----------------|------------------|
| Cost (year 1) | $0 | $0 |
| Cost (year 2+) | $6-8/month | $0-2/month |
| Re-auth | Never | Every 30d - 1yr |
| Code changes | None | Storage rewrite |
| Maintenance | Medium (OS updates) | Low |
| Mobile access | Tailscale app required | Browser only |

---

## Sources

### Hosting & Pricing
- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vercel Pricing](https://vercel.com/pricing)
- [Vercel Storage](https://vercel.com/docs/storage)
- [Vercel Fluid Compute](https://vercel.com/docs/fluid-compute)
- [AWS Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [AWS API Gateway Pricing](https://aws.amazon.com/api-gateway/pricing/)
- [AWS Free Tier](https://aws.amazon.com/free/)
- [Mangum - ASGI Adapter for Lambda](https://github.com/Kludex/mangum)

### Storage & Latency
- [Understanding Amazon DynamoDB Latency](https://aws.amazon.com/blogs/database/understanding-amazon-dynamodb-latency/)
- [DynamoDB Performance & Latency](https://dynobase.dev/dynamodb-performance-latency/)
- [AWS S3 Performance Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html)
- [Tigris Small Objects Benchmark](https://www.tigrisdata.com/blog/benchmark-small-objects/)
- [Serverless Database Latency Comparison](https://pilcrow.vercel.app/blog/serverless-database-latency)
- [Upstash Latency Comparison](https://upstash.com/blog/latency-comparison)

### Cold Starts
- [Cold Starts in AWS Lambda](https://mikhail.io/serverless/coldstarts/aws/)
- [AWS Lambda SnapStart for Python](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)
- [Vercel Cold Start Performance Guide](https://vercel.com/kb/guide/how-can-i-improve-serverless-function-lambda-cold-start-performance-on-vercel)
- [OpenStatus: Vercel Edge vs Serverless Latency](https://www.openstatus.dev/blog/monitoring-latency-vercel-edge-vs-serverless)

### Authentication
- [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/policies/access/)
- [Cloudflare Access CORS Configuration](https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/cors/)
- [Cloudflare Zero Trust - Free Plan](https://www.cloudflare.com/plans/zero-trust-services/)
- [Set up API Gateway with Cloudflare](https://www.leanx.eu/tutorials/set-up-amazons-api-gateway-custom-domain-with-cloudflare)
- [Tailscale](https://tailscale.com/)
- [AWS Cognito Developer Guide](https://docs.aws.amazon.com/cognito/latest/developerguide/) (if staying AWS-only)

### Custom Domains
- [Namecheap Subdomain Setup](https://www.namecheap.com/support/knowledgebase/article.aspx/9776/2237/how-to-create-a-subdomain-for-my-domain/)
- [API Gateway Custom Domains](https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-custom-domains.html)
