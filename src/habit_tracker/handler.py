"""AWS Lambda handler using Mangum."""

# v0.1.0
from mangum import Mangum

from habit_tracker.main import app

handler = Mangum(app, lifespan="off")
