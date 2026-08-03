from rest_framework import serializers
from django.contrib.auth.models import User
from core.models import ShopCredentials


class UserSerializer(serializers.ModelSerializer):
    shopify_order_prefix = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'shopify_order_prefix']

    def get_shopify_order_prefix(self, obj):
        try:
            return obj.shop_credentials.shopify_order_prefix
        except (AttributeError, ShopCredentials.DoesNotExist):
            return "" 
