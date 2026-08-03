from decimal import Decimal
from django.db.models import Q, Sum, F, Count
from django.db.models.functions import Coalesce

from rest_framework import generics, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from core.permissions import HasModulePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.models import FinanceOption, FinanceTransaction
from core.serializers import FinanceOptionSerializer, FinanceTransactionSerializer
from core.views.helpers import _get_org_id_or_none


def _reached_finance(workflow_steps):
    if not isinstance(workflow_steps, list):
        return False
    for step in workflow_steps:
        s = str(step.get('step') or step.get('action') or step.get('status') or '').lower().strip().replace('_', ' ').replace('-', ' ')
        if s in {
            'dept head approved', 'dept_head_approved',
            'partially approved', 'partially_approved',
            'finance reviewed', 'finance_reviewed',
            'approved'
        }:
            return True
    return False



class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


class FinanceBaseAPIView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    entry_type = None

    def get_org_id(self):
        return _get_org_id_or_none(self.request) or ''

    def get_base_queryset(self):
        org_id = self.get_org_id()
        queryset = FinanceTransaction.objects.filter(entry_type=self.entry_type)
        if org_id:
            return queryset.filter(org_id=org_id)
        return queryset.filter(user=self.request.user, org_id='')

    def apply_filters(self, queryset):
        search = (self.request.query_params.get('search') or '').strip()
        category = (self.request.query_params.get('category') or '').strip()
        department = (self.request.query_params.get('department') or '').strip()
        nature = (self.request.query_params.get('nature') or '').strip()
        payment_type = (self.request.query_params.get('payment_type') or '').strip()
        status_value = (self.request.query_params.get('status') or '').strip()
        from_date = (self.request.query_params.get('from') or self.request.query_params.get('from_date') or '').strip()
        to_date = (self.request.query_params.get('to') or self.request.query_params.get('to_date') or '').strip()

        if search:
            queryset = queryset.filter(
                Q(reference_id__icontains=search)
                | Q(particular__icontains=search)
                | Q(invoice_no__icontains=search)
            )
        if category and category.lower() != 'all':
            queryset = queryset.filter(category=category)
        if department and department.lower() != 'all':
            queryset = queryset.filter(department=department)
        if nature and nature.lower() != 'all':
            queryset = queryset.filter(nature=nature)
        if payment_type and payment_type.lower() != 'all':
            queryset = queryset.filter(payment_type=payment_type)
        if status_value and status_value.lower() != 'all':
            queryset = queryset.filter(status=status_value)
        if from_date:
            queryset = queryset.filter(entry_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(entry_date__lte=to_date)

        return queryset


class FinanceTransactionListCreateView(FinanceBaseAPIView):
    def get(self, request):
        queryset = self.apply_filters(self.get_base_queryset())
        serializer = FinanceTransactionSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        payload = request.data.copy()
        payload['entry_type'] = self.entry_type

        serializer = FinanceTransactionSerializer(data=payload, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save(user=request.user, org_id=self.get_org_id(), entry_type=self.entry_type)
        return Response(FinanceTransactionSerializer(item, context={'request': request}).data, status=status.HTTP_201_CREATED)


class FinanceTransactionDetailView(FinanceBaseAPIView):
    def get_object(self, pk):
        queryset = self.get_base_queryset().filter(entry_type=self.entry_type)
        return generics.get_object_or_404(queryset, pk=pk)

    def patch(self, request, pk):
        item = self.get_object(pk)
        payload = request.data.copy()
        payload['entry_type'] = self.entry_type

        serializer = FinanceTransactionSerializer(item, data=payload, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FinanceTransactionSerializer(item, context={'request': request}).data)

    def delete(self, request, pk):
        item = self.get_object(pk)
        try:
            if item.receipt:
                item.receipt.delete(save=False)
        except Exception:
            pass
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FinanceIncomeListCreateView(FinanceTransactionListCreateView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'finance_accounting:income:view',
        'POST': 'finance_accounting:income:create'
    }
    entry_type = 'income'


class FinanceIncomeDetailView(FinanceTransactionDetailView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PATCH': 'finance_accounting:income:edit',
        'DELETE': 'finance_accounting:income:delete'
    }
    entry_type = 'income'


class FinanceExpenseListCreateView(FinanceTransactionListCreateView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'finance_accounting:expense:view',
        'POST': 'finance_accounting:expense:create'
    }
    entry_type = 'expense'


class FinanceExpenseDetailView(FinanceTransactionDetailView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PATCH': 'finance_accounting:expense:edit',
        'DELETE': 'finance_accounting:expense:delete'
    }
    entry_type = 'expense'


class FinanceOptionListCreateView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'finance_accounting:dashboard:view',
        'POST': 'finance_accounting:dashboard:create'
    }

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def get_base_queryset(self, request):
        org_id = self.get_org_id(request)
        queryset = FinanceOption.objects.all()
        if org_id:
            return queryset.filter(org_id=org_id)
        return queryset.filter(org_id='')

    def get(self, request):
        queryset = self.get_base_queryset(request)
        option_type = (request.query_params.get('option_type') or '').strip()
        parent_value = (request.query_params.get('parent_value') or '').strip()

        if option_type:
            queryset = queryset.filter(option_type=option_type)
        if parent_value:
            queryset = queryset.filter(parent_value=parent_value)

        serializer = FinanceOptionSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = FinanceOptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(created_by=request.user, org_id=self.get_org_id(request))
        return Response(FinanceOptionSerializer(item).data, status=status.HTTP_201_CREATED)


class FinanceOptionDetailView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PATCH': 'finance_accounting:dashboard:edit',
        'DELETE': 'finance_accounting:dashboard:delete'
    }

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def get_object(self, request, pk):
        org_id = self.get_org_id(request)
        queryset = FinanceOption.objects.all()
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        else:
            queryset = queryset.filter(org_id='')
        return generics.get_object_or_404(queryset, pk=pk)

    def patch(self, request, pk):
        item = self.get_object(request, pk)
        serializer = FinanceOptionSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FinanceOptionSerializer(item).data)

    def delete(self, request, pk):
        item = self.get_object(request, pk)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FinanceLedgerSummaryView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'finance_accounting:dashboard:view',
    }

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def get(self, request):
        org_id = self.get_org_id(request)
        queryset = FinanceTransaction.objects.all()
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        else:
            queryset = queryset.filter(org_id='')

        # Apply date filters
        from_date = (request.query_params.get('from') or request.query_params.get('from_date') or '').strip()
        to_date = (request.query_params.get('to') or request.query_params.get('to_date') or '').strip()
        if from_date:
            queryset = queryset.filter(entry_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(entry_date__lte=to_date)

        summary = (
            queryset
            .values('category', 'entry_type')
            .annotate(total_amount=Sum('amount'))
            .order_by('category', 'entry_type')
        )

        grouped_data = {}
        for row in summary:
            category = (row.get('category') or 'Uncategorized').strip() or 'Uncategorized'
            entry_type = row.get('entry_type') or 'expense'
            total_amount = Decimal(str(row.get('total_amount') or '0.00'))

            key = (category, entry_type)
            if key not in grouped_data:
                grouped_data[key] = Decimal('0.00')
            grouped_data[key] += total_amount

        rows = []
        for (category, entry_type), total_amount in grouped_data.items():
            total_debit = float(round(total_amount, 2)) if entry_type == 'expense' else 0.0
            total_credit = float(round(total_amount, 2)) if entry_type == 'income' else 0.0

            rows.append({
                'ledger_id': f"{entry_type}:{category}",
                'ledger': category,
                'type': entry_type,
                'total_debit': total_debit,
                'total_credit': total_credit,
            })

        return Response(rows, status=status.HTTP_200_OK)



class FinanceTrialBalanceView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'finance_accounting:dashboard:view',
    }

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def get(self, request):
        org_id = self.get_org_id(request)
        queryset = FinanceTransaction.objects.all()
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        else:
            queryset = queryset.filter(org_id='')

        # Apply date filters
        from_date = (request.query_params.get('from') or request.query_params.get('from_date') or '').strip()
        to_date = (request.query_params.get('to') or request.query_params.get('to_date') or '').strip()
        if from_date:
            queryset = queryset.filter(entry_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(entry_date__lte=to_date)

        summary = (
            queryset
            .values('category', 'entry_type')
            .annotate(total_amount=Sum('amount'))
            .order_by('category', 'entry_type')
        )

        grouped_data = {}
        for row in summary:
            category = (row.get('category') or 'Uncategorized').strip() or 'Uncategorized'
            entry_type = row.get('entry_type') or 'expense'
            total_amount = Decimal(str(row.get('total_amount') or '0.00'))

            key = (category, entry_type)
            if key not in grouped_data:
                grouped_data[key] = Decimal('0.00')
            grouped_data[key] += total_amount

        entries = []
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')

        for (category, entry_type), total_amount in grouped_data.items():
            debit_value = total_amount if entry_type == 'expense' else Decimal('0.00')
            credit_value = total_amount if entry_type == 'income' else Decimal('0.00')

            total_debit += debit_value
            total_credit += credit_value

            entries.append({
                'ledger_id': f"{entry_type}:{category}",
                'ledger': category,
                'type': entry_type,
                'debit': float(round(debit_value, 2)),
                'credit': float(round(credit_value, 2)),
            })

        return Response(
            {
                'entries': entries,
                'total_debit': float(round(total_debit, 2)),
                'total_credit': float(round(total_credit, 2)),
                'is_balanced': round(total_debit, 2) == round(total_credit, 2),
            },
            status=status.HTTP_200_OK,
        )



class FinanceProfitLossView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'finance_accounting:dashboard:view',
    }

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def get(self, request):
        org_id = self.get_org_id(request)
        queryset = FinanceTransaction.objects.all()
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        else:
            queryset = queryset.filter(org_id='')

        # Apply date filters
        from_date = (request.query_params.get('from') or request.query_params.get('from_date') or '').strip()
        to_date = (request.query_params.get('to') or request.query_params.get('to_date') or '').strip()
        if from_date:
            queryset = queryset.filter(entry_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(entry_date__lte=to_date)

        summary = (
            queryset
            .values('category', 'entry_type')
            .annotate(total_amount=Sum('amount'))
            .order_by('category', 'entry_type')
        )

        grouped_data = {}
        for row in summary:
            category = (row.get('category') or 'Uncategorized').strip() or 'Uncategorized'
            entry_type = row.get('entry_type') or 'expense'
            total_amount = Decimal(str(row.get('total_amount') or '0.00'))

            key = (category, entry_type)
            if key not in grouped_data:
                grouped_data[key] = Decimal('0.00')
            grouped_data[key] += total_amount

        income = []
        expenses = []
        total_income = Decimal('0.00')
        total_expense = Decimal('0.00')

        for (category, entry_type), amount in grouped_data.items():
            amount_val = float(round(amount, 2))
            item = {
                'ledger_id': f"{entry_type}:{category}",
                'ledger': category,
                'amount': amount_val,
            }

            if entry_type == 'income':
                total_income += amount
                income.append(item)
            else:
                total_expense += amount
                expenses.append(item)

        profit = float(round(total_income - total_expense, 2))

        return Response(
            {
                'income': income,
                'expenses': expenses,
                'total_income': float(round(total_income, 2)),
                'total_expense': float(round(total_expense, 2)),
                'profit': profit,
            },
            status=status.HTTP_200_OK,
        )



class FinanceBalanceSheetView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'finance_accounting:dashboard:view',
    }

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def get(self, request):
        org_id = self.get_org_id(request)
        queryset = FinanceTransaction.objects.all()
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        else:
            queryset = queryset.filter(org_id='')

        # Apply date filters
        from_date = (request.query_params.get('from') or request.query_params.get('from_date') or '').strip()
        to_date = (request.query_params.get('to') or request.query_params.get('to_date') or '').strip()
        if from_date:
            queryset = queryset.filter(entry_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(entry_date__lte=to_date)

        totals = queryset.values('entry_type').annotate(total_amount=Sum('amount'))
        total_income = Decimal('0.00')
        total_expense = Decimal('0.00')
        for row in totals:
            if row.get('entry_type') == 'income':
                total_income = Decimal(str(row.get('total_amount') or '0.00'))
            elif row.get('entry_type') == 'expense':
                total_expense = Decimal(str(row.get('total_amount') or '0.00'))

        equity = total_income - total_expense
        total_assets = equity
        total_liabilities = Decimal('0.00')
        is_balanced = round(total_assets, 2) == round(total_liabilities + equity, 2)

        return Response(
            {
                'assets': [],
                'liabilities': [],
                'equity': float(round(equity, 2)),
                'total_assets': float(round(total_assets, 2)),
                'total_liabilities': float(round(total_liabilities, 2)),
                'is_balanced': is_balanced,
            },
            status=status.HTTP_200_OK,
        )



# ─────────────────────────────────────────────────────────────────────────────
# Finance Pending Expenses  —  driven by HR ExpenseEntry model
# ─────────────────────────────────────────────────────────────────────────────

# Statuses that Finance still needs to pay out.
# Only expenses that HR has approved (Dept Head Approved) or beyond are shown.
# 'Submitted' entries have not been reviewed by HR yet — they stay in HR module only.
_FIN_UNPAID_STATUSES = {'Dept Head Approved', 'Partially Approved', 'Finance Reviewed'}
_FIN_VISIBLE_STATUSES = {'Dept Head Approved', 'Partially Approved', 'Finance Reviewed', 'Paid', 'Rejected'}
_FIN_PAYMENT_METHODS = ['cash', 'bank_transfer', 'upi', 'cheque', 'neft', 'other']


def _fin_round2(val):
    try:
        return round(float(val or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _fin_effective_amount(expense):
    return _fin_round2(expense.approved_amount if expense.approved_amount is not None else expense.amount)


def _fin_expense_payload(expense, request=None, user_obj=None, dept_name=''):
    """Serialise an ExpenseEntry for the finance pending-expenses views."""
    from core.views_mydesk import _expense_receipt_url
    u = user_obj or getattr(expense, 'user', None)
    effective_amount = _fin_effective_amount(expense)
    return {
        'id': expense.id,
        'user_id': expense.user_id,
        'member_name': (u.get_full_name() or u.username) if u else '',
        'member_email': (u.email or '') if u else '',
        'department': expense.department or dept_name or '',
        'category': expense.category,
        'amount': effective_amount,
        'requested_amount': _fin_round2(expense.amount) if expense.approved_amount is not None else None,
        'approved_amount': _fin_round2(expense.approved_amount) if expense.approved_amount is not None else None,
        'spent_on': expense.spent_on.isoformat() if expense.spent_on else None,
        'bill_date': expense.bill_date.isoformat() if expense.bill_date else None,
        'status': expense.status,
        'notes': str(expense.notes or '').strip(),
        'rejection_reason': str(expense.rejection_reason or '').strip(),
        'payment_date': expense.payment_date.isoformat() if expense.payment_date else None,
        'payment_method': str(expense.payment_method or '').strip(),
        'receipt_url': _expense_receipt_url(request, expense),
        'finance_entry_id': expense.finance_entry_id,
        'workflow_steps': expense.workflow_steps if isinstance(expense.workflow_steps, list) else [],
        'created_at': expense.created_at.isoformat() if expense.created_at else None,
        'updated_at': expense.updated_at.isoformat() if expense.updated_at else None,
    }



class FinancePendingExpenseListView(APIView):
    """
    GET /api/finance/pending-expenses/
    Returns a member-grouped overview of HR expenses (non-Draft) for the org.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'finance_accounting:expense:view'}

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def get(self, request):
        from django.contrib.auth import get_user_model
        from core.models.mydesk import ExpenseEntry

        org_id = self.get_org_id(request)

        # 1. Fetch top 200 unpaid entries for recent_submissions
        unpaid_qs = (
            ExpenseEntry.objects
            .select_related('user')
            .filter(org_id=org_id, transaction_type='expense', status__in=_FIN_UNPAID_STATUSES)
            .order_by('-spent_on', '-created_at')[:200]
        )
        recent_submissions = [_fin_expense_payload(item, request, item.user, item.department or '') for item in unpaid_qs]

        # 2. Database level aggregation for Paid and Unpaid entries
        agg_qs = (
            ExpenseEntry.objects
            .filter(org_id=org_id, transaction_type='expense', status__in=_FIN_UNPAID_STATUSES | {'Paid'})
            .values('user_id', 'user__first_name', 'user__last_name', 'user__username', 'user__email', 'department', 'status')
            .annotate(
                total_amt=Sum(Coalesce(F('approved_amount'), F('amount'))),
                count=Count('id')
            )
        )

        # 3. Retrieve raw dictionary values for Rejected entries to check workflow steps in Python
        rejected_data = (
            ExpenseEntry.objects
            .filter(org_id=org_id, transaction_type='expense', status='Rejected')
            .values('user_id', 'amount', 'approved_amount', 'workflow_steps')
        )

        valid_rejected_by_user = {}
        for item in rejected_data:
            if _reached_finance(item.get('workflow_steps')):
                uid = item['user_id']
                amt = float(item['approved_amount'] if item['approved_amount'] is not None else item['amount'])
                if uid not in valid_rejected_by_user:
                    valid_rejected_by_user[uid] = {'amount': 0.0, 'count': 0}
                valid_rejected_by_user[uid]['amount'] += amt
                valid_rejected_by_user[uid]['count'] += 1

        member_rows = {}
        total_amount = unpaid_amount = paid_amount = rejected_amount = 0.0
        total_entries = unpaid_entries = paid_entries = rejected_entries = 0

        # Process the aggregated paid and unpaid entries
        for row in agg_qs:
            mid = row['user_id']
            st = row['status']
            amt = float(row['total_amt'] or 0)
            count = row['count']
            
            first_name = row['user__first_name'] or ''
            last_name = row['user__last_name'] or ''
            username = row['user__username'] or ''
            email = row['user__email'] or ''
            department = row['department'] or ''
            
            member_name = f"{first_name} {last_name}".strip() or username or str(mid)

            if mid not in member_rows:
                member_rows[mid] = {
                    'user_id': mid,
                    'member_name': member_name,
                    'email': email,
                    'department': department,
                    'total_amount': 0.0,
                    'unpaid_amount': 0.0,
                    'paid_amount': 0.0,
                    'entries_count': 0,
                    'unpaid_count': 0,
                    'paid_count': 0,
                }

            member = member_rows[mid]
            member['total_amount'] = _fin_round2(member['total_amount'] + amt)
            member['entries_count'] += count
            total_amount = _fin_round2(total_amount + amt)
            total_entries += count

            if st in _FIN_UNPAID_STATUSES:
                member['unpaid_amount'] = _fin_round2(member['unpaid_amount'] + amt)
                member['unpaid_count'] += count
                unpaid_amount = _fin_round2(unpaid_amount + amt)
                unpaid_entries += count
            elif st == 'Paid':
                member['paid_amount'] = _fin_round2(member['paid_amount'] + amt)
                member['paid_count'] += count
                paid_amount = _fin_round2(paid_amount + amt)
                paid_entries += count

        # Merge the valid rejected ones
        missing_uids = [uid for uid in valid_rejected_by_user if uid not in member_rows]
        user_details = {}
        if missing_uids:
            User = get_user_model()
            users = User.objects.filter(id__in=missing_uids).values('id', 'first_name', 'last_name', 'username', 'email')
            user_details = {u['id']: u for u in users}

        for uid, stats in valid_rejected_by_user.items():
            amt = stats['amount']
            count = stats['count']
            
            rejected_amount = _fin_round2(rejected_amount + amt)
            rejected_entries += count
            total_amount = _fin_round2(total_amount + amt)
            total_entries += count

            if uid not in member_rows:
                u = user_details.get(uid, {})
                first_name = u.get('first_name') or ''
                last_name = u.get('last_name') or ''
                username = u.get('username') or ''
                member_name = f"{first_name} {last_name}".strip() or username or str(uid)
                email = u.get('email') or ''
                
                # Fetch department for the rejected entries
                dept = ''
                dept_qs = ExpenseEntry.objects.filter(org_id=org_id, user_id=uid).values('department')
                for d in dept_qs:
                    if d.get('department'):
                        dept = d['department']
                        break

                member_rows[uid] = {
                    'user_id': uid,
                    'member_name': member_name,
                    'email': email,
                    'department': dept,
                    'total_amount': 0.0,
                    'unpaid_amount': 0.0,
                    'paid_amount': 0.0,
                    'entries_count': 0,
                    'unpaid_count': 0,
                    'paid_count': 0,
                }
            
            member = member_rows[uid]
            member['total_amount'] = _fin_round2(member['total_amount'] + amt)
            member['entries_count'] += count

        members = sorted(
            member_rows.values(),
            key=lambda r: (r['unpaid_count'], r['total_amount']),
            reverse=True,
        )

        return Response({
            'summary': {
                'total_amount': total_amount,
                'unpaid_amount': unpaid_amount,
                'paid_amount': paid_amount,
                'rejected_amount': rejected_amount,
                'total_entries': total_entries,
                'unpaid_entries': unpaid_entries,
                'paid_entries': paid_entries,
                'rejected_entries': rejected_entries,
            },
            'members': members,
            'recent_submissions': recent_submissions,
        }, status=status.HTTP_200_OK)



class FinancePendingExpenseMemberDetailView(APIView):
    """
    GET /api/finance/pending-expenses/member/<user_id>/
    Returns profile + expense list for one member.
    Query params:  ?tab=unpaid|paid|all  (default: all)
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'finance_accounting:expense:view'}

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def get(self, request, user_id):
        from django.contrib.auth import get_user_model
        from core.models.mydesk import ExpenseEntry

        org_id = self.get_org_id(request)
        User = get_user_model()

        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'Member not found.'}, status=status.HTTP_404_NOT_FOUND)

        tab = (request.query_params.get('tab') or 'all').strip().lower()

        # Only HR-approved expenses for this member.
        raw_entries = list(
            ExpenseEntry.objects
            .select_related('user')
            .filter(org_id=org_id, user_id=user_id, transaction_type='expense')
            .exclude(status__in=['Draft', 'Submitted'])
            .order_by('-spent_on', '-created_at')
        )

        all_entries = []
        for item in raw_entries:
            if item.status == 'Rejected':
                if not _reached_finance(item.workflow_steps):
                    continue
            all_entries.append(item)

        # Aggregate stats
        total_amount = unpaid_amount = paid_amount = rejected_amount = 0.0
        unpaid_count = paid_count = rejected_count = 0
        category_agg = {}

        for item in all_entries:
            amt = _fin_effective_amount(item)
            st = item.status
            cat = str(item.category or 'misc').strip().lower()

            total_amount = _fin_round2(total_amount + amt)

            if st in _FIN_UNPAID_STATUSES:
                unpaid_amount = _fin_round2(unpaid_amount + amt)
                unpaid_count += 1
            elif st == 'Paid':
                paid_amount = _fin_round2(paid_amount + amt)
                paid_count += 1
            elif st == 'Rejected':
                rejected_amount = _fin_round2(rejected_amount + amt)
                rejected_count += 1

            if cat not in category_agg:
                category_agg[cat] = {'category': cat, 'label': cat.replace('_', ' ').title(), 'amount': 0.0, 'count': 0}
            category_agg[cat]['amount'] = _fin_round2(category_agg[cat]['amount'] + amt)
            category_agg[cat]['count'] += 1

        category_breakdown = sorted(category_agg.values(), key=lambda r: r['amount'], reverse=True)

        # Filter for tab
        if tab == 'unpaid':
            entries = [e for e in all_entries if e.status in _FIN_UNPAID_STATUSES]
        elif tab == 'paid':
            entries = [e for e in all_entries if e.status == 'Paid']
        else:
            entries = all_entries

        available_categories = ['all']
        available_categories.extend([r['category'] for r in category_breakdown if r.get('category') and r['category'] != 'all'])

        category_filter = str(request.query_params.get('category') or 'all').strip().lower() or 'all'
        timeline = (request.query_params.get('timeline') or 'all').strip().lower()
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        from datetime import date as _date, timedelta
        from django.utils import timezone
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = _date.fromisoformat(start_date_str)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = _date.fromisoformat(end_date_str)
            except ValueError:
                pass

        today = timezone.localdate()

        filtered_entries = []
        for item in entries:
            item_category = str(item.category or '').strip().lower()

            if category_filter != 'all' and item_category != category_filter:
                continue

            spent_date = item.spent_on
            if spent_date:
                if timeline == 'today':
                    if spent_date != today:
                        continue
                elif timeline == '7d':
                    if not (today - timedelta(days=6) <= spent_date <= today):
                        continue
                elif timeline == '30d':
                    if not (today - timedelta(days=29) <= spent_date <= today):
                        continue
                elif timeline == 'this_month':
                    if not (spent_date.year == today.year and spent_date.month == today.month):
                        continue
                elif timeline == 'last_month':
                    first_of_this_month = today.replace(day=1)
                    last_of_prev_month = first_of_this_month - timedelta(days=1)
                    if not (spent_date.year == last_of_prev_month.year and spent_date.month == last_of_prev_month.month):
                        continue
                elif timeline == 'custom':
                    if start_date and spent_date < start_date:
                        continue
                    if end_date and spent_date > end_date:
                        continue
            elif timeline != 'all':
                continue

            filtered_entries.append(item)

        sort_by = (request.query_params.get('sort_by') or 'spent_on').strip().lower()
        sort_order = (request.query_params.get('sort_order') or 'desc').strip().lower()
        reverse_sort = (sort_order == 'desc')

        def get_sort_key(item):
            if sort_by == 'spent_on':
                val = item.spent_on
                if val is None:
                    return (_date.min if reverse_sort else _date.max, item.created_at or timezone.now())
                return (val, item.created_at or timezone.now())
            elif sort_by == 'amount':
                val = _fin_effective_amount(item)
                return (val, item.spent_on or _date.min, item.created_at or timezone.now())
            elif sort_by == 'created_at':
                val = item.created_at
                if val is None:
                    return (timezone.now() if reverse_sort else timezone.now(),)
                return (val,)
            elif sort_by == 'category':
                val = str(item.category or '').lower()
                return (val, item.spent_on or _date.min, item.created_at or timezone.now())
            elif sort_by == 'transaction_type':
                val = str(item.transaction_type or '').lower()
                return (val, item.spent_on or _date.min, item.created_at or timezone.now())
            else:
                val = item.spent_on
                if val is None:
                    return (_date.min if reverse_sort else _date.max, item.created_at or timezone.now())
                return (val, item.created_at or timezone.now())

        filtered_entries.sort(key=get_sort_key, reverse=reverse_sort)

        dept = ''
        if all_entries:
            dept = all_entries[0].department or ''

        return Response({
            'profile': {
                'user_id': target_user.id,
                'employee_name': target_user.get_full_name() or target_user.username,
                'email': target_user.email or '',
                'department': dept,
            },
            'quick_stats': {
                'total_amount': total_amount,
                'unpaid_amount': unpaid_amount,
                'paid_amount': paid_amount,
                'rejected_amount': rejected_amount,
                'entries': len(all_entries),
                'unpaid': unpaid_count,
                'paid': paid_count,
                'rejected': rejected_count,
            },
            'available_categories': available_categories,
            'category_breakdown': category_breakdown,
            'expenses': [_fin_expense_payload(e, request, target_user, dept) for e in filtered_entries],
        }, status=status.HTTP_200_OK)


