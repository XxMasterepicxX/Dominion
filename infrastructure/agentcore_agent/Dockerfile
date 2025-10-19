# Dockerfile for Dominion Multi-Agent System
# Supervisor + 4 Specialist Agents with AgentCore Runtime

# Use AWS Lambda Python base image for ARM64
FROM public.ecr.aws/lambda/python:3.12-arm64

# Copy requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy multi-agent system to Lambda task root
COPY dominion_multiagent.py ${LAMBDA_TASK_ROOT}/
COPY agents/ ${LAMBDA_TASK_ROOT}/agents/
COPY prompts/ ${LAMBDA_TASK_ROOT}/prompts/

# Set Lambda handler - BedrockAgentCoreApp provides Lambda handler
CMD ["dominion_multiagent.lambda_handler"]
