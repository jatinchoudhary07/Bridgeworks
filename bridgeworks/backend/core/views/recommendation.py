from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Count

from core.models.recommendation import Recommendation
from core.serializers.recommendation import RecommendationSerializer
from core.views_sales import _resolve_org

class RecommendationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RecommendationSerializer
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return Recommendation.objects.none()
        
        qs = Recommendation.objects.filter(shop=shop)
        
        # Filter by status. Default is active.
        status_param = self.request.query_params.get('status', 'active')
        if status_param != 'all':
            qs = qs.filter(status=status_param)
            
        type_param = self.request.query_params.get('type')
        if type_param:
            qs = qs.filter(type=type_param)

        severity_param = self.request.query_params.get('severity')
        if severity_param:
            qs = qs.filter(severity=severity_param)
            
        return qs

    def perform_create(self, serializer):
        org_id, shop = _resolve_org(self.request)
        serializer.save(shop=shop)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def recommendation_summary(request):
    """
    Get summary statistics of active recommendations broken down by severity and type.
    """
    org_id, shop = _resolve_org(request)
    if not shop:
        return Response({'error': 'Organization not found'}, status=status.HTTP_400_BAD_REQUEST)
        
    active_qs = Recommendation.objects.filter(shop=shop, status='active')
    
    # Severity breakdown
    severity_counts = active_qs.values('severity').annotate(count=Count('id'))
    severities = {choice[0]: 0 for choice in Recommendation.SEVERITY_CHOICES}
    for item in severity_counts:
        if item['severity'] in severities:
            severities[item['severity']] = item['count']
            
    # Type breakdown
    type_counts = active_qs.values('type').annotate(count=Count('id'))
    types = {choice[0]: 0 for choice in Recommendation.TYPE_CHOICES}
    for item in type_counts:
        if item['type'] in types:
            types[item['type']] = item['count']
            
    total_active = active_qs.count()
    
    return Response({
        'severities': severities,
        'types': types,
        'total_active': total_active
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def run_recommendation_scan(request):
    """
    Trigger manual execution of recommendation engine scanner for the shop.
    """
    org_id, shop = _resolve_org(request)
    if not shop:
        return Response({'error': 'Organization not found'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        from core.services.recommendation_engine import generate_recommendations_for_shop
        created_count, resolved_count = generate_recommendations_for_shop(shop)
        return Response({
            'status': 'success',
            'message': 'Recommendation scan completed.',
            'created_count': created_count,
            'resolved_count': resolved_count
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
