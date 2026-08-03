"""
Gemini AI Agent Service
========================
Uses Google GenAI SDK (Gemini) to evaluate orders for fraud risk
and logistics efficiency using native Function Calling.

The system prompt is loaded dynamically from the AgentConfiguration model
so behavior can be changed from Django Admin without code deploys.
"""
import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from django.conf import settings

from core.agent_tools import get_customer_history, get_pincode_health, put_order_on_hold

logger = logging.getLogger(__name__)


# =============================================================================
# 1. Pydantic Output Schema
# =============================================================================

class OrderVerdict(BaseModel):
    """Structured output the AI agent must return for every order evaluation."""
    risk_score: int = Field(
        description="Trust score from 0 to 100. 0 = highest risk, 100 = most trustworthy."
    )
    intelligence_flag: str = Field(
        description="Color-coded risk flag. Must be exactly one of: GREEN, YELLOW, RED."
    )
    recommended_courier: str = Field(
        description="The best courier to use for this order based on region data, or 'Standard' if no data."
    )
    agent_reasoning: str = Field(
        description="A detailed explanation of why this verdict was reached."
    )
    is_confirmed: bool = Field(
        description="True if the order is safe and should be auto-confirmed, False if it should be put on hold."
    )
    confirmation_reason: Optional[str] = Field(
        default=None,
        description="Reason for auto-confirmation, if any. Set only if is_confirmed is True."
    )
    hold_reason: Optional[str] = Field(
        default=None,
        description="Reason for putting the order on hold, if any. Set only if is_confirmed is False."
    )
    is_international: bool = Field(
        description="True if the shipping address country is other than India, False otherwise."
    )


# =============================================================================
# 2. Default Fallback Response
# =============================================================================

DEFAULT_VERDICT = OrderVerdict(
    risk_score=50,
    intelligence_flag="YELLOW",
    recommended_courier="Standard",
    agent_reasoning="AI API Timeout - Requires Manual Review",
    is_confirmed=False,
    confirmation_reason=None,
    hold_reason="AI API Timeout",
    is_international=False
)

