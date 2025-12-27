"""Tests for the Lambda handler."""

from unittest.mock import MagicMock


def test_handler_exists():
    """Test that the Mangum handler is properly configured."""
    from habit_tracker.handler import handler

    # Verify handler is a Mangum instance wrapping our app
    assert handler is not None
    assert callable(handler)


def test_handler_processes_event():
    """Test that handler can process a REST API v1 event."""
    from habit_tracker.handler import handler

    # Create a REST API v1 event (used with AWS::Serverless::Api)
    event = {
        "resource": "/",
        "path": "/",
        "httpMethod": "GET",
        "headers": {
            "Host": "test.execute-api.us-east-1.amazonaws.com",
            "Accept": "text/html",
        },
        "queryStringParameters": None,
        "pathParameters": None,
        "stageVariables": None,
        "requestContext": {
            "resourceId": "root",
            "resourcePath": "/",
            "httpMethod": "GET",
            "path": "/Prod/",
            "accountId": "123456789012",
            "protocol": "HTTP/1.1",
            "stage": "Prod",
            "requestTimeEpoch": 1735689600000,
            "requestId": "test-request-id",
            "identity": {
                "sourceIp": "127.0.0.1",
                "userAgent": "test-agent",
            },
            "domainName": "test.execute-api.us-east-1.amazonaws.com",
            "apiId": "abcdef123",
        },
        "body": None,
        "isBase64Encoded": False,
    }
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 256
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    context.aws_request_id = "test-request-id"
    context.get_remaining_time_in_millis = MagicMock(return_value=30000)

    response = handler(event, context)

    # Should get an HTML response (the index page)
    assert response is not None
    assert "statusCode" in response
    assert response["statusCode"] == 200
    assert "text/html" in response.get("headers", {}).get("content-type", "")


def test_handler_redirects_missing_trailing_slash():
    """Request to /Prod (no slash) redirects to /Prod/ for relative URL resolution."""
    from habit_tracker.handler import handler

    # Request to /Prod WITHOUT trailing slash
    event = {
        "resource": "/",
        "path": "/",
        "httpMethod": "GET",
        "headers": {
            "Host": "test.execute-api.us-east-1.amazonaws.com",
            "Accept": "text/html",
        },
        "queryStringParameters": None,
        "pathParameters": None,
        "stageVariables": None,
        "requestContext": {
            "resourceId": "root",
            "resourcePath": "/",
            "httpMethod": "GET",
            "path": "/Prod",  # NO trailing slash - this is the problem case
            "stage": "Prod",
            "requestTimeEpoch": 1735689600000,
            "requestId": "test-request-id",
            "identity": {"sourceIp": "127.0.0.1"},
            "domainName": "test.execute-api.us-east-1.amazonaws.com",
            "apiId": "abcdef123",
        },
        "body": None,
        "isBase64Encoded": False,
    }
    context = MagicMock()
    context.get_remaining_time_in_millis = MagicMock(return_value=30000)

    response = handler(event, context)

    # Should redirect to add trailing slash
    assert response["statusCode"] == 307
    assert response["headers"]["location"] == "/Prod/"
