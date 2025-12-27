"""AWS Lambda handler using Mangum."""

from mangum import Mangum

from habit_tracker.main import app
from habit_tracker.storage import get_storage

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    """Lambda handler with trailing slash redirect for API Gateway."""
    # Handle EventBridge warmup events to reduce cold starts
    if event.get("source") == "warmup":
        storage = get_storage()
        storage.load_habits()  # Warm DynamoDB connection
        return {"statusCode": 200, "body": "warm"}

    # Check if request needs trailing slash redirect for relative URL resolution
    request_context = event.get("requestContext", {})
    full_path = request_context.get("path", "")
    resource_path = event.get("path", "")

    # If hitting index route without trailing slash, redirect to add it
    if resource_path == "/" and full_path and not full_path.endswith("/"):
        return {
            "statusCode": 307,
            "headers": {"location": full_path + "/"},
            "body": "",
        }

    return _mangum_handler(event, context)
