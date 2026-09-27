import UIKit
import WebKit

public class RazorpayPaymentManager: NSObject {
    public static let shared = RazorpayPaymentManager()
    public weak var activeWebView: WKWebView?
    
    public func openCheckout(optionsJson: String) {
        guard let data = optionsJson.data(using: .utf8),
              let _ = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            print("[RazorpayPaymentManager] Invalid options JSON")
            return
        }
        
        DispatchQueue.main.async { [weak self] in
            let escapedJson = optionsJson.replacingOccurrences(of: "\\", with: "\\\\")
                                         .replacingOccurrences(of: "\"", with: "\\\"")
                                         .replacingOccurrences(of: "\n", with: " ")
                                         .replacingOccurrences(of: "\r", with: "")
            let js = """
            (function() {
                try {
                    var opts = JSON.parse("\(escapedJson)");
                    if (typeof Razorpay !== 'undefined') {
                        var rzp = new Razorpay(opts);
                        rzp.open();
                    } else {
                        console.error('Razorpay script not found');
                    }
                } catch(e) {
                    console.error('Failed to open Razorpay in iOS WebView', e);
                }
            })();
            """
            self?.activeWebView?.evaluateJavaScript(js, completionHandler: nil)
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
