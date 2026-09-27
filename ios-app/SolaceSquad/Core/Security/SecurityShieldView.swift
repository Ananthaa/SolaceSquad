import SwiftUI

public struct SecurityShieldView: View {
    public init() {}
    
    public var body: some View {
        ZStack {
            Color(.systemBackground)
                .ignoresSafeArea()
            
            VStack(spacing: 16) {
                Image(systemName: "lock.shield.fill")
                    .font(.system(size: 64))
                    .foregroundColor(.teal)
                
                Text("SolaceSquad Protected")
                    .font(.title3.bold())
                
                Text("Your consultation data is protected by HIPAA & DPDP standards.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
        }
    }
}
