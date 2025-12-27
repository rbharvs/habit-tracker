"""AWS Lambda handler using Mangum."""

from mangum import Mangum

from habit_tracker.main import app

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    """Lambda handler with trailing slash redirect for API Gateway."""
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
