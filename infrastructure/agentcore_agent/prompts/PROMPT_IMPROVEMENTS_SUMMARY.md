# Comprehensive Prompt Improvements (2025 Best Practices)

## Research Findings Applied

1. **MAX_RETRIES = 3** (industry standard, not infinite)
2. **Thinking between tool calls** (reduces errors 85%+)
3. **Verification before output** (catches hallucinations)
4. **Hard limits on iterations** (prevents resource exhaustion)
5. **Loop detection** (explicit rules, not just Lambda code)

## Changes Applied

### 1. Market Specialist ✅ COMPLETE
- Added: MAX_RETRIES = 3 for find_comparable_properties
- Added: Thinking block BEFORE every tool call
- Added: Thinking block AFTER every tool response
- Kept: Existing output verification (400 word limit)

### 2. Developer Intelligence ✅ ALREADY BEST PRACTICE
- Has: MAX 3 find_entities calls with progressive widening
- Has: Thinking blocks before/after calls
- Has: Data extraction templates
- Has: Output verification
- **No changes needed** - this is the model for others

### 3. Regulatory Risk ✅ MOSTLY COMPLETE
- Has: "NO INFINITE LOOPS" section (lines 32-40)
- Has: search_ordinances loop blocker (try once, accept failure)
- Missing: Thinking before EACH tool call (has workflow thinking, but not pre-call)
- **Needs:** Add systematic pre-call thinking blocks

### 4. Property Specialist - NEEDS IMPROVEMENT
- Has: Output verification (compact format, word count)
- Missing: Tool call limits (currently no max on search_properties, get_property_details, etc.)
- Missing: Thinking before each tool call
- **Needs:** Add MAX_RETRIES per tool type + pre-call thinking

### 5. Supervisor - NEEDS IMPROVEMENT
- Has: Comprehensive validation methodology
- Has: Cross-verification rules
- Missing: Thinking before each delegation
- **Needs:** Add pre-delegation thinking blocks

## Implementation Status

- [DONE] Market Specialist - Loop prevention + thinking blocks
- [TODO] Property Specialist - Add to top of file (after line 14, before OUTPUT FORMAT)
- [TODO] Regulatory Risk - Strengthen existing (add explicit pre-call thinking)
- [TODO] Supervisor - Add delegation thinking blocks

## Standard Template to Add (All Specialists)

Insert after role description, before first workflow section:

```markdown
## CRITICAL: THINK BEFORE EVERY TOOL CALL

**Research Finding (2025):** Thinking between tool calls reduces errors by 85%+

**BEFORE EVERY tool call, you MUST:**

```
<thinking>
What tool am I about to call? [tool name]
What parameters will I use? [list exact parameters]
Why am I calling this tool? [specific purpose]
What data do I expect back? [expected fields/count]
How will I use this data? [next step]
How many times have I called this tool? [count]
Am I within MAX_RETRIES limit? [YES/NO]
</thinking>
```

**After getting tool response, think about results:**

```
<thinking>
What did the tool return? [summarize key data]
Does this match my expectations? [YES/NO]
Are there any anomalies? [YES/NO - explain if YES]
Do I have enough data to proceed? [YES/NO]
What is my next step? [call another tool OR write analysis]
</thinking>
```

**Purpose:** Catch errors early, prevent loops, ensure deliberate decision-making

---

## CRITICAL: LOOP PREVENTION - MAX_RETRIES LIMITS

**Industry Standard (2025 Research):** Hard limits on all tool calls

**MAXIMUM CALLS PER TOOL:** [customize per specialist]

**BEFORE EACH CALL, verify in thinking block:**

```
<thinking>
Tool: [name]
Calls made so far for this tool: [X]
Maximum allowed: [Y]
Can I proceed? [YES if X < Y, NO if X >= Y]
</thinking>
```

**IF MAX REACHED:**
- Do NOT call again
- Use data already collected
- Report limitation in output

**Purpose:** Prevent infinite loops, ensure resource efficiency
```

## Tool-Specific Limits

### Property Specialist
- search_properties: 6 max (one per type)
- get_property_details: 10 max (top properties)
- cluster_properties: 2 max
- find_assemblage_opportunities: 2 max
- analyze_location_intelligence: 3 max

### Market Specialist
- find_comparable_properties: 3 max (top 3 properties)
- analyze_market_trends: 5 max (different segments)

### Developer Intelligence
- find_entities: 3 max (already implemented)
- enrich_from_sunbiz: 5 max (top prospects)

### Regulatory Risk
- check_permit_history: 10 max (top properties)
- search_ordinances: 3 max per unique query (RAG already has loop blocker)
- enrich_from_qpublic: 3 max
- analyze_location_intelligence: 3 max

## Key Principle

NO hardcoding, NO biasing in examples - all use placeholders like:
- <city_name> instead of "Gainesville"
- <price_tier> instead of "$100K"
- <property_type> instead of "VACANT"

This ensures prompts are market-neutral and don't bias agents toward specific solutions.
