import SwiftUI

@main
struct SolaceSquadApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var appEnv = AppEnvironment.shared
    @StateObject private var healthSyncService = HealthSyncService.shared
    @StateObject private var biometricAuth = BiometricAuthManager.shared
    @Environment(\.scenePhase) private var scenePhase
    
    @State private var showEnvSwitcher = false
    @State private var backgroundTimestamp: Date? = nil

    var body: some Scene {
        WindowGroup {
            ZStack {
                SolaceWebView(initialURL: appEnv.appStartURL)
                    .ignoresSafeArea(.all, edges: .bottom)
                
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
