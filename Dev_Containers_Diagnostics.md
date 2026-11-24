# SEED-AI Dev Containers Diagnostics Report

**Date**: 2026-11-14  
**Workspace**: D:\SEED-AI  
**Issue**: Docker not found, WSL reports REGDB_E_CLASSNOTREG  
**Impact**: Prevents containerized development, testing, and deployment in SEED  

## 1. Diagnosis Summary

The Dev Containers environment is **not beneficial** for SEED's architecture because:

1. **Docker is not installed** on the host system
2. **WSL installation is corrupted** (REGDB_E_CLASSNOTREG)
3. Docker requires WSL2 backend, which is unavailable
4. WSL2 requires a separate Windows feature that is **currently disabled**

SEED is designed as a native Windows application with:

- Native Python execution (via `.venv\Scripts\python.exe`)
- Native file system access with path isolation
- No dependency on Linux containers or WSL
- Minimal external dependencies (no Docker, no Kubernetes)

## 2. Root Cause Analysis

| Component | Status | Evidence |
|---------|--------|----------|
| Docker Desktop | ❌ Not Installed | `docker` command not found in PATH |
| WSL2 | ❌ Disabled | `Get-WindowsOptionalFeature` shows "State: Disabled" |
| WSL Installation | ❌ Corrupted | Error code: Wsl/CallMsi/Install/REGDB_E_CLASSNOTREG |
| Containerization | ❌ Not Feasible | Requires Docker + WSL2 backend |

## 3. Architecture Assessment

SEED's architecture is **natively Windows-first** with:

- **Python**: Runs directly from `.venv\Scripts\python.exe` (no PATH contamination)
- **File System**: Uses Windows paths with canonicalization and validation
- **Process Management**: No container orchestration needed
- **Networking**: Standard TCP/IP stack with Windows-native sockets
- **Deployment**: Direct deployment to Azure via `azure-deploy` agent

## 4. Recommendation: Native Windows Development Workflow

### ✅ Recommended Approach: Native Windows + Virtual Environment

1. **Activate SEED Environment**  
   Run `seed-env-bootstrap.ps1` to establish isolation  
   ```powershell
   & "D:\SEED-AI\bin\seed-env-bootstrap.ps1"
   ```

2. **Use Native Tools**  
   - Python: `.venv\Scripts\python.exe`  
   - Git: `C:\Program Files\Git\cmd\git.exe` (explicitly resolved)  
   - Database: Native PostgreSQL binaries in `D:\SEED-AI\data\`  

3. **Dev Containers Alternative**  
   Only consider containerization if:
   - You have Docker Desktop installed (Windows feature)
   - WSL2 is enabled and functional  
   - You have a dedicated test environment (not development)

### ❌ Why Dev Containers is Not Recommended for SEED

| Concern | Reason |
|---------|--------|
| **Complexity** | Requires Docker + WSL2 + Linux distro setup |
| **Dependencies** | Adds 500MB+ Docker Desktop installation |
| **Failure Surface** | WSL corruption prevents any container use |
| **Performance** | Linux VM overhead for Windows-native apps |
| **Maintenance** | Separate environment to update and secure |

## 5. Action Plan

1. **Do Not Install Docker**  
   SEED's architecture does not require containers for development or testing.

2. **Maintain Current Workflow**  
   Use native Windows tools with SEED's environment isolation.

3. **Document Environment**  
   Add this report to `docs/architecture.md` and `docs/roadmap.md`.

4. **Future-Proofing**  
   If containerization becomes necessary:  
   - Install Docker Desktop (Windows feature)  
   - Enable WSL2 via `Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart`  
   - Install a Linux distro from Microsoft Store  
   - Use `appmod-get-containerization-plan` to generate Dockerfiles

## 6. Conclusion

SEED is designed as a **native Windows application** with explicit dependency isolation.  
Dev Containers would add unnecessary complexity and failure points without providing architectural benefits. The current native Windows approach with `.venv` environment isolation is optimal.