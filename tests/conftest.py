import os
import tempfile

os.environ["MODE"] = "fixtures"
os.environ["FIXTURE_PACE"] = "0"
for k in ("ANTHROPIC_API_KEY", "TAVILY_API_KEY", "ADMIN_PASSCODE", "MODEL_FAST", "MODEL_SMART"):
    os.environ.pop(k, None)
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="rw-test-")