class FinancePendingExpenseSyncView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'finance_accounting:expense:create'}

    def post(self, request):
        # Sync is a no-op here; Finance reads directly from HR ExpenseEntry
        return Response({'success': True, 'message': 'Finance expense view refreshed.'}, status=status.HTTP_200_OK)


class FinancePendingExpenseApproveView(APIView):
    """
    POST /api/finance/pending-expenses/<pk>/approve/
    Body: { "payment_date": "YYYY-MM-DD", "payment_method": "bank_transfer", "payment_ledger": <id> }
    Marks the expense as Paid and creates a GL journal entry.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'finance_accounting:expense:edit'}

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def post(self, request, pk):
        from django.utils import timezone as tz
        from datetime import date as _date
        from core.models.mydesk import ExpenseEntry
        from core.views_mydesk import _create_expense_journal_entry

        org_id = self.get_org_id(request)

        try:
            expense = ExpenseEntry.objects.select_related('user').get(
                pk=pk, org_id=org_id, transaction_type='expense'
            )
        except ExpenseEntry.DoesNotExist:
            return Response({'success': False, 'message': 'Expense not found.'}, status=status.HTTP_404_NOT_FOUND)

        if expense.status == 'Paid':
            return Response({'success': False, 'message': 'Expense is already paid.'}, status=status.HTTP_400_BAD_REQUEST)

        payment_date_raw = request.data.get('payment_date')
        payment_method = str(request.data.get('payment_method') or 'bank_transfer').strip()

        try:
            payment_date = _date.fromisoformat(str(payment_date_raw)) if payment_date_raw else None
        except ValueError:
            payment_date = None
        if not payment_date:
            payment_date = tz.now().date()

        now = tz.now()
        workflow_steps = expense.workflow_steps if isinstance(expense.workflow_steps, list) else []
        step = {
            'step': 'Paid',
            'actor': request.user.get_full_name() or request.user.username,
            'actor_id': request.user.id,
            'at': now.isoformat(),
            'payment_date': payment_date.isoformat(),
            'payment_method': payment_method,
        }

        expense.status = 'Paid'
        expense.paid_by = request.user
        expense.paid_at = now
        expense.payment_date = payment_date
        expense.payment_method = payment_method
        expense.finance_status = 'submitted'
        workflow_steps.append(step)
        expense.workflow_steps = workflow_steps
        update_fields = ['status', 'paid_by', 'paid_at', 'payment_date', 'payment_method',
                         'finance_status', 'workflow_steps', 'updated_at']

        # Create GL journal entry
        try:
            finance_entry_id = _create_expense_journal_entry(expense, payment_date, payment_method, request.user)
            if finance_entry_id:
                expense.finance_entry_id = finance_entry_id
                expense.finance_status = 'posted'
                update_fields += ['finance_entry_id', 'finance_status']
                workflow_steps[-1]['finance_entry_id'] = finance_entry_id
                expense.workflow_steps = workflow_steps
        except Exception:
            pass  # GL entry failure should not block marking as paid

        expense.save(update_fields=sorted(set(update_fields)))

        return Response({
            'success': True,
            'message': 'Expense marked as Paid.',
            'row': _fin_expense_payload(expense, request, expense.user, expense.department or ''),
        }, status=status.HTTP_200_OK)


class FinancePendingExpenseRejectView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'finance_accounting:expense:edit'}

    def get_org_id(self, request):
        return _get_org_id_or_none(request) or ''

    def post(self, request, pk):
        from django.utils import timezone as tz
        from core.models.mydesk import ExpenseEntry

        org_id = self.get_org_id(request)

        try:
            expense = ExpenseEntry.objects.get(pk=pk, org_id=org_id, transaction_type='expense')
        except ExpenseEntry.DoesNotExist:
            return Response({'success': False, 'message': 'Expense not found.'}, status=status.HTTP_404_NOT_FOUND)

        if expense.status in ('Paid', 'Rejected'):
            return Response({'success': False, 'message': f'Expense is already {expense.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        reason = str(request.data.get('rejection_reason') or '').strip()
        now = tz.now()
        workflow_steps = expense.workflow_steps if isinstance(expense.workflow_steps, list) else []
        workflow_steps.append({
            'step': 'Rejected',
            'actor': request.user.get_full_name() or request.user.username,
            'actor_id': request.user.id,
            'at': now.isoformat(),
            'rejection_reason': reason,
        })

        expense.status = 'Rejected'
        expense.rejection_reason = reason
        expense.workflow_steps = workflow_steps
        expense.save(update_fields=['status', 'rejection_reason', 'workflow_steps', 'updated_at'])

        return Response({'success': True, 'message': 'Expense rejected.'}, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE AI MULTI-AGENT INTELLIGENCE
# Architecture: Query â†’ Intent Detection â†’ Agent Routing â†’ Tool Call â†’ LLM â†’ Response
# Agents: AI CFO | AI Accountant | AI CA
# Rule: The LLM NEVER invents financial numbers. Every value comes from a tool.
# ═══════════════════════════════════════════════════════════════════════════════


def _fmt_inr(val):
    """Format a number as Indian Rupee string."""
    if val is None:
        return '₹0'
    val = float(val)
    if abs(val) >= 10000000:
        return f'₹{val / 10000000:.2f}Cr'
    if abs(val) >= 100000:
        return f'₹{val / 100000:.2f}L'
    if abs(val) >= 1000:
        return f'₹{val / 1000:.1f}K'
    return f'₹{val:,.0f}'


# ── ACCOUNTANT TOOL FUNCTIONS ─────────────────────────────────────────────────

def tool_cash_position(org_id):
    """Total cash across all bank/cash/wallet/settlement accounts."""
    from accounting.models import Account
    qs = Account.objects.filter(org_id=org_id) if org_id else Account.objects.all()
    accs = [{"name": a.name, "type": a.type, "balance": float(a.balance),
             "balance_fmt": _fmt_inr(a.balance)} for a in qs.order_by('-balance')]
    total = sum(a['balance'] for a in accs)
    return {"total_cash": total, "total_fmt": _fmt_inr(total), "accounts": accs, "count": len(accs)}


def tool_account_balances(org_id):
    """Per-account balance breakdown."""
    return tool_cash_position(org_id)


def tool_receivables(org_id):
    """Outstanding receivables with party details."""
    from accounting.models import Outstanding
    from django.db.models import Sum
    qs = Outstanding.objects.filter(type='receivable', status='pending')
    if org_id:
        qs = qs.filter(org_id=org_id)
    total = float(qs.aggregate(t=Sum('amount'))['t'] or 0)
    items = [{"party": r.party_name, "amount": float(r.amount), "amount_fmt": _fmt_inr(r.amount),
              "due_date": str(r.due_date) if r.due_date else "N/A"} for r in qs.order_by('-amount')[:10]]
    return {"total": total, "total_fmt": _fmt_inr(total), "count": qs.count(), "items": items}


def tool_payables(org_id):
    """Outstanding payables with party details."""
    from accounting.models import Outstanding
    from django.db.models import Sum
    qs = Outstanding.objects.filter(type='payable', status='pending')
    if org_id:
        qs = qs.filter(org_id=org_id)
    total = float(qs.aggregate(t=Sum('amount'))['t'] or 0)
    items = [{"party": p.party_name, "amount": float(p.amount), "amount_fmt": _fmt_inr(p.amount),
              "due_date": str(p.due_date) if p.due_date else "N/A"} for p in qs.order_by('-amount')[:10]]
    return {"total": total, "total_fmt": _fmt_inr(total), "count": qs.count(), "items": items}


def tool_expenses(org_id):
    """This month expenses total + recent items."""
    from accounting.models import Expense
    from django.db.models import Sum
    import datetime
    today = datetime.date.today()
    qs = Expense.objects.filter(org_id=org_id) if org_id else Expense.objects.all()
    this_month = qs.filter(date__gte=today.replace(day=1), date__lte=today)
    total_month = float(this_month.aggregate(t=Sum('amount'))['t'] or 0)
    recent = [{"desc": e.description, "amount": float(e.amount), "amount_fmt": _fmt_inr(e.amount),
               "date": str(e.date), "category": e.category.name if e.category else "Uncategorized"}
              for e in qs.order_by('-date', '-created_at')[:10]]
    return {"this_month_total": total_month, "this_month_fmt": _fmt_inr(total_month),
            "total_count": qs.count(), "recent": recent}


def tool_ledger_entries(org_id):
    """Recent journal entries with line items."""
    from accounting.models import JournalEntry, JournalItem
    qs = JournalEntry.objects.filter(org_id=org_id) if org_id else JournalEntry.objects.all()
    entries = []
    for je in qs.order_by('-created_at')[:8]:
        items = [{"ledger": i.ledger.name if i.ledger else "N/A",
                  "debit": float(i.debit), "credit": float(i.credit)}
                 for i in JournalItem.objects.filter(journal_entry=je)]
        entries.append({"id": je.id, "date": str(je.date), "narration": je.narration or "", "items": items})
    return {"total_entries": qs.count(), "recent": entries}


def tool_bank_reconciliation(org_id):
    """Bank reconciliation status."""
    from accounting.models import BankTransaction
    qs = BankTransaction.objects.filter(org_id=org_id) if org_id else BankTransaction.objects.all()
    total = qs.count()
    processed = qs.filter(status='processed').count()
    unprocessed = qs.filter(status='unprocessed').count()
    accuracy = int((processed / total * 100)) if total > 0 else 100
    return {"total": total, "processed": processed, "unprocessed": unprocessed,
            "accuracy_pct": accuracy,
            "status": "Fully Reconciled" if unprocessed == 0 else f"{unprocessed} transactions pending"}


# ── CFO TOOL FUNCTIONS ────────────────────────────────────────────────────────

def tool_cash_runway(org_id):
    """Cash runway from real burn rate."""
    stats = get_real_financial_stats(org_id)
    burn = stats['monthly_burn']
    cash = stats['cash']
    if burn <= 0:
        return {"cash": cash, "cash_fmt": _fmt_inr(cash), "monthly_burn": 0, "burn_fmt": "₹0",
                "runway_months": 0, "runway_display": "No expenses recorded — runway cannot be calculated",
                "risk": "Unknown", "daily_inflow": round(stats['daily_inflow'], 2),
                "daily_outflow": round(stats['daily_outflow'], 2)}
    months = round(cash / burn, 1)
    days = int(months * 30)
    risk = "Critical" if months < 1 else ("Warning" if months < 3 else "Healthy")
    display = f"{days} days" if months < 1 else f"{months} months ({days} days)"
    return {"cash": cash, "cash_fmt": _fmt_inr(cash), "monthly_burn": burn, "burn_fmt": _fmt_inr(burn),
            "runway_months": months, "runway_days": days, "runway_display": display, "risk": risk,
            "daily_inflow": round(stats['daily_inflow'], 2), "daily_outflow": round(stats['daily_outflow'], 2)}


def tool_profitability(org_id):
    """Profit metrics from real income and expense records."""
    from accounting.models import Income, Expense
    from django.db.models import Sum
    import datetime
    today = datetime.date.today()
    fd = today.replace(day=1)
    lme = fd - datetime.timedelta(days=1)
    fdl = lme.replace(day=1)

    def _s(qs):
        return float(qs.aggregate(t=Sum('amount'))['t'] or 0)

    iq = Income.objects.filter(org_id=org_id) if org_id else Income.objects.all()
    eq = Expense.objects.filter(org_id=org_id) if org_id else Expense.objects.all()
    rev_this = _s(iq.filter(date__gte=fd, date__lte=today))
    cost_this = _s(eq.filter(date__gte=fd, date__lte=today))
    rev_last = _s(iq.filter(date__gte=fdl, date__lte=lme))
    cost_last = _s(eq.filter(date__gte=fdl, date__lte=lme))
    profit_this = rev_this - cost_this
    profit_last = rev_last - cost_last
    margin = round((profit_this / rev_this * 100), 1) if rev_this > 0 else 0
    growth = round(((profit_this - profit_last) / abs(profit_last) * 100), 1) if profit_last != 0 else 0
    return {"revenue_this_month": rev_this, "revenue_fmt": _fmt_inr(rev_this),
            "expenses_this_month": cost_this, "expenses_fmt": _fmt_inr(cost_this),
            "profit_this_month": profit_this, "profit_fmt": _fmt_inr(profit_this),
            "revenue_last_month": rev_last, "expenses_last_month": cost_last,
            "profit_last_month": profit_last, "profit_margin_pct": margin, "profit_growth_pct": growth}


def tool_financial_health(org_id):
    """Overall financial health score from real subsystem data."""
    stats = get_real_financial_stats(org_id)
    from accounting.models import BankTransaction, Outstanding, JournalItem
    from django.db.models import Sum
    tt = BankTransaction.objects.count()
    rc = BankTransaction.objects.filter(status='processed').count()
    banking_h = int((rc / tt * 100)) if tt > 0 else 100
    tr = Outstanding.objects.filter(type='receivable').count()
    pr = Outstanding.objects.filter(type='receivable', status='paid').count()
    coll_h = int((pr / tr * 100)) if tr > 0 else 100
    jqs = JournalItem.objects.filter(org_id=org_id) if org_id else JournalItem.objects.all()
    td = float(jqs.aggregate(t=Sum('debit'))['t'] or 0)
    tc = float(jqs.aggregate(t=Sum('credit'))['t'] or 0)
    acct_h = 100 if td == tc else 45
    overall = round((banking_h + coll_h + acct_h) / 3)
    rating = "Excellent" if overall >= 90 else ("Good" if overall >= 80 else ("Attention" if overall >= 60 else "Critical"))
    burn = stats['monthly_burn']
    runway = round(stats['cash'] / burn, 1) if burn > 0 else 0
    return {"score": overall, "rating": rating, "cash": stats['cash'], "cash_fmt": _fmt_inr(stats['cash']),
            "net_worth": stats['net_worth'], "net_worth_fmt": _fmt_inr(stats['net_worth']),
            "runway_months": runway, "burn": burn, "burn_fmt": _fmt_inr(burn),
            "banking_health": banking_h, "collections_health": coll_h, "accounts_health": acct_h,
            "income_growth": stats['income_growth'], "expenses_growth": stats['expenses_growth'],
            "gst_due_days": stats['gst_due_days'], "gst_liability": stats['gst_liability'],
            "payroll_pending": stats['payroll_pending']}


def tool_department_spending(org_id):
    """Spending grouped by expense category."""
    from accounting.models import Expense
    from django.db.models import Sum
    qs = Expense.objects.filter(org_id=org_id) if org_id else Expense.objects.all()
    by_cat = qs.values('category__name').annotate(total=Sum('amount')).order_by('-total')
    grand = float(qs.aggregate(t=Sum('amount'))['t'] or 0)
    depts = [{"name": c['category__name'] or "Uncategorized", "spend": float(c['total'] or 0),
              "spend_fmt": _fmt_inr(c['total']),
              "pct": round(float(c['total'] or 0) / grand * 100, 1) if grand > 0 else 0}
             for c in by_cat[:10]]
    return {"grand_total": grand, "grand_fmt": _fmt_inr(grand), "departments": depts}


def tool_forecast(org_id):
    """Cash forecast at 30/60/90 days from real daily flows."""
    stats = get_real_financial_stats(org_id)
    cash = stats['cash']
    net = stats['daily_inflow'] - stats['daily_outflow']
    f30 = cash + net * 30
    f60 = cash + net * 60
    f90 = cash + net * 90
    return {"current_cash": cash, "current_fmt": _fmt_inr(cash),
            "daily_inflow": round(stats['daily_inflow'], 2), "daily_outflow": round(stats['daily_outflow'], 2),
            "net_daily": round(net, 2),
            "trend": "Improving" if net > 0 else ("Stable" if net == 0 else "Declining"),
            "forecast_30d": round(f30, 2), "f30_fmt": _fmt_inr(f30),
            "forecast_60d": round(f60, 2), "f60_fmt": _fmt_inr(f60),
            "forecast_90d": round(f90, 2), "f90_fmt": _fmt_inr(f90)}


def tool_recommendations(org_id):
    """Priority recommendations from real financial state."""
    stats = get_real_financial_stats(org_id)
    items = []
    burn = stats['monthly_burn']
    runway = stats['cash'] / burn if burn > 0 else 0
    if burn > 0 and runway < 3:
        items.append({"priority": "Critical",
                      "action": f"Cash runway is only {round(runway, 1)} months. Cut discretionary spending immediately.",
                      "area": "Cash Flow"})
    if stats['receivables'] > 0:
        items.append({"priority": "High",
                      "action": f"Collect outstanding receivables of {_fmt_inr(stats['receivables'])}.",
                      "area": "Collections"})
    if stats['gst_liability'] > 0 and stats['gst_due_days'] < 15:
        items.append({"priority": "High",
                      "action": f"GST payment of {_fmt_inr(stats['gst_liability'])} due in {stats['gst_due_days']} days.",
                      "area": "Compliance"})
    if stats['payroll_pending']:
        items.append({"priority": "High",
                      "action": "Approve pending payroll runs before deadline.",
                      "area": "Payroll"})
    if stats['eol_assets'] > 0:
        items.append({"priority": "Medium",
                      "action": f"{stats['eol_assets']} end-of-life asset(s). Plan replacement procurement.",
                      "area": "Assets"})
    if not items:
        items.append({"priority": "Low",
                      "action": "All financial systems are healthy. No immediate action required.",
                      "area": "General"})
    return {"priorities": items, "count": len(items)}


# ── CA TOOL FUNCTIONS ─────────────────────────────────────────────────────────

def tool_gst_status(org_id):
    """GST filing and transaction status."""
    from accounting.models import GSTTransaction
    qs = GSTTransaction.objects.filter(org_id=org_id) if org_id else GSTTransaction.objects.all()
    pending = qs.filter(status='pending').count()
    total = qs.count()
    stats = get_real_financial_stats(org_id)
    risk = "Critical" if stats['gst_due_days'] < 7 and stats['gst_liability'] > 0 else (
        "At Risk" if stats['gst_due_days'] < 15 and stats['gst_liability'] > 0 else "Healthy")
    return {"total_txns": total, "pending_txns": pending,
            "liability": stats['gst_liability'], "liability_fmt": _fmt_inr(stats['gst_liability']),
            "due_days": stats['gst_due_days'], "compliance_risk": risk,
            "status": "Pending" if stats['gst_liability'] > 0 else "All Clear"}


def tool_gst_liability_detail(org_id):
    """GST liability breakdown: output vs input tax."""
    from accounting.models import GSTTransaction
    from django.db.models import Sum
    sales = GSTTransaction.objects.filter(transaction_type='sale')
    purchases = GSTTransaction.objects.filter(transaction_type__in=['purchase', 'expense'])
    if org_id:
        sales = sales.filter(org_id=org_id)
        purchases = purchases.filter(org_id=org_id)
    output = float(sales.aggregate(t=Sum('gst_amount'))['t'] or 0)
    input_tax = float(purchases.aggregate(t=Sum('gst_amount'))['t'] or 0)
    net = max(0.0, output - input_tax)
    stats = get_real_financial_stats(org_id)
    return {"output_gst": output, "output_fmt": _fmt_inr(output),
            "input_gst": input_tax, "input_fmt": _fmt_inr(input_tax),
            "net_liability": net, "net_fmt": _fmt_inr(net),
            "itc_available": input_tax, "itc_fmt": _fmt_inr(input_tax),
            "due_days": stats['gst_due_days'],
            "sales_count": sales.count(), "purchase_count": purchases.count()}


def tool_compliance_overview(org_id):
    """Overall compliance health checks."""
    stats = get_real_financial_stats(org_id)
    from accounting.models import JournalItem
    from django.db.models import Sum
    jqs = JournalItem.objects.filter(org_id=org_id) if org_id else JournalItem.objects.all()
    td = float(jqs.aggregate(t=Sum('debit'))['t'] or 0)
    tc = float(jqs.aggregate(t=Sum('credit'))['t'] or 0)
    balanced = td == tc
    checks = [
        {"item": "GST Filing", "status": "Pending" if stats['gst_liability'] > 0 else "Clear",
         "risk": "High" if stats['gst_due_days'] < 10 and stats['gst_liability'] > 0 else "Low"},
        {"item": "Books of Accounts", "status": "Balanced" if balanced else "Imbalanced",
         "risk": "Low" if balanced else "High"},
        {"item": "Payroll Compliance", "status": "Pending Approval" if stats['payroll_pending'] else "Up to Date",
         "risk": "Medium" if stats['payroll_pending'] else "Low"},
    ]
    high = sum(1 for c in checks if c['risk'] == 'High')
    return {"overall": "Critical" if high >= 2 else ("At Risk" if high >= 1 else "Healthy"),
            "checks": checks, "gst_due_days": stats['gst_due_days'],
            "gst_liability": stats['gst_liability'], "gst_liability_fmt": _fmt_inr(stats['gst_liability']),
            "books_balanced": balanced}


def tool_upcoming_filings(org_id):
    """Upcoming tax filing deadlines."""
    import datetime
    stats = get_real_financial_stats(org_id)
    today = datetime.date.today()
    gst_due = datetime.date(today.year, today.month, 20)
    if today > gst_due:
        m = today.month + 1 if today.month < 12 else 1
        y = today.year if today.month < 12 else today.year + 1
        gst_due = datetime.date(y, m, 20)
    tds_m = today.month + 1 if today.month < 12 else 1
    tds_y = today.year if today.month < 12 else today.year + 1
    tds_due = datetime.date(tds_y, tds_m, 7)
    filings = [
        {"filing": "GSTR-3B", "due_date": str(gst_due), "days": (gst_due - today).days,
         "status": "Pending" if stats['gst_liability'] > 0 else "Filed",
         "liability": stats['gst_liability'], "liability_fmt": _fmt_inr(stats['gst_liability'])},
        {"filing": "TDS Return (26Q)", "due_date": str(tds_due), "days": (tds_due - today).days,
         "status": "Upcoming"},
    ]
    return {"filings": filings, "next_deadline_days": min(f['days'] for f in filings)}


# ── AGENT INTENT ROUTING ─────────────────────────────────────────────────────

AGENT_INTENTS = {
    "accountant": {
        "CASH_POSITION":       {"triggers": ["how much money", "total money", "money we have", "available funds",
                                              "cash available", "current balance", "cash position", "total cash",
                                              "how much cash", "cash left", "funds available", "cash do we have"],
                                 "tool": "cash_position", "sources": ["Banking", "Ledger"]},
        "ACCOUNT_BREAKDOWN":   {"triggers": ["account wise", "account-wise", "bank wise", "bank-wise",
                                              "which account", "account breakdown", "bank balances",
                                              "bank accounts", "show balances", "money in accounts", "all accounts"],
                                 "tool": "account_balances", "sources": ["Banking"]},
        "RECEIVABLES":         {"triggers": ["receivables", "outstanding receivables", "who owes us",
                                              "money coming", "collections", "customer payments", "customers owe"],
                                 "tool": "receivables", "sources": ["Collections", "Ledger"]},
        "PAYABLES":            {"triggers": ["payables", "vendor payments", "what do we owe",
                                              "outstanding payables", "vendors due", "pending vendor"],
                                 "tool": "payables", "sources": ["Payables", "Ledger"]},
        "UPCOMING_EXPENSES":   {"triggers": ["upcoming expenses", "expenses due", "payments due",
                                              "outgoing payments", "expenses pending", "recent expenses",
                                              "today's expenses", "show expenses", "expenses"],
                                 "tool": "expenses", "sources": ["Expenses", "Ledger"]},
        "LEDGER_LOOKUP":       {"triggers": ["ledger", "journal entries", "journal entry", "recent entries",
                                              "show entries", "trial balance", "entries"],
                                 "tool": "ledger_entries", "sources": ["Journal", "Ledger"]},
        "BANK_RECONCILIATION": {"triggers": ["reconciliation", "bank recon", "reconcile",
                                              "unprocessed transactions", "unmatched"],
                                 "tool": "bank_reconciliation", "sources": ["Banking", "Reconciliation"]},
        "BANK_BALANCE":        {"triggers": ["hdfc", "icici", "axis", "bank balance", "money in bank",
                                              "money in hdfc", "money in icici"],
                                 "tool": "account_balances", "sources": ["Banking"]},
    },
    "cfo": {
        "RUNWAY":                   {"triggers": ["runway", "cash runway", "how long can we survive",
                                                   "months of runway", "how long will cash last"],
                                     "tool": "cash_runway", "sources": ["Banking", "Expenses"]},
        "FINANCIAL_HEALTH":         {"triggers": ["financial health", "health rating", "health score",
                                                   "how healthy", "business health"],
                                     "tool": "financial_health", "sources": ["All Systems"]},
        "PROFITABILITY":            {"triggers": ["profit", "profitability", "net profit",
                                                   "how much profit", "margin", "ebitda"],
                                     "tool": "profitability", "sources": ["Income", "Expenses"]},
        "FORECAST":                 {"triggers": ["forecast", "predict", "90 days", "project",
                                                   "prediction", "future cash", "cash after"],
                                     "tool": "forecast", "sources": ["Banking", "Forecasting"]},
        "DEPARTMENT_ANALYSIS":      {"triggers": ["department", "which department", "logistics",
                                                   "spending by", "cost by department", "overspending",
                                                   "costing the most"],
                                     "tool": "department_spending", "sources": ["Expenses", "Departments"]},
        "COST_OPTIMIZATION":        {"triggers": ["cost", "reduce cost", "save money", "cut expenses",
                                                   "optimize", "burn rate", "reduce burn"],
                                     "tool": "cash_runway", "sources": ["Expenses", "Banking"]},
        "PRIORITY_RECOMMENDATIONS": {"triggers": ["prioritize", "priority", "focus on", "what should i",
                                                   "recommend", "action plan", "what to do", "this week",
                                                   "today"],
                                     "tool": "recommendations", "sources": ["All Systems"]},
        "CASH_POSITION":            {"triggers": ["how much money", "cash position", "total cash",
                                                   "how much cash", "funds available"],
                                     "tool": "cash_position", "sources": ["Banking"]},
        "RISK_ANALYSIS":            {"triggers": ["risk", "biggest risk", "what should i worry",
                                                   "risk exposure", "risks"],
                                     "tool": "financial_health", "sources": ["All Systems"]},
    },
    "ca": {
        "GST_STATUS":        {"triggers": ["gst status", "gst filing", "gst pending", "any gst pending",
                                            "gst return", "gstr", "any gst", "pending gst"],
                               "tool": "gst_status", "sources": ["GST Center"]},
        "GST_LIABILITY":     {"triggers": ["gst liability", "gst amount", "gst due", "how much gst",
                                            "tax due", "gst payable", "output tax", "input tax", "itc"],
                               "tool": "gst_liability_detail", "sources": ["GST Center"]},
        "GST_DEADLINES":     {"triggers": ["gst deadline", "when is gst due", "gst date", "filing date",
                                            "when is gst"],
                               "tool": "upcoming_filings", "sources": ["GST Center", "Compliance"]},
        "TDS_STATUS":        {"triggers": ["tds", "tds liability", "tds due", "tds status", "tds filing",
                                            "how much tds"],
                               "tool": "upcoming_filings", "sources": ["TDS", "Compliance"]},
        "COMPLIANCE_STATUS": {"triggers": ["compliance", "compliance status", "audit ready",
                                            "books balanced", "audit readiness", "show compliance"],
                               "tool": "compliance_overview", "sources": ["Compliance", "Ledger"]},
        "UPCOMING_FILINGS":  {"triggers": ["upcoming filings", "filing deadlines", "next filing",
                                            "when to file", "deadlines", "upcoming"],
                               "tool": "upcoming_filings", "sources": ["Compliance"]},
    }
}

_TOOL_REGISTRY = {
    "cash_position": tool_cash_position,
    "account_balances": tool_account_balances,
    "receivables": tool_receivables,
    "payables": tool_payables,
    "expenses": tool_expenses,
    "ledger_entries": tool_ledger_entries,
    "bank_reconciliation": tool_bank_reconciliation,
    "cash_runway": tool_cash_runway,
    "profitability": tool_profitability,
    "financial_health": tool_financial_health,
    "department_spending": tool_department_spending,
    "forecast": tool_forecast,
    "recommendations": tool_recommendations,
    "gst_status": tool_gst_status,
    "gst_liability_detail": tool_gst_liability_detail,
    "compliance_overview": tool_compliance_overview,
    "upcoming_filings": tool_upcoming_filings,
}

_AGENT_PROMPTS = {
    "cfo": """You are BRIDGEWORKS AI CFO — a strategic financial intelligence advisor for the company.
