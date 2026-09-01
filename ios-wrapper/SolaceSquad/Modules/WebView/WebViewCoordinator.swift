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
        
        // Intercept external native deep links (tel:, mailto:, upi:, whatsapp:, sms:)
        if !urlString.starts(with: "http://") && !urlString.starts(with: "https://") {
            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
            }
            decisionHandler(.cancel)
            return
        }
        
        // Allow all web URLs (including Razorpay, 3D secure banks, and SolaceSquad) to load in-app
        decisionHandler(.allow)
    }
    
    // Handle window.open and target="_blank" popup windows seamlessly in the same WebView
    public func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if navigationAction.targetFrame == nil {
            webView.load(navigationAction.request)
        }
        return nil
    }
    
    public func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        // Expose iOS native bridge for Apple Health sync
        let bridgePolyfill = """
        window.iOSBridge = {
            syncAppleHealth: function() {
                if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.syncAppleHealth) {
                    window.webkit.messageHandlers.syncAppleHealth.postMessage({});
                }
            }
        };
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
