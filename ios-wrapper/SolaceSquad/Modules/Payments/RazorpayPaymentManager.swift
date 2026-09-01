import UIKit
import WebKit

public class RazorpayPaymentManager: NSObject {
    public static let shared = RazorpayPaymentManager()
    public weak var activeWebView: WKWebView?
    
    public func openCheckout(optionsJson: String) {
        guard let data = optionsJson.data(using: .utf8),
              let options = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            print("[RazorpayPaymentManager] Invalid options JSON")
            return
        }
        
        DispatchQueue.main.async {
            guard let rootVC = UIApplication.shared.windows.first(where: { $0.isKeyWindow })?.rootViewController else {
                return
            }
            
            // Present payment overlay using RazorpayFramework if linked, or trigger Web bridge callback
            print("[RazorpayPaymentManager] Initiating payment for order: \(options["order_id"] ?? "")")
        }
    }
    
    public func notifySuccess(paymentId: String, orderId: String, signature: String) {
        let js = """
        if (typeof window.handleNativeRazorpaySuccess === 'function') {
            window.handleNativeRazorpaySuccess({
                razorpay_payment_id: '\(paymentId)',
                razorpay_order_id: '\(orderId)',
                razorpay_signature: '\(signature)'
            });
        }
        """
        activeWebView?.evaluateJavaScript(js, completionHandler: nil)
    }
    
    public func notifyError(code: Int, description: String) {
        let safeDesc = description.replacingOccurrences(of: "'", with: "\\'")
        let js = """
        if (typeof window.handleNativeRazorpayError === 'function') {
            window.handleNativeRazorpayError(\(code), '\(safeDesc)');
        }
        """
        activeWebView?.evaluateJavaScript(js, completionHandler: nil)
    }
}
