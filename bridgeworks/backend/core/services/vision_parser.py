"""
vision_parser.py — Gemini Vision AI integration for Rate Card parsing
=====================================================================
Processes uploaded rate card images/PDFs and uses Gemini's multimodal
capabilities to extract pricing slabs and surcharges into structured JSON.
"""

import os
import json
import logging
from PIL import Image

logger = logging.getLogger(__name__)

STRUCTURE_PROMPT = """
You are an expert logistics data extractor. Analyze this courier rate card image/document.
Extract the pricing and surcharge mechanisms.
Map the zones using this strict relation to our normalized 7 zones:
- 'Local', 'Same City' -> 'Local'
- 'Intra City', 'Intra-City' -> 'Intra-City'
- 'Intra Region', 'Within State' -> 'Within State'
- 'Regional', 'State Zones', 'Rest of State' -> 'Regional'
- 'Metro-Metro', 'Metro' -> 'Metro'
- 'Rest of India', 'National', 'ROI' -> 'National'
- 'NE & JK', 'Special', 'Remote' -> 'Special'

Return exactly a JSON object (without markdown wrappers, just raw JSON string) with the following structure:
{
    "flat_surcharges": {
        "fuel_surcharge_percent": float (e.g. 10.0),
        "rto_charge_multiplier": float (e.g. 1.0 for same as forward, 1.5 for 1.5x),
        "cod_charge_flat": float (e.g. 30),
        "cod_charge_percent": float (e.g. 1.5),
        "ndr_reattempt_charge": float (e.g. 0),
        "reverse_pickup_charge": float (e.g. 70.0 for reverse RVP fee per AWB)
    },
    "pricing_mode": "SLAB" or "BASE_PLUS",
    "slabs": [
        {
            "zone": str (must be exactly one of the 7 mapped normalized zones),
            "weight_from_kg": float (e.g. 0.0),
            "weight_to_kg": float (e.g. 0.5),
            "rate": float (e.g. 20.0),
            "increment_kg": float (e.g. 0.5, if BASE_PLUS mode)
        }
    ]
}

Very Important instructions for slabs:
1. If the card says "First 500g = 20" and "Additional 500g = 20", set `pricing_mode` to "BASE_PLUS". Then create exactly ONE slab for each zone where: `weight_from_kg` = 0.0, `weight_to_kg` = 0.5, `rate` = 20.0, `increment_kg` = 0.5. (For the additional weight rate, we assume it matches the increment. If the additional rate is different, we can't map it properly to BASE_PLUS, so output multiple SLABs up to 5kg).
2. If the card shows "Intra city: First 500g=20, Addl 500g=20", map it to "Intra-City" zone.
3. For Fuel Surcharge, if it says "Mechanism minus 30%", just extract "0" as we can't calculate mechanisms automatically. If it lists a pure percentage like "15%", extract 15.0.
4. For COD, if it says "Min Rs 30 or 1.5%", extract `cod_charge_flat` = 30 and `cod_charge_percent` = 1.5.

Output ONLY valid JSON.
"""

def parse_rate_card_image(image_file):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set. Please add it to your .env or settings.")
    
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    
    try:
        img = Image.open(image_file)
    except Exception as e:
        logger.error(f"Error opening image: {e}")
        raise ValueError("Invalid image file provided. Please upload a valid JPG/PNG/WEBP.")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[STRUCTURE_PROMPT, img],
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
            ),
        )
        text = response.text.strip()
        data = json.loads(text)
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from AI. Raw response: {response.text}")
        raise ValueError("AI failed to return valid data. Try manually entering.")
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        raise ValueError(f"Error processing image with AI: {str(e)}")
