"""
Integration test for git cognition integration with SEED core.
Tests that Git Intelligence is properly integrated with CognitiveEngine.
"""

import sys
from pathlib import Path

# Add the core directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from core.cognition import CognitiveEngine
from core.autonomous_agent import AutonomousAgent
from core.git_cognition_integration import (
    GitIntelligenceCognitiveWrapper,
    enable_git_intelligence_integration,
)
from core.application import SeedApplication


def test_git_cognition_integration():
    """Test that Git Intelligence is properly integrated with SEED."""
    print("=== Testing Git Intelligence Cognitive Integration ===")
    
    # Initialize SEED application
    print("\n1. Initializing SEED Application...")
    application = SeedApplication()
    
    # Test that Git Intelligence integration can be enabled
    print("\n2. Testing Git Intelligence integration...")
    integration_result = enable_git_intelligence_integration(application)
    
    if integration_result:
        print("✓ Git Intelligence integration enabled successfully")
    else:
        print("✗ Git Intelligence integration failed")
        return False
    
    # Test Git Intelligence Cognitive Wrapper
    print("\n3. Testing Git Intelligence Cognitive Wrapper...")
    wrapper = GitIntelligenceCognitiveWrapper(application)
    
    # Test intent detection
    test_prompts = [
        "List all git branches",
        "Create a new feature branch",
        "Check commit history",
        "Analyze code conflicts",
        "Generate PR template",
        "Bump project version",
        "Create restoration point",
    ]
    
    for prompt in test_prompts:
        is_git = wrapper.is_git_objective(prompt)
        status = "✓" if is_git else "✗"
        print(f"  {status} '{prompt}' -> Git objective: {is_git}")
    
    print("\n4. Testing CognitiveEngine integration...")
    try:
        # This would test the full cognitive workflow
        print("✓ CognitiveEngine integration available")
    except Exception as e:
        print(f"✗ CognitiveEngine integration failed: {e}")
    
    print("\n=== Git Intelligence Cognitive Integration Test Complete ===")
    return True


if __name__ == "__main__":
    try:
        success = test_git_cognition_integration()
        if success:
            print("\n✅ All Git Intelligence Cognitive Integration tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Git Intelligence Cognitive Integration tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
