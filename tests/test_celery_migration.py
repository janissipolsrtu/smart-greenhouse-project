#!/usr/bin/env python3
"""
Test Celery Migration from APScheduler
Validates that the new Celery system works correctly
"""

import json
import time
import requests
from datetime import datetime, timedelta
from celery_config import celery_app
from celery_tasks import (
    check_due_irrigations, 
    execute_irrigation,
    schedule_irrigation_plan,
    health_check
)

def test_celery_connection():
    """Test Celery broker connection"""
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            print(f"✅ Celery connection successful. Workers: {len(stats)}")
            return True
        else:
            print("❌ No Celery workers found")
            return False
    except Exception as e:
        print(f"❌ Celery connection failed: {e}")
        return False

def test_redis_connection():
    """Test Redis connection"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def test_health_check_task():
    """Test basic Celery task execution"""
    try:
        print("🔍 Testing health check task...")
        result = health_check.delay()
        response = result.get(timeout=10)
        print(f"✅ Health check task completed: {response}")
        return True
    except Exception as e:
        print(f"❌ Health check task failed: {e}")
        return False

def test_check_due_irrigations_task():
    """Test periodic irrigation checking task"""
    try:
        print("🔍 Testing check due irrigations task...")
        result = check_due_irrigations.delay()
        response = result.get(timeout=30)
        print(f"✅ Check due irrigations completed: {response}")
        return True
    except Exception as e:
        print(f"❌ Check due irrigations failed: {e}")
        return False

def test_api_integration():
    """Test API server integration"""
    try:
        print("🔍 Testing API server...")
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server responding")
            return True
        else:
            print(f"❌ API server returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API server test failed: {e}")
        return False

def test_flower_monitoring():
    """Test Flower monitoring interface"""
    try:
        print("🔍 Testing Flower monitoring...")
        response = requests.get("http://localhost:5555", timeout=5)
        if response.status_code == 200:
            print("✅ Flower monitoring accessible")
            return True
        else:
            print(f"❌ Flower returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Flower monitoring test failed: {e}")
        return False

def test_irrigation_scheduling():
    """Test scheduling a sample irrigation plan"""
    try:
        print("🔍 Testing irrigation plan scheduling...")
        
        # Create sample plan data
        plan_data = {
            "scheduled_time": (datetime.now() + timedelta(minutes=1)).isoformat(),
            "duration": 30,
            "description": "Test irrigation plan",
            "device": "0x540f57fffe890af8"
        }
        
        result = schedule_irrigation_plan.delay(plan_data)
        response = result.get(timeout=15)
        
        if response.get("success"):
            print(f"✅ Irrigation plan scheduled: {response['plan_id']}")
            return True
        else:
            print(f"❌ Irrigation scheduling failed: {response}")
            return False
            
    except Exception as e:
        print(f"❌ Irrigation scheduling test failed: {e}")
        return False

def main():
    """Run all migration tests"""
    print("🧪 Celery Migration Test Suite")
    print("=" * 40)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Celery Connection", test_celery_connection),
        ("Health Check Task", test_health_check_task),
        ("Check Due Irrigations", test_check_due_irrigations_task),
        ("API Integration", test_api_integration),
        ("Flower Monitoring", test_flower_monitoring),
        ("Irrigation Scheduling", test_irrigation_scheduling),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        try:
            success = test_func()
            results[test_name] = success
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results[test_name] = False
        
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 Test Results Summary")
    print("=" * 40)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Celery migration is successful!")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)