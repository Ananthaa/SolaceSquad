import SwiftUI

public struct BiometricConsentView: View {
    @Environment(\.presentationMode) var presentationMode
    var onConsentGranted: () -> Void
    var onConsentDeclined: () -> Void
    
    private let kBiometricConsentGranted = "ssq_dpdp_biometric_consent_granted"
    
    public init(onConsentGranted: @escaping () -> Void, onConsentDeclined: @escaping () -> Void) {
        self.onConsentGranted = onConsentGranted
        self.onConsentDeclined = onConsentDeclined
    }
    
    public static var hasConsented: Bool {
        UserDefaults.standard.bool(forKey: "ssq_dpdp_biometric_consent_granted")
    }
    
    public static func recordConsent(_ granted: Bool) {
        UserDefaults.standard.set(granted, forKey: "ssq_dpdp_biometric_consent_granted")
    }
    
    public var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "faceid")
                .font(.system(size: 56))
                .foregroundColor(.teal)
                .padding(.top, 28)
            
            Text("Consent for Health & Face Scan")
                .font(.title2.bold())
                .multilineTextAlignment(.center)
            
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "shield.checkered")
                        .foregroundColor(.teal)
                    Text("In accordance with India's DPDP Act 2023 and HIPAA privacy guidelines, your optical facial video is used exclusively to estimate pulse rate, respiration, and stress biomarkers.")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
                
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "lock.shield")
                        .foregroundColor(.teal)
                    Text("No facial images, photos, or raw video streams are recorded, uploaded to public servers, or shared with third parties.")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
                
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "arrow.counterclockwise.circle")
                        .foregroundColor(.teal)
                    Text("You may revoke this consent or delete your health records at any time from Account Settings.")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 8)
            
            Spacer()
            
            VStack(spacing: 12) {
                Button(action: {
                    Self.recordConsent(true)
                    presentationMode.wrappedValue.dismiss()
                    onConsentGranted()
                }) {
                    Text("I Agree & Continue")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 50)
                        .background(Color.teal)
                        .cornerRadius(12)
                }
                
                Button(action: {
                    Self.recordConsent(false)
                    presentationMode.wrappedValue.dismiss()
                    onConsentDeclined()
                }) {
                    Text("Decline")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 24)
        }
    }
}
