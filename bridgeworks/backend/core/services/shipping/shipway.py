from .base import BaseShippingProvider
from core.utils import _get_decrypted_credentials

class ShipwayProvider(BaseShippingProvider):
    """
    Adapter class for the Shipway platform.
    Wraps the existing book_shipment_on_shipway function to maintain stability.
    """

    def book_shipment(self, order, carrier_id) -> tuple[bool, dict]:
        # Deferred import to prevent circular dependencies
        from core.tasks.shipway_sync import book_shipment_on_shipway

        creds = _get_decrypted_credentials(self.credentials.organization_id)
        if not creds:
            return False, {
                "error": "Shipway credentials not found or could not be decrypted.",
                "code": "SHIPWAY_CREDENTIALS_MISSING"
            }

        success, res = book_shipment_on_shipway(order, creds, carrier_id)
        if success:
            # Map carrier title based on ID passed
            primary_id = str(self.credentials.shipway_primary_carrier_id)
            fallback_id = str(self.credentials.shipway_fallback_carrier_id)
            
            carrier_title = self.credentials.shipway_primary_carrier_title
            if str(carrier_id) == fallback_id:
                carrier_title = self.credentials.shipway_fallback_carrier_title
            elif str(carrier_id) != primary_id:
                carrier_title = f"Shipway Carrier #{carrier_id}"

            return True, {
                "awb": res["awb"],
                "carrier_name": carrier_title,
                "tracking_url": res.get("shipping_url") or f"https://track.shipway.com/t/{res['awb']}"
            }
        else:
            # res holds error message on failure
            return False, {
                "error": res,
                "code": "SHIPWAY_API_FAILURE"
            }

    def validate_credentials(self) -> bool:
        try:
            email = self.credentials.get_shipway_email()
            license_key = self.credentials.get_shipway_license_key()
            return bool(email and license_key)
        except Exception:
            return False
