#!/usr/bin/env python3
"""
Marketing Lead Agent — powered by Claude API (Anthropic Python SDK)

Uses Claude with an agentic loop to find and qualify business leads:
  - web_search (server-side tool) for discovering companies
  - extract_company_info (client-side tool) for structuring qualified leads

Usage:
    python marketing_agent.py [industry] [location] [company_size] [keywords]

Examples:
    python marketing_agent.py
    python marketing_agent.py "FinTech" "New York, NY" "50-200 employees" "payments,API,B2B"

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY="your-api-key"
"""

import json
import os
import sys
from typing import Any

import anthropic

# ── Configuration ────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"

# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    # Server-side web search (Anthropic executes this automatically)
    {
        "type": "web_search_20260209",
        "name": "web_search",
    },
    # Client-side lead capture tool
    {
        "name": "extract_company_info",
        "description": (
            "Capture and structure a discovered company as a qualified lead. "
            "Call this for every company that matches the search criteria after "
            "gathering enough information about it from web search results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Full legal or trade name of the company.",
                },
                "website": {
                    "type": "string",
                    "description": "Company website URL (if found).",
                },
                "industry": {
                    "type": "string",
                    "description": "Primary industry or sector.",
                },
                "location": {
                    "type": "string",
                    "description": "Headquarters city and country/state.",
                },
                "company_size": {
                    "type": "string",
                    "description": "Estimated headcount or revenue range (e.g. '100-500 employees').",
                },
                "contact_name": {
                    "type": "string",
                    "description": "Key decision-maker name, if publicly available.",
                },
                "contact_title": {
                    "type": "string",
                    "description": "Job title of the contact person.",
                },
                "contact_email": {
                    "type": "string",
                    "description": "Contact email address, if publicly available.",
                },
                "description": {
                    "type": "string",
                    "description": "One- or two-sentence summary of what the company does.",
                },
                "qualification_score": {
                    "type": "integer",
                    "description": (
                        "Lead quality score from 1 (poor fit) to 10 (excellent fit), "
                        "based on how closely the company matches the target criteria."
                    ),
                    "minimum": 1,
                    "maximum": 10,
                },
                "qualification_reason": {
                    "type": "string",
                    "description": "One sentence explaining the qualification score.",
                },
            },
            "required": [
                "company_name",
                "industry",
                "location",
                "description",
                "qualification_score",
                "qualification_reason",
            ],
        },
    },
]

# ── Tool execution ────────────────────────────────────────────────────────────


def execute_extract_company_info(tool_input: dict[str, Any]) -> tuple[dict, str]:
    """
    Validate and structure the lead captured by Claude.
    Returns (lead_dict, json_result_for_api).
    """
    lead = {
        "company_name": tool_input.get("company_name", "Unknown"),
        "website": tool_input.get("website", ""),
        "industry": tool_input.get("industry", ""),
        "location": tool_input.get("location", ""),
        "company_size": tool_input.get("company_size", "Unknown"),
        "contact": {
            "name": tool_input.get("contact_name", ""),
            "title": tool_input.get("contact_title", ""),
            "email": tool_input.get("contact_email", ""),
        },
        "description": tool_input.get("description", ""),
        "qualification_score": tool_input.get("qualification_score", 5),
        "qualification_reason": tool_input.get("qualification_reason", ""),
    }
    result = json.dumps({"status": "lead_captured", "company": lead["company_name"]})
    return lead, result


# ── Agentic loop ──────────────────────────────────────────────────────────────


def find_leads(
    industry: str,
    location: str,
    company_size: str,
    keywords: list[str],
    max_leads: int = 5,
) -> list[dict]:
    """
    Run the marketing agent and return a list of qualified lead dicts.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    keywords_str = ", ".join(keywords) if keywords else "any"

    system_prompt = f"""You are an expert B2B marketing lead researcher.

Your goal is to find exactly {max_leads} qualified business leads that match:
  • Industry:      {industry}
  • Location:      {location}
  • Company size:  {company_size}
  • Keywords:      {keywords_str}

How to work:
1. Use web_search to discover companies. Try varied queries
   (company directories, LinkedIn, Crunchbase, industry news, etc.).
2. After finding a promising company, use extract_company_info to record it.
3. Score each lead 1–10 based on fit. Prefer scores ≥ 7.
4. Keep searching until you have captured {max_leads} leads.
5. Do not capture duplicates.

