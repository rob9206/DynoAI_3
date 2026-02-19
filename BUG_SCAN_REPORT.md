# DynoAI Bug Scan Report

**Generated:** 2026-02-12
**Scope:** Backend (api, dynoai), frontend patterns, security tools

---

## 1. Bandit (Python security)

```
Working... ---------------------------------------- 100% 0:00:02

Run started:2026-02-12 21:04:53.422228+00:00

Test results:
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\app.py:1446:35
1445	    debug_flag = bool(os.getenv("DYNOAI_DEBUG", "true").lower() == "true")
1446	    app.run(debug=debug_flag, host="0.0.0.0", port=5001, threaded=True)
1447	

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\config.py:34:76
33	
34	    host: str = field(default_factory=lambda: os.environ.get("DYNOAI_HOST", "0.0.0.0"))
35	    port: int = field(default_factory=lambda: _get_int_env("DYNOAI_PORT", 5001))

--------------------------------------------------
>> Issue: [B310:blacklist] Audit url open for permitted schemes. Allowing use of file:/ or custom schemes is often unexpected.
   Severity: Medium   Confidence: High
   CWE: CWE-22 (https://cwe.mitre.org/data/definitions/22.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/blacklists/blacklist_calls.html#b310-urllib-urlopen
   Location: api\jetstream\client.py:68:17
67	        try:
68	            with urlopen(request, timeout=self._timeout) as response:
69	                response_data = response.read().decode("utf-8")

--------------------------------------------------
>> Issue: [B310:blacklist] Audit url open for permitted schemes. Allowing use of file:/ or custom schemes is often unexpected.
   Severity: Medium   Confidence: High
   CWE: CWE-22 (https://cwe.mitre.org/data/definitions/22.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/blacklists/blacklist_calls.html#b310-urllib-urlopen
   Location: api\jetstream\client.py:217:17
216	        try:
217	            with urlopen(request, timeout=60) as response:
218	                with open(safe_dest, "wb") as f:

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\routes\jetdrive\_shared.py:193:45
192	JETDRIVE_PORT = int(os.getenv("JETDRIVE_PORT", "22344"))
193	JETDRIVE_IFACE = os.getenv("JETDRIVE_IFACE", "0.0.0.0")
194	

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\routes\jetdrive\_shared.py:228:47
227	
228	def test_multicast_support(interface_ip: str = "0.0.0.0") -> tuple[bool, str]:
229	    """Test if multicast is supported."""

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\routes\jetdrive\hardware.py:95:37
94	
95	    ok, msg = test_multicast_support("0.0.0.0")
96	    multicast_results.append(

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\routes\jetdrive\hardware.py:1102:28
1101	        mreq = socket.inet_aton(config.multicast_group) + socket.inet_aton(
1102	            config.iface or "0.0.0.0"
1103	        )

--------------------------------------------------
>> Issue: [B108:hardcoded_tmp_directory] Probable insecure usage of temp file/directory.
   Severity: Medium   Confidence: Medium
   CWE: CWE-377 (https://cwe.mitre.org/data/definitions/377.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b108_hardcoded_tmp_directory.html
   Location: api\services\coverage_tracker.py:28:23
27	    logger.warning(f"Cannot create {TRACKER_DIR}: {e}. Using /tmp fallback.")
28	    TRACKER_DIR = Path("/tmp/coverage_tracker")
29	    TRACKER_DIR.mkdir(parents=True, exist_ok=True)

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\services\ingestion\config.py:230:21
229	    port: int = 22344
230	    interface: str = "0.0.0.0"
231	    discovery_timeout_sec: float = 3.0

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\services\ingestion\config.py:256:44
255	            port=data.get("port", 22344),
256	            interface=data.get("interface", "0.0.0.0"),
257	            discovery_timeout_sec=data.get("discovery_timeout_sec", 3.0),

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\services\ingestion\config.py:271:50
270	            port=int(os.getenv("JETDRIVE_PORT", "22344")),
271	            interface=os.getenv("JETDRIVE_IFACE", "0.0.0.0"),
272	        )

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\services\jetdrive\jetdrive_client.py:25:44
24	# Set JETDRIVE_IFACE to a specific IP (e.g., 169.254.x.x) if you need to bind to a particular interface.
25	DEFAULT_IFACE = os.getenv("JETDRIVE_IFACE", "0.0.0.0")
26	# UDP receive buffer size -- 1 MB prevents OS-level packet drops under load.

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io/en/1.9.3/plugins/b104_hardcoded_bind_all_interfaces.html
   Location: api\services\jetdrive\jetdrive_client.py:284:41
283	    """
284	    target = iface.strip() if iface else "0.0.0.0"
285	    try:

--------------------------------------------------
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   CWE: CWE-605 (https://cwe.mitre.org/data/definitions/605.html)
   More Info: https://bandit.readthedocs.io
... (truncated)
```

## 2. Safety (dependency vulnerabilities)

```
C:\Python314\python.exe: No module named safety

```

## 3. Known-issue pattern checks

Checks for patterns from BUG_SCAN_REPORT (critical/high).

- **api/app.py**: Global CWD mutation (concurrent request risk)
  - L377: `os.chdir(project_root)`

- **api/app.py**: No match for pattern (may be fixed or refactored).

- **api/app.py**: Startup banner / app.run() call
  - L1381: `def print_startup_banner():`
  - L1454: `print_startup_banner()`
  - L1463: `print_startup_banner()`

- **api/routes/wizards.py**: Path traversal (run_id in path)
  - L135: `output_dir = OUTPUT_FOLDER / output_id`
  - L303: `output_dir = OUTPUT_FOLDER / output_id`

- **api/routes/reports.py**: Unauthenticated branding write
  - L64: `@reports_bp.route("/branding", methods=["PUT"])`

- **api/routes/jetstream/config.py**: Credential persistence (plaintext key)
  - L54: `json.dump(config.to_dict(mask_key=False), f, indent=2)`

- **frontend/src/lib/api.ts**: Frontend confidence-report path (404 if backend is /api/confidence/)
  - L293: `const response = await api.get(`/api/confidence-report/${runId}`);`

- **dynoai/core/ve_operations.py**: Divide-by-zero risk in rollback
  - L538: `restored_row.append(current_val / multiplier)`

- **api/app.py**: Subprocess timeout missing
  - L442: `result = subprocess.run(cmd, capture_output=True, text=True)`

---

## How to run this scan

```bash
pip install bandit safety  # if not already installed
python scripts/dev/run_bug_scan.py
python scripts/dev/run_bug_scan.py --output BUG_SCAN_REPORT.md
```
