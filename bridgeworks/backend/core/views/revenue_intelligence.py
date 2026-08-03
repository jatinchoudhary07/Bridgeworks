from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models.revenue_intelligence import DealRisk
from core.serializers.revenue_intelligence import DealRiskSerializer
from core.services.deal_risk_engine import calculate_deal_risks_for_shop
from core.views_sales import _resolve_org

class DealRiskViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DealRiskSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return DealRisk.objects.none()
            
        qs = DealRisk.objects.filter(shop=shop)
        entity_type = self.request.query_params.get('entity_type')
        entity_id = self.request.query_params.get('entity_id')
        
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
            
        return qs

    @action(detail=False, methods=['post'], url_path='run')
    def run_risk_scan(self, request):
        org_id, shop = _resolve_org(request)
        if not shop:
            return Response({'error': 'Organization not found'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            recs_updated = calculate_deal_risks_for_shop(shop)
            return Response({
                'status': 'success',
                'message': f'Deal risk engine executed. Recalculated {recs_updated} records.'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
