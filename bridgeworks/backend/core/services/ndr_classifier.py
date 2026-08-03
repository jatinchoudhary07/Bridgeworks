"""
ndr_classifier.py
=================
AI-driven classifier for raw courier NDR (Non-Delivery Report) remarks.
Uses Gemini via the native Google GenAI SDK to map unstructured text
into one of 6 clean reason categories.
"""

import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. PYDANTIC RESPONSE SCHEMA
# ==============================================================================
class NDRClassificationResult(BaseModel):
    """Structured classification result for NDR remarks."""
    category: str = Field(
        description="The classified NDR reason category. Must be exactly one of: "
                    "'CUSTOMER_UNAVAILABLE', 'ADDRESS_ISSUE', 'REFUSED_DELIVERY', "
                    "'PREMISES_CLOSED', 'COD_NOT_READY', or 'OTHERS'."
    )
    confidence: int = Field(
        description="Confidence score of the classification from 0 to 100."
    )
    explanation: str = Field(
        description="A short 1-sentence explanation of why this category was chosen."
    )


# ==============================================================================
# 2. SYSTEM PROMPT
# ==============================================================================
CLASSIFIER_SYSTEM_PROMPT = """You are an expert logistics intelligence analyzer. You will be given raw courier tracking status scan remarks and details from an NDR (Non-Delivery Report).

Your job is to classify the raw text into exactly one of the following categories:
1. 'CUSTOMER_UNAVAILABLE': Customer not contactable, phone switched off, customer out of station, customer did not answer call, consignee unavailable.
2. 'ADDRESS_ISSUE': Address incorrect, incomplete address, address not found, wrong pincode, non-serviceable location.
3. 'REFUSED_DELIVERY': Consignee refused to accept, customer cancelled order, customer refused to pay, open delivery requested and refused.
4. 'PREMISES_CLOSED': Office/residence closed, premises closed, entry restricted area, local holiday, Sunday/closed.
5. 'COD_NOT_READY': COD payment not ready, customer asked for future delivery due to cash issue, customer did not have change.
6. 'OTHERS': Future delivery requested (generic), delivery delayed, pickup exception, natural calamity, or any other unspecified reasons.

Evaluate the raw text carefully, map it to the closest category, and return the category name along with your confidence score (0-100) and a brief 1-sentence explanation."""


# ==============================================================================
# 3. CLASSIFICATION SERVICE
# ==============================================================================
def classify_ndr_remark(remark_text: str) -> dict:
    """
    Classify a raw NDR remark using Gemini AI.
    Returns a dict with 'category', 'confidence', and 'explanation'.
    Falls back to a default rule-based classification if Gemini fails.
    """
    if not remark_text or not remark_text.strip():
        return {
            'category': 'OTHERS',
            'confidence': 100,
            'explanation': 'Empty remark text provided.'
        }

    try:
        from google import genai
        from google.genai import types
        from django.conf import settings

        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key:
            return _rule_based_fallback(remark_text)

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=15_000)
        )

        import time
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"{CLASSIFIER_SYSTEM_PROMPT}\n\n--- RAW TEXT TO CLASSIFY ---\n{remark_text}",
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type='application/json',
                        response_schema=NDRClassificationResult,
                    ),
                )
                
                import json
                data = json.loads(response.text)
                
                # Verify the returned category is one of the valid choices
                valid_categories = {'CUSTOMER_UNAVAILABLE', 'ADDRESS_ISSUE', 'REFUSED_DELIVERY', 'PREMISES_CLOSED', 'COD_NOT_READY', 'OTHERS'}
                category = data.get('category', 'OTHERS').upper().replace(' ', '_')
                if category not in valid_categories:
                    category = 'OTHERS'

                return {
                    'category': category,
                    'confidence': data.get('confidence', 50),
                    'explanation': data.get('explanation', '')
                }
            except Exception as e:
                attempt += 1
                err_str = str(e).upper()
                is_transient = any(x in err_str for x in ["503", "429", "UNAVAILABLE", "TIMEOUT", "RESOURCE_EXHAUSTED", "LIMIT"])
                if attempt < max_attempts and is_transient:
                    sleep_time = 2 ** attempt
                    logger.warning(f"Gemini NDR classification transient error on attempt {attempt}: {e}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    raise e

    except Exception as e:
        logger.error(f"Failed to classify NDR remark with Gemini: {e}")
        return _rule_based_fallback(remark_text)


def _rule_based_fallback(remark: str) -> dict:
    """Keyword-matching fallback if Gemini API is offline or unconfigured."""
    remark_lower = remark.lower()
    
    # Check Refused Delivery
    refused_keywords = ['refus', 'reject', 'cancel', 'no money', 'want open delivery']
    if any(kw in remark_lower for kw in refused_keywords):
        return {
            'category': 'REFUSED_DELIVERY',
            'confidence': 70,
            'explanation': 'Fallback: Matched refusal keywords.'
        }

    # Check COD Not Ready
    cod_keywords = ['cod not ready', 'payment not ready', 'cash not ready', 'change not available', 'money not ready', 'payment ready', 'no payment', 'cash ready', 'money ready']
    if any(kw in remark_lower for kw in cod_keywords):
        return {
            'category': 'COD_NOT_READY',
            'confidence': 75,
            'explanation': 'Fallback: Matched COD payment not ready keywords.'
        }

    # Check Address Issue
    address_keywords = ['address', 'pincode', 'location', 'non service', 'unservice', 'landmark', 'incomplete']
    if any(kw in remark_lower for kw in address_keywords):
        return {
            'category': 'ADDRESS_ISSUE',
            'confidence': 75,
            'explanation': 'Fallback: Matched address/pincode keywords.'
        }

    # Check Premises Closed
    closed_keywords = ['closed', 'premises', 'entry restrict', 'holiday', 'sunday']
    if any(kw in remark_lower for kw in closed_keywords):
        return {
            'category': 'PREMISES_CLOSED',
            'confidence': 75,
            'explanation': 'Fallback: Matched closed premises keywords.'
        }

    # Check Customer Unavailable
    unavailable_keywords = ['unavailable', 'unreachable', 'switched off', 'switch off', 'out of station', 'not answering', 'no answer', 'not pick', 'busy']
    if any(kw in remark_lower for kw in unavailable_keywords):
        return {
            'category': 'CUSTOMER_UNAVAILABLE',
            'confidence': 70,
            'explanation': 'Fallback: Matched customer unreachable keywords.'
        }

    return {
        'category': 'OTHERS',
        'confidence': 50,
        'explanation': 'Fallback: Default classification mapping.'
    }
