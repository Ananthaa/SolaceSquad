import Foundation

public enum EnvironmentType: String, CaseIterable, Identifiable {
    case production = "Production"
    case staging = "Mirror (Staging)"
    case local = "Custom / Local"
    
    public var id: String { rawValue }
    
    public var defaultURL: String {
        switch self {
        case .production:
            return "https://www.solacesquad.com"
        case .staging:
            return "https://solacesquad-mirror-312011725712.us-central1.run.app"
        case .local:
            return "http://localhost:8000"
        }
    }
}

public class AppEnvironment: ObservableObject {
    public static let shared = AppEnvironment()
    
    private let kSelectedEnv = "ssq_selected_environment"
    private let kCustomURL = "ssq_custom_environment_url"
    
    @Published public var currentEnv: EnvironmentType {
        didSet {
            UserDefaults.standard.set(currentEnv.rawValue, forKey: kSelectedEnv)
        }
    }
    
    @Published public var customURLString: String {
        didSet {
            UserDefaults.standard.set(customURLString, forKey: kCustomURL)
        }
    }
    
    public init() {
        let defaultEnv = EnvironmentType.production
        
        let savedEnv = UserDefaults.standard.string(forKey: kSelectedEnv) ?? defaultEnv.rawValue
        self.currentEnv = EnvironmentType(rawValue: savedEnv) ?? defaultEnv
        self.customURLString = UserDefaults.standard.string(forKey: kCustomURL) ?? EnvironmentType.local.defaultURL
    }
    
    public var baseURL: String {
        switch currentEnv {
        case .production:
            return EnvironmentType.production.defaultURL
        case .staging:
            return EnvironmentType.staging.defaultURL
        case .local:
            return customURLString.isEmpty ? EnvironmentType.local.defaultURL : customURLString
        }
    }
    
    public var appStartURL: URL {
        URL(string: "\(baseURL)/login")!
    }
    
    public var bundleId: String {
        #if DEBUG
        return "com.ssq2.solacesquad.staging"
        #else
        return "com.ssq2.solacesquad"
        #endif
    }
    
    public var syncXPushEndpoint: String {
        "\(baseURL)/api/sync-x/push"
    }
}
