import sys
sys.path.insert(0, ".")
import threading
import time
import json
from urllib.request import urlopen
from interfaces.desktop_server import create_server
from core.application import SeedApplication

def test_model_status_endpoint():
    # Create application instance
    app = SeedApplication()
    
    # Create server on a test port
    server = create_server(application=app, host="127.0.0.1", port=8766)
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    # Give server time to start
    time.sleep(1)
    
    try:
        response = urlopen("http://127.0.0.1:8766/api/model/status")
        data = json.loads(response.read().decode("utf-8"))
        
        assert data["model"] == "qwen3:4b"
        assert data["provider"] in ("ollama", "llama_embedded", "llama_real", "omniroute")
        assert data["health"] in ("healthy", "unhealthy", "unknown")
        assert data["status"] in ("running", "stopped", "unknown")
        assert isinstance(data["temperature"], float)
        assert isinstance(data["timeout_seconds"], int)
        print("Model status endpoint test passed")
    finally:
        server.shutdown()
        server_thread.join(timeout=2)

if __name__ == "__main__":
    test_model_status_endpoint()