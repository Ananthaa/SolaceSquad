import Foundation

public struct PaymentSuccessResult {
    public let paymentId: String
    public let orderId: String
    public let signature: String
}

public struct PaymentErrorResult {
    public let code: Int
    public let description: String
}