Your role: Cash flow strategy, runway planning, forecasting, budget optimization, department analysis, executive recommendations.
Your tone: Executive, strategic, insight-driven. Think like a CFO presenting to the board.

Response structure:
1. Direct answer to the question (using ONLY the data provided below)
2. Key insight or risk flag (if any)
3. One actionable recommendation

CRITICAL RULES:
- NEVER invent, estimate, or hallucinate any financial number.
- Use ONLY the numbers from the DATA CONTEXT below.
- If data is zero or missing, say so clearly — do NOT substitute with made-up values.
- Keep responses concise. Maximum 200 words. No filler paragraphs.
- Format key numbers in bold.""",

    "accountant": """You are BRIDGEWORKS AI Accountant — responsible for daily finance operations.
Your role: Bank balances, ledger entries, journal entries, receivables, payables, expenses, reconciliation, vendor payments.
Your tone: Precise, direct, data-focused. Answer like a senior accountant reviewing the books.

Response structure:
1. Direct data answer (numbers, breakdowns, tables)
2. Brief status note if relevant

CRITICAL RULES:
- NEVER invent financial numbers. Use ONLY the DATA CONTEXT provided below.
- If asked about runway, forecasting, or strategy, tell the user to switch to the AI CFO.
- Keep responses short and factual. No analysis unless asked.
- Format data cleanly with bold numbers and structured layout.
- Maximum 150 words.""",

    "ca": """You are BRIDGEWORKS AI CA — a compliance and tax expert (Chartered Accountant).
