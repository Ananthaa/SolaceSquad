content = open('google_auth.py', 'r', encoding='utf-8').read()

old = (
    'def _redirect_uri(request: Request) -> str:\n'
    '    """Always use APP_BASE_URL so it matches GCP Credentials regardless of proxy headers."""\n'
    '    return f"{_BASE_URL}/auth/google/callback"'
)

new = (
    'def _redirect_uri(request: Request) -> str:\n'
    '    """Build redirect URI dynamically from the incoming request host.\n'
    '    Fixes CSRF/session mismatch when accessed via multiple domains\n'
    '    (solacesquad.com, solacesquad.in, mirror). Cloud Run sets\n'
    '    X-Forwarded-Proto and X-Forwarded-Host automatically.\n'
    '    """\n'
    '    forwarded_host  = request.headers.get("x-forwarded-host", "")\n'
    '    forwarded_proto = request.headers.get("x-forwarded-proto", "https")\n'
    '    host = forwarded_host or request.headers.get("host", "")\n'
    '    if host:\n'
    '        host = host.split(":")[0]  # strip port if present\n'
    '        return f"{forwarded_proto}://{host}/auth/google/callback"\n'
    '    return f"{_BASE_URL}/auth/google/callback"  # fallback to APP_BASE_URL'
)

if old in content:
    content = content.replace(old, new)
    open('google_auth.py', 'w', encoding='utf-8').write(content)
    print('SUCCESS: _redirect_uri updated to dynamic host-based URI')
else:
    print('NOT FOUND — showing current function:')
    idx = content.find('def _redirect_uri')
    print(repr(content[idx:idx+200]))
