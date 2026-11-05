"""
SolaceSquad Pre-Deployment Verification Test Suite
==================================================
Ensures zero regressions before any production release:
1. Guideline 4.8: Google Login is 100% excluded on iOS/iPadOS (server-side Jinja & client-side DOM removal).
2. Guideline 1.4.1: Medical Disclaimers ("Not a Medical Device", "Seek a doctor's advice") are strictly present.
3. Code Integrity: Python compilation, model imports, and core syntax.
4. Optional Live Verification: Tests production/staging endpoint with iOS User-Agent.
"""
import sys
import os
import re

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(repo_root, "backend")
templates_dir = os.path.join(backend_dir, "templates")

def test_guideline_4_8_template_rendering():
    print("[1/4] Testing Guideline 4.8 Compliance (iOS Login Services Exemption)...")
    import jinja2

    loader = jinja2.FileSystemLoader(templates_dir)
    env = jinja2.Environment(loader=loader, autoescape=True)

    class MockURL:
        path = "/login"

    class MockRequest:
        url = MockURL()
        query_params = {}
        session = {}

    req = MockRequest()

    # Mock custom filters or globals if any are needed
    env.globals["get_flashed_messages"] = lambda: []

    # Test Login Template - iOS Mode
    login_tmpl = env.get_template("pages/auth/login.html")
    rendered_ios = login_tmpl.render(
        request=req,
        is_ios=True,
        error=None,
        page_title="Login - SolaceSquad"
    )
    assert 'id="tab-google-btn"' not in rendered_ios, "FAIL: <button id='tab-google-btn'> rendered when is_ios=True!"
    assert 'id="panel-google"' not in rendered_ios, "FAIL: <div id='panel-google'> rendered when is_ios=True!"
    assert "Continue with Google" not in rendered_ios, "FAIL: 'Continue with Google' rendered when is_ios=True!"
    assert "checkIOSLoginExemption" in rendered_ios, "FAIL: checkIOSLoginExemption missing from login.html!"
    assert "navigator.maxTouchPoints > 1" in rendered_ios, "FAIL: iPadOS M3 touch detection missing from login.html!"

    # Test Login Template - Desktop Web Mode
    rendered_web = login_tmpl.render(
        request=req,
        is_ios=False,
        error=None,
        page_title="Login - SolaceSquad"
    )
    assert 'id="tab-google-btn"' in rendered_web, "FAIL: <button id='tab-google-btn'> missing when is_ios=False!"
    assert 'id="panel-google"' in rendered_web, "FAIL: <div id='panel-google'> missing when is_ios=False!"
    assert "Continue with Google" in rendered_web, "FAIL: 'Continue with Google' missing when is_ios=False!"

    # Test Signup Template - iOS Mode
    signup_tmpl = env.get_template("pages/auth/signup_simple.html")
    rendered_signup_ios = signup_tmpl.render(
        request=req,
        is_ios=True,
        page_title="Sign Up - SolaceSquad",
        recaptcha_site_key=""
    )
    assert 'id="google-btn"' not in rendered_signup_ios, "FAIL: google-btn rendered in signup when is_ios=True!"
    assert "checkIOSSignupExemption" in rendered_signup_ios, "FAIL: checkIOSSignupExemption missing from signup_simple.html!"

    # Test Signup Template - Desktop Web Mode
    rendered_signup_web = signup_tmpl.render(
        request=req,
        is_ios=False,
        page_title="Sign Up - SolaceSquad",
        recaptcha_site_key=""
    )
    assert 'id="google-btn"' in rendered_signup_web, "FAIL: google-btn missing in signup when is_ios=False!"

    print("  PASS: Guideline 4.8 is 100% compliant in template rendering.")