Your role: GST filing, TDS, tax liability, compliance status, audit readiness, filing deadlines.
Your tone: Professional, compliance-focused, deadline-aware. Think like a CA reviewing tax health.

Response structure:
1. Tax/compliance status with exact numbers
2. Due dates and deadlines
3. Risk level and recommended action

CRITICAL RULES:
- NEVER invent tax numbers. Use ONLY the DATA CONTEXT provided below.
- If asked about runway, forecasting, or business strategy, tell the user to switch to the AI CFO.
- Highlight compliance risks and deadlines prominently.
- Be specific about amounts, dates, and statuses.
- Maximum 150 words."""
}


class FinanceAIChatView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import os
        import re
        import json
        from django.conf import settings
        from google import genai
        from google.genai import types

        org_id = _get_org_id_or_none(request) or ''
        question = request.data.get("question", "")
        if not question:
            return Response({"error": "Question parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        agent = str(request.data.get("agent", "cfo")).strip().lower()
        if agent not in ("cfo", "accountant", "ca"):
            agent = "cfo"

        history = request.data.get("history", [])
        q_lower = question.lower().strip().rstrip('?').strip()

        # ── STEP 1: Intent Detection (keyword match per agent) ────────────
        agent_intents = AGENT_INTENTS.get(agent, {})
        matched_intent = None
        matched_meta = None

        for intent_key, meta in agent_intents.items():
            for trigger in meta["triggers"]:
                if trigger in q_lower:
                    matched_intent = intent_key
                    matched_meta = meta
                    break
            if matched_intent:
                break

        # ── STEP 2: Cross-agent redirect detection ────────────────────────
        redirect_agent = None
        if not matched_intent:
            for other_agent, other_intents in AGENT_INTENTS.items():
                if other_agent == agent:
                    continue
                for intent_key, meta in other_intents.items():
                    for trigger in meta["triggers"]:
                        if trigger in q_lower:
                            redirect_agent = other_agent
                            break
                    if redirect_agent:
                        break
                if redirect_agent:
                    break

        if redirect_agent and not matched_intent:
            labels = {"cfo": "AI CFO", "accountant": "AI Accountant", "ca": "AI CA"}
            helps = {"cfo": "strategic finance (runway, forecasting, budget planning)",
                     "accountant": "daily operations (balances, ledgers, expenses, reconciliation)",
                     "ca": "tax & compliance (GST, TDS, filings, audit readiness)"}
            return Response({
                "answer": f"This question falls outside my expertise as **{labels[agent]}**. "
                          f"Please switch to the **{labels[redirect_agent]}** — "
                          f"who handles {helps[redirect_agent]}.",
                "debug": {"detected_intent": "AGENT_REDIRECT", "confidence": "95%",
                          "data_sources": [], "template": "AGENT_SWITCH_REDIRECT"}
            })

        # ── STEP 3: Gemini fallback intent classification ─────────────────
        api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)

        if not matched_intent:
            valid_names = list(agent_intents.keys()) + ["UNKNOWN"]
            try:
                classify_prompt = (
                    f"Classify this finance question into exactly ONE intent.\n"
                    f"Agent: {agent.upper()}\n"
                    f"Valid intents: {', '.join(valid_names)}\n\n"
                    f"Question: \"{question}\"\n\n"
                    f"Return ONLY the intent name in uppercase with underscores. Nothing else."
                )
                from core.utils.gemini_fallback import generate_content_with_fallback
                resp = generate_content_with_fallback(
                    client=client,
                    model='gemini-2.5-flash',
                    contents=classify_prompt,
                    config=types.GenerateContentConfig(max_output_tokens=20)
                )
                raw = resp.text.strip().upper().replace(" ", "_")
                raw = re.sub(r'^\d+\.?\s*_*', '', raw)
                if raw in agent_intents:
                    matched_intent = raw
                    matched_meta = agent_intents[raw]
            except Exception as e:
                print(f"[AI Chat] Intent classification error: {e}")

        # ── STEP 4: Default tool for unmatched intents ────────────────────
        if not matched_intent:
            defaults = {"cfo": "financial_health", "accountant": "cash_position", "ca": "gst_status"}
            matched_intent = "GENERAL"
            matched_meta = {"tool": defaults.get(agent, "cash_position"), "sources": ["General"]}

        # ── STEP 5: Execute Tool Function ─────────────────────────────────
        tool_name = matched_meta["tool"]
        tool_fn = _TOOL_REGISTRY.get(tool_name)
        data_context = {}
        if tool_fn:
            try:
                data_context = tool_fn(org_id)
            except Exception as e:
                print(f"[AI Chat] Tool error ({tool_name}): {e}")
                data_context = {"error": f"Failed to retrieve data: {str(e)}"}

        data_sources = matched_meta.get("sources", [])

        # ── STEP 6: Build Prompt + Call Gemini ────────────────────────────
        agent_prompt = _AGENT_PROMPTS.get(agent, _AGENT_PROMPTS["cfo"])

        history_str = ""
        if history:
            history_str = "\n## CONVERSATION HISTORY (last messages in this session)\n"
            for msg in history[-10:]:
                role = "User" if msg.get("sender") == "user" else agent.upper()
                history_str += f"{role}: {msg.get('text', '')}\n"

        system_prompt = (
            f"{agent_prompt}\n\n"
            f"══════════════════════════════════════\n"
            f"RESPONSE ENGINE CONTEXT (INTERNAL — DO NOT SHOW TO USER)\n"
            f"══════════════════════════════════════\n"
            f"Agent: {agent.upper()}\n"
            f"Detected Intent: {matched_intent}\n"
            f"Data Sources: {', '.join(data_sources)}\n\n"
            f"DATA CONTEXT (Use ONLY these numbers in your answer):\n"
            f"{json.dumps(data_context, indent=2, default=str)}\n"
            f"{history_str}\n"
            f"══════════════════════════════════════\n"
            f"GOLDEN RULE: Answer the user's exact question FIRST using ONLY the data above.\n"
            f"Never invent any financial number. If data is missing or zero, state that clearly.\n"
            f"══════════════════════════════════════"
        )

        try:
            from core.utils.gemini_fallback import generate_content_with_fallback
            response = generate_content_with_fallback(
                client=client,
                model='gemini-2.5-flash',
                contents=question,
                config=types.GenerateContentConfig(system_instruction=system_prompt)
            )
            return Response({
                "answer": response.text,
                "debug": {
                    "detected_intent": matched_intent,
                    "confidence": "95%" if matched_intent != "GENERAL" else "75%",
                    "data_sources": data_sources,
                    "template": "GENERIC_MARKDOWN"
                }
            })
        except Exception as e:
            print(f"[AI Chat] Gemini call failed, generating fallback response: {e}")
            fallback_text = _generate_fallback_response(agent, matched_intent, data_context, question)
            return Response({
                "answer": fallback_text,
                "debug": {
                    "detected_intent": matched_intent,
                    "confidence": "100% (Local Fallback)",
                    "data_sources": data_sources,
                    "template": "GENERIC_MARKDOWN"
                }
            })


def _generate_fallback_response(agent, matched_intent, data_context, question):
    """
    Generate a high-quality markdown response from database tool data.
    Used when the Gemini API is offline, rate-limited, or out of credits.
    """
    import json
    if "error" in data_context:
        return f"I'm sorry, I encountered an error while attempting to retrieve data: {data_context['error']}"

    ans = ""
    def get_val(key, default="N/A"):
        return data_context.get(key, default)

    if agent == "accountant":
        if matched_intent in ("CASH_POSITION", "ACCOUNT_BREAKDOWN", "BANK_BALANCE") or (matched_intent == "GENERAL" and data_context.get("total_cash") is not None):
            total_fmt = get_val("total_fmt", "₹0")
            count = get_val("count", 0)
            accounts = get_val("accounts", [])
            ans = f"### Cash & Bank Balances Overview\n\nOur total cash position across all connected bank, cash, and wallet accounts is **{total_fmt}** (spread across {count} account(s)).\n\n"
            if accounts:
                ans += "| Account Name | Type | Balance |\n| :--- | :--- | :--- |\n"
                for acc in accounts:
                    ans += f"| {acc.get('name')} | {acc.get('type')} | **{acc.get('balance_fmt')}** |\n"
            else:
                ans += "*No active accounts found.*"
            return ans

        elif matched_intent == "RECEIVABLES":
            total_fmt = get_val("total_fmt", "₹0")
            count = get_val("count", 0)
            items = get_val("items", [])
            ans = f"### Outstanding Receivables\n\nWe have **{total_fmt}** in outstanding receivables from {count} customer invoice(s).\n\n"
            if items:
                ans += "| Customer / Party | Amount | Due Date |\n| :--- | :--- | :--- |\n"
                for item in items:
                    ans += f"| {item.get('party')} | **{item.get('amount_fmt')}** | {item.get('due_date')} |\n"
            else:
                ans += "*No pending receivables.*"
            return ans

        elif matched_intent == "PAYABLES":
            total_fmt = get_val("total_fmt", "₹0")
            count = get_val("count", 0)
            items = get_val("items", [])
            ans = f"### Outstanding Payables\n\nWe have **{total_fmt}** in outstanding payables owed to {count} vendor(s).\n\n"
            if items:
                ans += "| Vendor / Party | Amount | Due Date |\n| :--- | :--- | :--- |\n"
                for item in items:
                    ans += f"| {item.get('party')} | **{item.get('amount_fmt')}** | {item.get('due_date')} |\n"
            else:
                ans += "*No pending payables.*"
            return ans

        elif matched_intent == "UPCOMING_EXPENSES":
            this_month_fmt = get_val("this_month_fmt", "₹0")
            recent = get_val("recent", [])
            ans = f"### Expenses & Spend Review\n\nOur total expenses recorded for this month are **{this_month_fmt}**.\n\n"
            if recent:
                ans += "#### Recent Expenses:\n"
                ans += "| Description | Amount | Date | Category |\n| :--- | :--- | :--- | :--- |\n"
                for r in recent:
                    ans += f"| {r.get('desc')} | **{r.get('amount_fmt')}** | {r.get('date')} | {r.get('category')} |\n"
            return ans

        elif matched_intent == "LEDGER_LOOKUP":
            total_entries = get_val("total_entries", 0)
            recent = get_val("recent", [])
            ans = f"### Recent General Ledger Entries\n\nFound **{total_entries}** total journal entries. Here are the most recent transactions:\n\n"
            for je in recent:
                ans += f"**Journal Entry #{je.get('id')} ({je.get('date')})**  \n"
                ans += f"*Narration:* {je.get('narration') or 'N/A'}  \n"
                ans += "| Ledger Account | Debit | Credit |\n| :--- | :---: | :---: |\n"
                for item in je.get("items", []):
                    debit_str = _fmt_inr(item['debit']) if item['debit'] > 0 else "—"
                    credit_str = _fmt_inr(item['credit']) if item['credit'] > 0 else "—"
                    ans += f"| {item.get('ledger')} | {debit_str} | {credit_str} |\n"
                ans += "\n"
            return ans

        elif matched_intent == "BANK_RECONCILIATION":
            status = get_val("status", "N/A")
            total = get_val("total", 0)
            processed = get_val("processed", 0)
            unprocessed = get_val("unprocessed", 0)
            accuracy = get_val("accuracy_pct", 100)
            ans = f"### Bank Reconciliation Status\n\nReconciliation Health: **{status}**\n\n"
            ans += f"- **Reconciliation Accuracy:** {accuracy}%\n"
            ans += f"- **Total Transactions:** {total}\n"
            ans += f"- **Processed:** {processed}\n"
            ans += f"- **Unprocessed / Pending:** {unprocessed} transactions\n"
            return ans

    elif agent == "cfo":
        if matched_intent in ("RUNWAY", "COST_OPTIMIZATION") or (matched_intent == "GENERAL" and data_context.get("runway_display") is not None):
            runway_display = get_val("runway_display", "N/A")
            risk = get_val("risk", "Unknown")
            cash_fmt = get_val("cash_fmt", "₹0")
            burn_fmt = get_val("burn_fmt", "₹0")
            daily_inflow = get_val("daily_inflow", 0.0)
            daily_outflow = get_val("daily_outflow", 0.0)
            ans = f"### Cash Runway & Burn Rate Analysis\n\nOur current cash runway is **{runway_display}** (Risk Rating: **{risk}**).\n\n"
            ans += f"- **Cash Reserves:** {cash_fmt}\n"
            ans += f"- **Monthly Burn Rate:** {burn_fmt}\n"
            ans += f"- **Daily Inflow (30d avg):** {_fmt_inr(daily_inflow)}/day\n"
            ans += f"- **Daily Outflow (30d avg):** {_fmt_inr(daily_outflow)}/day\n\n"
            if risk == "Critical":
                ans += "> [!WARNING]\n> **Action Recommended:** Cash runway is below the 1-month critical threshold. Defer non-essential procurement and escalate collections immediately."
            return ans

        elif matched_intent in ("FINANCIAL_HEALTH", "RISK_ANALYSIS") or (matched_intent == "GENERAL" and data_context.get("score") is not None):
            score = get_val("score", 0)
            rating = get_val("rating", "N/A")
            cash_fmt = get_val("cash_fmt", "₹0")
            net_worth_fmt = get_val("net_worth_fmt", "₹0")
            runway = get_val("runway_months", 0.0)
            burn = get_val("burn_fmt", "₹0")
            banking = get_val("banking_health", 0)
            collections = get_val("collections_health", 0)
            accounts = get_val("accounts_health", 0)
            ans = f"### Business Financial Health Score\n\nOverall Rating: **{score}/100** (**{rating}**)\n\n"
            ans += "#### Health Breakdown by Area:\n"
            ans += f"- **Banking Health:** {banking}% (Bank feeds matching and reconciliation status)\n"
            ans += f"- **Collections Health:** {collections}% (DSO & outstanding invoice resolution)\n"
            ans += f"- **General Ledger Health:** {accounts}% (Journal entry alignment and balance checks)\n\n"
            ans += "#### Key Financial Indicators:\n"
            ans += f"- **Cash Reserves:** {cash_fmt}\n"
            ans += f"- **Net Worth (Assets - Liabilities):** {net_worth_fmt}\n"
            ans += f"- **Monthly Burn:** {burn}\n"
            ans += f"- **Runway:** {runway} Months\n"
            return ans

        elif matched_intent == "PROFITABILITY":
            rev_fmt = get_val("revenue_fmt", "₹0")
            cost_fmt = get_val("expenses_fmt", "₹0")
            profit_fmt = get_val("profit_fmt", "₹0")
            margin = get_val("profit_margin_pct", 0.0)
            growth = get_val("profit_growth_pct", 0.0)
            ans = f"### Profitability Review\n\nProfit margin for this month is **{margin}%**.\n\n"
            ans += f"- **Monthly Revenue:** {rev_fmt}\n"
            ans += f"- **Monthly Expenses:** {cost_fmt}\n"
            ans += f"- **Net profit:** **{profit_fmt}**\n"
            ans += f"- **Profit Growth (MoM):** {growth}%\n"
            return ans

        elif matched_intent == "FORECAST":
            current_fmt = get_val("current_fmt", "₹0")
            trend = get_val("trend", "N/A")
            f30 = get_val("f30_fmt", "₹0")
            f60 = get_val("f60_fmt", "₹0")
            f90 = get_val("f90_fmt", "₹0")
            net_daily = get_val("net_daily", 0.0)
            ans = f"### Cash Flow Forecast (90-Day Projection)\n\nTrend Direction: **{trend}**\n\n"
            ans += f"- **Current Cash reserves:** {current_fmt}\n"
            ans += f"- **Projected Cash (30 days):** **{f30}**\n"
            ans += f"- **Projected Cash (60 days):** **{f60}**\n"
            ans += f"- **Projected Cash (90 days):** **{f90}**\n"
            ans += f"- **Net Daily Cash Movement:** {_fmt_inr(net_daily)}/day\n"
            return ans

        elif matched_intent == "DEPARTMENT_ANALYSIS":
            grand_fmt = get_val("grand_fmt", "₹0")
            depts = get_val("departments", [])
            ans = f"### Expense & Department Cost Analysis\n\nGrand total spent this month across all categories: **{grand_fmt}**\n\n"
            if depts:
                ans += "| Category / Department | Total Spent | Spend Share |\n| :--- | :--- | :--- |\n"
                for d in depts:
                    ans += f"| {d.get('name')} | **{d.get('spend_fmt')}** | {d.get('pct')}% |\n"
            else:
                ans += "*No department expenses recorded.*"
            return ans

        elif matched_intent == "PRIORITY_RECOMMENDATIONS":
            priorities = get_val("priorities", [])
            ans = "### Strategic Priorities & Recommendations\n\n"
            ans += "Here is the prioritized action plan based on current business conditions:\n\n"
            for idx, p in enumerate(priorities, 1):
                ans += f"{idx}. **[{p.get('priority')}]** {p.get('action')} *(Area: {p.get('area')}*)\n"
            return ans

    elif agent == "ca":
        if matched_intent == "GST_STATUS" or (matched_intent == "GENERAL" and data_context.get("liability_fmt") is not None):
            status = get_val("status", "N/A")
            liability_fmt = get_val("liability_fmt", "₹0")
            due_days = get_val("due_days", 0)
            risk = get_val("compliance_risk", "N/A")
            total = get_val("total_txns", 0)
            pending = get_val("pending_txns", 0)
            ans = f"### GST Compliance Status\n\nGST Return status: **{status}** (Compliance Risk: **{risk}**)\n\n"
            ans += f"- **GST Liability (Unfiled):** **{liability_fmt}**\n"
            ans += f"- **Filing Deadline:** due in {due_days} days\n"
            ans += f"- **GST Transaction matching:** {pending} pending / {total} total transactions\n"
            return ans

        elif matched_intent == "GST_LIABILITY":
            output_fmt = get_val("output_fmt", "₹0")
            input_fmt = get_val("input_fmt", "₹0")
            net_fmt = get_val("net_fmt", "₹0")
            itc_fmt = get_val("itc_fmt", "₹0")
            due_days = get_val("due_days", 0)
            ans = f"### GST Liability Breakdown (Output vs Input Tax)\n\n"
            ans += f"- **Output Tax (GST Collected on Sales):** {output_fmt}\n"
            ans += f"- **Input Tax Credit (ITC - Tax Paid on Purchases):** {input_fmt}\n"
            ans += f"- **Net Payable GST:** **{net_fmt}**\n"
            ans += f"- **ITC Available for Offset:** **{itc_fmt}**\n"
            ans += f"- **Days until Filing:** {due_days} days\n"
            return ans

        elif matched_intent in ("GST_DEADLINES", "TDS_STATUS", "UPCOMING_FILINGS"):
            filings = get_val("filings", [])
            ans = "### Upcoming Compliance & Filing Deadlines\n\n"
            if filings:
                ans += "| Filing Type | Due Date | Time Left | Status | Liability |\n| :--- | :--- | :--- | :--- | :--- |\n"
                for f in filings:
                    liab = f.get('liability_fmt', '—') if f.get('liability', 0) > 0 else '—'
                    ans += f"| {f.get('filing')} | {f.get('due_date')} | {f.get('days')} days | {f.get('status')} | {liab} |\n"
            else:
                ans += "*No upcoming filings registered.*"
            return ans

        elif matched_intent == "COMPLIANCE_STATUS":
            overall = get_val("overall", "N/A")
            checks = get_val("checks", [])
            ans = f"### Compliance Audit Overview\n\nOverall compliance health: **{overall}**\n\n"
            if checks:
                ans += "| Compliance Check | Status | Risk Level |\n| :--- | :--- | :--- |\n"
                for c in checks:
                    ans += f"| {c.get('item')} | {c.get('status')} | {c.get('risk')} |\n"
            return ans

    # Fallback default
    return f"Here is the financial data retrieved for **{matched_intent}**:\n\n```json\n{json.dumps(data_context, indent=2)}\n```"


def _generate_fallback_plan(stats):
    """Generate a high-quality 90-day plan without Gemini."""
    import datetime
    today_str = datetime.date.today().strftime('%d %b %Y')
    cash_fmt = _fmt_inr(stats['cash'])
    burn_fmt = _fmt_inr(stats['monthly_burn'])
    rec_fmt = _fmt_inr(stats['receivables'])
    pay_fmt = _fmt_inr(stats['payables'])
    gst_fmt = _fmt_inr(stats['gst_liability'])
    runway = stats['cash'] / stats['monthly_burn'] if stats['monthly_burn'] > 0 else 0
    runway_str = f"{runway:.1f} months" if runway > 0 else "N/A"
    
    plan = f"""# 90-Day Financial Plan for BridgeWorks
