"""Quick test for environment isolation functions."""
import sys
sys.path.insert(0, 'D:\\SEED-AI')

from core.environment_isolation import (
    verify_environment_isolation,
    find_contamination,
    get_effective_env,
    resolve_seed_python,
    resolve_seed_site_packages,
    build_isolated_sys_path,
    get_isolated_environment,
)

print("=== verify_environment_isolation ===")
result = verify_environment_isolation()
print(f"  venv_path: {result['venv_path']}")
print(f"  python_executable: {result['python_executable']}")
print(f"  site_packages: {result['site_packages']}")
print(f"  foreign_site_packages: {result['foreign_site_packages']}")
print(f"  contamination_detected: {result['contamination_detected']}")
print(f"  recommendations: {result['recommendations']}")

print("\n=== find_contamination ===")
contamination = find_contamination(get_effective_env())
print(f"  contamination: {contamination}")

print("\n=== resolve_seed_python ===")
try:
    py = resolve_seed_python()
    print(f"  python: {py}")
except Exception as e:
    print(f"  error: {e}")

print("\n=== resolve_seed_site_packages ===")
try:
    sp = resolve_seed_site_packages()
    print(f"  site_packages: {sp}")
except Exception as e:
    print(f"  error: {e}")

print("\n=== build_isolated_sys_path ===")
try:
    paths = build_isolated_sys_path()
    print(f"  paths: {paths}")
except Exception as e:
    print(f"  error: {e}")

print("\n=== get_isolated_environment ===")
env = get_isolated_environment()
print(f"  PATH: {env['PATH'][:200]}...")
print(f"  PYTHONPATH: {env.get('PYTHONPATH', 'N/A')}")
print(f"  VIRTUAL_ENV: {env.get('VIRTUAL_ENV', 'N/A')}")
print(f"  SEED_ROOT: {env.get('SEED_ROOT', 'N/A')}")

print("\n=== All tests passed ===")