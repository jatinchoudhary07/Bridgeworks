import logging
import requests
import json
from datetime import datetime, timezone, timedelta
from django.conf import settings
from core.models import AIAgent
from core.services.chatwoot_service import ChatwootService

logger = logging.getLogger(__name__)

def auto_close_inactive_conversations():
    """
    Periodically queries active (open) Chatwoot conversations assigned to Shori bot (ID 1).
    If the customer hasn't replied for 5+ hours (the last message is outgoing from the bot),
    closes the conversation (resolves it) and marks it as 'handled'.
    """
    logger.info("Executing background task: auto_close_inactive_conversations...")
    agents = AIAgent.objects.filter(status='live') | AIAgent.objects.filter(status='sandbox')
    if not agents.exists():
        logger.info("No active or sandbox AI Agents found. Auto-close skipped.")
        return

    cw_service = ChatwootService()
    if not cw_service.platform_key:
        logger.info("CHATWOOT_PLATFORM_KEY is not configured. Auto-close skipped (Mock Mode).")
        return
    
    # 1. Fetch platform/user token for Shori bot (ID 1)
    token_url = f"{cw_service.api_url}/platform/api/v1/users/1/token"
    try:
        token_resp = requests.post(token_url, headers=cw_service._get_headers(), timeout=10)
        if token_resp.status_code not in (200, 201):
            logger.error(f"Failed to fetch platform token for auto-close: {token_resp.status_code}, {token_resp.text}")
            return
        user_token = token_resp.json().get("access_token")
    except Exception as e:
        logger.error(f"Exception fetching platform token for auto-close: {e}")
        return

    headers = {
        "api_access_token": user_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # 2. Iterate through each agent to inspect their inbox's conversations
    for agent in agents:
        inbox_id = agent.chatwoot_inbox_id
        if not inbox_id:
            continue
            
        try:
            account = cw_service.get_or_create_account(agent.organization_id, org_id=agent.organization_id)
            account_id = account.get("id") if isinstance(account, dict) else getattr(account, 'id', None)
            if not account_id:
                account_id = 1
        except Exception as ae:
            logger.error(f"Failed to resolve account for org {agent.organization_id}: {ae}")
            account_id = 1

        logger.info(f"Checking conversations for Org: {agent.organization_id}, Account ID: {account_id}, Inbox: {inbox_id}...")

        # Fetch open conversations
        convs_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations?status=open"
        try:
            convs_resp = requests.get(convs_url, headers=headers, timeout=10)
            if convs_resp.status_code != 200:
                logger.error(f"Failed to fetch conversations: {convs_resp.status_code}, {convs_resp.text}")
                continue
            
            data = convs_resp.json()
            conversations = data if isinstance(data, list) else data.get("payload", [])
            
            for conv in conversations:
                # Verify conversation is assigned to Shori bot (ID 1)
                assignee = conv.get("meta", {}).get("assignee") or conv.get("assignee") or {}
                assignee_id = assignee.get("id")
                
                # Check labels
                labels = [l.lower() for l in (conv.get("labels") or [])]
                
                # Auto-close condition:
                # - It is assigned to the bot (ID 1)
                # - AND does NOT have human handling labels
                is_assigned_to_bot = (assignee_id == 1)
                is_handled_by_human = any(l in labels for l in ["agent-handling", "escalated to agent", "human-needed", "needs reply"])
                
                if is_assigned_to_bot and not is_handled_by_human:
                    conv_id = conv.get("id")
                    
                    # Fetch messages of this conversation to check timing
                    messages_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conv_id}/messages"
                    msg_resp = requests.get(messages_url, headers=headers, timeout=10)
                    if msg_resp.status_code != 200:
                        continue
                        
                    msg_data = msg_resp.json()
                    messages = msg_data if isinstance(msg_data, list) else msg_data.get("payload", [])
                    
                    # Filter out private notes
                    public_messages = [m for m in messages if not m.get("private")]
                    if not public_messages:
                        continue
                        
                    # Get last message
                    last_msg = public_messages[-1]
                    last_sender_type = last_msg.get("sender", {}).get("type")
                    last_sender_id = last_msg.get("sender", {}).get("id")
                    created_at_epoch = last_msg.get("created_at")
                    
                    # Last message must be from Shori bot (User ID 1)
                    is_last_msg_from_bot = (last_sender_type == "user" and last_sender_id == 1)
                    
                    if is_last_msg_from_bot:
                        try:
                            if isinstance(created_at_epoch, (int, float)):
                                last_msg_time = datetime.fromtimestamp(created_at_epoch, tz=timezone.utc)
                            else:
                                iso_str = str(created_at_epoch).replace("Z", "+00:00")
                                last_msg_time = datetime.fromisoformat(iso_str)
                        except Exception as te:
                            logger.error(f"Error parsing last message time: {te}")
                            continue
                            
                        idle_duration = datetime.now(timezone.utc) - last_msg_time
                        
                        # Auto-close after 5 hours
                        if idle_duration > timedelta(hours=5):
                            logger.info(f"Conv #{conv_id} is idle for 5+ hours. Resolving and labeling as 'handled'...")
                            
                            # A. Toggle status to resolved
                            status_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conv_id}/toggle_status"
                            requests.post(status_url, json={"status": "resolved"}, headers=headers, timeout=10)
                            
                            # B. Update labels: add 'handled', remove 'ai-handling'
                            updated_labels = list(set(labels + ["handled"]))
                            for label_to_remove in ["ai-handling", "awaiting"]:
                                if label_to_remove in updated_labels:
                                    updated_labels.remove(label_to_remove)
                                    
                            labels_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conv_id}/labels"
                            requests.post(labels_url, json={"labels": updated_labels}, headers=headers, timeout=10)
                            
                            # C. Post a private internal note
                            note_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conv_id}/messages"
                            note_payload = {
                                "content": "🤖 **Shori Automation**: Conversation resolved and marked as 'handled' after 5+ hours of customer inactivity.",
                                "message_type": "outgoing",
                                "private": True
                            }
                            requests.post(note_url, json=note_payload, headers=headers, timeout=10)
                            
        except Exception as e:
            logger.error(f"Error checking conversations for Org {agent.organization_id}: {e}", exc_info=True)
