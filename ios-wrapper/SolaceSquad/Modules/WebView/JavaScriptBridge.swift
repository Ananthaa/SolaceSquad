import Foundation
import WebKit

public class JavaScriptBridge: NSObject, WKScriptMessageHandler {
    public static let shared = JavaScriptBridge()
    public weak var activeWebView: WKWebView?
    
    public func registerHandlers(on controller: WKUserContentController) {
        controller.add(self, name: "openRazorpay")
        controller.add(self, name: "syncAppleHealth")
        controller.add(self, name: "getApnsToken")
    }
    
    public func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        switch message.name {
        case "openRazorpay":
            if let jsonString = message.body as? String {
                RazorpayPaymentManager.shared.openCheckout(optionsJson: jsonString)
            }
        case "syncAppleHealth":
            HealthSyncService.shared.syncTodayVitalsAndWorkouts { success in
                let js = "if (window.onAppleHealthSyncComplete) { window.onAppleHealthSyncComplete(\(success)); }"
                self.activeWebView?.evaluateJavaScript(js, completionHandler: nil)
            }
        case "getApnsToken":
            let token = PushNotificationManager.shared.apnsToken ?? ""
            let js = "if (window.onReceiveApnsToken) { window.onReceiveApnsToken('\(token)'); }"
            self.activeWebView?.evaluateJavaScript(js, completionHandler: nil)
        default:
            break
        }
    }
}
