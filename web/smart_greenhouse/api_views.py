from rest_framework import serializers, viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from .models import WateringPlan, WateringCycle
import uuid
import time


class WateringCycleSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    device_display = serializers.CharField(source='get_device_display', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    
    class Meta:
        model = WateringCycle
        fields = '__all__'
    
    def create(self, validated_data):
        # Generate unique cycle ID if not provided
        if 'id' not in validated_data:
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            validated_data['id'] = f"cycle_{timestamp}_{unique_id}"
        
        # Set default device if not provided
        if 'device' not in validated_data:
            validated_data['device'] = '0x540f57fffe890af8'
        
        return super().create(validated_data)


class WateringCycleViewSet(viewsets.ModelViewSet):
    queryset = WateringCycle.objects.all()
    serializer_class = WateringCycleSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        plan_filter = self.request.query_params.get('plan_id')
        if plan_filter == 'none':
            queryset = queryset.filter(plan__isnull=True)
        elif plan_filter:
            queryset = queryset.filter(plan_id=plan_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(scheduled_time__gte=start_date)
        if end_date:
            queryset = queryset.filter(scheduled_time__lte=end_date)
        
        return queryset.order_by('-scheduled_time')

    @action(detail=True, methods=['post'])
    def assign_plan(self, request, pk=None):
        cycle = self.get_object()
        plan_id = request.data.get('plan_id')

        if not plan_id:
            return Response({'detail': 'plan_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = WateringPlan.objects.get(id=plan_id)
        except WateringPlan.DoesNotExist:
            return Response({'detail': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)

        cycle.plan = plan
        cycle.save(update_fields=['plan', 'updated_at'])
        return Response(self.get_serializer(cycle).data)

    @action(detail=True, methods=['post'])
    def unassign_plan(self, request, pk=None):
        cycle = self.get_object()
        cycle.plan = None
        cycle.save(update_fields=['plan', 'updated_at'])
        return Response(self.get_serializer(cycle).data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get watering system statistics"""
        now = timezone.now()
        
        stats = {
            'total_cycles': self.get_queryset().count(),
            'pending_cycles': self.get_queryset().filter(status='pending').count(),
            'completed_cycles': self.get_queryset().filter(status='completed').count(),
            'failed_cycles': self.get_queryset().filter(status='failed').count(),
            'overdue_cycles': self.get_queryset().filter(
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
        """Get upcoming watering cycles"""
        now = timezone.now()
        upcoming = self.get_queryset().filter(
            scheduled_time__gte=now,
            status='pending'
        )[:10]
        
        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue watering cycles"""
        now = timezone.now()
        overdue = self.get_queryset().filter(
            scheduled_time__lt=now,
            status='pending'
        )
        
        serializer = self.get_serializer(overdue, many=True)
        return Response(serializer.data)


class WateringPlanSerializer(serializers.ModelSerializer):
    cycle_count = serializers.SerializerMethodField()

    class Meta:
        model = WateringPlan
        fields = '__all__'

    def get_cycle_count(self, obj):
        return obj.cycles.count()

    def create(self, validated_data):
        if 'id' not in validated_data:
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            validated_data['id'] = f"plan_{timestamp}_{unique_id}"
        return super().create(validated_data)


class WateringPlanViewSet(viewsets.ModelViewSet):
    queryset = WateringPlan.objects.all().order_by('-created_at')
    serializer_class = WateringPlanSerializer

    @action(detail=True, methods=['get'])
    def cycles(self, request, pk=None):
        plan = self.get_object()
        cycles = plan.cycles.all().order_by('-scheduled_time')
        serializer = WateringCycleSerializer(cycles, many=True)
        return Response(serializer.data)