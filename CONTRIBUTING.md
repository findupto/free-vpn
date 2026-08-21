# Contributing

1. Keep changes focused and testable.
2. Do not commit VPN credentials, private keys, generated executables, caches, or runtime logs.
3. Add or update unit tests for behavior changes.
4. Run `python -m unittest discover -s tests -v` before submitting a change.
5. Keep platform-specific behavior isolated and document Windows/Linux/macOS differences.
6. Never treat a TLS handshake alone as proof that a VPN tunnel is usable.
