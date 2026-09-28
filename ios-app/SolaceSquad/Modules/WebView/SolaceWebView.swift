import SwiftUI
import WebKit

public struct SolaceWebView: UIViewRepresentable {
    public let initialURL: URL
    
    public init(initialURL: URL) {
        self.initialURL = initialURL
    }
    
    public func makeCoordinator() -> WebViewCoordinator {
        WebViewCoordinator()
    }
    
    public func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.preferences.javaScriptCanOpenWindowsAutomatically = true
        config.applicationNameForUserAgent = "SolaceSquadApp/iOS"
        config.websiteDataStore = WKWebsiteDataStore.default()
        
        // Attach JavaScript Message Handler Bridge
        let userContentController = WKUserContentController()
        JavaScriptBridge.shared.registerHandlers(on: userContentController)
        config.userContentController = userContentController
        
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        
        // Attach native iOS Pull-to-Refresh
        let refreshControl = UIRefreshControl()
        refreshControl.tintColor = UIColor(red: 0.05, green: 0.46, blue: 0.43, alpha: 1.0)
        refreshControl.addTarget(context.coordinator, action: #selector(context.coordinator.handleRefresh(_:)), for: .valueChanged)
        webView.scrollView.refreshControl = refreshControl
        
        context.coordinator.activeWebView = webView
        JavaScriptBridge.shared.activeWebView = webView
        HealthSyncService.shared.activeWebView = webView
        RazorpayPaymentManager.shared.activeWebView = webView
        NavigationManager.shared.activeWebView = webView
        
        let request = URLRequest(url: initialURL)
        webView.load(request)
        return webView
    }
    
    public func updateUIView(_ uiView: WKWebView, context: Context) {}
}
