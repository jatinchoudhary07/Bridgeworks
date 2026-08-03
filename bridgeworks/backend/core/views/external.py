from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import Sum, Q
from ..models import Order, LineItem, WorkforceMember, ExpenseEntry, RTOEngineItem
from ..serializers.external import (
    PicklistOrderSerializer, 
    GlobalPicklistSerializer, 
    WorkforceMemberExternalSerializer,
    ExpenseExternalSerializer
)
from ..authentication_external import ExternalAPITokenAuthentication

class PicklistExternalAPIView(APIView):
    """
    Exposes picklist data to external warehouse systems.
    Requires Bearer Token authentication.
    """
    authentication_classes = [ExternalAPITokenAuthentication]
    
    def get(self, request, shop_id):
        # 1. Validate that the shop_id in URL matches the authenticated token's shop
        if shop_id != request.org_id:
            return Response(
                {"error": "Unauthorized. Token does not belong to the requested shop."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Get Filters
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        # 3. Query Logic: Fetch only Batched orders currently in the active confirmation workflow
        visible_internal_statuses = ['Pending', 'Fulfilled', 'On Hold']
        orders = Order.objects.filter(
            org_id=shop_id,
            status='Batched',
            internal_fulfillment_status__in=visible_internal_statuses
        ).prefetch_related('batches').distinct()
        
        if from_date or to_date:
            start = parse_datetime(from_date) if from_date else None
            end = parse_datetime(to_date) if to_date else None
            
            date_q = Q()
            if start and end:
                # Filter strictly by the date the Batch was created
                date_q |= Q(batches__created_at__range=(start, end))
            elif start:
                date_q |= Q(batches__created_at__gte=start)
            elif end:
                date_q |= Q(batches__created_at__lte=end)
            
            orders = orders.filter(date_q).distinct()

        # 4. Aggregate Picklist Data (Summary of Items to Pick)
        items_summary = LineItem.objects.filter(order__in=orders).values('sku', 'title').annotate(
            total_quantity=Sum('quantity')
        ).order_by('sku')

        # 5. Build Response
        response_data = {
            "shop_id": shop_id,
            "period": {"from": from_date, "to": to_date},
            "summary": GlobalPicklistSerializer(items_summary, many=True).data,
            "orders": PicklistOrderSerializer(orders, many=True).data
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

class WorkforceExternalAPIView(APIView):
    """
    Exposes workforce member data to external systems.
    Aggregates both WorkforceMember model and standard User (Team) model.
    Requires Bearer Token authentication.
    """
    authentication_classes = [ExternalAPITokenAuthentication]
    
    def get(self, request, shop_id):
        # 1. Validate that the shop_id in URL matches the authenticated token's shop
        if shop_id != request.org_id:
            return Response(
                {"error": "Unauthorized. Token does not belong to the requested shop."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Extract query params
        search = request.query_params.get('search', '').strip()
        department = request.query_params.get('department')
        working_style = request.query_params.get('working_style')
        member_status = request.query_params.get('status')
        archive_state = str(request.query_params.get('archive_state', 'active')).lower()

        # 3. Fetch Workforce Members
        workforce_qs = WorkforceMember.objects.filter(org_id=shop_id).select_related('department')
        if archive_state == 'archived':
            workforce_qs = workforce_qs.filter(is_archived=True)
        elif archive_state == 'all':
            pass
        else:
            workforce_qs = workforce_qs.filter(is_archived=False)

        if search:
            workforce_qs = workforce_qs.filter(
                Q(full_name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search)
            )
        
        if department and department != 'all':
            if str(department).isdigit():
                workforce_qs = workforce_qs.filter(department_id=department)
            else:
                workforce_qs = workforce_qs.filter(department__name__icontains=department)
        
        if working_style and working_style != 'all':
            workforce_qs = workforce_qs.filter(working_style=working_style)
            
        if member_status and member_status != 'all':
            workforce_qs = workforce_qs.filter(status=member_status)

        # 4. Fetch Team Members (Users)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Note: Team members are usually never archived in the same way, 
        # but we follow archive_state logic where possible.
        team_qs = User.objects.filter(
            team_settings__organization__organization_id=shop_id,
            is_active=True
        ).prefetch_related('profile')

        if search:
            team_qs = team_qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(username__icontains=search)
            )
        
        # 5. Normalize and Combine
        from core.models.users import WorkspaceMembership
        co_founder_ids = set(
            WorkspaceMembership.objects.filter(
                user__in=team_qs, is_co_founder=True
            ).values_list('user_id', flat=True)
        )

        results = []

        # Add Workforce members
        for m in workforce_qs.order_by('-created_at'):
            results.append({
                'id': m.id,
                'full_name': m.full_name,
                'department_name': m.department.name if m.department else '—',
                'category': m.category or 'Workforce',
                'role_designation': m.role_designation or '—',
                'working_style': m.working_style or '—',
                'status': m.status or 'Active',
                'phone': m.phone or '—',
                'email': m.email or '—',
                'current_location': m.current_location or '—',
                'is_archived': m.is_archived,
                'source': 'workforce'
            })

        # Add Team members (if not archived-only)
        if archive_state != 'archived':
            for u in team_qs:
                profile = getattr(u, 'profile', None)
                full_name = f"{u.first_name} {u.last_name}".strip() or u.username
                
                # Apply secondary filters that might be in profile or manually mapped
                if working_style and working_style != 'all':
                    # Teammates don't have working style in models direct yet, 
                    # they usually show up as blank in UI, so they won't match.
                    continue
                
                if member_status and member_status != 'all' and member_status != 'Active':
                    continue

                results.append({
                    'id': u.id,
                    'full_name': full_name,
                    'department_name': '—', # Team members don't have department field in User model
                    'category': 'Team',
                    'role_designation': '—',
                    'working_style': '—',
                    'status': 'Active',
                    'phone': profile.phone if profile else '—',
                    'email': u.email or '—',
                    'current_location': profile.location if profile else '—',
                    'is_archived': False,
                    'source': 'team'
                })

        return Response(results, status=status.HTTP_200_OK)


class ExpenseExternalAPIView(APIView):
    """
    Exposes expense data and allows creation of new expenses for external systems.
    Requires Bearer Token authentication.
    """
    authentication_classes = [ExternalAPITokenAuthentication]
    
    def get(self, request, shop_id):
        if shop_id != request.org_id:
            return Response(
                {"error": "Unauthorized. Token does not belong to the requested shop."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        status_param = request.query_params.get('status')
        email = request.query_params.get('email')
        
        expenses = ExpenseEntry.objects.filter(org_id=shop_id, transaction_type='expense').select_related('user')
        
        if from_date:
            expenses = expenses.filter(spent_on__gte=from_date)
        if to_date:
            expenses = expenses.filter(spent_on__lte=to_date)
        if status_param:
            expenses = expenses.filter(status__iexact=status_param)
        if email:
            expenses = expenses.filter(user__email__iexact=email)
            
        expenses = expenses.order_by('-spent_on', '-created_at')
        
        return Response(ExpenseExternalSerializer(expenses, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, shop_id):
        if shop_id != request.org_id:
            return Response(
                {"error": "Unauthorized. Token does not belong to the requested shop."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        email = request.data.get('email')
        if not email:
            return Response({"error": "email is required to identify the user."}, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Look for the user in the organization
        user = User.objects.filter(
            team_settings__organization__organization_id=shop_id,
            email__iexact=email,
            is_active=True
        ).first()
        
        if not user:
            return Response({"error": "User with the provided email not found in this organization."}, status=status.HTTP_404_NOT_FOUND)

        # Create the expense entry
        serializer = ExpenseExternalSerializer(data=request.data)
        if serializer.is_valid():
            # Override status if not provided, default to 'Submitted'
            expense_status = request.data.get('status', 'Submitted')
            
            expense = serializer.save(
                user=user,
                org_id=shop_id,
                transaction_type='expense',
                status=expense_status
            )
            return Response(ExpenseExternalSerializer(expense).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RepairQueueExternalAPIView(APIView):
    """
    Exposes product-only RTO repair queue data to external repair systems.
    Requires Bearer Token authentication.
    """
    authentication_classes = [ExternalAPITokenAuthentication]

    def get(self, request, shop_id):
        if shop_id != request.org_id:
            return Response(
                {"error": "Unauthorized. Token does not belong to the requested shop."},
                status=status.HTTP_403_FORBIDDEN
            )

        search = request.query_params.get('search', '').strip()
        stage = request.query_params.get('stage', '').strip()
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        sort = request.query_params.get('sort', '-scanned_at')

        qs = RTOEngineItem.objects.filter(
            order__org_id=shop_id,
            scan_status='sent_for_repair',
        ).select_related('order', 'line_item', 'resolved_by')

        if search:
            qs = qs.filter(
                Q(line_item__title__icontains=search)
                | Q(line_item__name__icontains=search)
                | Q(line_item__sku__icontains=search)
                | Q(repair_stage__icontains=search)
            )
        if stage:
            qs = qs.filter(repair_stage=stage)
        if date_from:
            qs = qs.filter(scanned_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(scanned_at__date__lte=date_to)

        allowed_sort = {
            'scanned_at', '-scanned_at',
            'line_item__title', '-line_item__title',
            'line_item__sku', '-line_item__sku',
        }
        qs = qs.order_by(sort if sort in allowed_sort else '-scanned_at')

        items = []
        for item in qs:
            li = item.line_item
            items.append({
                "repair_item_id": item.id,
                "product": li.title if li else "",
                "sku": li.sku or "" if li else "",
                "variant": li.name or li.title if li else "",
                "quantity": li.quantity if li else 0,
                "repair_stage": item.repair_stage or "",
                "repair_stage_label": item.get_repair_stage_display() if item.repair_stage else "",
                "resolved_by": item.resolved_by.get_full_name() if item.resolved_by else "",
            })

        return Response({
            "shop_id": shop_id,
            "count": len(items),
            "items": items,
        }, status=status.HTTP_200_OK)


class RepairQueueCompleteExternalAPIView(APIView):
    """
    Marks external repair queue items as repaired and sends them to inventory.
    Requires Bearer Token authentication.
    """
    authentication_classes = [ExternalAPITokenAuthentication]

    def post(self, request, shop_id):
        if shop_id != request.org_id:
            return Response(
                {"error": "Unauthorized. Token does not belong to the requested shop."},
                status=status.HTTP_403_FORBIDDEN
            )

        ids = request.data.get('repair_item_ids') or request.data.get('item_ids') or []
        if not ids:
            return Response({"error": "repair_item_ids is required"}, status=status.HTTP_400_BAD_REQUEST)

        qs = RTOEngineItem.objects.filter(
            pk__in=ids,
            order__org_id=shop_id,
            scan_status='sent_for_repair',
        )
        items = list(qs.select_related('order', 'line_item'))
        if not items:
            return Response({"updated": 0, "message": "No matching repair queue items found."}, status=status.HTTP_200_OK)

        qs.update(scan_status='sent_to_inventory', qc_at=timezone.now())

        from ..views_rto_engine import _send_items_to_inventory
        _send_items_to_inventory(shop_id, items)

        return Response({"updated": len(items)}, status=status.HTTP_200_OK)
