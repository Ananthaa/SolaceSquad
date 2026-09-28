import SwiftUI
import WebKit

// MARK: - Native Navigation Manager
public enum TabItem: String, CaseIterable {
    case home = "Home"
    case quickConsult = "Quick Consult"
    case specialists = "Specialists"
    case profile = "Profile"
    
    public var iconName: String {
        switch self {
        case .home: return "house.fill"
        case .quickConsult: return "bolt.fill"
        case .specialists: return "stethoscope"
        case .profile: return "person.crop.circle.fill"
        }
    }
}

public class NavigationManager: ObservableObject {
    public static let shared = NavigationManager()
    
    @Published public var selectedTab: TabItem = .home
    @Published public var showBottomBar: Bool = false
    @Published public var currentPath: String = ""
    public weak var activeWebView: WKWebView?
    
    public func navigate(to tab: TabItem, baseURL: String) {
        selectedTab = tab
        let feedback = UIImpactFeedbackGenerator(style: .medium)
        feedback.prepare()
        feedback.impactOccurred()
        
        guard let webView = activeWebView else { return }
        let path: String
        switch tab {
        case .home:
            path = "/user-dashboard"
        case .quickConsult:
            path = "/quickconsult"
        case .specialists:
            path = "/consultants"
        case .profile:
            path = "/user-dashboard#profile"
        }
        
        if let targetURL = URL(string: "\(baseURL)\(path)") {
            webView.load(URLRequest(url: targetURL))
        }
    }
    
    public func updateForURL(_ url: URL) {
        let path = url.path.lowercased()
        currentPath = path
        
        // Hide bottom bar on login, signup, reset password, and live video call rooms
        let isAuthOrCall = path.contains("login") || 
                           path.contains("signup") || 
                           path.contains("call_room") || 
                           path.contains("call-room") || 
                           path.contains("reset_password") ||
                           path == "/"
        
        DispatchQueue.main.async {
            withAnimation(.easeInOut(duration: 0.25)) {
                self.showBottomBar = !isAuthOrCall
            }
            
            if path.contains("quickconsult") {
                self.selectedTab = .quickConsult
            } else if path.contains("consultant") {
                self.selectedTab = .specialists
            } else if path.contains("dashboard") {
                self.selectedTab = .home
            }
        }
    }
}

// MARK: - Native iOS Bottom Tab Bar View
struct NativeTabBarView: View {
    @ObservedObject var navManager = NavigationManager.shared
    let baseURL: String
    
    var body: some View {
        HStack(spacing: 0) {
            // Tab 1: Home
            tabButton(tab: .home)
            
            // Tab 2: Quick Consult (Prominent Center Action)
            quickConsultButton
            
            // Tab 3: Specialists
            tabButton(tab: .specialists)
            
            // Tab 4: Profile
            tabButton(tab: .profile)
        }
        .padding(.horizontal, 12)
        .padding(.top, 8)
        .padding(.bottom, 22)
        .background(
            Color(.systemBackground)
                .opacity(0.97)
                .shadow(color: Color.black.opacity(0.08), radius: 10, x: 0, y: -4)
        )
    }
    
    private func tabButton(tab: TabItem) -> some View {
        Button(action: {
            navManager.navigate(to: tab, baseURL: baseURL)
        }) {
            VStack(spacing: 4) {
                Image(systemName: tab.iconName)
                    .font(.system(size: 20, weight: navManager.selectedTab == tab ? .bold : .regular))
                Text(tab.rawValue)
                    .font(.system(size: 11, weight: navManager.selectedTab == tab ? .semibold : .medium))
            }
            .foregroundColor(navManager.selectedTab == tab ? Color(red: 0.05, green: 0.46, blue: 0.43) : Color(.secondaryLabel))
            .frame(maxWidth: .infinity)
        }
    }
    
    private var quickConsultButton: some View {
        Button(action: {
            navManager.navigate(to: .quickConsult, baseURL: baseURL)
        }) {
            VStack(spacing: 3) {
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [Color(red: 0.08, green: 0.58, blue: 0.53), Color(red: 0.05, green: 0.46, blue: 0.43)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 48, height: 48)
                        .shadow(color: Color(red: 0.05, green: 0.46, blue: 0.43).opacity(0.35), radius: 6, x: 0, y: 3)
                    
                    Image(systemName: "bolt.fill")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundColor(.white)
                }
                .offset(y: -10)
                
                Text("Quick Consult")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(navManager.selectedTab == .quickConsult ? Color(red: 0.05, green: 0.46, blue: 0.43) : Color(.secondaryLabel))
                    .offset(y: -10)
            }
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Main Application Root
@main
struct SolaceSquadApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var appEnv = AppEnvironment.shared
    @StateObject private var navManager = NavigationManager.shared
    @StateObject private var healthSyncService = HealthSyncService.shared
    @StateObject private var biometricAuth = BiometricAuthManager.shared
    @Environment(\.scenePhase) private var scenePhase
    
    @State private var showEnvSwitcher = false
    @State private var backgroundTimestamp: Date? = nil

    var body: some Scene {
        WindowGroup {
            ZStack(alignment: .bottom) {
                SolaceWebView(initialURL: appEnv.appStartURL)
                    .ignoresSafeArea(.all, edges: .top)
                
                // Native iOS Bottom Navigation Tab Bar
                if navManager.showBottomBar {
                    NativeTabBarView(baseURL: appEnv.baseURL)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
                
                // HIPAA Privacy Shield in App Switcher / Background
                if scenePhase != .active {
                    SecurityShieldView()
                }
                
                // Biometric security lock overlay if locked
                if biometricAuth.isLocked && biometricAuth.isBiometricsAvailable && scenePhase == .active {
                    Color(.systemBackground)
                        .ignoresSafeArea()
                        .overlay(
                            VStack(spacing: 20) {
                                Image(systemName: "lock.shield.fill")
                                    .font(.system(size: 64))
                                    .foregroundColor(.teal)
                                Text("SolaceSquad is Locked")
                                    .font(.title2.bold())
                                Button("Unlock with Face ID / Touch ID") {
                                    biometricAuth.authenticate()
                                }
                                .buttonStyle(.borderedProminent)
                                .tint(.teal)
                            }
                        )
                }
            }
            .sheet(isPresented: $showEnvSwitcher) {
                EnvironmentSwitcherSheet()
            }
            .onAppear {
                healthSyncService.requestHealthKitPermissionsAndSync()
            }
            .onChange(of: scenePhase) { newPhase in
                if newPhase == .active {
                    // Check if background duration exceeded 2 minutes (120s) -> lock
                    if let bgTime = backgroundTimestamp, Date().timeIntervalSince(bgTime) > 120 {
                        biometricAuth.lock()
                    }
                    backgroundTimestamp = nil
                    healthSyncService.syncTodayVitalsAndWorkouts()
                } else if newPhase == .background {
                    backgroundTimestamp = Date()
                }
            }
        }
    }
}