DEFAULT_SYSTEM_PROMPT = """You are an Order Intelligence Agent for an Indian e-commerce company based in Jaipur, India. Your job is to evaluate new orders for fraud/RTO risk and recommend the best logistics courier.

TOOLS — you MUST use these before forming a verdict, never guess:
1. get_customer_history — pulls the customer's past order behavior.
2. get_pincode_health — pulls the delivery region's reliability and courier performance data.
3. Determine if the order is international by checking the shipping address fields (country, pincode/postal code format, phone country code). We operate from Jaipur, India and do not currently have country-specific international shipping rules.

FRAUD RISK EVALUATION
Start every order at a baseline of 85 (clean slate). Apply ONLY the deductions below that actually apply to this specific order. A clean/neutral factor contributes ZERO — never apply a hidden or implied penalty for a factor that has no red flag. The final risk_score must mathematically trace back to baseline minus the deductions you list; do not adjust the number afterward based on a general "feeling" about the order.

DEDUCTIONS (apply only what is present; do not double-count the same red flag under two categories):
- RTO history: 0 past RTOs/refusals = -0. 1-2 past RTOs = -15 to -25. 3+ past RTOs = -40 to -60 (this overrides and dominates other factors when present).
- Account/order history: New customer (0 past orders) with no other red flag present = -0. Never penalize newness alone, and never use an order-value threshold to flag a new customer. If a new customer's order ALSO has another red flag below (e.g. COD + high-RTO pincode, or address mismatch), apply only that other flag's deduction — do not add an extra penalty on top for "being new." Established customer (5+ clean orders, 0 RTOs) = +5 bonus (cap total at 100).
- Payment / COD: Prepaid = -0. COD with NO other red flag present (clean pincode, matching address, no COD refusal history) = -10 to -15 ONLY — this is a mild baseline deduction for general COD risk and must never by itself push a clean order below 65. COD WITH a pairing red flag (past COD refusal, OR billing/shipping address mismatch) = -25 to -35 total for the combination (this replaces, not stacks with, the bare-COD deduction).
- Pincode/region (get_pincode_health): RTO rate 0-5% = -0. RTO rate 6-15% = -10 to -15. RTO rate 16%+ or courier reports poor serviceability = -25 to -35.
- Order Tags: Weigh any tags attached to the order. Consider them for additional context (e.g. VIP status, test tags, custom fraud warnings).

WORKED EXAMPLE — get this exact pattern right every time: new customer (0 past orders), COD, pincode RTO rate 0%, no address mismatch, no COD refusal history. Deductions: RTO history -0 (clean), account history -0 (new but nothing else flagged), pincode -0 (0% RTO is clean), COD -10 to -15 (bare COD only). Final score = 85 minus ~12 = roughly 70-75, landing GREEN/YELLOW boundary. A score below 50 for this exact pattern is WRONG — if your calculation lands there, re-check your deductions before finalizing.

In agent_reasoning, write out the deduction math like a receipt, e.g. "Baseline 85. RTO history: 0 past RTOs, -0. Account history: new customer, no other flag, -0. Pincode: 0% RTO, -0. Payment: bare COD, -12. Final: 73." This makes the score auditable against your own stated reasoning. If the customer is new, explicitly state that "new customer" alone was not penalized, and name the actual factor(s), if any, that lowered the score from baseline.

INTERNATIONAL ORDER HANDLING
- If the shipping address resolves to a country other than India, set is_international: true and ALWAYS recommend manual review for this order, regardless of how clean the customer's history looks.
- This is a separate signal from fraud risk. International status does NOT add to or subtract from the risk_score — keep risk_score based purely on the fraud factors above.
- In agent_reasoning, clearly state that the order is international, that we don't have a fixed list of approved countries yet, and that it requires manual review for shipping feasibility before fulfillment.
- If the order is domestic (India), set is_international: false and proceed with normal courier recommendation logic.

COURIER RECOMMENDATION
- Recommend the courier with the best historical performance for that specific pincode, based on get_pincode_health data (lowest RTO rate, best delivery success rate).
- If no pincode-specific courier data exists, recommend 'Standard' and say so explicitly rather than guessing a courier name.
- For international orders, recommended_courier should be 'Pending Manual Review' since courier selection depends on which courier services that country.

ORDER STATUS LOGIC
- is_confirmed: True if the order is domestic AND risk_score is 30 or higher (i.e. intelligence_flag is GREEN or YELLOW). False if risk_score is below 30 (RED) OR the order is international (international orders always hold for manual review regardless of score).
- confirmation_reason: Required (non-null) only when is_confirmed is True. State briefly why the order was safe to auto-confirm, referencing the actual deduction drivers (e.g. "Clean RTO history, low-risk pincode, no compounding red flags with COD").
- hold_reason: Required (non-null) only when is_confirmed is False. State briefly why it's held — either "risk_score below 30 due to [actual driver]" or "international order pending manual feasibility review." Set to null whenever is_confirmed is True.

OUTPUT FORMAT
Always respond in this exact structure, in this order, with these exact labels:

risk_score: [0-100 integer]
intelligence_flag: [GREEN if score > 75, YELLOW if 30-75, RED if < 30]
is_international: [true/false]
recommended_courier: [courier name, 'Standard', or 'Pending Manual Review']
is_confirmed: [true/false]
confirmation_reason: [brief reason if is_confirmed is true, else null]
hold_reason: [brief reason if is_confirmed is false, else null]
agent_reasoning: [5-6 sentences. Cover: (1) what the customer history showed, (2) what the pincode health data showed, (3) the deduction math from baseline 85 to final score, (4) the international status and any manual review need, (5) why this courier was recommended, (6) confirm whether the order was auto-confirmed or held and why.]

Do not add extra commentary, headers, or sections beyond these fields. Do not omit a field even if data is missing — state "no data available" explicitly within the relevant field instead of skipping it.
"""


# =============================================================================
# 3. The Agent Service
# =============================================================================

def _get_system_prompt() -> str:
    """Fetch the active system prompt from the database, or use the default."""
    try:
        from core.models import AgentConfiguration
        config = AgentConfiguration.objects.filter(is_active=True).order_by('-updated_at').first()
        if config and config.system_prompt.strip():
            return config.system_prompt
    except Exception as e:
        logger.warning(f"Could not load AgentConfiguration: {e}")
    return DEFAULT_SYSTEM_PROMPT


def _get_model_name() -> str:
    """Fetch the model name from AgentConfiguration, or use the default."""
    try:
        from core.models import AgentConfiguration
        config = AgentConfiguration.objects.filter(is_active=True).order_by('-updated_at').first()
        if config and hasattr(config, 'model_name') and config.model_name:
            return config.model_name
    except Exception:
        pass
    return 'gemini-2.5-flash-lite'


