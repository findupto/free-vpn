from __future__ import annotations

import app
import resilient

# Keep the existing UI/connection engine, but replace the broken discovery path.
# This avoids the ThreadPoolExecutor context-manager bug that caused
# "3 (of 3) futures unfinished" after a refresh timeout.
app.fetch_servers = resilient.fetch_servers
app.APP_VERSION = "4.0.0"

if __name__ == "__main__":
    app.App().mainloop()
