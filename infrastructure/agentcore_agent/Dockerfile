# Dockerfile for Dominion Multi-Agent System
# Supervisor + 4 Specialist Agents with AgentCore Runtime

# Use Python slim base image (NOT Lambda base)
# Platform specified in .bedrock_agentcore.yaml (linux/arm64)
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy multi-agent system
COPY dominion_multiagent.py .
COPY agents/ ./agents/
COPY prompts/ ./prompts/

# Set environment variables (will be overridden by AgentCore)
ENV PYTHONUNBUFFERED=1

# Expose port 8080 for AgentCore HTTP server
EXPOSE 8080

# Run multi-agent entry point - BedrockAgentCoreApp starts HTTP server automatically
CMD ["python", "dominion_multiagent.py"]
