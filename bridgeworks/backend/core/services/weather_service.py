"""
weather_service.py — Gemini AI Weather Intelligence Service
============================================================
Fetches live regional weather warnings (cyclones, monsoons, storms, floods)
across India using Gemini 2.5 and Google Search Grounding.
Updates the local WeatherAlert database table.
"""
import json
import logging
from django.conf import settings
from django.utils import timezone
from pydantic import BaseModel, Field
from typing import List

from core.models.delivery import WeatherAlert

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. PYDANTIC SCHEMAS FOR SYSTEM STRUCTURE
# ==============================================================================

class StateWeatherAlert(BaseModel):
    """Represents an active weather alert in a specific Indian state."""
    state_name: str = Field(
        description="Name of the Indian state or union territory in lowercase (e.g. 'kerala', 'assam', 'rajasthan', 'maharashtra')"
    )
    is_active: bool = Field(
        description="True if there is currently an active major weather warning (e.g. heavy rainfall, floods, cyclones, storms) disrupting transport or logistics in this state, False otherwise"
    )
    alert_type: str = Field(
        default="None",
        description="Brief category of alert (e.g. 'Heavy Rain', 'Flood Alert', 'Cyclone Alert', 'High Winds', or 'None')"
    )


class IndiaWeatherAlerts(BaseModel):
    """Full mapping of all active weather alerts across India."""
    alerts: List[StateWeatherAlert] = Field(
        description="List of active weather alerts for Indian states and regions."
    )


# ==============================================================================
# 2. GEMINI PROMPT DEFINITION
# ==============================================================================

WEATHER_SYSTEM_PROMPT = """You are a real-time logistics weather intelligence agent.
Your task is to search Google Search for active weather warnings, alerts, cyclones, heavy rains, or severe floods currently occurring in India today.
Focus specifically on weather events that cause transport disruptions, logistics delays, or highway blockages.

Evaluate all major states and union territories in India, including but not limited to:
maharashtra, delhi, karnataka, tamil nadu, west bengal, rajasthan, haryana, gujarat, uttar pradesh, telangana, madhya pradesh, punjab, andhra pradesh, bihar, kerala, odisha, assam, chhattisgarh, jharkhand, uttarakhand, himachal pradesh, jammu & kashmir, goa.

For each state, if there is a severe warning issued by the IMD (India Meteorological Department) or general reports of severe rainfall/flooding today, set is_active to True and list the alert_type. Otherwise, set is_active to False and alert_type to 'None'."""


# ==============================================================================
# 3. WEATHER SYNC LOGIC
# ==============================================================================

def sync_weather_alerts_via_gemini() -> dict:
    """
    Query Gemini with Google Search Grounding to extract active weather alerts in India.
    Saves or updates state warning flags in the WeatherAlert table.
    
    Returns:
        dict: Summary of the sync execution
    """
    try:
        from google import genai
        from google.genai import types

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logger.error("[WEATHER-SYNC] GEMINI_API_KEY is not set. Skipping sync.")
            return {'error': 'GEMINI_API_KEY is not set'}

        logger.info("[WEATHER-SYNC] Querying Gemini with Search Grounding for live Indian weather alerts...")
        client = genai.Client(api_key=api_key)

        # Append schema requirements to the prompt since JSON output formats cannot be combined with tools (Search Grounding) in the Gemini API.
        prompt = (
            WEATHER_SYSTEM_PROMPT
            + "\n\nYou must return a valid JSON object matching the following structure. Do NOT include any introductory or concluding text. Just return the JSON object, optionally enclosed in a markdown ```json ... ``` block.\n"
            + "Structure:\n"
            + '{\n  "alerts": [\n    {"state_name": "state in lowercase", "is_active": true/false, "alert_type": "None or category"}\n  ]\n}'
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
            ),
        )

        if not response.text:
            logger.error("[WEATHER-SYNC] Empty response received from Gemini.")
            return {'error': 'Empty response from Gemini'}

        # Parse JSON output (defensively handling code block wrapping)
        text = response.text.strip()
        if text.startswith("```"):
            if text.startswith("```json"):
                text = text[7:]
            else:
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        parsed_data = json.loads(text)
        alert_list = parsed_data.get('alerts', [])
        
        active_count = 0
        inactive_count = 0

        # Update database in atomic bulk transaction
        for alert in alert_list:
            state_cleaned = alert.get('state_name', '').strip().lower()
            if not state_cleaned:
                continue

            is_active = alert.get('is_active', False)
            alert_type = alert.get('alert_type', 'None')

            # Normalize to avoid "none" strings
            if not is_active or alert_type.lower() == 'none':
                is_active = False
                alert_type = 'None'

            # Truncate strings to prevent DB CharField(max_length=100) truncation crash
            state_cleaned = state_cleaned[:100]
            alert_type = alert_type[:100]

            # Get or create record
            WeatherAlert.objects.update_or_create(
                state_name=state_cleaned,
                defaults={
                    'is_active': is_active,
                    'alert_type': alert_type,
                    'last_updated': timezone.now()
                }
            )

            if is_active:
                active_count += 1
            else:
                inactive_count += 1

        logger.info(f"[WEATHER-SYNC] Successfully synced {len(alert_list)} states. Active: {active_count}, Inactive: {inactive_count}")
        return {
            'status': 'success',
            'total_states': len(alert_list),
            'active_warnings': active_count,
            'inactive': inactive_count
        }

    except Exception as e:
        logger.exception(f"[WEATHER-SYNC] Sync failed: {e}")
        return {'error': str(e)}
