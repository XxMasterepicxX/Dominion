#!/usr/bin/env python3
"""
Dominion Real Estate Intelligence - AWS CDK App
AWS AI Agent Global Hackathon - October 2025

Deployment architecture:
- Aurora Serverless v2 with scale-to-zero (experimental)
- 3 Lambda functions (Intelligence, RAG, Enrichment)
- Bedrock Knowledge Base with Quick Create
- AgentCore Runtime for agent execution
"""

import os
from aws_cdk import App, Environment, Tags

from lib.dominion_aurora_stack import DominionAuroraStack
from lib.dominion_lambda_stack import DominionLambdaStack
from lib.dominion_kb_stack import DominionKnowledgeBaseStack
# from lib.dominion_scraper_stack import DominionScraperStack  # TODO: Add after fixing Patchright/Crawl4AI

# Get AWS account and region from environment or use defaults
account = os.environ.get("CDK_DEFAULT_ACCOUNT", "872041712923")
region = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")

env = Environment(account=account, region=region)

app = App()

# Stack 1: Aurora Serverless v2 Database with scale-to-zero
# Stores: 108,380 properties, 89,189 entities, 2,588 ordinance chunks
aurora_stack = DominionAuroraStack(
    app,
    "Dominion-Database",
    env=env,
    description="Aurora Serverless v2 PostgreSQL with pgvector and scale-to-zero for Dominion",
)

# Stack 2: Lambda Functions (Intelligence Tools)
# 3 consolidated functions instead of 10 separate ones
lambda_stack = DominionLambdaStack(
    app,
    "Dominion-Tools",
    aurora_stack=aurora_stack,  # Pass Aurora stack for DB access
    env=env,
    description="Lambda functions for Dominion intelligence tools (3 consolidated functions)",
)

# Stack 3: Bedrock Knowledge Base (RAG for ordinances)
# Uses Aurora pgvector (cost optimization: saves $200/month vs OpenSearch)
kb_stack = DominionKnowledgeBaseStack(
    app,
    "Dominion-Knowledge",
    aurora_stack=aurora_stack,  # Pass Aurora for pgvector storage
    env=env,
    description="Bedrock Knowledge Base with Aurora pgvector for ordinance RAG",
)

# Add common tags for hackathon tracking and AWS Application grouping
for stack in [aurora_stack, lambda_stack, kb_stack]:
    # AWS Application tag (groups resources in AWS Console)
    Tags.of(stack).add("awsApplication", "arn:aws:resource-groups:us-east-1:872041712923:group/Dominion/04ipu3hc6wg3jebw9lzqs2qrf1")
    # Project tags
    Tags.of(stack).add("Project", "Dominion")
    Tags.of(stack).add("Hackathon", "AWS-AI-Agent-Global-2025")
    Tags.of(stack).add("Category", "Best-AgentCore-Implementation")
    Tags.of(stack).add("Environment", "Hackathon")
    Tags.of(stack).add("ManagedBy", "CDK")

app.synth()
