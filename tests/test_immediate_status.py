#!/usr/bin/env python3
"""Test script to verify immediate status updates in Celery tasks"""

import sys
import os
sys.path.append('/app')

from celery_tasks import execute_irrigation
from irrigation_db_service import IrrigationPlanService
from models import IrrigationPlan
from datetime import datetime

def test_immediate_status_update():
    # Create a test plan in database using individual parameters
    test_id = 'manual_test_' + str(int(datetime.utcnow().timestamp()))
    
    try:
        created_plan = IrrigationPlanService.create_plan(
            scheduled_time=datetime.utcnow(),
            duration=10,
            description='Manual test execution',
            device='irrigation_valve'
        )
        print(f'✅ Created test plan: {created_plan.id}')
        print(f'Initial status: {created_plan.status}')
        
        # Execute irrigation task directly (not via Celery queue)
        print('\n🚀 Executing irrigation task...')
        
        # Call the function directly by importing the actual function implementation
        from celery_tasks import execute_irrigation
        
        # Create a mock task instance for testing
        class MockTask:
            def retry(self, exc=None):
                raise exc
        
        mock_task = MockTask()
        
        result = execute_irrigation(
            mock_task,  # self parameter
            created_plan.id, 
            '0x540f57fffe890af8', 
            10, 
            'Manual test execution'
        )
        print(f'Task execution result: {result}')
        
        # Check plan status immediately after execution
        print('\n📊 Checking plan status after execution...')
        updated_plan = IrrigationPlanService.get_plan_by_id(created_plan.id)
        print(f'Plan status: {updated_plan.status}')
        print(f'Plan result: {updated_plan.result}')
        print(f'Executed at: {updated_plan.executed_at}')
        
        if updated_plan.status == 'completed':
            print('\n✅ SUCCESS: Plan status was immediately updated to "completed"!')
        else:
            print(f'\n❌ ISSUE: Plan status is "{updated_plan.status}", expected "completed"')
            
    except Exception as e:
        print(f'❌ Error during test: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_immediate_status_update()