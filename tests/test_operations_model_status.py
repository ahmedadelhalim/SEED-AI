#!/usr/bin/env python3

import sys
import time
import threading
import urllib.request
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.operations import OperationsAPI
from brain.model_gateway import ModelGateway
from core.tool_registry import ToolRegistry

def test_operations_api():
    """Test that OperationsAPI includes model_status correctly."""
    
    print("Testing OperationsAPI model status...")
    
    # Create components
    gateway = ModelGateway.with_local_defaults()
    tools = ToolRegistry()
    
    # Create OperationsAPI
    ops = OperationsAPI(gateway, tools)
    
    # Get status
    status = ops.status()
    
    # Check model_status field
    if 'model_status' not in status:
        print('❌ model_status not found in operations status')
        return False
    
    model_status = status['model_status']
    print('✅ model_status found in operations status')
    print(f'Model status: {model_status}')
    
    # Verify fields
    required_fields = ['provider', 'model', 'healthy', 'status']
    for field in required_fields:
        if field not in model_status:
            print(f'❌ Missing field: {field}')
            return False
    
    print('✅ All required fields present')
    return True

def test_desktop_server_status():
    """Test that desktop server returns model_status."""
    
    print("\nTesting desktop server status endpoint...")
    
    # Start desktop server in background thread
    def run_server():
        from interfaces.desktop_server import create_server
        server = create_server()
        server.serve_forever()
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)  # Give server time to start
    
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/status') as resp:
            status = json.loads(resp.read().decode())
            
            if 'model_status' not in status:
                print('❌ model_status not found in server response')
                return False
            
            model_status = status['model_status']
            print('✅ model_status found in server response')
            print(f'Model status: {model_status}')
            
            # Verify fields
            required_fields = ['provider', 'model', 'healthy', 'status']
            for field in required_fields:
                if field not in model_status:
                    print(f'❌ Missing field: {field}')
                    return False
            
            print('✅ All required fields present in server response')
            return True
    except Exception as e:
        print(f'❌ Server test failed: {e}')
        return False

if __name__ == '__main__':
    # Test OperationsAPI directly
    api_ok = test_operations_api()
    
    # Test desktop server
    server_ok = test_desktop_server_status()
    
    if api_ok and server_ok:
        print('\n✅ All tests passed!')
        sys.exit(0)
    else:
        print('\n❌ Some tests failed')
        sys.exit(1)