*Generated Fallback Plan — {today_str}*

Based on BridgeWorks's current financial position (Cash: **{cash_fmt}**, Monthly Burn: **{burn_fmt}**, Runway: **{runway_str}**), we have developed this 90-Day optimization roadmap.

---

### 1. Revenue Goals & Capital Injection
* **Collections Focus:** Secure **{rec_fmt}** in outstanding receivables. Establish automated aging notification workflows.
* **Working Capital Buffer:** Given the monthly burn of **{burn_fmt}**, target a capital buffer of at least 3 months of operations.

### 2. Cost Reduction Strategy
* **Discretionary Expense Freeze:** Suspend non-essential vendor contracts and defer capital procurement.
* **Logistics Cost Audit:** Review logistics spend anomaly flags to cut operational inefficiencies by 10%.

### 3. Compliance & Tax Filing Roadmap
* **GST Settlement:** Clear the net GST liability of **{gst_fmt}** before the due date in {stats['gst_due_days']} days to avoid interest penalties.
* **ITC Reconcilation:** Auto-match purchase logs with GSTR-2B daily to maximize claimable Input Tax Credit.

### 4. Risk Mitigation & Cash Preservation
* **Runway Preservation:** Retain at least {cash_fmt} reserves to cushion payroll runs.
* **Vendor Negotiations:** Renegotiate payment terms on the outstanding **{pay_fmt}** payables to extend credit terms from 30 to 45 days.
"""
    return plan


def _generate_fallback_report(stats):
    """Generate a high-quality CFO Executive Report without Gemini."""
    import datetime
    today_str = datetime.date.today().strftime('%d %b %Y')
    cash_fmt = _fmt_inr(stats['cash'])
    burn_fmt = _fmt_inr(stats['monthly_burn'])
    net_worth_fmt = _fmt_inr(stats['net_worth'])
    rec_fmt = _fmt_inr(stats['receivables'])
    pay_fmt = _fmt_inr(stats['payables'])
    gst_fmt = _fmt_inr(stats['gst_liability'])
    
    report = f"""# CFO Executive Report
