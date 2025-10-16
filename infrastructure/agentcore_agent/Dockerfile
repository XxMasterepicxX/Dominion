# Dockerfile for Dominion AgentCore Agent
# Python 3.12 with Strands framework and BedrockAgentCoreApp

# Use Python slim base image (NOT Lambda base)
# Platform specified in .bedrock_agentcore.yaml (linux/amd64)
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY dominion_agent.py .

# Set environment variables (will be overridden by AgentCore)
ENV PYTHONUNBUFFERED=1

# Expose port 8080 for AgentCore HTTP server
EXPOSE 8080

# Run Python directly - BedrockAgentCoreApp starts HTTP server automatically
CMD ["python", "dominion_agent.py"]
