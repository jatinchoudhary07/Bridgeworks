import csv
import io
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.http import HttpResponse

from core.models.readiness import SystemAuditLog, SavedFilter
from core.serializers.readiness import SystemAuditLogSerializer, SavedFilterSerializer
from core.views_sales import _resolve_org
from core.models import WholesaleLead

class SystemAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SystemAuditLogSerializer

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return SystemAuditLog.objects.none()
        return SystemAuditLog.objects.filter(shop=shop)


class SavedFilterViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SavedFilterSerializer

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return SavedFilter.objects.none()
        return SavedFilter.objects.filter(shop=shop, user=self.request.user)

    def perform_create(self, serializer):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            raise ValidationError("Organization/Shop not found")
        serializer.save(shop=shop, user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def import_leads_csv(request):
    org_id, shop = _resolve_org(request)
    if not shop:
        return Response({'error': 'Organization/Shop not found'}, status=status.HTTP_400_BAD_REQUEST)

    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        data = file_obj.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(data))
        imported_count = 0
        for row in reader:
            WholesaleLead.objects.create(
                shop=shop,
                company_name=row.get('company_name', 'Unnamed Company'),
                contact_person=row.get('contact_person', ''),
                contact_designation=row.get('contact_designation', ''),
                phone=row.get('phone', ''),
                email=row.get('email', ''),
                city=row.get('city', ''),
                category=row.get('category', 'domestic'),
                industry=row.get('industry', ''),
                estimated_monthly_value=row.get('estimated_monthly_value') or None,
                expected_deal_value=row.get('expected_deal_value') or None,
                stage=row.get('stage', 'cold_lead'),
                created_by=request.user
            )
            imported_count += 1
            
        SystemAuditLog.objects.create(
            shop=shop,
            user=request.user,
            action='bulk_import',
            model_name='WholesaleLead',
            object_id='bulk',
            changed_fields={'count': imported_count}
        )

        return Response({
            'status': 'success',
            'message': f'Successfully imported {imported_count} leads.'
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def export_leads_csv(request):
    org_id, shop = _resolve_org(request)
    if not shop:
        return Response({'error': 'Organization/Shop not found'}, status=status.HTTP_400_BAD_REQUEST)

    leads = WholesaleLead.objects.filter(shop=shop)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="wholesale_leads.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'company_name', 'contact_person', 'contact_designation', 'phone', 
        'email', 'city', 'category', 'industry', 'estimated_monthly_value', 
        'expected_deal_value', 'stage', 'created_at'
    ])

    for lead in leads:
        writer.writerow([
            lead.company_name,
            lead.contact_person,
            lead.contact_designation,
            lead.phone,
            lead.email,
            lead.city,
            lead.category,
            lead.industry,
            lead.estimated_monthly_value or '',
            lead.expected_deal_value or '',
            lead.stage,
            lead.created_at.strftime('%Y-%m-%d %H:%M:%S') if lead.created_at else ''
        ])

    return response
