"""
Stub API views for the extended Marketing module.
Returns empty data structures so the frontend can render properly.
When real integrations are built, only these views need implementation changes.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class SocialPostsAPIView(APIView):
    """Stub: Social media posts list."""
    def get(self, request):
        return Response({"posts": [], "total": 0}, status=status.HTTP_200_OK)


class SocialCalendarAPIView(APIView):
    """Stub: Content calendar data."""
    def get(self, request):
        return Response({"calendar": [], "month": None}, status=status.HTTP_200_OK)


class SocialAnalyticsAPIView(APIView):
    """Stub: Social media analytics."""
    def get(self, request):
        return Response({
            "summary": {
                "total_posts": 0, "total_reach": 0,
                "total_engagement": 0, "follower_growth": 0,
                "avg_engagement_rate": 0
            },
            "posts_by_type": [],
            "daily_metrics": []
        }, status=status.HTTP_200_OK)


class InfluencerListAPIView(APIView):
    """Stub: Influencer database."""
    def get(self, request):
        return Response({"influencers": [], "total": 0}, status=status.HTTP_200_OK)


class InfluencerCampaignsAPIView(APIView):
    """Stub: Influencer campaigns."""
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)


class OfflineEventsAPIView(APIView):
    """Stub: Offline events list."""
    def get(self, request):
        return Response({"events": [], "total": 0}, status=status.HTTP_200_OK)


class OfflineLeadsAPIView(APIView):
    """Stub: Offline leads list."""
    def get(self, request):
        return Response({"leads": [], "total": 0}, status=status.HTTP_200_OK)


class OfflineAnalyticsAPIView(APIView):
    """Stub: Offline analytics."""
    def get(self, request):
        return Response({
            "summary": {
                "total_events": 0, "total_revenue": 0,
                "total_leads": 0, "avg_roi": 0
            },
            "events_by_city": [],
            "events_by_type": []
        }, status=status.HTTP_200_OK)


class PRCoverageAPIView(APIView):
    """Stub: PR coverage list."""
    def get(self, request):
        return Response({"coverage": [], "total": 0}, status=status.HTTP_200_OK)


class PROutreachAPIView(APIView):
    """Stub: PR outreach pipeline."""
    def get(self, request):
        return Response({"outreach": [], "total": 0}, status=status.HTTP_200_OK)


class CelebritySpottingsAPIView(APIView):
    """Stub: Celebrity spottings."""
    def get(self, request):
        return Response({"spottings": [], "total": 0}, status=status.HTTP_200_OK)


class CelebrityCampaignsAPIView(APIView):
    """Stub: Celebrity campaigns."""
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)


class CampaignsHubAPIView(APIView):
    """Stub: Unified campaigns hub."""
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)


class BrandMonitoringAPIView(APIView):
    """Stub: Brand monitoring / mentions."""
    def get(self, request):
        return Response({
            "mentions": [],
            "summary": {
                "total_mentions": 0,
                "positive": 0, "neutral": 0, "negative": 0,
                "branded_search_volume": 0
            }
        }, status=status.HTTP_200_OK)


class AttributionAPIView(APIView):
    """Stub: Revenue attribution."""
    def get(self, request):
        return Response({
            "attributions": [],
            "summary": {
                "total_attributed_revenue": 0,
                "campaigns_tracked": 0
            }
        }, status=status.HTTP_200_OK)

class YouTubeAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class PinterestAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class SnapchatAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class AmazonAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class FlipkartAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class EtsyAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class AjioAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class TataCliqAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class MyntraAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class NykaaAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class BlinkitAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class InstamartAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)

class ZeptoAdsAPIView(APIView):
    def get(self, request):
        return Response({"campaigns": [], "total": 0}, status=status.HTTP_200_OK)
