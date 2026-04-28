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

    func pendingMutations() throws -> [PendingMutation] {
        var descriptor = FetchDescriptor<PendingMutation>(
            sortBy: [SortDescriptor(\.createdAt, order: .forward)]
        )
        descriptor.fetchLimit = 50
        return try modelContext.fetch(descriptor)
    }

    @discardableResult
    func flush(apiClient: APIClient) async -> Int {
        let mutations: [PendingMutation]
        do {
            mutations = try pendingMutations()
        } catch {
            return 0
        }

        var completed = 0
        for mutation in mutations {
            guard mutation.entityType == "job_action",
                  let serverID = mutation.serverID,
                  let jobID = Int(serverID),
                  let data = mutation.payloadJSON.data(using: .utf8),
                  let payload = try? JSONDecoder().decode([String: String].self, from: data)
            else {
                mutation.retryCount += 1
                mutation.failureReason = "Could not read queued action."
                continue
            }

            do {
                _ = try await apiClient.performQueuedJobMutation(jobID: jobID, payload: payload)
                modelContext.delete(mutation)
                completed += 1
            } catch {
                mutation.retryCount += 1
                mutation.failureReason = error.localizedDescription
            }
        }
        try? modelContext.save()
        return completed
    }
}
