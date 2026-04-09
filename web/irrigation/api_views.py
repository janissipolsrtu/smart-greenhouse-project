from rest_framework import serializers, viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from .models import IrrigationPlan
import uuid
import time


class IrrigationPlanSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    device_display = serializers.CharField(source='get_device_display', read_only=True)
    
    class Meta:
        model = IrrigationPlan
        fields = '__all__'
    
    def create(self, validated_data):
        # Generate unique plan ID if not provided
        if 'id' not in validated_data:
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            validated_data['id'] = f"plan_{timestamp}_{unique_id}"
        
        # Set default device if not provided
        if 'device' not in validated_data:
            validated_data['device'] = '0x540f57fffe890af8'
        
        return super().create(validated_data)


class IrrigationPlanViewSet(viewsets.ModelViewSet):
    queryset = IrrigationPlan.objects.all()
    serializer_class = IrrigationPlanSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(scheduled_time__gte=start_date)
        if end_date:
            queryset = queryset.filter(scheduled_time__lte=end_date)
        
        return queryset.order_by('-scheduled_time')
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get irrigation system statistics"""
        now = timezone.now()
        
        stats = {
            'total_plans': self.get_queryset().count(),
            'pending_plans': self.get_queryset().filter(status='pending').count(),
            'completed_plans': self.get_queryset().filter(status='completed').count(),
            'failed_plans': self.get_queryset().filter(status='failed').count(),
            'overdue_plans': self.get_queryset().filter(
                scheduled_time__lt=now,
                status='pending'
            ).count(),
            'upcoming_24h': self.get_queryset().filter(
                scheduled_time__gte=now,
                scheduled_time__lte=now + timezone.timedelta(days=1),
                status='pending'
            ).count(),
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming irrigation plans"""
        now = timezone.now()
        upcoming = self.get_queryset().filter(
            scheduled_time__gte=now,
            status='pending'
        )[:10]
        
        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue irrigation plans"""
        now = timezone.now()
        overdue = self.get_queryset().filter(
            scheduled_time__lt=now,
            status='pending'
        )
        
        serializer = self.get_serializer(overdue, many=True)
        return Response(serializer.data)