import Foundation

public enum AppEnvironment {
    #if DEBUG
    public static let baseURL = "https://solacesquad-mirror-312011725712.us-central1.run.app"
    public static let isDebug = true
    #else
    public static let baseURL = "https://www.solacesquad.com"
    public static let isDebug = false
    #endif
    
    public static let syncXPushEndpoint = "\(baseURL)/api/sync-x/push"
    public static let bundleId = "com.ssq2.solacesquad"
}