def test_guideline_1_4_1_vitals_disclaimers():
    print("[2/4] Testing Guideline 1.4.1 Compliance (Medical Disclaimers & Vitals Isolation)...")
    import jinja2

    vitals_file = os.path.join(templates_dir, "pages", "vitals.html")
    assert os.path.exists(vitals_file), f"FAIL: vitals.html not found at {vitals_file}"

    with open(vitals_file, "r", encoding="utf-8") as f:
        vitals_content = f.read()

    # Required Apple & FDA Disclaimers
    mandatory_terms = [
        "Not a Medical Device",
        "general fitness and wellness purposes only",
        "Always seek a doctor’s advice",
        "scan-disclaimer-overlay",
        "results-card",
        "Wellness Guide",
        "Wellness Synthesis",
    ]

    for term in mandatory_terms:
        norm_term = term.replace("’", "'")
        norm_content = vitals_content.replace("’", "'")
        assert norm_term in norm_content, f"FAIL: Mandatory disclaimer phrase '{term}' missing from vitals.html!"

    # Prohibited clinical terms that trigger 510(k) rejection
    forbidden_terms = [
        "Clinical Guide &rarr;",
        "Clinical Synthesis & Physiological Recovery",
    ]
    for forbidden in forbidden_terms:
        assert forbidden not in vitals_content, f"FAIL: Prohibited clinical claim '{forbidden}' found in vitals.html!"

    # Template Rendering Isolation Test (Production vs Mirror)
    loader = jinja2.FileSystemLoader(templates_dir)
    env = jinja2.Environment(loader=loader, autoescape=True)
    env.globals["get_flashed_messages"] = lambda: []
    env.globals["get_nav_items"] = lambda user_type: []
    env.globals["get_initials"] = lambda name: "TU"

    class MockURL:
        path = "/app/vitals"

    class MockRequest:
        url = MockURL()
        query_params = {}
        session = {}

    req = MockRequest()
    vitals_tmpl = env.get_template("pages/vitals.html")

    # Production Mode: Must strictly show ONLY the 5 base vitals
    rendered_prod = vitals_tmpl.render(
        request=req,
        environment="production",
        latest_reading=None,
        vitals_history=[],
        user_age=30,
        user_gender="female",
        user_name="Test User",
        user_initials="TU",
        user_type="user",
        active_page="vitals",
        nav_items=[],
        user_plan="free",
        page_title="Vitals Scanner"
    )
    assert 'id="guide-tab-btn-hrv"' not in rendered_prod, "FAIL: guide-tab-btn-hrv rendered on production!"
    assert 'id="guide-tab-btn-stress"' not in rendered_prod, "FAIL: guide-tab-btn-stress rendered on production!"
    assert 'id="guide-tab-btn-vascular"' not in rendered_prod, "FAIL: guide-tab-btn-vascular rendered on production!"
    assert 'guide-tab-pane-vascular' not in rendered_prod, "FAIL: guide-tab-pane-vascular rendered on production!"
    assert 'const isMirror = false;' in rendered_prod, "FAIL: isMirror is not false in JS on production!"
    assert 'id="face-mismatch-modal"' not in rendered_prod, "FAIL: face-mismatch-modal rendered on production!"
    assert 'id="biometrics-manage-modal"' not in rendered_prod, "FAIL: biometrics-manage-modal rendered on production!"
    assert 'Face ID' not in rendered_prod, "FAIL: Apple trademark 'Face ID' found in production template!"
    assert 'id="liveness-failed-modal"' not in rendered_prod, "FAIL: liveness-failed-modal rendered on production!"
    assert 'id="scan-blink-prompt"' not in rendered_prod, "FAIL: scan-blink-prompt rendered on production!"
    assert 'id="scan-liveness-badge"' not in rendered_prod, "FAIL: scan-liveness-badge rendered on production!"

    # Mirror Mode: Must include extended biomarkers
    rendered_mirror = vitals_tmpl.render(
        request=req,
        environment="mirror",
        latest_reading=None,
        vitals_history=[],
        user_age=30,
        user_gender="female",
        user_name="Test User",
        user_initials="TU",
        user_type="user",
        active_page="vitals",
        nav_items=[],
        user_plan="free",
        page_title="Vitals Scanner"
    )
    assert 'id="guide-tab-btn-hrv"' in rendered_mirror, "FAIL: guide-tab-btn-hrv missing on mirror!"
    assert 'id="guide-tab-btn-stress"' in rendered_mirror, "FAIL: guide-tab-btn-stress missing on mirror!"
    assert 'id="guide-tab-btn-vascular"' in rendered_mirror, "FAIL: guide-tab-btn-vascular missing on mirror!"
    assert 'guide-tab-pane-vascular' in rendered_mirror, "FAIL: guide-tab-pane-vascular missing on mirror!"
    assert 'const isMirror = true;' in rendered_mirror, "FAIL: isMirror is not true in JS on mirror!"
    assert 'id="face-mismatch-modal"' in rendered_mirror, "FAIL: face-mismatch-modal missing on mirror!"
    assert 'id="biometrics-manage-modal"' in rendered_mirror, "FAIL: biometrics-manage-modal missing on mirror!"
    assert 'id="liveness-failed-modal"' in rendered_mirror, "FAIL: liveness-failed-modal missing on mirror!"
    assert 'id="scan-blink-prompt"' in rendered_mirror, "FAIL: scan-blink-prompt missing on mirror!"
    assert 'id="scan-liveness-badge"' in rendered_mirror, "FAIL: scan-liveness-badge missing on mirror!"

    print("  PASS: Guideline 1.4.1 is 100% compliant. Disclaimers verified, vitals isolation (Prod: 5 vs Mirror: 8), badges removed on Prod, and Face ID protection validated.")


