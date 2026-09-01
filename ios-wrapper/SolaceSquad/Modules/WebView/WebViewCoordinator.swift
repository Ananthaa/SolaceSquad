import UIKit
import WebKit

public class WebViewCoordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
    public weak var activeWebView: WKWebView?
    
    public func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        
        let urlString = url.absoluteString
        
        // Intercept external and deep links (tel:, mailto:, upi:, whatsapp:)
        if !urlString.starts(with: "http://") && !urlString.starts(with: "https://") {
            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
            }
            decisionHandler(.cancel)
            return
        }
        
        // Open third-party external links outside the SolaceSquad domain in Safari
        if !urlString.contains("solacesquad") && !urlString.contains("run.app") && !urlString.contains("razorpay") {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
            decisionHandler(.cancel)
            return
        }
        
        decisionHandler(.allow)
    }
    
    public func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        // Evaluate helper JS bridge for web compatibility
        let bridgePolyfill = """
        window.iOSBridge = {
            openRazorpay: function(jsonStr) {
                window.webkit.messageHandlers.openRazorpay.postMessage(jsonStr);
            },
            syncAppleHealth: function() {
                window.webkit.messageHandlers.syncAppleHealth.postMessage({});
            }
        };
        // Also alias AndroidBridge so shared web templates work automatically!
        window.AndroidBridge = window.iOSBridge;
        """
        webView.evaluateJavaScript(bridgePolyfill, completionHandler: nil)
    }
    
    // Support WebRTC camera & microphone permissions
    @available(iOS 15.0, *)
    public func webView(
        _ webView: WKWebView,
        requestMediaCapturePermissionFor origin: WKSecurityOrigin,
        initiatedByFrame frame: WKFrameInfo,
        type: WKMediaCaptureType,
        decisionHandler: @escaping (WKPermissionDecision) -> Void
    ) {
        decisionHandler(.grant)
    }
}
