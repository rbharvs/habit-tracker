# IAM Setup

## Architecture

```
┌─────────────────────────────┐
│   HabitTrackerDeploy        │  (Managed Policy)
│   - CloudFormation          │
│   - S3 (artifacts)          │
│   - Lambda                  │
│   - API Gateway             │
│   - DynamoDB                │
│   - EventBridge             │
│   - IAM (for Lambda role)   │
└──────────────┬──────────────┘
               │ attached to
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐  ┌─────────────────────┐
│ Local Role  │  │ GitHub Actions Role │
│ (AssumeRole)│  │ (OIDC Federation)   │
└──────┬──────┘  └──────────┬──────────┘
       │                    │
       ▼                    ▼
   IAM User            GitHub OIDC
                       Provider
```

## Roles

| Role | Trust | Purpose |
|------|-------|---------|
| `HabitTrackerDeployRole` | IAM user | Local `make deploy` |
| `GitHubActionsHabitTracker` | GitHub OIDC | CI/CD deploys |

Both roles attach the same `HabitTrackerDeploy` policy.

## Local Setup

1. IAM user with permission to assume the deploy role
2. AWS CLI profile in `~/.aws/config`:
   ```ini
   [profile habit-tracker-deploy]
   role_arn = arn:aws:iam::ACCOUNT:role/HabitTrackerDeployRole
   source_profile = your-iam-user-profile
   ```
3. `.env` sets `AWS_PROFILE=habit-tracker-deploy`

## Policy Updates

Update the single `HabitTrackerDeploy` policy. Both roles automatically use the default version.

```bash
# View current policy
aws iam get-policy-version \
  --policy-arn arn:aws:iam::ACCOUNT:policy/HabitTrackerDeploy \
  --version-id $(aws iam get-policy --policy-arn arn:aws:iam::ACCOUNT:policy/HabitTrackerDeploy --query 'Policy.DefaultVersionId' --output text) \
  --query 'PolicyVersion.Document'

# Create new version (delete old if at 5 version limit)
aws iam create-policy-version \
  --policy-arn arn:aws:iam::ACCOUNT:policy/HabitTrackerDeploy \
  --policy-document file://new-policy.json \
  --set-as-default
```

## Why This Setup?

- **Single policy**: Update permissions once, applies to both local and CI
- **Role assumption locally**: Catches permission errors before pushing to CI
- **Least privilege**: Deploy permissions are scoped to this project's resources
