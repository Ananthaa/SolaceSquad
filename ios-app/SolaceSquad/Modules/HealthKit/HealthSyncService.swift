import Foundation
import WebKit

public class HealthSyncService: ObservableObject {
    public static let shared = HealthSyncService()
    public weak var activeWebView: WKWebView?
    
    public func requestHealthKitPermissionsAndSync() {
        HealthKitManager.shared.requestAuthorization { granted, error in
            if granted {
                self.syncTodayVitalsAndWorkouts()
            }
        }
    }
    
    public func syncTodayVitalsAndWorkouts(completion: ((Bool) -> Void)? = nil) {
        let group = DispatchGroup()
        
        var todaySteps = 0
        var latestHR: Double? = nil
        var latestSpO2: Double? = nil
        
        group.enter()
        HealthKitManager.shared.fetchTodaySteps { steps in
            todaySteps = steps
            group.leave()
        }
        
        group.enter()
        HealthKitManager.shared.fetchLatestHeartRate { hr in
            latestHR = hr
            group.leave()
        }
        
        group.enter()
        HealthKitManager.shared.fetchLatestSpO2 { o2 in
            latestSpO2 = o2
            group.leave()
        }
        
        group.notify(queue: .main) {
            var vitalsPayload: [String: Any] = [:]
            if let hr = latestHR { vitalsPayload["heart_rate"] = Int(hr) }
            if let o2 = latestSpO2 { vitalsPayload["spo2"] = Double(String(format: "%.1f", o2)) }
            
            let dateFormatter = DateFormatter()
            dateFormatter.dateFormat = "yyyy-MM-dd"
            let todayStr = dateFormatter.string(from: Date())
            
            let workoutsPayload: [[String: Any]] = [
                [
                    "external_id": "apple_health_steps_\(todayStr)",
                    "sync_date": todayStr,
                    "workout_type": "Walking",
                    "step_count": todaySteps,
                    "duration_min": 0,
                    "calories": 0
                ]
            ]
            
            let payload: [String: Any] = [
                "source": "apple_health",
                "workouts": workoutsPayload,
                "vitals": vitalsPayload
            ]
            
            self.postToBackend(payload: payload, completion: completion)
        }
    }
    
    private func postToBackend(payload: [String: Any], completion: ((Bool) -> Void)?) {
        guard let url = URL(string: AppEnvironment.syncXPushEndpoint),
              let jsonData = try? JSONSerialization.data(withJSONObject: payload) else {
            completion?(false)
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData
        
        // Pass session cookies from WKWebView if available
        if let webView = activeWebView {
            CookieStorageManager.shared.getCookieHeader(from: webView) { cookieHeader in
                if !cookieHeader.isEmpty {
                    request.setValue(cookieHeader, forHTTPHeaderField: "Cookie")
                }
                self.executeRequest(request, completion: completion)
            }
        } else {
            self.executeRequest(request, completion: completion)
        }
    }
    
    private func executeRequest(_ request: URLRequest, completion: ((Bool) -> Void)?) {
        URLSession.shared.dataTask(with: request) { data, response, error in
            let success = (response as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async {
                print("[HealthSyncService] Push result: \(success ? "SUCCESS" : "FAILED")")
                completion?(success)
            }
        }.resume()
    }
}
