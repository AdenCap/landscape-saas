import Foundation
import SwiftData

@MainActor
final class SyncQueue {
    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
    }

    func enqueue(
        entityType: String,
        serverID: String?,
        operation: SyncOperation,
        payload: [String: Any],
        baseRevision: String?,
        requiresConfirmation: Bool = false
    ) throws {
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        let json = String(data: data, encoding: .utf8) ?? "{}"
        let mutation = PendingMutation(
            entityType: entityType,
            serverID: serverID,
            operation: operation,
            payloadJSON: json,
            baseRevision: baseRevision,
            requiresConfirmation: requiresConfirmation
        )
        modelContext.insert(mutation)
        try modelContext.save()
    }

    func pendingCount() throws -> Int {
        let descriptor = FetchDescriptor<PendingMutation>()
        return try modelContext.fetchCount(descriptor)
    }
}
