import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Module-level cache to avoid creating duplicate accounts/users across requests
_account_cache = {}  # org_id -> account_id
_user_cache = {}     # email -> user_id
_labels_seeded = {}  # account_id -> bool


class ChatwootService:
    """
    Handles all communication with the Chatwoot Platform API.
    Enables dynamic Account provisioning, Agent mapping, and secure SSO login link generation.
    """

    def __init__(self):
        self.api_url = getattr(settings, 'CHATWOOT_API_URL', 'http://localhost:3000').rstrip('/')
        self.platform_key = getattr(settings, 'CHATWOOT_PLATFORM_KEY', '')

        if not self.platform_key:
            logger.warning("CHATWOOT_PLATFORM_KEY is not configured. Chatwoot integrations will run in mock/fallback mode.")

    def _get_headers(self):
        return {
            "api_access_token": self.platform_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # ------------------------------------------------------------------
    # Account helpers
    # ------------------------------------------------------------------

    def _list_accounts(self):
        """GET /platform/api/v1/accounts — returns all accounts."""
        url = f"{self.api_url}/platform/api/v1/accounts"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                return resp.json()  # list of account dicts
        except Exception:
            logger.exception("Error listing Chatwoot accounts")
        return []

    def _find_account_by_name(self, name):
        """Search existing accounts for one that matches *name*."""
        for acct in self._list_accounts():
            if acct.get("name", "").lower() == name.lower():
                return acct
        return None

    def get_or_create_account(self, name, org_id=None):
        """
        Return an existing account whose name matches, or create a new one.
        Results are cached in-process so repeated calls don't hit the API.
        """
        cache_key = org_id or name
        if cache_key in _account_cache:
            return {"id": _account_cache[cache_key], "name": name}

        if not self.platform_key:
            return {"id": 1, "name": name, "mock": True}

        # Try to find an existing account first
        existing = self._find_account_by_name(name)
        if existing and "id" in existing:
            _account_cache[cache_key] = existing["id"]
            logger.info(f"Reusing existing Chatwoot account #{existing['id']} for '{name}'")
            return existing

        # Create a new one
        url = f"{self.api_url}/platform/api/v1/accounts"
        try:
            resp = requests.post(url, json={"name": name}, headers=self._get_headers(), timeout=10)
            if resp.status_code in (200, 201):
                data = resp.json()
                _account_cache[cache_key] = data["id"]
                logger.info(f"Created new Chatwoot account #{data['id']} for '{name}'")
                return data
            logger.error(f"Failed to create Chatwoot account: {resp.status_code}, {resp.text}")
        except Exception:
            logger.exception("Error calling Chatwoot create_account API")

        return None

    # Keep the old name as an alias so nothing breaks
    def create_account(self, name):
        return self.get_or_create_account(name)

    # ------------------------------------------------------------------
    # User helpers
    # ------------------------------------------------------------------

    def _find_user_by_email(self, email):
        """Search for an existing Chatwoot platform user by email."""
        url = f"{self.api_url}/platform/api/v1/users"
        try:
            resp = requests.get(url, headers=self._get_headers(), params={"email": email}, timeout=10)
            if resp.status_code == 200:
                users = resp.json()
                if isinstance(users, list):
                    for u in users:
                        if u.get("email", "").lower() == email.lower():
                            return u
                elif isinstance(users, dict) and users.get("email"):
                    return users
        except Exception:
            logger.exception("Error searching Chatwoot users")
        return None

    def get_or_create_user(self, email, name, role="agent"):
        """Return existing user or create a new one. Cached in-process."""
        if email in _user_cache:
            return {"id": _user_cache[email], "email": email, "name": name}

        if not self.platform_key:
            return {"id": 1, "email": email, "name": name, "mock": True}

        # Try to find existing user first
        existing = self._find_user_by_email(email)
        if existing and "id" in existing:
            _user_cache[email] = existing["id"]
            return existing

        # Create new user
        url = f"{self.api_url}/platform/api/v1/users"
        payload = {"email": email, "name": name, "role": role}
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=10)
            if resp.status_code in (200, 201):
                data = resp.json()
                _user_cache[email] = data["id"]
                return data
            if resp.status_code == 422:
                # User already exists — try to look them up
                existing = self._find_user_by_email(email)
                if existing and "id" in existing:
                    _user_cache[email] = existing["id"]
                    return existing
            logger.warning(f"Create Chatwoot user returned {resp.status_code}: {resp.text}")
        except Exception:
            logger.exception("Error calling Chatwoot create_user API")

        return None

    # Keep old name as alias
    def create_user(self, email, name, role="agent"):
        return self.get_or_create_user(email, name, role)

    # ------------------------------------------------------------------
    # Account-User association
    # ------------------------------------------------------------------

    def add_user_to_account(self, account_id, user_id, role="agent"):
        """Associates a user with an account."""
        if not self.platform_key:
            return True

        url = f"{self.api_url}/platform/api/v1/accounts/{account_id}/account_users"
        payload = {"user_id": user_id, "role": role}
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=10)
            if resp.status_code in (200, 201, 204):
                return True
            # 422 likely means already associated — that's fine
            if resp.status_code == 422:
                return True
            logger.error(f"Failed to associate user with Chatwoot account: {resp.status_code}, {resp.text}")
        except Exception:
            logger.exception("Error calling Chatwoot add_user_to_account API")

        return False

    def ensure_essential_labels(self, account_id, token):
        """
        Ensures the essential escalation/status labels exist in Chatwoot for this account,
        setting show_on_sidebar=True so they are rendered as folders in the agent dashboard.
        """
        if _labels_seeded.get(account_id):
            return
        labels = [
            {"title": "in-queue", "color": "#7f8c8d", "description": "Conversations waiting in the main queue"},
            {"title": "awaiting", "color": "#ffab00", "description": "Awaiting customer or agent input"},
            {"title": "investigating", "color": "#00d2ff", "description": "Complaint analysis or photo verification in progress"},
            {"title": "escalated-to-agent", "color": "#ff3b30", "description": "Escalated to human support specialist"},
            {"title": "ai-handling", "color": "#1f93ff", "description": "Conversations active with AI Support"},
            {"title": "human-agent", "color": "#1f93ff", "description": "Conversations active with human Agent"},
            {"title": "handled", "color": "#30d158", "description": "Completed and resolved conversations"},
            {"title": "needs-reply", "color": "#af52de", "description": "Human agent reply required"},
            {"title": "needs-first-reply", "color": "#30d158", "description": "New conversations requiring first response"}
        ]
        
        headers = {
            "api_access_token": token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # 1. Fetch existing labels
        list_url = f"{self.api_url}/api/v1/accounts/{account_id}/labels"
        existing_titles = set()
        try:
            resp = requests.get(list_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                # Chatwoot returns a list directly or in payload
                data = resp.json()
                lbls = data if isinstance(data, list) else data.get("payload", [])
                for lbl in lbls:
                    existing_titles.add(lbl.get("title", "").lower())
        except Exception as e:
            logger.error(f"Failed to fetch existing Chatwoot labels: {e}")
            
        # 2. Provision missing ones
        for lbl in labels:
            if lbl["title"] in existing_titles:
                continue
            
            create_url = f"{self.api_url}/api/v1/accounts/{account_id}/labels"
            payload = {
                "title": lbl["title"],
                "color": lbl["color"],
                "description": lbl["description"],
                "show_on_sidebar": True
            }
            try:
                post_resp = requests.post(create_url, json=payload, headers=headers, timeout=10)
                if post_resp.status_code in (200, 201):
                    logger.info(f"Successfully seeded label '{lbl['title']}' in Chatwoot.")
                else:
                    logger.warning(f"Failed to seed label '{lbl['title']}': {post_resp.status_code}, {post_resp.text}")
            except Exception as e:
                logger.error(f"Error seeding label '{lbl['title']}': {e}")
        
        _labels_seeded[account_id] = True

    # ------------------------------------------------------------------
    # SSO URL generation
    # ------------------------------------------------------------------

    def generate_sso_url(self, user_email, user_name, org_name, org_id):
        """
        Generates a secure Single Sign-On (SSO) login URL for the agent.
        Steps:
        1. Ensures Chatwoot account exists for org_id (reuses existing)
        2. Ensures Chatwoot user exists for user_email (reuses existing)
        3. Ensures user is added to account
        4. Generates SSO login token: GET /platform/api/v1/users/{user_id}/login
        """
        if not self.platform_key:
            logger.info("Chatwoot is in mock mode. Returning fallback dev dashboard.")
            return f"{self.api_url}/app/accounts/1/dashboard"

        try:
            # 1. Get or create Account (no duplicates!)
            account = self.get_or_create_account(org_name, org_id=org_id)
            if not account or 'id' not in account:
                logger.error("Could not verify Chatwoot account")
                return f"{self.api_url}/app/accounts/1/dashboard"

            account_id = account['id']

            # 2. Get or create User (no duplicates!)
            cw_user = self.get_or_create_user(user_email, user_name)
            if not cw_user or 'id' not in cw_user:
                logger.warning(f"Could not provision user {user_email}, falling back.")
                return f"{self.api_url}/app/accounts/{account_id}/dashboard"

            user_id = cw_user['id']

            # 3. Associate User with Account
            self.add_user_to_account(
                account_id, user_id,
                role="administrator" if cw_user.get("role") == "admin" else "agent"
            )

            # 4. Generate Login URL
            url = f"{self.api_url}/platform/api/v1/users/{user_id}/login"
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                sso_data = resp.json()
                if "url" in sso_data:
                    return sso_data["url"]

            logger.error(f"Failed to generate SSO token URL: {resp.status_code}, {resp.text}")
            return f"{self.api_url}/app/accounts/{account_id}/dashboard"

        except Exception:
            logger.exception("Failed to execute Chatwoot SSO onboarding flow")
            return f"{self.api_url}/app/accounts/1/dashboard"
