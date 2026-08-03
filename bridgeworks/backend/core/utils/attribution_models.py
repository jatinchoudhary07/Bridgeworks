from datetime import datetime
import dateutil.parser
from core.utils.url_parser import classify_channel

def parse_ts(ts_str):
    if not ts_str:
        return datetime.utcnow()
    try:
        return dateutil.parser.isoparse(ts_str)
    except Exception:
        try:
            return dateutil.parser.parse(ts_str)
        except Exception:
            return datetime.utcnow()

def get_touchpoint_channel(touchpoint):
    """
    Classify a touchpoint into a channel slug.
    """
    utm_data = {
        'utm_source': touchpoint.get('source', '') or touchpoint.get('utm_source', ''),
        'utm_medium': touchpoint.get('medium', '') or touchpoint.get('utm_medium', ''),
        'utm_campaign': touchpoint.get('campaign', '') or touchpoint.get('utm_campaign', ''),
        'utm_content': touchpoint.get('content', '') or touchpoint.get('utm_content', ''),
        'utm_term': touchpoint.get('term', '') or touchpoint.get('utm_term', ''),
        'fbclid': touchpoint.get('fbclid', ''),
        'gclid': touchpoint.get('gclid', ''),
        'ttclid': touchpoint.get('ttclid', ''),
        'epik': touchpoint.get('epik', ''),
        'sclid': touchpoint.get('sclid', ''),
    }
    referring_site = touchpoint.get('referer', '') or touchpoint.get('referring_site', '')
    return classify_channel(utm_data, referring_site)

def compute_attribution(journey, fallback_channel, model_name='last_touch', half_life_hours=72):
    """
    Distributes credit (summing to 1.0) among channels for an order.
    Returns:
        dict: {channel_slug: credit_percentage}
    """
    if not journey:
        return {fallback_channel: 1.0}

    # Extract classified channel and parsed datetime for each step
    steps = []
    for step in journey:
        ch = get_touchpoint_channel(step)
        ts = parse_ts(step.get('ts'))
        steps.append({'channel': ch, 'ts': ts})

    if not steps:
        return {fallback_channel: 1.0}

    # 1. Last Touch
    if model_name == 'last_touch':
        last_ch = steps[-1]['channel']
        return {last_ch: 1.0}

    # 2. First Touch
    if model_name == 'first_touch':
        first_ch = steps[0]['channel']
        return {first_ch: 1.0}

    # 3. Linear
    if model_name == 'linear':
        num_steps = len(steps)
        credit = 1.0 / num_steps
        result = {}
        for s in steps:
            ch = s['channel']
            result[ch] = result.get(ch, 0.0) + credit
        return result

    # 4. Time Decay
    if model_name == 'time_decay':
        if len(steps) == 1:
            return {steps[0]['channel']: 1.0}

        latest_ts = max(s['ts'] for s in steps)
        weights = []
        for s in steps:
            hours_before = (latest_ts - s['ts']).total_seconds() / 3600.0
            # weight decreases exponentially as hours_before increases
            weight = 0.5 ** (hours_before / half_life_hours)
            weights.append(weight)

        total_weight = sum(weights)
        if total_weight <= 0:
            # Fallback to linear
            num_steps = len(steps)
            return {s['channel']: 1.0 / num_steps for s in steps}

        result = {}
        for s, w in zip(steps, weights):
            ch = s['channel']
            result[ch] = result.get(ch, 0.0) + (w / total_weight)
        return result

    # Default fallback
    return {fallback_channel: 1.0}
