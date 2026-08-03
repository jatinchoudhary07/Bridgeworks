from abc import ABC, abstractmethod

class BaseShippingProvider(ABC):
    """
    Abstract base class defining the standard interface for all
    shipping / AWB generation providers (Shipway, Shiprocket, etc.)
    """

    def __init__(self, credentials):
        self.credentials = credentials

    @abstractmethod
    def book_shipment(self, order, carrier_id) -> tuple[bool, dict]:
        """
        Book a shipment/generate AWB with the carrier.

        Args:
            order: The Django Order model instance.
            carrier_id: Platform-specific carrier ID or code.

        Returns:
            A tuple of (success: bool, response_dict: dict)
            
            On success, response_dict must contain:
            {
                "awb": "tracking_number_string",
                "carrier_name": "courier_partner_title",
                "tracking_url": "https://..."
            }
            
            On failure, response_dict must contain:
            {
                "error": "Error message details",
                "code": "ERROR_CODE"
            }
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Validates the configured API credentials.
        Returns: True if valid, False otherwise.
        """
        pass
