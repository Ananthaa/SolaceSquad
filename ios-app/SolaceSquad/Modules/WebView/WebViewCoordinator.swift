import UIKit
import WebKit
import SafariServices

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
        let host = (url.host ?? "").lowercased()
        let path = url.path
        
        // 1. Intercept external native deep links (tel:, mailto:, upi:, whatsapp:, sms:)
        if !urlString.starts(with: "http://") && !urlString.starts(with: "https://") {
            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
            }
            decisionHandler(.cancel)
            return
        }
        
        // 2. Intercept Home page navigation: NEVER open public marketing homepage in the app
        let isSolaceDomain = host.contains("solacesquad.com") || host.contains("run.app") || host.contains("localhost")
        if isSolaceDomain && (path == "/" || path.isEmpty) {
            decisionHandler(.cancel)
            webView.load(URLRequest(url: AppEnvironment.shared.appStartURL))
            return
        }
        
        // 3. Open external domains (e.g. YouTube, external medical journals, Zoom) in SFSafariViewController
        // Allowed in-app domains: SolaceSquad, Razorpay, banks (for 3D secure verification)
        let isPaymentOrBank = host.contains("razorpay.com") || host.contains("bank") || host.contains("billdesk") || host.contains("paytm")
        if !isSolaceDomain && !isPaymentOrBank && navigationAction.navigationType == .linkActivated {
            decisionHandler(.cancel)
            if let rootVC = UIApplication.shared.windows.first?.rootViewController {
                let safariVC = SFSafariViewController(url: url)
                rootVC.present(safariVC, animated: true)
            }
            return
        }
        
        // Allow all internal web URLs
        NavigationManager.shared.updateForURL(url)
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
    
    @objc public func handleRefresh(_ sender: UIRefreshControl) {
        activeWebView?.reload()
    }

    public func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.scrollView.refreshControl?.endRefreshing()
        
        if let currentURL = webView.url {
            NavigationManager.shared.updateForURL(currentURL)
        }
        
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

    public func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        webView.scrollView.refreshControl?.endRefreshing()
    }

    public func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        webView.scrollView.refreshControl?.endRefreshing()
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
