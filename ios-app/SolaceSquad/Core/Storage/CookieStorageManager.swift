import Foundation
import WebKit

public class CookieStorageManager {
    public static let shared = CookieStorageManager()
    
    public func getCookieHeader(from webView: WKWebView, completion: @escaping (String) -> Void) {
        webView.configuration.websiteDataStore.httpCookieStore.getAllCookies { cookies in
            let header = cookies.map { "\($0.name)=\($0.value)" }.joined(separator: "; ")
            completion(header)
        }
    }
    
    public func syncCookies(from response: HTTPURLResponse, to webView: WKWebView) {
        guard let fields = response.allHeaderFields as? [String: String],
              let url = response.url else { return }
        
        let cookies = HTTPCookie.cookies(withResponseHeaderFields: fields, for: url)
        for cookie in cookies {
            webView.configuration.websiteDataStore.httpCookieStore.setCookie(cookie)
        }
    }
}