def run_gemini_agent(order) -> OrderVerdict:
    """
    Main entry point. Runs the Gemini agent with native function calling
    to evaluate an order. Falls back sequentially to alternative models if the primary model fails.

    Args:
        order: An Order model instance.

    Returns:
        OrderVerdict: Structured verdict with risk_score, flag, courier, reasoning, confirmation_reason, hold_reason.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.error("GEMINI_API_KEY is not set. Returning default verdict.")
        return DEFAULT_VERDICT

    model_name = _get_model_name()
    system_prompt = _get_system_prompt()

    # Fallback model sequence configuration
    from core.utils.gemini_fallback import DEFAULT_FALLBACK_SEQUENCE
    candidates = [model_name]
    for fallback in DEFAULT_FALLBACK_SEQUENCE:
        if fallback not in candidates:
            candidates.append(fallback)

    last_error = None
    for idx, current_model in enumerate(candidates):
        try:
            logger.info(f"Attempting order evaluation with model: {current_model} (Attempt {idx+1}/{len(candidates)})")
            
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            order_context = (
                f"Evaluate this new order:\n"
                f"- Order ID: {order.id}\n"
                f"- Order Number: {order.order_number}\n"
                f"- Customer Name: {order.customer_first_name} {order.customer_last_name}\n"
                f"- Phone: {order.contact_phone or 'N/A'}\n"
                f"- Email: {order.contact_email or 'N/A'}\n"
                f"- Shipping Pincode: {order.shipping_pincode or 'N/A'}\n"
                f"- Shipping State: {order.shipping_state or 'N/A'}\n"
                f"- Shipping Address: {order.shipping_address or 'N/A'}\n"
                f"- Total Price: ₹{order.total_price or 0}\n"
                f"- Payment Method: {', '.join(order.payment_gateway_names) if order.payment_gateway_names else 'N/A'}\n"
                f"- Previous Order Count (Shopify): {order.previous_order_count}\n"
                f"- Order Tags: {order.tags or 'None'}\n"
                f"\nAfter gathering data with tools, provide your final verdict. If the order is risky, call put_order_on_hold first."
            )

            # ── PHASE 1: Tool Calling ──────────────────────────────────────
            # Gather data via automatic function calling (tools + response_schema
            # can't be combined in one call, so we split into two phases).
            response = client.models.generate_content(
                model=current_model,
                contents=order_context,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.1,
                    tools=[get_customer_history, get_pincode_health, put_order_on_hold],
                ),
            )

            # The model's text response after tool calls contains its reasoning
            tool_reasoning = response.text or ""

            # ── PHASE 2: Structured Verdict ───────────────────────────────
            # Now ask for the final verdict as structured JSON using the
            # reasoning from Phase 1 (which includes tool call results).
            verdict_response = client.models.generate_content(
                model=current_model,
                contents=(
                    f"Based on this analysis, provide your final verdict:\n\n"
                    f"{tool_reasoning}\n\n"
                    f"Output ONLY valid JSON matching the schema of OrderVerdict: risk_score (int 0-100), "
                    f"intelligence_flag (GREEN/YELLOW/RED), recommended_courier (str), "
                    f"agent_reasoning (str), is_confirmed (bool), confirmation_reason (str or null), hold_reason (str or null), "
                    f"is_international (bool)."
                ),
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type='application/json',
                    response_schema=OrderVerdict,
                ),
            )

            text = verdict_response.text.strip()

            try:
                data = json.loads(text)
                verdict = OrderVerdict(**data)
            except Exception as pe:
                logger.warning(f"Failed to parse verdict JSON for Order #{order.order_number} using model {current_model}: {pe}. Raw: {text}")
                # Raise exception to trigger fallback model
                raise pe

            # Validate the flag value
            if verdict.intelligence_flag not in ('GREEN', 'YELLOW', 'RED'):
                verdict.intelligence_flag = 'YELLOW'
            
            # Clamp risk score
            verdict.risk_score = max(0, min(100, verdict.risk_score))

            logger.info(
                f"Order #{order.order_number} verdict SUCCESS using model {current_model}: "
                f"Score={verdict.risk_score}, Flag={verdict.intelligence_flag}, "
                f"Courier={verdict.recommended_courier}"
            )
            return verdict

        except Exception as e:
            logger.warning(f"Gemini evaluation failed for Order #{order.order_number} with model {current_model}: {e}")
            last_error = e

    logger.error(f"All models failed for Order #{order.order_number} in evaluate task. Last error: {last_error}", exc_info=True)
    return DEFAULT_VERDICT