Be thorough. Multiple search queries are encouraged."""

    user_message = (
        f"Find {max_leads} qualified B2B leads in the {industry} industry "
        f"located in {location}, company size {company_size}, "
        f"related to: {keywords_str}. "
        f"Use web search to discover real companies, then capture each one "
        f"with extract_company_info."
    )

    messages: list[dict] = [{"role": "user", "content": user_message}]
    captured_leads: list[dict] = []
    iteration = 0
    max_iterations = 20  # safety cap

    print(f"\n🔍 Starting lead search — targeting {max_leads} leads\n")

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,  # type: ignore[arg-type]
            messages=messages,
        )

        # Append the full assistant turn (preserves server_tool_use blocks)
        messages.append({"role": "assistant", "content": response.content})

        # Surface server-side web search calls for visibility
        for block in response.content:
            if getattr(block, "type", None) == "server_tool_use":
                if block.name == "web_search":
                    query = block.input.get("query", "")
                    print(f"  🌐 Searching: {query}")

        # ── Done ──────────────────────────────────────────────────────────────
        if response.stop_reason == "end_turn":
            break

        # ── Server-side loop hit iteration limit — resume ─────────────────────
        if response.stop_reason == "pause_turn":
            # Re-send user message + last assistant turn so server can continue
            messages = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response.content},
            ]
            continue

        # ── Client-side tool calls ────────────────────────────────────────────
        if response.stop_reason == "tool_use":
            tool_results: list[dict] = []

            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue

                if block.name == "extract_company_info":
                    lead, result_json = execute_extract_company_info(block.input)
                    captured_leads.append(lead)
                    score = lead["qualification_score"]
                    print(
                        f"  📋 Captured: {lead['company_name']} "
                        f"(score {score}/10)"
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_json,
                        }
                    )
                else:
                    # Unknown client-side tool — return an error
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "is_error": True,
                            "content": f"Unknown tool: {block.name}",
                        }
                    )

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Stop early if we have enough leads
            if len(captured_leads) >= max_leads:
                break
            continue

        # Unexpected stop reason — exit loop
        break

    print(f"\n✅ Search complete — {len(captured_leads)} lead(s) captured\n")
    return captured_leads


# ── Reporting ─────────────────────────────────────────────────────────────────


def print_leads_report(leads: list[dict], criteria: dict) -> None:
    """Print a formatted console report."""
    WIDTH = 72

    print("\n" + "=" * WIDTH)
    print("📊  MARKETING LEAD REPORT")
    print("=" * WIDTH)
    print(f"Industry : {criteria['industry']}")
    print(f"Location : {criteria['location']}")
    print(f"Size     : {criteria['company_size']}")
    print(f"Keywords : {', '.join(criteria['keywords'])}")
    print(f"Leads    : {len(leads)} found")
    print("=" * WIDTH)

    if not leads:
        print("\n❌  No leads found. Try broadening your criteria.\n")
        return

    sorted_leads = sorted(
        leads, key=lambda x: x.get("qualification_score", 0), reverse=True
    )

    for i, lead in enumerate(sorted_leads, 1):
        score = lead.get("qualification_score", 0)
        stars = "★" * score + "☆" * (10 - score)

        print(f"\n  Lead #{i}  {lead['company_name']}")
        print(f"  Score : {score}/10  {stars}")
        print(f"  {'─' * (WIDTH - 4)}")

        if lead.get("website"):
            print(f"  🌐  Website  : {lead['website']}")
        print(f"  🏭  Industry : {lead['industry']}")
        print(f"  📍  Location : {lead['location']}")
        if lead.get("company_size"):
            print(f"  👥  Size     : {lead['company_size']}")

        contact = lead.get("contact", {})
        if contact.get("name"):
            print(f"  👤  Contact  : {contact['name']}")
        if contact.get("title"):
            print(f"  💼  Title    : {contact['title']}")
        if contact.get("email"):
            print(f"  📧  Email    : {contact['email']}")

        print(f"\n  Description:")
        # Wrap at ~65 chars
        desc = lead.get("description", "")
        for chunk_start in range(0, len(desc), 65):
            print(f"    {desc[chunk_start:chunk_start + 65]}")

        print(f"\n  Qualification:")
        reason = lead.get("qualification_reason", "")
        for chunk_start in range(0, len(reason), 65):
            print(f"    {reason[chunk_start:chunk_start + 65]}")

    print(f"\n{'=' * WIDTH}")
    high = [l for l in leads if l.get("qualification_score", 0) >= 7]
    print(f"  ✨  High-quality leads (≥7/10): {len(high)} of {len(leads)}")
    print("=" * WIDTH + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("       export ANTHROPIC_API_KEY='your-api-key'")
        sys.exit(1)

    # Default criteria (override via CLI args)
    criteria: dict[str, Any] = {
        "industry": "SaaS / B2B Software",
        "location": "New York, NY",
        "company_size": "50-500 employees",
        "keywords": ["CRM", "enterprise software", "cloud platform"],
    }

    if len(sys.argv) > 1:
        criteria["industry"] = sys.argv[1]
    if len(sys.argv) > 2:
        criteria["location"] = sys.argv[2]
    if len(sys.argv) > 3:
        criteria["company_size"] = sys.argv[3]
    if len(sys.argv) > 4:
        criteria["keywords"] = [k.strip() for k in sys.argv[4].split(",")]

    print("🚀  Marketing Lead Agent")
    print(f"    Model    : {MODEL}")
    print(f"    Industry : {criteria['industry']}")
    print(f"    Location : {criteria['location']}")
    print(f"    Size     : {criteria['company_size']}")
    print(f"    Keywords : {', '.join(criteria['keywords'])}")

    leads = find_leads(
        industry=criteria["industry"],
        location=criteria["location"],
        company_size=criteria["company_size"],
        keywords=criteria["keywords"],
        max_leads=5,
    )

    print_leads_report(leads, criteria)

    # Persist results as JSON
    output_path = "leads_output.json"
    with open(output_path, "w") as fh:
        json.dump({"criteria": criteria, "total": len(leads), "leads": leads}, fh, indent=2)
    print(f"💾  Results saved to {output_path}\n")


if __name__ == "__main__":
    main()
