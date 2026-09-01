import SwiftUI

@main
struct SolaceSquadApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var healthSyncService = HealthSyncService.shared
    @StateObject private var biometricAuth = BiometricAuthManager.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ZStack {
                SolaceWebView(initialURL: URL(string: AppEnvironment.baseURL)!)
                    .ignoresSafeArea(.all, edges: .bottom)
                
                // Biometric security overlay if enabled and locked
                if biometricAuth.isLocked && biometricAuth.isBiometricsAvailable {
                    Color(.systemBackground)
                        .ignoresSafeArea()
                        .overlay(
                            VStack(spacing: 20) {
                                Image(systemName: "lock.shield.fill")
                                    .font(.system(size: 64))
                                    .foregroundColor(.accentColor)
                                Text("SolaceSquad is Locked")
                                    .font(.title2.bold())
                                Button("Unlock with Face ID / Touch ID") {
                                    biometricAuth.authenticate()
                                }
                                .buttonStyle(.borderedProminent)
                            }
                        )
                }
            }
            .onAppear {
                healthSyncService.requestHealthKitPermissionsAndSync()
            }
            .onChange(of: scenePhase) { newPhase in
                if newPhase == .active {
                    // Sync health data when app resumes to foreground
                    healthSyncService.syncTodayVitalsAndWorkouts()
                } else if newPhase == .background {
                    biometricAuth.lock()
                }
            }
        }
    }
}
