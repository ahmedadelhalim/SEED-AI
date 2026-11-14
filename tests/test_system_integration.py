"""
SEED System Integration Tests
اختبارات التكامل الشاملة لنظام SEED
"""
import sys
import os
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_brain_initialization():
    """اختبار: هل يتم تهيئة العقل المركزي بنجاح؟"""
    try:
        from brain.model_gateway import ModelGateway
        gateway = ModelGateway.with_local_defaults()
        assert gateway is not None
        assert gateway.default_provider in ["ollama", "omniroute"]
        print("✅ Brain initialization: PASSED")
        return True
    except Exception as e:
        print(f"❌ Brain initialization: FAILED - {e}")
        return False


def test_voice_engine():
    """اختبار: هل نظام الصوت جاهز؟"""
    try:
        from runtime.advanced_voice import AdvancedVoiceManager, VoiceProfile
        profile = VoiceProfile()
        manager = AdvancedVoiceManager(profile)
        
        # Test script generation
        script = manager.generate_client_script()
        assert "SeedVoice" in script
        assert "listen" in script
        assert "speak" in script
        
        print("✅ Voice Engine: PASSED")
        return True
    except Exception as e:
        print(f"❌ Voice Engine: FAILED - {e}")
        return False


def test_task_engine():
    """اختبار: هل محرك المهام يعمل؟"""
    try:
        from core.task_engine import TaskEngine
        engine = TaskEngine()
        
        # Create a test task
        result = engine.submit("test-task-integration")
        assert result["task_id"] is not None
        assert result["status"] == "pending"
        
        # Get task
        task = engine.get(result["task_id"])
        assert task is not None
        assert task["command"] == "test-task-integration"
        
        print("✅ Task Engine: PASSED")
        return True
    except Exception as e:
        print(f"❌ Task Engine: FAILED - {e}")
        return False


def test_security_system():
    """اختبار: هل نظام الأمان والموافقات يعمل؟"""
    try:
        from security.approval_manager import ApprovalManager
        from security.permission_engine import PermissionEngine, ExecutionIdentity
        
        # Test approval manager
        approvals = ApprovalManager()
        assert approvals is not None
        
        # Test permission engine
        perms = PermissionEngine()
        identity = ExecutionIdentity(
            principal_id="test-user",
            kind="user",
            project_id="test-project"
        )
        assert identity is not None
        
        print("✅ Security System: PASSED")
        return True
    except Exception as e:
        print(f"❌ Security System: FAILED - {e}")
        return False


def test_memory_system():
    """اختبار: هل نظام الذاكرة يعمل؟"""
    try:
        from memory.store import initialize, connect, create_task, get_task
        
        # Initialize DB
        initialize()
        
        # Create a test task
        with connect() as db:
            cursor = db.execute(
                "INSERT INTO tasks (command, status) VALUES (?, ?)",
                ("memory-test", "pending")
            )
            db.commit()
            task_id = cursor.lastrowid
        
        # Retrieve it
        task = get_task(task_id)
        assert task is not None
        assert task["command"] == "memory-test"
        
        print("✅ Memory System: PASSED")
        return True
    except Exception as e:
        print(f"❌ Memory System: FAILED - {e}")
        return False


def test_mcp_integration():
    """اختبار: هل نظام MCP جاهز؟"""
    try:
        from core.tool_registry import ToolRegistry, ToolDefinition
        
        registry = ToolRegistry()
        assert registry is not None
        
        # Try to register a test tool
        test_tool = ToolDefinition(
            name="test.integration",
            description="Integration test tool",
            handler=lambda: {"status": "ok"},
            parameters={"type": "object", "properties": {}, "required": []},
            action="read",
            scope="workspace"
        )
        registry.register(test_tool)
        
        # Verify registration
        tools = registry.list_tools()
        tool_names = [t.name for t in tools]
        assert "test.integration" in tool_names
        
        print("✅ MCP Integration: PASSED")
        return True
    except Exception as e:
        print(f"❌ MCP Integration: FAILED - {e}")
        return False


def test_application_startup():
    """اختبار: هل التطبيق يبدأ بنجاح؟"""
    try:
        from core.application import SeedApplication
        
        app = SeedApplication()
        assert app is not None
        assert app.gateway is not None
        assert app.tools is not None
        assert app.tasks is not None
        assert app.permissions is not None
        
        print("✅ Application Startup: PASSED")
        return True
    except Exception as e:
        print(f"❌ Application Startup: FAILED - {e}")
        return False


def test_orchestrator():
    """اختبار: هل المنسق المركزي يعمل؟"""
    try:
        from core.orchestrator import SeedOrchestrator
        from core.application import SeedApplication
        
        app = SeedApplication()
        orchestrator = app.orchestrator
        
        assert orchestrator is not None
        print("✅ Orchestrator: PASSED")
        return True
    except Exception as e:
        print(f"❌ Orchestrator: FAILED - {e}")
        return False


def test_full_workflow():
    """اختبار: هل يمكن تنفيذ سير عمل كامل من البداية للنهاية؟"""
    try:
        from core.application import SeedApplication
        
        app = SeedApplication()
        
        # Step 1: Submit a request
        task_result = app.tasks.submit("integration-test-workflow")
        task_id = task_result["task_id"]
        
        # Step 2: Verify task exists
        task = app.tasks.get(task_id)
        assert task is not None
        
        # Step 3: Update status
        app.tasks.set_status(task_id, "running")
        task = app.tasks.get(task_id)
        assert task["status"] == "running"
        
        # Step 4: Record event
        app.tasks.record_event(task_id, "test_event", "Test event details")
        
        # Step 5: Complete task
        app.tasks.set_status(task_id, "completed")
        task = app.tasks.get(task_id)
        assert task["status"] == "completed"
        
        print("✅ Full Workflow: PASSED")
        return True
    except Exception as e:
        print(f"❌ Full Workflow: FAILED - {e}")
        return False


def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*60)
    print("SEED SYSTEM INTEGRATION TEST SUITE")
    print("="*60 + "\n")
    
    tests = [
        ("1. Brain Initialization", test_brain_initialization),
        ("2. Voice Engine", test_voice_engine),
        ("3. Task Engine", test_task_engine),
        ("4. Security System", test_security_system),
        ("5. Memory System", test_memory_system),
        ("6. MCP Integration", test_mcp_integration),
        ("7. Application Startup", test_application_startup),
        ("8. Orchestrator", test_orchestrator),
        ("9. Full Workflow E2E", test_full_workflow),
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\nRunning {test_name}...")
        result = test_func()
        results[test_name] = result
        time.sleep(0.1)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
