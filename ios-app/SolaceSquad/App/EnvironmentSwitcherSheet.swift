import SwiftUI

public struct EnvironmentSwitcherSheet: View {
    @ObservedObject var appEnv = AppEnvironment.shared
    @Environment(\.presentationMode) var presentationMode
    @State private var tempCustomURL: String = ""
    
    public init() {
        _tempCustomURL = State(initialValue: AppEnvironment.shared.customURLString)
    }
    
    public var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Active Server Environment")) {
                    ForEach(EnvironmentType.allCases) { env in
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(env.rawValue)
                                    .font(.headline)
                                Text(env.defaultURL)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            if appEnv.currentEnv == env {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(.teal)
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture {
                            appEnv.currentEnv = env
                        }
                    }
                }
                
                if appEnv.currentEnv == .local {
                    Section(header: Text("Custom Host URL")) {
                        TextField("http://192.168.1.10:8000", text: $tempCustomURL)
                            .keyboardType(.URL)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                        Button("Save Custom URL") {
                            appEnv.customURLString = tempCustomURL
                        }
                    }
                }
                
                Section(header: Text("Diagnostics & Staging Tools")) {
                    HStack {
                        Text("Active Base URL")
                        Spacer()
                        Text(appEnv.baseURL)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                    HStack {
                        Text("App Bundle ID")
                        Spacer()
                        Text(appEnv.bundleId)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("QA Environment Switcher")
            .navigationBarItems(trailing: Button("Done") {
                presentationMode.wrappedValue.dismiss()
            })
        }
    }
}