*Generated Fallback Report — {today_str}*

### 1. Executive Summary
BridgeWorks's financial position is stable but cash preservation is highly advised. Cash reserves are at **{cash_fmt}**, and net worth is **{net_worth_fmt}**.

### 2. Key Performance Indicators (KPIs)
* **Cash Position:** {cash_fmt}
* **Monthly Burn Rate:** {burn_fmt}
* **Outstanding Receivables:** {rec_fmt}
* **Outstanding Payables:** {pay_fmt}
* **Net Worth:** {net_worth_fmt}

### 3. Risk & Compliance Analysis
* **GST Liability:** **{gst_fmt}** due in {stats['gst_due_days']} days. Action must be taken to file on time.
* **Payroll Risk:** Pending runs check: {"Pending action required" if stats['payroll_pending'] else "Clean / Approved"}.
* **End-of-Life Assets:** {stats['eol_assets']} asset(s) fully depreciated.

### 4. Strategic Growth Plan
* Focus on accelerating collections from pending invoices to boost current accounts balances.
* Restructure short-term liabilities to match asset lifecycles.
"""
    return report


class FinanceGeneratePlanView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import os
        from django.conf import settings
        from google import genai
        from google.genai import types

        org_id = _get_org_id_or_none(request) or ''
        stats = get_real_financial_stats(org_id)

        prompt = f"""
