#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.model_gateway import ModelGateway

if __name__ == '__main__':
    try:
        print("Testing ModelGateway health...")
        g = ModelGateway.with_local_defaults()
        print(f"Health check result: {g.health()}")
        print("✅ ModelGateway health check successful")
        sys.exit(0)
    except Exception as e:
        print(f"❌ ModelGateway health check failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)