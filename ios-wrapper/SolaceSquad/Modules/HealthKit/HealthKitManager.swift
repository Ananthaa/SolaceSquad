import Foundation
import HealthKit

public class HealthKitManager {
    public static let shared = HealthKitManager()
    private let healthStore = HKHealthStore()
    
    public var isHealthDataAvailable: Bool {
        HKHealthStore.isHealthDataAvailable()
    }
    
    public func requestAuthorization(completion: @escaping (Bool, Error?) -> Void) {
        guard isHealthDataAvailable else {
            completion(false, NSError(domain: "HealthKit", code: 1, userInfo: [NSLocalizedDescriptionKey: "HealthKit not available on this device"]))
            return
        }
        
        guard let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount),
              let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate),
              let oxygenType = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation),
              let energyType = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned) else {
            completion(false, nil)
            return
        }
        
        let typesToRead: Set<HKObjectType> = [
            stepType,
            heartRateType,
            oxygenType,
            energyType,
            HKWorkoutType.workoutType()
        ]
        
        healthStore.requestAuthorization(toShare: nil, read: typesToRead) { success, error in
            DispatchQueue.main.async {
                completion(success, error)
            }
        }
    }
    
    public func fetchTodaySteps(completion: @escaping (Int) -> Void) {
        guard let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount) else {
            completion(0)
            return
        }
        
        let startOfDay = Calendar.current.startOfDay(for: Date())
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: Date(), options: .strictStartDate)
        
        let query = HKStatisticsQuery(quantityType: stepType, quantitySamplePredicate: predicate, options: .cumulativeSum) { _, result, _ in
            let steps = Int(result?.sumQuantity()?.doubleValue(for: HKUnit.count()) ?? 0)
            DispatchQueue.main.async { completion(steps) }
        }
        healthStore.execute(query)
    }
    
    public func fetchLatestHeartRate(completion: @escaping (Double?) -> Void) {
        guard let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate) else {
            completion(nil)
            return
        }
        
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: hrType, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { _, samples, _ in
            guard let sample = samples?.first as? HKQuantitySample else {
                DispatchQueue.main.async { completion(nil) }
                return
            }
            let bpm = sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
            DispatchQueue.main.async { completion(bpm) }
        }
        healthStore.execute(query)
    }
    
    public func fetchLatestSpO2(completion: @escaping (Double?) -> Void) {
        guard let o2Type = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else {
            completion(nil)
            return
        }
        
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: o2Type, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { _, samples, _ in
            guard let sample = samples?.first as? HKQuantitySample else {
                DispatchQueue.main.async { completion(nil) }
                return
            }
            let pct = sample.quantity.doubleValue(for: HKUnit.percent()) * 100.0
            DispatchQueue.main.async { completion(pct) }
        }
        healthStore.execute(query)
    }
}