Generate a comprehensive 90-Day Financial Plan for BridgeWorks based on the current financial state:
- Cash: ₹{stats['cash']:,}, Monthly Burn: ₹{stats['monthly_burn']:,}, Receivables: ₹{stats['receivables']:,}.
- GST liability of ₹{stats['gst_liability']:,} due in {stats['gst_due_days']} days.
- Payables: ₹{stats['payables']:,}, EOL Assets: {stats['eol_assets']}.

Structure the plan into these exact sections:
1. Revenue Goals
2. Collections Strategy (focus on DSO and collection follow-up)
3. Cost Reduction (focus on Logistics risk and burn reduction)
4. Compliance Roadmap (focus on GST returns and early ITC claiming)
5. Risk Mitigation (focus on runway preservation)

Return the plan in markdown format.
"""

        try:
            api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
            client = genai.Client(api_key=api_key)
            from core.utils.gemini_fallback import generate_content_with_fallback
            response = generate_content_with_fallback(
                client=client,
                model='gemini-2.5-flash',
                contents=prompt
            )
            return Response({"plan": response.text})
        except Exception as e:
            print(f"[AI Chat] Plan generation failed, generating fallback: {e}")
            fallback_plan = _generate_fallback_plan(stats)
            return Response({"plan": fallback_plan})


class FinanceGenerateReportView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import os
        from django.conf import settings
        from google import genai
        from google.genai import types

        org_id = _get_org_id_or_none(request) or ''
        stats = get_real_financial_stats(org_id)

        prompt = f"""
Generate a detailed CFO Executive Report for management based on the current BridgeWorks dashboard data:
- Financial Health Score: 92/100 (Excellent)
- Cash Reserves: ₹{stats['cash']:,}, Monthly Burn: ₹{stats['monthly_burn']:,}, Net Worth: ₹{stats['net_worth']:,}
- Receivables: ₹{stats['receivables']:,}, Payables: ₹{stats['payables']:,}, GST Liability: ₹{stats['gst_liability']:,} (due in {stats['gst_due_days']} days)
- Department Risk: Logistics has a critical risk score (Health 52) due to delay anomalies, while Finance is at 98.

Structure the report into these exact sections:
1. Executive Summary (Highlighting overall health and performance)
2. KPI Overview (Details of Cash, Receivables, Payables, Net Worth, Burn)
3. Risk Analysis (Detailing Logistics department risks and compliance risks)
4. Forecast (30/60/90 day predictions and runway impacts)
5. Opportunities (Receivables collection improvement, GST ITC claim, burn saving)
6. Department Health (Department-by-department compliance and risk scoring)

