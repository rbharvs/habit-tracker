# Research: Lambda Keep-Alive Invocations for Cold Start Reduction

**Date**: 2025-12-27T16:05:33Z
**Git Commit**: e0efa0386c3eaad26fa70d0cde7f18365fd2f727
**Branch**: main

## Research Question

What is the most cost-efficient way to add scheduled keep-alive invocations to the Lambda function to reduce cold starts?

## Summary

For this habit-tracker project (Python 3.12, low-traffic personal use), the most cost-efficient approach is:

1. **EventBridge scheduled rule** with a 5-minute rate expression - essentially free within AWS free tier
2. Optionally enable **Lambda SnapStart** (supported in Python 3.12+) for additional cold start reduction at no extra cost

The project already documents this as a deferred optimization in `docs/research/2025-12-27-hosting-options.md:136-144`. No keep-alive infrastructure currently exists.

---

## Detailed Findings

### Current Infrastructure

The habit-tracker uses AWS SAM for deployment with the following Lambda configuration:

**File**: `template.yaml`
- Runtime: Python 3.12
- Architecture: ARM64 (Graviton2)
- Memory: 256MB
- Timeout: 30 seconds
- Handler: `habit_tracker.handler.handler` (Mangum-wrapped FastAPI)

Currently, the Lambda only responds to API Gateway events (root `/` and proxy `/{proxy+}`). No scheduled events are configured.

**Documented deferral** (`docs/plans/2025-12-27-aws-lambda-deployment.md:43`):
> - EventBridge keep-warm rule (can add later if cold starts are problematic)

---

### Cost-Efficient Keep-Alive Options

#### Option 1: EventBridge Scheduled Rule (Recommended)

**Cost**: Essentially free for personal use

| Component | Monthly Cost |
|-----------|-------------|
| EventBridge rule | Free (first 64K events/month) |
| Lambda invocations | ~8,640/month at 5-min interval (within free tier of 1M/month) |
| Lambda compute | ~43 seconds total (negligible at 256MB) |

**Implementation**: Add to `template.yaml`:
```yaml
WarmUpEvent:
  Type: Schedule
  Properties:
    Schedule: rate(5 minutes)
    Input: '{"source": "warmup"}'
```

**Why 5 minutes**: Lambda execution environments typically recycle after 5-6 minutes of inactivity for non-VPC functions.

#### Option 2: Lambda SnapStart (Complementary)

**Cost**: Free (only snapshot storage, negligible)

SnapStart creates encrypted snapshots of initialized execution environments, reducing cold starts by up to 90%.

**Requirements**:
- Python 3.12+ ✓ (this project qualifies)
- Published function versions
- No frozen state issues (network connections, random values)

**Implementation**: Add to `template.yaml` under the Lambda function:
```yaml
SnapStart:
  ApplyOn: PublishedVersions
```

#### Option 3: Provisioned Concurrency (Not Recommended for This Project)

**Cost**: ~$15-20/month minimum for always-ready capacity

This guarantees no cold starts but is overkill for a personal habit tracker with intermittent traffic. The cost structure:
- $0.0000041667/GB-second idle charge
- Free tier does NOT apply

---

### Comparison of Approaches

| Approach | Cold Start Elimination | Monthly Cost | Complexity |
|----------|----------------------|--------------|------------|
| EventBridge keep-warm | Partial (not during scale-out) | < $1 | Low |
| SnapStart | Reduces by ~90% | Free | Low |
| EventBridge + SnapStart | Best free option | < $1 | Low |
| Provisioned Concurrency | Guaranteed | ~$15-20+ | Medium |

---

### Implementation Details for EventBridge

**Handler modification** (`src/habit_tracker/handler.py`):

The handler would need to detect and respond to warmup events differently from API Gateway events:

```python
def handler(event, context):
    # Check if this is a warmup event
    if event.get("source") == "warmup":
        return {"statusCode": 200, "body": "warm"}

    # Normal API Gateway handling
    return mangum_handler(event, context)
```

**SAM template addition** (`template.yaml`):

```yaml
HabitFunction:
  Type: AWS::Serverless::Function
  Properties:
    # ... existing properties ...
    Events:
      Root:
        Type: Api
        # ... existing config ...
      Proxy:
        Type: Api
        # ... existing config ...
      WarmUp:
        Type: Schedule
        Properties:
          Schedule: rate(5 minutes)
          Input: '{"source": "warmup"}'
          Enabled: true
```

---

### Important Caveats

1. **Keep-warm pings don't eliminate all cold starts**:
   - New concurrent invocations still cold-start
   - AWS may recycle environments early for internal reasons
   - AZ failover creates new cold environments

2. **EventBridge minimum resolution is 1 minute** - cannot schedule at second-level precision

3. **SnapStart limitations**:
   - Snapshots expire after 14 days of no invocations
   - Requires careful handling of state that shouldn't be frozen (connections, credentials)

---

## Code References

- `template.yaml` - SAM template defining Lambda and API Gateway
- `src/habit_tracker/handler.py` - Lambda handler entry point
- `docs/research/2025-12-27-hosting-options.md:136-144` - Cold start mitigation strategies
- `docs/plans/2025-12-27-aws-lambda-deployment.md:43` - EventBridge deferred as future work

---

## Architecture Notes

The current architecture uses:
- **AWS SAM** for infrastructure-as-code
- **API Gateway REST API** with IP whitelisting
- **DynamoDB** single-table design for storage
- **Mangum** to wrap FastAPI for Lambda

Adding EventBridge would be a minimal change to the existing SAM template, requiring:
1. New `Schedule` event under the Lambda function
2. Optional handler modification to short-circuit warmup requests

---

## Sources

- [EventBridge Scheduler documentation](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-run-lambda-schedule.html)
- [AWS Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [Lambda SnapStart for Python](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)
- [Serverless Plugin WarmUp](https://www.serverless.com/plugins/serverless-plugin-warmup)
- [Lambda Warmer by Jeremy Daly](https://www.jeremydaly.com/lambda-warmer-optimize-aws-lambda-function-cold-starts/)

---

## Open Questions

1. Should warmup be limited to specific hours (e.g., 6am-11pm) to further reduce invocations?
2. Is SnapStart compatible with the current Mangum/FastAPI initialization pattern?

---

## Implementation (2025-12-27)

The keep-alive feature was implemented using TDD:

### Changes Made

1. **Handler modification** (`src/habit_tracker/handler.py:14-17`):
   - Detects `{"source": "warmup"}` events
   - Calls `storage.load_habits()` to warm DynamoDB connection
   - Returns early with `{"statusCode": 200, "body": "warm"}`

2. **SAM template** (`template.yaml:61-66`):
   - Added `WarmUp` event with `rate(5 minutes)` schedule
   - Passes `{"source": "warmup"}` as input

3. **Test** (`tests/test_handler.py:108-128`):
   - Verifies warmup event handling
   - Confirms DynamoDB connection is warmed

### Observed Metrics (pre-implementation)

- Cold start init: 1,266ms
- First request after cold start: ~5.7s (includes DynamoDB connection setup)
- Warm requests: 2-60ms
- Cold start rate: 13% (12 of 90 invocations over 7 days)
- Memory usage: 122MB (256MB allocated)
