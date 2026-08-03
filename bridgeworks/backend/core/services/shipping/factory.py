from .shipway import ShipwayProvider
from .shiprocket import ShiprocketProvider

def get_shipping_provider(credentials):
    """
    Factory function that instantiates the active shipping provider
    based on the ShopCredentials model configuration.
    """
    platform = getattr(credentials, 'shipping_platform', 'shipway').lower()
    
    if platform == 'shiprocket':
        return ShiprocketProvider(credentials)
    elif platform == 'shipway':
        return ShipwayProvider(credentials)
    else:
        # Fallback default to Shipway for backwards compatibility
        return ShipwayProvider(credentials)