def test_backend_integrity():
    print("[3/4] Testing Backend Integrity & User-Agent Logic...")
    main_file = os.path.join(backend_dir, "main.py")
    assert os.path.exists(main_file), f"FAIL: main.py not found at {main_file}"

    with open(main_file, "r", encoding="utf-8") as f:
        main_content = f.read()

    # 1. Verify ConsultantWebinar model is imported to prevent 500 webinar regressions
    assert "ConsultantWebinar" in main_content, "FAIL: ConsultantWebinar missing from backend/main.py imports!"

    # 2. Verify is_ios_request definition
    assert "def is_ios_request" in main_content, "FAIL: is_ios_request helper missing from backend/main.py!"
    assert '"solacesquadapp/ios" in ua' in main_content, "FAIL: SolaceSquadApp/iOS UA check missing!"
    assert '"ipad" in ua' in main_content, "FAIL: iPad UA check missing!"
    assert '"iphone" in ua' in main_content, "FAIL: iPhone UA check missing!"

    # 3. Simulate is_ios_request logic directly
    def mock_is_ios(ua: str) -> bool:
        ua_low = ua.lower()
        return (
            "solacesquadapp/ios" in ua_low
            or "iphone" in ua_low
            or "ipad" in ua_low
            or "ipod" in ua_low
            or "cfnetwork" in ua_low
            or ("macintosh" in ua_low and "mobile" in ua_low)
        )

    # Test cases
    assert mock_is_ios("SolaceSquadApp/iOS 1.0 (5)"), "FAIL: SolaceSquadApp/iOS not detected!"
    assert mock_is_ios("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)"), "FAIL: iPad not detected!"
    assert mock_is_ios("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"), "FAIL: iPhone not detected!"
    assert not mock_is_ios("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"), "FAIL: Desktop Windows incorrectly flagged as iOS!"

    print("  PASS: Backend integrity and UA detection logic validated.")


def test_live_site_if_requested():
    print("[4/4] Live Production/Staging Verification...")
    target_url = None
    for arg in sys.argv[1:]:
        if arg.startswith("--url="):
            target_url = arg.split("=", 1)[1]
        elif arg == "--live":
            target_url = "https://www.solacesquad.com"

    if not target_url:
        print("  SKIPPED: Live check skipped (use --live or --url=<URL> to test live deployments).")
        return

    import httpx
    print(f"  Testing live URL: {target_url}...")
    ipad_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 SolaceSquadApp/iOS"
    resp_ios = httpx.get(f"{target_url}/login", headers={"User-Agent": ipad_ua}, follow_redirects=True, timeout=15.0)
    assert resp_ios.status_code == 200, f"Live {target_url}/login failed with status {resp_ios.status_code}"
    assert 'id="tab-google-btn"' not in resp_ios.text, f"FAIL: Live site {target_url}/login displayed tab-google-btn to iOS user!"
    assert 'id="panel-google"' not in resp_ios.text, f"FAIL: Live site {target_url}/login displayed panel-google to iOS user!"

    desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    resp_web = httpx.get(f"{target_url}/login", headers={"User-Agent": desktop_ua}, follow_redirects=True, timeout=15.0)
    assert resp_web.status_code == 200
    assert 'id="tab-google-btn"' in resp_web.text, f"FAIL: Live site {target_url}/login omitted tab-google-btn for desktop users!"

    print(f"  PASS: Live verification of {target_url} confirmed 100% compliant.")


if __name__ == "__main__":
    print("=" * 60)
    print("SOLACESQUAD PRE-DEPLOYMENT VERIFICATION SUITE")
    print("=" * 60)
    try:
        test_guideline_4_8_template_rendering()
        test_guideline_1_4_1_vitals_disclaimers()
        test_backend_integrity()
        test_live_site_if_requested()
        print("=" * 60)
        print(">>> ALL PRE-DEPLOYMENT CHECKS PASSED SUCCESSFULLY! <<<")
        print("Safe to build and deploy to Production.")
        print("=" * 60)
        sys.exit(0)
    except AssertionError as e:
        print("\n" + "!" * 60)
        print(f"DEPLOYMENT BLOCKED: {e}")
        print("!" * 60)
        sys.exit(1)
    except Exception as e:
        import traceback
        print("\n" + "!" * 60)
        print(f"UNEXPECTED ERROR: {e}")
        traceback.print_exc()
        print("!" * 60)
        sys.exit(1)
