import Foundation
import LocalAuthentication

public class BiometricAuthManager: ObservableObject {
    public static let shared = BiometricAuthManager()
    
    @Published public var isLocked: Bool = false
    
    public var isBiometricsAvailable: Bool {
        let context = LAContext()
        var error: NSError?
        return context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
    }
    
    public func lock() {
        if isBiometricsAvailable {
            isLocked = true
        }
    }
    
    public func authenticate(completion: ((Bool) -> Void)? = nil) {
        let context = LAContext()
        context.localizedCancelTitle = "Use Passcode"
        
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            self.isLocked = false
            completion?(true)
            return
        }
        
        let reason = "Unlock SolaceSquad to access your personalized wellness records."
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { [weak self] success, authError in
            DispatchQueue.main.async {
                if success {
                    self?.isLocked = false
                }
                completion?(success)
            }
        }
    }
}