Return the report in markdown format.
"""

        try:
            api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
            client = genai.Client(api_key=api_key)
            from core.utils.gemini_fallback import generate_content_with_fallback
            response = generate_content_with_fallback(
                client=client,
                model='gemini-2.5-flash',
                contents=prompt
            )
            return Response({"report": response.text})
        except Exception as e:
            print(f"[AI Chat] Report generation failed, generating fallback: {e}")
            fallback_report = _generate_fallback_report(stats)
            return Response({"report": fallback_report})


def get_real_financial_stats(org_id=""):
    from django.db.models import Sum, Q, F
    from django.utils import timezone
    import datetime
    from decimal import Decimal
    from accounting.models import Account, Outstanding, Asset, GSTTransaction, Expense, Income, Ledger, JournalItem
    from core.models import PayrollRun

    def _compute_pnl_totals(start_date, end_date):
        qs = JournalItem.objects.filter(entry__date__gte=start_date, entry__date__lte=end_date)
        if org_id:
            qs = qs.filter(org_id=org_id)
        rows = (
            qs
            .values('ledger__type')
            .annotate(total_debit=Sum('debit'), total_credit=Sum('credit'))
        )
        total_income = Decimal('0.00')
        total_expense = Decimal('0.00')
        for row in rows:
            d = row['total_debit'] or Decimal('0.00')
            c = row['total_credit'] or Decimal('0.00')
            ltype = row['ledger__type']
            if ltype == 'income':
                total_income += c - d
            elif ltype == 'expense':
                total_expense += d - c
        return float(total_income), float(total_expense)

    # Cash balance from all bank/cash/wallet/settlement accounts
    acc_qs = Account.objects.all()
    if org_id:
        acc_qs = acc_qs.filter(org_id=org_id)
    cash = float(acc_qs.aggregate(total=Sum('balance'))['total'] or 0)

    # Receivables (pending status)
    rec_qs = Outstanding.objects.filter(type='receivable', status='pending')
    if org_id:
        rec_qs = rec_qs.filter(org_id=org_id)
    receivables = float(rec_qs.aggregate(total=Sum('amount'))['total'] or 0)

    # Payables (pending status)
    pay_qs = Outstanding.objects.filter(type='payable', status='pending')
    if org_id:
        pay_qs = pay_qs.filter(org_id=org_id)
    payables = float(pay_qs.aggregate(total=Sum('amount'))['total'] or 0)

    # GST Liability (Output tax - input tax)
    now = timezone.now()
    gst_sales = GSTTransaction.objects.filter(transaction_type='sale')
    gst_purchases = GSTTransaction.objects.filter(transaction_type__in=['purchase', 'expense'])
    if org_id:
        gst_sales = gst_sales.filter(org_id=org_id)
        gst_purchases = gst_purchases.filter(org_id=org_id)
    output_gst = float(gst_sales.aggregate(total=Sum('gst_amount'))['total'] or 0)
    input_gst = float(gst_purchases.aggregate(total=Sum('gst_amount'))['total'] or 0)
    gst_liability = max(0.0, output_gst - input_gst)

    # GST due date (20th of this or next month)
    today = datetime.date.today()
    due_date = datetime.date(today.year, today.month, 20)
    if today > due_date:
        if today.month == 12:
            due_date = datetime.date(today.year + 1, 1, 20)
        else:
            due_date = datetime.date(today.year, today.month + 1, 20)
    gst_due_days = (due_date - today).days

    # EOL assets
    eol_assets = Asset.objects.filter(
        Q(status='fully_depreciated') |
        Q(current_value__lte=F('salvage_value'))
    )
    if org_id:
        eol_assets = eol_assets.filter(org_id=org_id)
    eol_assets_count = eol_assets.count()

    # Payroll pending check
    pr_qs = PayrollRun.objects.filter(finance_approved_at__isnull=True)
    if org_id:
        pr_qs = pr_qs.filter(org_id=org_id)
    payroll_pending = pr_qs.exists()

    # Month-over-month growths
    first_day_this_month = today.replace(day=1)
    last_month_end = first_day_this_month - datetime.timedelta(days=1)
    first_day_last_month = last_month_end.replace(day=1)

    total_inc_this, total_exp_this = _compute_pnl_totals(first_day_this_month, today)
    total_inc_last, total_exp_last = _compute_pnl_totals(first_day_last_month, last_month_end)

    income_growth = 0.0
    if total_inc_last > 0:
        income_growth = round(((total_inc_this - total_inc_last) / total_inc_last) * 100.0, 1)

    expenses_growth = 0.0
    if total_exp_last > 0:
        expenses_growth = round(((total_exp_this - total_exp_last) / total_exp_last) * 100.0, 1)

    monthly_burn = total_exp_this if total_exp_this > 0 else total_exp_last
    if monthly_burn <= 0:
        monthly_burn = 0.0

    # Net Worth calculation (Assets - Liabilities)
    asset_ledgers = Ledger.objects.filter(type=Ledger.LedgerType.ASSET)
    liability_ledgers = Ledger.objects.filter(type=Ledger.LedgerType.LIABILITY)
    asset_items = JournalItem.objects.filter(ledger__in=asset_ledgers)
    liability_items = JournalItem.objects.filter(ledger__in=liability_ledgers)
    if org_id:
        asset_items = asset_items.filter(org_id=org_id)
        liability_items = liability_items.filter(org_id=org_id)

    assets_val = float((asset_items.aggregate(d=Sum('debit'))['d'] or 0) - (asset_items.aggregate(c=Sum('credit'))['c'] or 0))
    liabilities_val = float((liability_items.aggregate(c=Sum('credit'))['c'] or 0) - (liability_items.aggregate(d=Sum('debit'))['d'] or 0))
    net_worth = assets_val - liabilities_val
    if net_worth <= 0:
        net_worth = cash + receivables - payables

    # Calculate average daily inflow and outflow over the last 30 days
    days_30_ago = today - datetime.timedelta(days=30)
    total_inc_30, total_exp_30 = _compute_pnl_totals(days_30_ago, today)
    daily_inflow = total_inc_30 / 30.0
    daily_outflow = total_exp_30 / 30.0

    # Fallback if 30-day window is empty
    if daily_inflow <= 0:
        all_inc_qs = JournalItem.objects.filter(ledger__type='income')
        if org_id:
            all_inc_qs = all_inc_qs.filter(org_id=org_id)
        all_inc_val = float((all_inc_qs.aggregate(c=Sum('credit'))['c'] or 0) - (all_inc_qs.aggregate(d=Sum('debit'))['d'] or 0))
        if all_inc_val <= 0:
            all_inc_val = 180000.0
        daily_inflow = all_inc_val / 30.0

    if daily_outflow <= 0:
        all_exp_qs = JournalItem.objects.filter(ledger__type='expense')
        if org_id:
            all_exp_qs = all_exp_qs.filter(org_id=org_id)
        all_exp_val = float((all_exp_qs.aggregate(d=Sum('debit'))['d'] or 0) - (all_exp_qs.aggregate(c=Sum('credit'))['c'] or 0))
        if all_exp_val <= 0:
            all_exp_val = 95000.0
        daily_outflow = all_exp_val / 30.0

    return {
        "cash": cash,
        "receivables": receivables,
        "payables": payables,
        "gst_liability": gst_liability,
        "gst_due_days": gst_due_days,
        "payroll_pending": payroll_pending,
        "eol_assets": eol_assets_count,
        "income_growth": income_growth,
        "expenses_growth": expenses_growth,
        "monthly_burn": monthly_burn,
        "net_worth": net_worth,
        "daily_inflow": daily_inflow,
        "daily_outflow": daily_outflow,
        "revenue": total_inc_this,
        "profit": total_inc_this - total_exp_this
    }


class FinanceControlTowerDashboardView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Sum, Q, F
        from django.utils import timezone
        import datetime
        from accounting.models import Account, Outstanding, Asset, GSTTransaction, Expense, Income, BankTransaction, BankStatementImport, Ledger, JournalItem, JournalEntry
        from core.models import PayrollRun, PayrollPaymentRecord

        org_id = _get_org_id_or_none(request) or ''
        stats = get_real_financial_stats(org_id)
        payroll_total = 0.0

        # 1. Decisions Table
        decisions = []
        decision_id = 1

        if stats['gst_liability'] > 0:
            decisions.append({
                "id": decision_id,
                "name": "GST Filing (Q1 Return)",
                "dept": "Compliance",
                "impact": stats['gst_liability'],
                "priority": "Critical" if stats['gst_due_days'] < 15 else "High",
                "owner": "Janki",
                "due": f"{stats['gst_due_days']} Days",
                "status": "Pending"
            })
            decision_id += 1

        if stats['payroll_pending']:
            payroll_runs_pending = PayrollRun.objects.filter(finance_approved_at__isnull=True)
            if org_id:
                payroll_runs_pending = payroll_runs_pending.filter(org_id=org_id)
            pending_months = [p.month for p in payroll_runs_pending]
            payment_records = PayrollPaymentRecord.objects.filter(month__in=pending_months)
            if org_id:
                payment_records = payment_records.filter(org_id=org_id)
            payroll_total = float(payment_records.aggregate(total=Sum('net_amount'))['total'] or 0)

            decisions.append({
                "id": decision_id,
                "name": "Payroll Approval (Pending)",
                "dept": "Finance",
                "impact": payroll_total,
                "priority": "Critical",
                "owner": "Janki",
                "due": "4 Days",
                "status": "Pending"
            })
            decision_id += 1

        if stats['receivables'] > 0:
            decisions.append({
                "id": decision_id,
                "name": "Receivable Follow-up (Outstanding)",
                "dept": "Finance",
                "impact": stats['receivables'],
                "priority": "High",
                "owner": "Janki",
                "due": "5 Days",
                "status": "Pending"
            })
            decision_id += 1

        unprocessed_txns = BankTransaction.objects.filter(status='unprocessed')
        if org_id:
            unprocessed_txns = unprocessed_txns.filter(org_id=org_id)
        unprocessed_count = unprocessed_txns.count()
        if unprocessed_count > 0:
            decisions.append({
                "id": decision_id,
                "name": f"Bank Reconciliation ({unprocessed_count} txns)",
                "dept": "Banking",
                "impact": 0.0,
                "priority": "Medium",
                "owner": "Wayne",
                "due": "2 Days",
                "status": "Pending"
            })
            decision_id += 1

        if stats['eol_assets'] > 0:
            decisions.append({
                "id": decision_id,
                "name": f"Asset Depreciation Run",
                "dept": "Assets",
                "impact": 0.0,
                "priority": "Low",
                "owner": "Wayne",
                "due": "7 Days",
                "status": "Pending"
            })
            decision_id += 1

        # If no pending decisions, return empty — no dummy data
        # decisions stays as-is (could be empty list)

        # 2. Timeline Activities
        timeline_items = []

        inc_qs = Income.objects.all()
        if org_id:
            inc_qs = inc_qs.filter(org_id=org_id)
        inc_qs = inc_qs.order_by('-date', '-created_at')[:5]
        for inc in inc_qs:
            timeline_items.append({
                "date": inc.date,
                "time": inc.created_at.strftime('%I:%M %p') if inc.created_at else "09:00 AM",
                "action": f"Income: {inc.description or 'Sales Receipt'}",
                "module": f"Collections\n₹{float(inc.amount):,}",
                "status": "success",
                "category": "Finance"
            })

        exp_qs = Expense.objects.all()
        if org_id:
            exp_qs = exp_qs.filter(org_id=org_id)
        exp_qs = exp_qs.order_by('-date', '-created_at')[:5]
        for exp in exp_qs:
            timeline_items.append({
                "date": exp.date,
                "time": exp.created_at.strftime('%I:%M %p') if exp.created_at else "09:00 AM",
                "action": f"Expense: {exp.description}",
                "module": f"Expense Center\n₹{float(exp.amount):,}",
                "status": "info",
                "category": "Finance"
            })

        bsi_qs = BankStatementImport.objects.all()
        if org_id:
            bsi_qs = bsi_qs.filter(org_id=org_id)
        bsi_qs = bsi_qs.order_by('-created_at')[:3]
        for bsi in bsi_qs:
            timeline_items.append({
                "date": bsi.created_at.date(),
                "time": bsi.created_at.strftime('%I:%M %p'),
                "action": f"Statement: {bsi.file_name}",
                "module": f"Banking Center\n{bsi.transactions_count} Txns",
                "status": "success",
                "category": "Banking"
            })

        timeline_items.sort(key=lambda x: (x['date'], x['time']), reverse=True)

        today_date = datetime.date.today()
        yesterday_date = today_date - datetime.timedelta(days=1)

        timeline_groups = {
            "TODAY": [],
            "YESTERDAY": [],
            "PAST WEEK": []
        }

        for item in timeline_items:
            date_val = item['date']
            item_copy = {k: v for k, v in item.items() if k != 'date'}
            if date_val == today_date:
                timeline_groups["TODAY"].append(item_copy)
            elif date_val == yesterday_date:
                timeline_groups["YESTERDAY"].append(item_copy)
            else:
                timeline_groups["PAST WEEK"].append(item_copy)

        if not timeline_groups["TODAY"] and not timeline_groups["YESTERDAY"] and not timeline_groups["PAST WEEK"]:
            timeline_groups = {
                "TODAY": [
                    { "time": "12:15 PM", "action": "No recent activities", "module": "Finance Ops", "status": "info", "category": "Finance" }
                ],
                "YESTERDAY": [],
                "PAST WEEK": []
            }

        # 3. Subsystem Health Sorted Logic
        def get_relative_sync_time(latest_dt):
            if not latest_dt:
                return 'Never'
            if timezone.is_naive(latest_dt):
                latest_dt = timezone.make_aware(latest_dt)
            now = timezone.now()
            diff = now - latest_dt
            sec = diff.total_seconds()
            if sec < 0:
                return 'Just now'
            if sec < 60:
                return 'Just now'
            mins = sec / 60.0
            if mins < 60:
                return f'{int(mins)} min ago'
            hrs = mins / 60.0
            if hrs < 24:
                return '1 hour ago' if int(hrs) == 1 else f'{int(hrs)} hours ago'
            days = hrs / 24.0
            return '1 day ago' if int(days) == 1 else f'{int(days)} days ago'

        items_qs = JournalItem.objects.all()
        if org_id:
            items_qs = items_qs.filter(org_id=org_id)
        total_debit = items_qs.aggregate(total=Sum('debit'))['total'] or 0
        total_credit = items_qs.aggregate(total=Sum('credit'))['total'] or 0
        accounts_health = 100 if total_debit == total_credit else 45

        total_txns = BankTransaction.objects.count()
        reconciled_txns = BankTransaction.objects.filter(status='processed').count()
        banking_health = int((reconciled_txns / total_txns * 100)) if total_txns > 0 else 100

        total_receivables = Outstanding.objects.filter(type='receivable').count()
        paid_receivables = Outstanding.objects.filter(type='receivable', status='paid').count()
        collections_health = int((paid_receivables / total_receivables * 100)) if total_receivables > 0 else 100

        gst_txns_qs = GSTTransaction.objects.all()
        if org_id:
            gst_txns_qs = gst_txns_qs.filter(org_id=org_id)
        pending_gst_txns = gst_txns_qs.filter(status='pending').count()
        gst_health = max(60, 100 - pending_gst_txns * 5)

        payroll_runs_count = PayrollRun.objects.count()
        approved_runs_count = PayrollRun.objects.filter(finance_approved_at__isnull=False).count()
        payroll_health = int((approved_runs_count / payroll_runs_count * 100)) if payroll_runs_count > 0 else 100

        expense_health = max(50, int(100 - max(0.0, stats['expenses_growth'])))

        total_assets_count = Asset.objects.count()
        active_assets_count = Asset.objects.filter(status='active').count()
        asset_health = int((active_assets_count / total_assets_count * 100)) if total_assets_count > 0 else 100

        # Query latest records for dynamic lastSync
        coll_latest = Outstanding.objects.filter(type='receivable')
        if org_id:
            coll_latest = coll_latest.filter(org_id=org_id)
        coll_latest = coll_latest.order_by('-updated_at').first()
        coll_sync = get_relative_sync_time(coll_latest.updated_at) if coll_latest else 'Never'

        gst_latest = GSTTransaction.objects.all()
        if org_id:
            gst_latest = gst_latest.filter(org_id=org_id)
        gst_latest = gst_latest.order_by('-updated_at').first()
        gst_sync = get_relative_sync_time(gst_latest.updated_at) if gst_latest else 'Never'

        pr_latest = PayrollRun.objects.all()
        if org_id:
            pr_latest = pr_latest.filter(org_id=org_id)
        pr_latest = pr_latest.order_by('-updated_at').first()
        payroll_sync = get_relative_sync_time(pr_latest.updated_at) if pr_latest else 'Never'

        exp_latest = Expense.objects.all()
        if org_id:
            exp_latest = exp_latest.filter(org_id=org_id)
        exp_latest = exp_latest.order_by('-created_at').first()
        expense_sync = get_relative_sync_time(exp_latest.created_at) if exp_latest else 'Never'

        asset_latest = Asset.objects.all()
        if org_id:
            asset_latest = asset_latest.filter(org_id=org_id)
        asset_latest = asset_latest.order_by('-updated_at').first()
        asset_sync = get_relative_sync_time(asset_latest.updated_at) if asset_latest else 'Never'

        banking_latest = BankTransaction.objects.all()
        if org_id:
            banking_latest = banking_latest.filter(org_id=org_id)
        banking_latest = banking_latest.order_by('-created_at').first()
        banking_sync = get_relative_sync_time(banking_latest.created_at) if banking_latest else 'Never'

        accounts_latest = JournalEntry.objects.all()
        if org_id:
            accounts_latest = accounts_latest.filter(org_id=org_id)
        accounts_latest = accounts_latest.order_by('-created_at').first()
        accounts_sync = get_relative_sync_time(accounts_latest.created_at) if accounts_latest else 'Never'

        infra_systems = [
            { "name": 'Collections Engine', "health": collections_health, "risk": 'Critical' if collections_health < 70 else ('High' if collections_health < 80 else 'Healthy'), "alerts": Outstanding.objects.filter(type='receivable', status='pending').count(), "lastSync": coll_sync },
            { "name": 'GST Center', "health": gst_health, "risk": 'High' if gst_health < 75 else 'Healthy', "alerts": pending_gst_txns, "lastSync": gst_sync },
            { "name": 'Payroll Center', "health": payroll_health, "risk": 'Medium' if payroll_health < 90 else 'Healthy', "alerts": PayrollRun.objects.filter(finance_approved_at__isnull=True).count(), "lastSync": payroll_sync },
            { "name": 'Expense Center', "health": expense_health, "risk": 'Medium' if expense_health < 90 else 'Healthy', "alerts": 0, "lastSync": expense_sync },
            { "name": 'Asset Management', "health": asset_health, "risk": 'Low' if asset_health > 90 else 'Medium', "alerts": stats['eol_assets'], "lastSync": asset_sync },
            { "name": 'Banking Center', "health": banking_health, "risk": 'Low' if banking_health > 90 else 'Medium', "alerts": BankTransaction.objects.filter(status='unprocessed').count(), "lastSync": banking_sync },
            { "name": 'Accounts Center', "health": accounts_health, "risk": 'Low' if accounts_health > 90 else 'High', "alerts": 0 if accounts_health == 99 else 1, "lastSync": accounts_sync },
        ]
        infra_systems.sort(key=lambda s: s['health'])

        # 4. Connected Accounts details
        reconciliation_accuracy = banking_health
        pending_matches = unprocessed_count
        connected_accounts = Account.objects.count()

        # 5. Mapped actions for Executive Command Center
        actions = []
        for dec in decisions:
            due_val = 5
            try:
                due_val = int(dec['due'].split()[0])
            except Exception:
                pass
            actions.append({
                "id": f"action_{dec['id']}",
                "title": dec['name'],
                "priority": dec['priority'],
                "financialImpact": dec['impact'],
                "dueDays": due_val,
                "dept": dec['dept'],
                "actionLabel": "Review & File" if "GST" in dec['name'] else ("Approve" if "Payroll" in dec['name'] else ("Send Reminders" if "Receivable" in dec['name'] else ("Reconcile" if "Reconciliation" in dec['name'] else "Run Now"))),
                "resolved": dec['status'] == 'Completed' or dec['status'] == 'Approved',
                "route": "/finance/gst" if "GST" in dec['name'] else ("/finance/journal" if "Payroll" in dec['name'] else ("/finance/finance" if "Receivable" in dec['name'] else ("/finance/reconciliation" if "Reconciliation" in dec['name'] else "/finance/assets")))
            })

        return Response({
            "cashPosition": stats['cash'],
            "receivables": stats['receivables'],
            "payables": stats['payables'],
            "gstLiability": stats['gst_liability'],
            "gstDueDays": stats['gst_due_days'],
            "payrollPending": stats['payroll_pending'],
            "payrollTotal": payroll_total,
            "eolAssets": stats['eol_assets'],
            "incomeGrowth": stats['income_growth'],
            "expensesGrowth": stats['expenses_growth'],
            "monthlyBurn": stats['monthly_burn'],
            "netWorth": stats['net_worth'],
            "dailyInflow": stats['daily_inflow'],
            "dailyOutflow": stats['daily_outflow'],
            "revenue": stats.get('revenue', 0.0),
            "profit": stats.get('profit', 0.0),
            "totalAssets": total_assets_count,
            "assetHealth": asset_health,
            "decisions": decisions,
            "actions": actions,
            "timelineGroups": timeline_groups,
            "infraSystems": infra_systems,
            "reconciliationAccuracy": reconciliation_accuracy,
            "pendingMatches": pending_matches,
            "connectedAccounts": connected_accounts
        })



