from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response

class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination style for the application.
    Frontend sends: ?page=1&limit=25
    """
    page_size = 25
    page_size_query_param = 'limit'  # Matches the 'limit' param from your React frontend
    max_page_size = 2000  # Increased for analytics to fetch bulk data

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class OrderCursorPagination(CursorPagination):
    """
    Cursor-based pagination for O(1) constant-time page access.
    
    Unlike offset pagination (which slows down on page 1000+), cursor pagination
    uses the ordering field's value as a bookmark — always fast regardless of page depth.
    
    Usage: Set as pagination_class on a view, or use directly:
        paginator = OrderCursorPagination()
        page = paginator.paginate_queryset(queryset, request)
    """
    page_size = 50
    page_size_query_param = 'limit'
    max_page_size = 100
    ordering = '-created_at'  # Uses the indexed (org_id, created_at) column