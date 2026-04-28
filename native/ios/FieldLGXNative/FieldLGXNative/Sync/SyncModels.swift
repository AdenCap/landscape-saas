import Foundation
import SwiftData

enum SyncOperation: String, Codable {
    case create
    case update
    case delete
    case externalAction
}

@Model
final class PendingMutation {
    @Attribute(.unique) var localID: UUID
    var entityType: String
    var serverID: String?
    var operation: String
    var payloadJSON: String
    var baseRevision: String?
    var createdAt: Date
    var retryCount: Int
    var failureReason: String?
    var requiresConfirmation: Bool
    var confirmedAt: Date?

    init(
        localID: UUID = UUID(),
        entityType: String,
        serverID: String? = nil,
        operation: SyncOperation,
        payloadJSON: String,
        baseRevision: String? = nil,
        requiresConfirmation: Bool = false
    ) {
        self.localID = localID
        self.entityType = entityType
        self.serverID = serverID
        self.operation = operation.rawValue
        self.payloadJSON = payloadJSON
        self.baseRevision = baseRevision
        self.createdAt = Date()
        self.retryCount = 0
        self.failureReason = nil
        self.requiresConfirmation = requiresConfirmation
        self.confirmedAt = nil
    }
}

@Model
final class CachedTodaySnapshot {
    @Attribute(.unique) var cacheKey: String
    var payloadJSON: String
    var cachedAt: Date

    init(cacheKey: String = "today", payloadJSON: String, cachedAt: Date = Date()) {
        self.cacheKey = cacheKey
        self.payloadJSON = payloadJSON
        self.cachedAt = cachedAt
    }
}
