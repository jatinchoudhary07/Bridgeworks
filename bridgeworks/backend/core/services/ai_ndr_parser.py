"""
ai_ndr_parser.py
================
AI-powered parser for BlueDart's messy raw-text email replies.

Uses Gemini via the native Google GenAI SDK to parse unstructured text
into structured call result data for escalation processing.
"""

import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Order, NDREscalationBatch, TrackingInfo

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. PYDANTIC SCHEMA
# ==============================================================================

class BlueDartCallResult(BaseModel):
    """Structured representation of a single AWB's call result from BlueDart."""
    awb_number: str = Field(description="The AWB/tracking number (e.g., '77703542125')")
    total_calls: int = Field(default=0, description="Total number of call attempts made")
    otp_provided: bool = Field(
        default=False,
        description="True if customer provided OTP or confirmed delivery (indicated by 'Y'), False otherwise"
    )
    latest_call_status: str = Field(
        default="Unknown",
        description="Latest call outcome (e.g., 'Customer_no-answer', 'Staff_completed', 'Connected')"
    )


class BlueDartParseResponse(BaseModel):
    """Wrapper for the full parsed response."""
    results: List[BlueDartCallResult] = Field(
        default_factory=list,
        description="List of parsed call results, one per AWB"
    )


# ==============================================================================
# 2. AI PARSING SERVICE
# ==============================================================================

PARSER_SYSTEM_PROMPT = """You are a data extraction specialist. You will be given messy, unstructured raw text 
from BlueDart courier's NDR (Non-Delivery Report) email replies.

Your job is to extract structured call attempt data for each AWB number found in the text.

Rules:
1. Each AWB number is typically 11-14 digits (e.g., 77703542125).
2. A "Y" at the end of a line means the customer provided OTP/confirmed (otp_provided = True).
3. "N" or no indicator means OTP was NOT provided (otp_provided = False).
4. Count the number of call attempt entries for each AWB to determine total_calls.
5. Extract the latest call status text (e.g., "Customer_no-answer", "Staff_completed", "Connected", "Switched_off").
6. If the same AWB appears multiple times, merge the data into one result.
7. Pipe characters (|) typically separate different call attempts for the same AWB.

Example input:
"77703542125 | 02-MAR-26 0803 Y
77702140036 2 |1 01-mar-26 1840 Staff_completed Customer_no-answer (0 sec)| 01-MAR-26 1840 Y"

Expected output:
- AWB 77703542125: 1 call, otp_provided=True, status="Completed"
- AWB 77702140036: 2 calls, otp_provided=True, status="Customer_no-answer"

Be thorough — extract ALL AWBs from the text, even if formatting is inconsistent."""


def parse_bluedart_raw_reply(raw_text: str) -> List[BlueDartCallResult]:
    """
    Parse BlueDart's messy raw text reply using Gemini AI.

    Args:
        raw_text: The raw text from BlueDart's email reply

    Returns:
        List of BlueDartCallResult objects
    """
    try:
        from google import genai
        from google.genai import types

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logger.error("GEMINI_API_KEY not configured")
            return []

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{PARSER_SYSTEM_PROMPT}\n\n--- RAW TEXT TO PARSE ---\n{raw_text}",
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type='application/json',
                response_schema=BlueDartParseResponse,
            ),
        )

        import json
        data = json.loads(response.text)
        result = BlueDartParseResponse(**data)

        if result and result.results:
            logger.info(f"AI parsed {len(result.results)} AWBs from raw text")
            return result.results

        return []

    except Exception as e:
        logger.error(f"AI NDR parsing failed: {e}")

        # FALLBACK: Try basic regex extraction
        return _fallback_regex_parse(raw_text)


def _fallback_regex_parse(raw_text: str) -> List[BlueDartCallResult]:
    """Simple regex fallback if AI parsing fails."""
    import re

    results = []
    # Find all 11-14 digit numbers (likely AWBs)
    awb_pattern = re.compile(r'\b(\d{11,14})\b')
    lines = raw_text.strip().split('\n')

    for line in lines:
        match = awb_pattern.search(line)
        if match:
            awb = match.group(1)
            otp = line.strip().upper().endswith('Y')
            pipe_count = line.count('|')

            results.append(BlueDartCallResult(
                awb_number=awb,
                total_calls=max(1, pipe_count),
                otp_provided=otp,
                latest_call_status="Parsed via fallback"
            ))

    return results


# ==============================================================================
# 3. PROCESSOR — Takes parsed results and updates orders
# ==============================================================================

ESCALATION_TIERS = {
    0: 'ESCALATION_1',
    1: 'ESCALATION_2',
    2: 'ESCALATION_3',
    3: 'RTO_CONFIRMED',
}


def _find_order_by_awb(awb: str) -> Optional[Order]:
    """Find an Order by its AWB number via TrackingInfo."""
    ti = TrackingInfo.objects.filter(number=awb).select_related(
        'fulfillment__order'
    ).first()
    if ti:
        return ti.fulfillment.order
    return None


@transaction.atomic
def process_parsed_results(batch_id: int, parsed_results: List[BlueDartCallResult]) -> dict:
    """
    Process AI-parsed BlueDart call results and update order escalation statuses.

    Args:
        batch_id: ID of the NDREscalationBatch
        parsed_results: List of BlueDartCallResult from AI parser

    Returns:
        dict with processing summary
    """
    try:
        batch = NDREscalationBatch.objects.get(id=batch_id)
    except NDREscalationBatch.DoesNotExist:
        return {'error': f'Batch {batch_id} not found'}

    summary = {
        'total': len(parsed_results),
        'rto_confirmed': 0,
        're_escalated': 0,
        'not_found': 0,
        'details': [],
    }

    for result in parsed_results:
        order = _find_order_by_awb(result.awb_number)
        if not order:
            summary['not_found'] += 1
            summary['details'].append({
                'awb': result.awb_number,
                'action': 'NOT_FOUND',
            })
            continue

        if result.otp_provided:
            # Customer gave OTP = they confirmed cancellation = RTO
            order.ndr_escalation_status = 'RTO_CONFIRMED'
            order.save(update_fields=['ndr_escalation_status'])
            summary['rto_confirmed'] += 1
            summary['details'].append({
                'awb': result.awb_number,
                'order': order.order_number,
                'action': 'RTO_CONFIRMED',
                'call_status': result.latest_call_status,
            })
        else:
            # Customer didn't answer / didn't give OTP = re-escalate
            order.ndr_escalation_count += 1
            next_tier = ESCALATION_TIERS.get(order.ndr_escalation_count, 'RTO_CONFIRMED')
            order.ndr_escalation_status = next_tier
            order.save(update_fields=['ndr_escalation_status', 'ndr_escalation_count'])
            summary['re_escalated'] += 1
            summary['details'].append({
                'awb': result.awb_number,
                'order': order.order_number,
                'action': next_tier,
                'call_status': result.latest_call_status,
            })

    # Update batch
    batch.status = 'PROCESSED'
    batch.processed_at = timezone.now()
    batch.summary = summary
    batch.save()

    return summary
